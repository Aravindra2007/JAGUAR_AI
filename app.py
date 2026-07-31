from flask import Flask, render_template, request, jsonify

from router import CommandRouter
from listener import VoiceListener
import state
import languages

app = Flask(__name__)

# ---------------------------------
# Jaguar Backend
# ---------------------------------

router = CommandRouter()
listener = VoiceListener()
listener.start()   # starts the background thread (mic stays idle until /start is called)


# ---------------------------------
# Home Page
# ---------------------------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------------------------
# Execute Command (typed, from GUI)
# ---------------------------------

@app.route("/command", methods=["POST"])
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
    # like {"type": "needs_confirmation", "envelope": {...}}. The Flask
    # template (when present) is responsible for rendering the envelope
    # as Approve/Deny controls and posting to /confirm with the token.
    return jsonify({
        "response": response
    })


# ---------------------------------
# Current Status (polled by GUI)
# ---------------------------------

@app.route("/status")
def status():

    current_status, current_text = state.get_status()

    return jsonify({
        "status": current_status,
        "text": current_text
    })


# ---------------------------------
# Chat History (typed + spoken)
# ---------------------------------

@app.route("/history")
def get_history():

    return jsonify(state.get_history())


# ---------------------------------
# Clear History
# ---------------------------------

@app.route("/clear", methods=["POST"])
def clear():

    state.clear_history()
    state.set_text("Conversation Cleared.")

    return jsonify({
        "success": True
    })


# ---------------------------------
# Mute / Unmute Speech
# ---------------------------------

@app.route("/mute", methods=["POST"])
def mute():

    data = request.get_json()
    muted = bool(data.get("muted", False))

    state.set_muted(muted)

    return jsonify({"success": True, "muted": muted})


# ---------------------------------
# LLM Config (get/set fallback model)
# ---------------------------------
# Anything typed or spoken that doesn't match a built-in command in
# router.py is sent to whichever LLM is configured here instead of
# just returning "I didn't understand". templates/index.html can POST
# here to add a settings panel; until then this is usable directly
# via curl/fetch, and works with sensible defaults out of the box.

@app.route("/llm-config", methods=["GET", "POST"])
def llm_config():

    if request.method == "POST":
        data = request.get_json() or {}
        state.set_llm_config(**{
            k: v for k, v in data.items()
            if k in (
                "enabled", "provider", "api_key", "model",
                "temperature", "system_prompt", "ollama_host",
            )
        })

    return jsonify(state.get_llm_config())


# ---------------------------------
# Start Listening
# (Called from GUI button)
# ---------------------------------

@app.route("/start", methods=["POST"])
def start():

    listener.start_listening()

    return jsonify({"success": True})


## Languages
@app.route("/language", methods=["GET", "POST"])
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

@app.route("/stop", methods=["POST"])
def stop():

    listener.stop_listening()

    return jsonify({"success": True})


# ---------------------------------
# Confirm a pending tool action
# ---------------------------------
# Called from the Flask GUI's Approve/Deny buttons (and any other
# client that has a token from a prior /command response). The router
# looks up the action by token and either runs it or cancels it.

@app.route("/confirm", methods=["POST"])
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
