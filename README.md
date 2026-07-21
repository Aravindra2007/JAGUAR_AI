<<<<<<< HEAD
# JAGUAR_AI
mini Voice Assistant That acts as like different models it integrated with different Ai Models
=======
# JAGUAR_AK

**Jaguar** is a Python voice/text assistant. It listens for spoken commands
(or accepts typed ones), first checks a table of built-in actions —
opening apps and websites, playing YouTube videos, searching the web,
telling the time/date, shutting down or restarting the machine — and if
nothing matches, **hands the text to an LLM** (OpenAI or a local Ollama
model) so it can hold a real conversation instead of just saying "I
didn't understand." It talks back using text-to-speech.

## What changed in this merge

Previously this repo had two separate things:

1. A rule-based voice assistant (`app.py` / `streamlit_app.py` +
   `router.py`, `commands.py`, `listener.py`, `speaker.py`, `state.py`,
   `wakeword.py`) that only understood a fixed list of phrases.
2. A standalone Streamlit LLM chat app (`llm_client.py` + its own
   `app.py`) with no voice input and no built-in commands.

They're now one app:

- **`router.py`** still matches built-in commands first (fast, no API
  call, works offline: `open google`, `time`, `shutdown`, etc.). If
  nothing matches, it calls **`llm_client.py`**'s `ask()` with the
  current LLM settings and a little recent conversation history for
  context.
- **`state.py`** now also stores the LLM configuration (provider, API
  key, model, temperature, system prompt, Ollama host), alongside the
  existing status/history/mute state. This is the shared source of
  truth both the GUI and the voice listener thread read from.
- **`listener.py`** is unchanged — it already calls
  `router.process(command)` for every recognized phrase. Since
  `router.process` now falls back to the LLM, **spoken input reaches
  the model automatically**, with no extra wiring.
- **`streamlit_app.py`** (the primary GUI) gained a "🧠 LLM settings"
  panel in the sidebar — pick OpenAI or Ollama, enter a key/host,
  model, temperature, and system prompt. Settings are written to
  `state` on every rerun, so they take effect immediately for both
  typed and spoken input.
- **`app.py`** (the Flask backend) gained a matching `/llm-config`
  GET/POST endpoint for the same purpose, for anyone driving Jaguar
  through `templates/index.html` or a raw HTTP request instead of the
  Streamlit UI. (No `index.html` was in this repo to edit — add a
  small settings form there if you want the Flask GUI to expose the
  same controls as the Streamlit sidebar.)

## How it works

- **`streamlit_app.py`** — Main GUI. Chat interface, Start/Stop mic
  button, mute toggle, history, and the LLM settings panel.
- **`app.py`** — Flask backend/GUI alternative. Serves
  `templates/index.html` (not included) and exposes `/command`,
  `/status`, `/history`, `/clear`, `/mute`, `/start`, `/stop`, and the
  new `/llm-config`.
- **`main.py`** — Entry point for the Flask version. Boots the server
  in a background thread and opens the browser.
- **`listener.py`** — `VoiceListener`, a background thread that owns
  the microphone. Only listens when told to (Start button / `/start`),
  transcribes speech with `speech_recognition`, and passes the text to
  the router — same pipeline as typed input.
- **`router.py`** — `CommandRouter`. Built-in command table first, LLM
  fallback second.
- **`commands.py`** — The built-in actions.
- **`llm_client.py`** — Provider-agnostic `ask()` used by the router:
  OpenAI (cloud) or Ollama (local).
- **`speaker.py`** — Text-to-speech output (`pyttsx3`).
- **`state.py`** — Shared status/history/mute/LLM-config state.
- **`wakeword.py`** — Wake-word handling for hands-free activation.
- **`static/`, `templates/`** — Front-end assets for the Flask GUI.

## Requirements

- Python 3.x
- A working microphone (for voice mode)
- Packages in `requirements.txt` (Flask, SpeechRecognition, pyttsx3,
  pyautogui, pywhatkit, PyAudio, streamlit, streamlit-autorefresh,
  openai, ollama)
- An OpenAI API key (if using OpenAI) **or** [Ollama](https://ollama.com)
  running locally with a pulled model (if using Ollama)

> **Note:** Several built-in commands (Notepad/Calculator/Paint/CMD,
> `shutdown`, `restart`) use Windows-specific calls, so this project is
> built primarily for **Windows**.

## Installation

```bash
git clone https://github.com/Aravindra2007/JAGUAR_AK.git
cd JAGUAR_AK
pip install -r requirements.txt
```

On Windows, `PyAudio` may need a prebuilt wheel if `pip install` fails —
install via `pipwin install pyaudio` or a matching `.whl`.

## Usage

**Streamlit GUI (recommended — includes the LLM settings panel):**

```bash
streamlit run streamlit_app.py
```

**Flask GUI:**

```bash
python main.py
```

Either way, from the GUI you can:

- Type a command, or just chat — anything that isn't a recognized
  command goes straight to the LLM
- Click **Start** to enable voice listening (say a command or ask a
  question, then pause) — voice input goes through the exact same
  pipeline as typed input, including the LLM fallback
- Click **Stop** to disable the microphone
- Mute/unmute spoken responses
- View or clear conversation history
- (Streamlit) open **🧠 LLM settings** in the sidebar to pick a
  provider, model, temperature, and system prompt

Built-in commands still work exactly as before:

- `open google` / `open youtube` / `open github`
- `play <song name>` (plays on YouTube)
- `search <query>` / `search youtube for <query>`
- `open notepad` / `open calculator` / `open paint` / `open vs code`
- `time` / `date`
- `shutdown` / `restart`
- `exit` / `quit` / `goodbye`
- `stop listening`, `go idle`, `sleep`, or `stop` (voice-only, pauses
  the mic)

Anything else — `"what's the capital of France"`,
`"summarize the plot of dune"`, `"why is the sky blue"` — is sent to
the configured LLM and the reply is spoken back (unless muted).

## Project structure

```
JAGUAR_AK/
├── app.py              # Flask routes + /llm-config
├── streamlit_app.py     # Main GUI (chat + LLM settings + voice controls)
├── main.py              # Entry point for the Flask version
├── listener.py           # Background voice listener thread
├── router.py             # Built-in commands, LLM fallback
├── commands.py            # Command implementations
├── llm_client.py           # OpenAI / Ollama client used by router.py
├── speaker.py              # Text-to-speech
├── state.py                # Shared status/history/mute/LLM-config state
├── wakeword.py              # Wake-word detection
├── static/                  # CSS/JS assets (Flask GUI)
├── templates/                # HTML templates (Flask GUI)
└── requirements.txt
```

## License

Released under the [MIT License](LICENSE).
>>>>>>> 5bbde330 (JAGUAR_AI)
