import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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
from overlay import start_overlay

# New autonomous-agent core (graceful when optional deps are missing)
try:
    from jaguar_core import memory as jaguar_memory
    from jaguar_core import personality as jaguar_personality
    from jaguar_core.autonomous import (
        run_autonomous_goal, get_job as get_autonomous_job,
        list_jobs as list_autonomous_jobs,
    )
    JAGUAR_AUTONOMOUS_AVAILABLE = True
except Exception as _e:  # pragma: no cover
    JAGUAR_AUTONOMOUS_AVAILABLE = False
    print(f"[jaguar] autonomous core unavailable: {_e}")

app = Flask(__name__)
app.secret_key = os.getenv("JAGUAR_SECRET_KEY", "dev-key-change-this-in-production")

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
    print("Firebase ready.")
except Exception as e:
    print(f"WARNING: could not initialize Firebase ({e}). "
          "Set FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS_JSON.")

init_auth(app)

# ---------------------------------
# Jaguar Backend
# ---------------------------------

router = CommandRouter()
listener = VoiceListener()
state.set_listener(listener)
listener.start()   # starts the background thread (mic stays idle until /start is called)

# Optional: mount the FastAPI mobile API inside the Flask app at
# /mobile, so a single `python main.py` (or gunicorn wsgi:app)
# serves both UIs. Disable with JAGUAR_MOUNT_MOBILE_API=0.
if os.getenv("JAGUAR_MOUNT_MOBILE_API", "0") == "1":
    try:
        from api.router_bridge import attach_mobile_api
        from api.mobile_api import app as _fastapi_app
        attach_mobile_api(app, _fastapi_app)
        print("[jaguar] FastAPI mobile API mounted at /mobile")
    except Exception as _mount_err:
        print(f"[jaguar] mobile API not mounted: {_mount_err}")


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
    state.set_current_user(current_user.id, current_user.username)

    if text == "":
        return jsonify({
            "response": "Please enter a command."
        })

    state.set_status("Processing...")

    response = router.process(text, user_id=str(current_user.id))

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
    data = request.get_json() or {}

    state.set_llm_config(
        enabled=True,
        provider=data.get("provider"),
        api_key=data.get("api_key"),
        model=data.get("model"),
        temperature=0.7,
        system_prompt="You are Jaguar AI",
        ollama_host="http://localhost:11434",
        tools_enabled=bool(data.get("tools_enabled", False)),
        workspace_dir=data.get("workspace_dir") or "~",
    )

    return {"success": True}

# ---------------------------------
# Chat History (typed + spoken)
# ---------------------------------

@app.route("/history")
@login_required
def get_history():
    try:
        rows = db.get_recent_chat(current_user.id, limit=100)
        history = [
            {"user": r["user_message"], "assistant": r["assistant_reply"]}
            for r in rows
        ]
        return jsonify(history)
    except Exception as e:
        # Fall back to in-memory history when Firebase is unavailable.
        print(f"[history] Firebase read failed, using in-memory: {e}")
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
        db.clear_chat_history(current_user.id)
    except Exception as e:
        print(f"[clear] Firebase clear failed: {e}")

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


@app.route("/launch-overlay", methods=["POST"])
@login_required
def launch_overlay_route():
    try:
        start_overlay()
        return jsonify({"success": True, "message": "Overlay launched successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



# ---------------------------------
# File / Image Upload (Supabase)
# ---------------------------------

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    if "file" not in request.files:
        return jsonify({
            "success": False,
            "error": "No file included in the request."
        }), 400

    upload_file = request.files["file"]

    if not upload_file or upload_file.filename == "":
        return jsonify({
            "success": False,
            "error": "No file selected."
        }), 400

    filename = secure_filename(upload_file.filename)
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return jsonify({
            "success": False,
            "error": f"Unsupported file type: {ext}"
        }), 400

    try:
        upload_file.stream.seek(0)
        content = upload_file.stream.read()
        extracted_text = file_reader.extract_text_bytes(filename, content)
        attachment_context = file_reader.build_attachment_context(
            filename, extracted_text
        )
        state.set_pending_attachment(attachment_context)

        upload_file.stream.seek(0)
        file_id = db.save_uploaded_file(
            user_id=str(current_user.id),
            filename=filename,
            filepath=upload_file,
            filetype=ext.lstrip("."),
            extracted_text=extracted_text,
        )

        return jsonify({
            "success": True,
            "file_id": file_id,
            "filename": filename,
            "is_image": ext in file_reader.IMAGE_EXTENSIONS,
            "preview": extracted_text[:600]
        })

    except Exception as e:
        print(f"[upload] Upload failed: {e}")

        return jsonify({
            "success": False,
            "error": "File upload failed."
        }), 500



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
# Liveness probe (for Docker / Render / Fly / k8s)
# ---------------------------------

@app.route("/health")
def health():
    """Cheap health check used by container orchestrators. Doesn't
    require login so external uptime checks work."""
    return jsonify({
        "status": "ok",
        "service": "jaguar-ai",
        "autonomous": JAGUAR_AUTONOMOUS_AVAILABLE,
        "time": __import__("time").time(),
    })


# ---------------------------------
# Autonomous goal (text in -> plan + execute)
# ---------------------------------
# Wires the new planner + executor + browser automation into the
# existing Flask UI. The endpoint always returns a job_id; the
# frontend polls /autonomous/<job_id> to follow progress.

@app.route("/autonomous", methods=["POST"])
@login_required
def autonomous_run():
    if not JAGUAR_AUTONOMOUS_AVAILABLE:
        return jsonify({"ok": False, "error": "Autonomous core unavailable."}), 503

    data = request.get_json() or {}
    goal = (data.get("goal") or "").strip()
    if not goal:
        return jsonify({"ok": False, "error": "Empty goal."}), 400

    cfg = state.get_llm_config()
    try:
        job = run_autonomous_goal(
            goal=goal,
            user_id=str(current_user.id),
            llm_provider=cfg.get("provider", "OpenAI"),
            llm_api_key=cfg.get("api_key", ""),
            llm_model=cfg.get("model", ""),
            llm_temperature=float(cfg.get("temperature", 0.3) or 0.3),
            ollama_host=cfg.get("ollama_host") or None,
            headless_browser=bool(data.get("headless_browser", False)),
            background=bool(data.get("background", True)),
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True, "job": job.to_dict()})


@app.route("/autonomous/<job_id>")
@login_required
def autonomous_status(job_id: str):
    job = get_autonomous_job(job_id, user_id=str(current_user.id))
    if not job:
        return jsonify({"ok": False, "error": "Unknown job_id"}), 404
    return jsonify({"ok": True, "job": job.to_dict()})


@app.route("/autonomous-jobs")
@login_required
def autonomous_list():
    return jsonify({
        "ok": True,
        "jobs": [
            j.to_dict()
            for j in list_autonomous_jobs(
                limit=50,
                user_id=str(current_user.id),
            )
        ],
    })


# ---------------------------------
# Personality preferences
# ---------------------------------

@app.route("/personality", methods=["GET", "POST"])
@login_required
def personality_route():
    if not JAGUAR_AUTONOMOUS_AVAILABLE:
        return jsonify({"ok": False, "error": "Personality core unavailable."}), 503

    if request.method == "POST":
        data = request.get_json() or {}
        for k, v in data.items():
            if v in (None, ""):
                continue
            jaguar_memory.update_preference(
                k,
                v,
                user_id=str(current_user.id),
            )
        # Reseat the LLM system prompt so the change is immediate.
        prefs = jaguar_memory.get_preferences(user_id=str(current_user.id))
        base = state.get_llm_config().get("system_prompt", "")
        new_system = jaguar_personality.build_system_prompt(base, preferences=prefs)
        state.set_llm_config(system_prompt=new_system)
        return jsonify({"ok": True, "preferences": prefs})

    return jsonify({
        "ok": True,
        "preferences": jaguar_memory.get_preferences(user_id=str(current_user.id)),
        "tones": jaguar_personality.available_tones(),
        "styles": jaguar_personality.available_styles(),
    })


# ---------------------------------
# Long-term memory recall
# ---------------------------------

@app.route("/memory/recall", methods=["POST"])
@login_required
def memory_recall():
    if not JAGUAR_AUTONOMOUS_AVAILABLE:
        return jsonify({"ok": False, "error": "Memory core unavailable."}), 503
    data = request.get_json() or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"ok": False, "error": "Empty query."}), 400
    entries = jaguar_memory.recall(
        query,
        top_k=int(data.get("top_k", 5) or 5),
        kind=data.get("kind"),
        user_id=str(current_user.id),
    )
    return jsonify({
        "ok": True,
        "query": query,
        "entries": [e.to_dict() for e in entries],
    })


@app.route("/memory/results")
@login_required
def memory_results():
    if not JAGUAR_AUTONOMOUS_AVAILABLE:
        return jsonify({"ok": False, "error": "Memory core unavailable."}), 503
    kind = request.args.get("kind")
    return jsonify({
        "ok": True,
        "results": jaguar_memory.list_results(
            kind=kind,
            limit=100,
            user_id=str(current_user.id),
        ),
    })


@app.route("/memory", methods=["GET"])
@login_required
def memory_list():
    if not JAGUAR_AUTONOMOUS_AVAILABLE:
        return jsonify({"ok": False, "error": "Memory core unavailable."}), 503
    entries = jaguar_memory.list_memories(
        user_id=str(current_user.id),
        kind=request.args.get("kind"),
        limit=int(request.args.get("limit", 100)),
    )
    return jsonify({"ok": True, "entries": [entry.to_dict() for entry in entries]})


@app.route("/memory", methods=["POST"])
@login_required
def memory_remember():
    if not JAGUAR_AUTONOMOUS_AVAILABLE:
        return jsonify({"ok": False, "error": "Memory core unavailable."}), 503
    data = request.get_json() or {}
    if data.get("approved") is not True:
        return jsonify({"ok": False, "error": "Explicit approval is required."}), 400
    try:
        memory_id = jaguar_memory.remember(
            data.get("text", ""),
            kind=data.get("kind", "project"),
            metadata=data.get("metadata") or {},
            importance=float(data.get("importance", 0.5)),
            user_id=str(current_user.id),
        )
    except ValueError as error:
        return jsonify({"ok": False, "error": str(error)}), 400
    return jsonify({"ok": True, "id": memory_id})


@app.route("/memory/<memory_id>", methods=["PUT", "DELETE"])
@login_required
def memory_item(memory_id: str):
    if not JAGUAR_AUTONOMOUS_AVAILABLE:
        return jsonify({"ok": False, "error": "Memory core unavailable."}), 503
    user_id = str(current_user.id)
    if request.method == "DELETE":
        changed = jaguar_memory.forget(memory_id, user_id=user_id)
    else:
        data = request.get_json() or {}
        changed = jaguar_memory.update_memory(
            memory_id,
            data.get("text", ""),
            user_id=user_id,
        )
    if not changed:
        return jsonify({"ok": False, "error": "Memory not found."}), 404
    return jsonify({"ok": True})


# ---------------------------------
# Start Listening
# ---------------------------------

@app.route("/start", methods=["POST"])
@login_required
def start():
    state.set_current_user(current_user.id, current_user.username)
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
    state.set_current_user(current_user.id, current_user.username)
    data = request.get_json() or {}
    token = data.get("token", "")
    decision = data.get("decision", "")

    if not token:
        return jsonify({"response": "Missing token."}), 400

    response = router.process_with_confirmation(
        token,
        decision,
        user_id=str(current_user.id),
    )
    state.add_history("[tool action]", response)
    if isinstance(response, dict) and response.get("type") == "needs_confirmation":
        prompt = (response.get("envelope") or {}).get("prompt", "Awaiting confirmation.")
        state.set_text(f"[Awaiting confirmation] {prompt}")
    else:
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
