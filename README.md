<div align="center">

# 🐆 JAGUAR AI

### Your Personalized Desktop AI Assistant

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green?style=for-the-badge&logo=qt)
![Status](https://img.shields.io/badge/Status-Actively%20Updating-orange?style=for-the-badge)
![License](https://img.shields.io/badge/License-Personal-purple?style=for-the-badge)

> ⚡ *JAGUAR AI is a powerful, modular, voice-enabled desktop AI assistant built entirely in Python — designed to work natively on your system with full local and cloud AI support.*

---

</div>

## 🚀 Overview

**JAGUAR AI** is a personal desktop AI assistant built to bring intelligent automation, voice interaction, memory, scheduling, and more — all in one unified application. It is actively being developed and upgraded with new capabilities.

The project is structured around a clean modular architecture, making it easy to extend with new skills, agents, plugins, and integrations as the project grows.

---

## ✨ Features

- 🎙️ **Voice Interaction** — Speak to JAGUAR using your microphone; it listens, understands, and responds via speech synthesis
- 🤖 **AI Backends** — Supports both OpenAI (cloud) and Ollama (local) for flexible, private AI responses
- 🖥️ **Desktop Automation** — Controls your system via PyAutoGUI and PyGetWindow — open apps, click, type, and more
- 🧠 **Memory System** — Persistent memory to recall past conversations and context
- 📅 **Scheduler** — Schedule tasks and reminders to run at specific times
- 🔌 **Plugin System** — Modular plugins to add new capabilities without modifying core code
- 👁️ **Vision & OCR** — Analyze screenshots, images, and documents using EasyOCR and OpenCV
- 📄 **PDF Support** — Read and process PDF files using PyMuPDF and pypdf
- 🌐 **Web Integration** — Browse and search the web using PyWhatKit and Requests
- 🔔 **Wake Word Detection** — Always-listening wake word support via Pvporcupine
- 🖼️ **Modern GUI** — Clean, responsive desktop interface built with PyQt6

---

## 🗂️ Project Structure

```
JAGUAR_AI/
│
├── main.py                 # Entry point — launches the GUI and assistant
│
├── core/                   # Core assistant engine (JaguarAssistant class)
├── ai/                     # AI model integrations (OpenAI, Ollama, etc.)
├── agents/                 # Autonomous agents for complex tasks
├── automation/             # System automation modules (PyAutoGUI, windows)
├── gui/                    # PyQt6 graphical user interface
├── memory/                 # Persistent memory and conversation history
├── plugins/                # Plug-and-play feature extensions
├── scheduler/              # Task and reminder scheduling engine
├── skills/                 # Individual skill definitions (web, files, etc.)
├── system/                 # System-level utilities and OS interaction
├── tasks/                  # Task management and execution
├── voice/                  # Speech recognition and TTS (text-to-speech)
├── logs/                   # Runtime logs
│
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

---

## 🛠️ Installation

### Prerequisites

- Python 3.10 or higher
- A microphone (for voice features)
- Optional: An OpenAI API key or a local [Ollama](https://ollama.com/) setup

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/Aravindra2007/JAGUAR_AI.git
cd JAGUAR_AI

# 2. (Recommended) Create a virtual environment
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables (API keys, etc.)
cp .env.example .env            # Edit .env with your keys

# 5. Run the assistant
python main.py
```

> **Note:** Some packages like `PyAudio` and `pvporcupine` may require additional system libraries. See the [Troubleshooting](#-troubleshooting) section below.

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `PyQt6` | Desktop GUI framework |
| `SpeechRecognition` | Voice input / speech-to-text |
| `PyAudio` | Audio stream handling |
| `pyttsx3` | Text-to-speech (offline) |
| `python-dotenv` | Environment variable management |
| `psutil` | System resource monitoring |
| `pyautogui` | Desktop automation |
| `pygetwindow` | Window management |
| `pyperclip` | Clipboard interaction |
| `pywhatkit` | Web search & WhatsApp automation |
| `requests` | HTTP requests |
| `openai` | OpenAI API integration |
| `ollama` | Local LLM via Ollama |
| `pillow` | Image processing |
| `easyocr` | Optical character recognition |
| `opencv-python` | Computer vision |
| `pymupdf` | PDF reading and rendering |
| `pypdf` | PDF text extraction |
| `pvporcupine` | Wake word detection |

---

## ⚙️ Configuration

Create a `.env` file in the project root with the following (fill in your own values):

```env
OPENAI_API_KEY=your_openai_api_key_here
PORCUPINE_ACCESS_KEY=your_picovoice_access_key_here
OLLAMA_MODEL=llama3           # or any other model you have pulled
```

You can get a free Porcupine key at [picovoice.ai](https://picovoice.ai) and an OpenAI key at [platform.openai.com](https://platform.openai.com).

---

## 🧩 Adding Plugins & Skills

JAGUAR AI is designed to grow. To add a new skill or plugin:

1. Create a new `.py` file inside the `skills/` or `plugins/` folder.
2. Follow the existing module structure in that folder.
3. Register the skill/plugin in the core assistant if required.

New capabilities can be added without touching the core engine.

---

## 🔧 Troubleshooting

**PyAudio installation fails:**
```bash
# On Ubuntu/Debian
sudo apt-get install portaudio19-dev
pip install pyaudio

# On Windows, download the wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
```

**EasyOCR / OpenCV issues:**
Make sure you have the correct C++ build tools installed on your system.

**Ollama not responding:**
Ensure Ollama is running locally (`ollama serve`) and the model is pulled (`ollama pull llama3`).

---

## 🛣️ Roadmap

> This project is actively being updated and upgraded.

- [ ] Enhanced agent workflows with multi-step planning
- [ ] Web browsing agent
- [ ] Improved memory with vector search (RAG)
- [ ] More voice wake words and custom hotwords
- [ ] Plugin marketplace / auto-loader
- [ ] Mobile companion app
- [ ] Multi-language support

---

## 👨‍💻 Author

**Aravindra** — [@Aravindra2007](https://github.com/Aravindra2007)

Built as a personal project to create the ultimate AI assistant tailored for personal system use.

---

## 📄 License

This is a personal project. All rights reserved by the author unless otherwise stated.

---

<div align="center">

⭐ **If you find this project interesting, give it a star!** ⭐

</div>
