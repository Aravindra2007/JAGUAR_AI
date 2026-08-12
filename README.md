<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 33294c91 (jaguar Please enter the commit message for your changes. Lines starting)
# 🐆 JAGUAR AI

> A modular, voice-enabled personal AI assistant for your desktop — built with Python and PyQt6.
=======
# Jaguar AI

**Jaguar** is a Python voice/text assistant that integrates with
multiple AI models (OpenAI, Anthropic Claude, Google Gemini, and local
Ollama models). It listens for spoken commands (or accepts typed ones),
first checks a table of built-in actions — opening apps and websites,
playing YouTube videos, searching the web, telling the time/date,
shutting down or restarting the machine — and if nothing matches,
**hands the text to the configured LLM** so it can hold a real
conversation instead of just saying "I didn't understand." It talks
back using text-to-speech.
<<<<<<< HEAD
=======
>>>>>>> cffc0614 (JAGUAR_AI)
>>>>>>> 33294c91 (jaguar Please enter the commit message for your changes. Lines starting)

---

## Overview

JAGUAR AI is a fully personalized desktop AI assistant designed to run locally on your system. It combines speech recognition, natural language processing, system automation, and a graphical interface into a cohesive, extensible platform. Whether you want to control your PC with your voice, automate repetitive tasks, or interact with local and cloud-based AI models, JAGUAR has you covered.

---

## Features

- 🎤 **Voice Input & Output** — Real-time speech recognition via `SpeechRecognition` + `PyAudio`, with text-to-speech responses powered by `pyttsx3`
- 🧠 **AI Brain** — Integrates with both **OpenAI** (cloud) and **Ollama** (local LLMs) for flexible, privacy-conscious AI responses
- 🖥️ **Desktop GUI** — Built with **PyQt6** for a clean, native desktop experience
- 🤖 **Agents** — Modular agent system for delegating tasks to specialized sub-routines
- 🔧 **System Automation** — Controls your PC via `pyautogui`, `pygetwindow`, and `pyperclip`
- 📅 **Scheduler** — Run tasks and reminders on a schedule
- 🧩 **Plugin Architecture** — Extend JAGUAR with custom plugins in the `plugins/` directory
- 🛠️ **Skills System** — Discrete, composable skills that the assistant can invoke
- 📝 **Memory** — Persistent memory layer to retain context across sessions
- 👁️ **Vision & OCR** — Screen and image understanding via `EasyOCR`, `OpenCV`, and `Pillow`
- 📄 **PDF Handling** — Read and process PDF documents with `PyMuPDF` and `pypdf`
- 🌐 **Web Actions** — Browse and interact with the web using `pywhatkit` and `requests`
- 🔔 **Wake Word Detection** — Always-listening trigger using **Picovoice Porcupine**
- 📊 **System Monitoring** — Track CPU, memory, and process stats via `psutil`
- 📋 **Logging** — Structured logs stored in the `logs/` directory

---

<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 33294c91 (jaguar Please enter the commit message for your changes. Lines starting)
## Project Structure
=======
## Requirements

- Python 3.x
- A working microphone (for voice mode)
- Packages in `requirements.txt` (Flask, SpeechRecognition, pyttsx3,
  pyautogui, pywhatkit, PyAudio, streamlit, streamlit-autorefresh,
  openai, ollama)
- An OpenAI API key, Anthropic API key, Google AI Studio key (if using
  those providers) **or** [Ollama](https://ollama.com) running locally
  with a pulled model (if using Ollama)

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
  provider (OpenAI / Claude / Gemini / Ollama), model, temperature,
  and system prompt

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
<<<<<<< HEAD
=======
>>>>>>> cffc0614 (JAGUAR_AI)
>>>>>>> 33294c91 (jaguar Please enter the commit message for your changes. Lines starting)

```
JAGUAR_AI/
├── main.py              # Entry point — launches the GUI and assistant core
├── requirements.txt     # Python dependencies
│
├── core/                # Assistant brain and orchestration logic
├── ai/                  # AI model integrations (OpenAI, Ollama)
├── agents/              # Specialized task agents
├── automation/          # Desktop automation routines
├── gui/                 # PyQt6 graphical interface
├── memory/              # Persistent memory and context storage
├── plugins/             # Extensible plugin system
├── scheduler/           # Task scheduling and reminders
├── skills/              # Discrete assistant skills
├── system/              # System-level utilities and monitoring
├── tasks/               # Task definitions and management
├── voice/               # Speech recognition and TTS modules
└── logs/                # Runtime logs
```

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- A working microphone (for voice features)
- [Ollama](https://ollama.com) installed locally (optional, for local LLM support)
- An OpenAI API key (optional, for cloud AI support)

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/Aravindra2007/JAGUAR_AI.git
   cd JAGUAR_AI
   ```

2. **Create and activate a virtual environment**

   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**

   Create a `.env` file in the project root and add your API keys:

   ```env
   OPENAI_API_KEY=your_openai_key_here
   PORCUPINE_ACCESS_KEY=your_picovoice_key_here
   ```

5. **Run JAGUAR AI**

   ```bash
   python main.py
   ```

---

## Dependencies

| Package | Purpose |
|---|---|
| `PyQt6` | Desktop GUI framework |
| `SpeechRecognition` + `PyAudio` | Voice input |
| `pyttsx3` | Text-to-speech output |
| `openai` | OpenAI API integration |
| `ollama` | Local LLM integration |
| `pvporcupine` | Wake word detection |
| `pyautogui` + `pygetwindow` | Desktop automation |
| `pyperclip` | Clipboard interaction |
| `pywhatkit` | Web-based actions |
| `psutil` | System resource monitoring |
| `easyocr` + `opencv-python` | Vision and OCR |
| `pillow` | Image processing |
| `pymupdf` + `pypdf` | PDF reading and parsing |
| `requests` | HTTP requests |
| `python-dotenv` | Environment variable management |

---

## Configuration

JAGUAR AI uses a `.env` file for secrets and configuration. Key variables:

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key (if using cloud AI) |
| `PORCUPINE_ACCESS_KEY` | Picovoice key for wake word detection |

Additional configuration (AI model selection, voice preferences, plugin toggles) can be found in the `core/` and `system/` modules.

---

## Extending JAGUAR

JAGUAR is built to be extensible. You can:

- **Add a plugin** — drop a new Python module into `plugins/` following the existing plugin interface
- **Add a skill** — define a new skill in `skills/` that the assistant can invoke by name or intent
- **Add an agent** — create a specialized agent in `agents/` for complex multi-step tasks

---

## Roadmap

- [ ] Web-based configuration dashboard
- [ ] Cross-platform packaging (Windows `.exe`, macOS `.app`)
- [ ] Expanded plugin marketplace
- [ ] Multi-language voice support
- [ ] Vision-based screen understanding (live feed)

---

## Author

**Aravindra** — [GitHub @Aravindra2007](https://github.com/Aravindra2007)

---

## License

<<<<<<< HEAD
This project is currently unlicensed. All rights reserved by the author unless otherwise specified.
=======
Released under the [MIT License](LICENSE).

=======
<<<<<<< HEAD
This project is currently unlicensed. All rights reserved by the author unless otherwise specified.
=======
Released under the [MIT License](LICENSE).
>>>>>>> cffc0614 (JAGUAR_AI)
>>>>>>> 33294c91 (jaguar Please enter the commit message for your changes. Lines starting)
