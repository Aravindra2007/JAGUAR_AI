import os
import uuid

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from router import CommandRouter
from listener import VoiceListener
from speaker import stop_speaking
import state
import languages
import db
import file_reader
from auth import init_auth

app = Flask(__name__)
app.secret_key = os.getenv("JAGUAR_SECRET_KEY", "dev-key-change-this-in-production")

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_UPLOAD_EXTENSIONS = {
    ".txt", ".md", ".csv", ".log", ".json",
    ".pdf", ".docx",
    ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp",
}
MAX_UPLOAD_MB = 20

app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

# ---------------------------------
# Database + Auth
# ---------------------------------
try:
    db.init_db()
    print("MySQL ready.")
except Exception as e:
    print(f"WARNING: could not initialize MySQL ({e}). "
          f"Set JAGUAR_DB_HOST/USER/PASSWORD/NAME and make sure MySQL is running.")

init_auth(app)

# ---------------------------------
# Jaguar Backend
# ---------------------------------

router = CommandRouter()
listener = VoiceListener()
listener.start()   # starts the background thread (mic stays idle until /start is called)


# ---------------------------------
# Home Page (chat UI)
# ---------------------------------

@app.route("/")
@login_required
def home():
    return render_template(
        "index.html",
        username=current_user.username,
        full_name=current_user.full_name,
        languages=languages.list_languages(),
    )


# ---------------------------------
# Execute Command (typed, from GUI)
# ---------------------------------

@app.route("/command", methods=["POST"])
@login_required
def command():

    data = request.get_json()
    text = data.get("text", "").strip()

    if text == "":
        return jsonify({
            "response": "Please enter a command."
        })

    state.set_status("Processing...")

    response = router.process(text)

    state.set_status("Idle")
    state.set_text(response if isinstance(response, str) else "Awaiting confirmation.")
    if isinstance(response, str):
        state.add_history(text, response)

    # `response` may be either a string (text reply) or a dict shaped
    # like {"type": "needs_confirmation", "envelope": {...}}. The
    # frontend renders the envelope as Approve/Deny controls and posts
    # to /confirm with the token.
    return jsonify({
        "response": response
    })


# ---------------------------------
# Current Status (polled by GUI)
# ---------------------------------

@app.route("/status")
@login_required
def status():

    current_status, current_text = state.get_status()

    return jsonify({
        "status": current_status,
        "text": current_text,
        "speaking": state.is_speaking(),
    })


@app.route("/set-llm-config", methods=["POST"])
def set_llm_config():
    data = request.json

    state.set_llm_config(
        enabled=True,
        provider=data.get("provider"),
        api_key=data.get("api_key"),
        model=data.get("model"),
        temperature=0.7,
        system_prompt="You are Jaguar AI",
        ollama_host="http://localhost:11434",
        tools_enabled=False,
        workspace_dir="~"
    )

    return {"success": True}

# ---------------------------------
# Chat History (typed + spoken)
# ---------------------------------

@app.route("/history")
@login_required
def get_history():
    try:
        rows = db.get_recent_chat(int(current_user.id), limit=100)
        history = [
            {"user": r["user_message"], "assistant": r["assistant_reply"]}
            for r in rows
        ]
        return jsonify(history)
    except Exception as e:
        # Fall back to in-memory history (e.g. MySQL not configured yet)
        print(f"[history] MySQL read failed, using in-memory: {e}")
        return jsonify(state.get_history())


# ---------------------------------
# Clear History
# ---------------------------------

@app.route("/clear", methods=["POST"])
@login_required
def clear():

    state.clear_history()
    state.set_text("Conversation Cleared.")
    try:
        db.clear_chat_history(int(current_user.id))
    except Exception as e:
        print(f"[clear] MySQL clear failed: {e}")

    return jsonify({
        "success": True
    })


# ---------------------------------
# Mute / Unmute Speech
# ---------------------------------

@app.route("/mute", methods=["POST"])
@login_required
def mute():

    data = request.get_json()
    muted = bool(data.get("muted", False))

    state.set_muted(muted)

    return jsonify({"success": True, "muted": muted})


# ---------------------------------
# Stop Speaking (interrupt TTS immediately)
# ---------------------------------
# Separate from /stop (which stops the microphone). This lets the GUI
# offer a dedicated "Stop speaking" control that cuts Jaguar off
# mid-sentence without touching the listener at all.

@app.route("/stop-speaking", methods=["POST"])
@login_required
def stop_speaking_route():
    stop_speaking()
    return jsonify({"success": True})


# ---------------------------------
# File / Image Upload (for reading + tasking)
# ---------------------------------
# Accepts a document or image, extracts whatever text it can, stores
# both the file and the extracted text in MySQL, and stashes the
# extracted text as "pending attachment context" so the user's very
# next message (typed OR spoken) is answered with that content in
# mind - e.g. "summarize this", "what's the answer to question 3".

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file included in the request."}), 400

    upload_file = request.files["file"]
    if not upload_file or upload_file.filename == "":
        return jsonify({"success": False, "error": "No file selected."}), 400

    filename = secure_filename(upload_file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return jsonify({
            "success": False,
            "error": f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}",
        }), 400

    user_dir = os.path.join(UPLOAD_DIR, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
    save_path = os.path.join(user_dir, unique_name)
    upload_file.save(save_path)

    extracted_text = file_reader.extract_text(save_path)
    attachment_context = file_reader.build_attachment_context(filename, extracted_text)
    state.set_pending_attachment(attachment_context)

    try:
        db.save_uploaded_file(
            int(current_user.id), filename, save_path,
            filetype=ext.lstrip("."), extracted_text=extracted_text,
        )
    except Exception as e:
        print(f"[upload] Could not save upload record to MySQL: {e}")

    preview = extracted_text[:600]

    return jsonify({
        "success": True,
        "filename": filename,
        "is_image": ext in file_reader.IMAGE_EXTENSIONS,
        "preview": preview,
    })


# ---------------------------------
# LLM Config (get/set fallback model)
# ---------------------------------

@app.route("/llm-config", methods=["GET", "POST"])
@login_required
def llm_config():

    if request.method == "POST":
        data = request.get_json() or {}
        state.set_llm_config(**{
            k: v for k, v in data.items()
            if k in (
                "enabled", "provider", "api_key", "model",
                "temperature", "system_prompt", "ollama_host",
                "tools_enabled", "workspace_dir",
            )
        })

    return jsonify(state.get_llm_config())


# ---------------------------------
# Start Listening
# ---------------------------------

@app.route("/start", methods=["POST"])
@login_required
def start():
    state.set_current_user(int(current_user.id), current_user.username)
    listener.start_listening()

    return jsonify({"success": True})


## Languages
@app.route("/language", methods=["GET", "POST"])
@login_required
def language():
    if request.method == "POST":
        data = request.get_json() or {}
        lang = data.get("language")
        if lang in languages.list_languages():
            state.set_language(lang)

    return jsonify({
        "language": state.get_language(),
        "available": languages.list_languages(),
    })

# ---------------------------------
# Stop Listening
# ---------------------------------
# Also interrupts anything currently being spoken - see listener.py's
# stop_listening(), which calls speaker.stop_speaking() first.

@app.route("/stop", methods=["POST"])
@login_required
def stop():

    listener.stop_listening()

    return jsonify({"success": True})


# ---------------------------------
# Confirm a pending tool action
# ---------------------------------

@app.route("/confirm", methods=["POST"])
@login_required
def confirm():
    data = request.get_json() or {}
    token = data.get("token", "")
    decision = data.get("decision", "")

    if not token:
        return jsonify({"response": "Missing token."}), 400

    response = router.process_with_confirmation(token, decision)
    state.add_history("[tool action]", response)
    state.set_text(response)

    return jsonify({"response": response})


# ---------------------------------
# Run Flask
# ---------------------------------

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
