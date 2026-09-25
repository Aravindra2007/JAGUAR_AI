
# 🐆 JAGUAR AI - Intelligent Local OS Assistant

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078d4?style=for-the-badge)

A sophisticated, voice-activated local agent that bridges Large Language Models (LLMs) with direct operating system control. Built entirely in Python with extensible architecture for seamless AI-driven desktop automation.

[Features](#-features) • [Installation](#-installation--setup) • [Quick Start](#-quick-start) • [Architecture](#-system-architecture) • [Contributing](#-contributing)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-features)
- [Technical Stack](#-technical-stack)
- [System Architecture](#-system-architecture)
- [Installation & Setup](#-installation--setup)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Project Structure](#-project-structure)
- [Security](#-security)
- [Deployment](#-deployment)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Overview

**JAGUAR AI** is an advanced, modular personal desktop assistant that combines cutting-edge AI technologies with intelligent system automation. Unlike cloud-based chatbots, JAGUAR operates as a **local-first agent** with the ability to:

- **Listen actively** via voice (STT - Speech-to-Text)
- **Think intelligently** using multiple LLM backends
- **Act deliberately** on your desktop with user confirmation
- **Speak naturally** via Text-to-Speech (TTS)
- **Remember contextually** by maintaining conversation history

Whether you prefer **cloud-based AI (OpenAI, Claude, Gemini)** or **privacy-first local models (Ollama)**, JAGUAR adapts to your needs.

---

## ✨ Features

### Core Capabilities

🎤 **Voice-First Interface**
- Real-time speech recognition with automatic activation
- Natural language understanding via multiple LLM providers
- Contextual awareness with conversation history
- Fallback to text-based input when audio is unavailable

🤖 **Intelligent Task Execution**
- Application launching and file management
- System command execution with safety guardrails
- Desktop automation via keyboard and mouse control
- Real-time action confirmation to prevent accidental changes

📱 **Multi-Interface Support**
- Voice command line interface
- Web dashboard for remote control
- Desktop overlay (status pill) showing agent state
- Streamlit UI for advanced features

🔄 **Background Intelligence**
- Autonomous reminder service
- Proactive task scheduling
- Persistent state management
- Asynchronous operation

🧠 **Flexible AI Backends**
- **Cloud Models**: OpenAI (GPT-4o), Anthropic (Claude 3.5), Google (Gemini)
- **Local Models**: Ollama (Llama 3, Mistral, etc.)
- **Hybrid Support**: Seamlessly switch between providers
- **Tool Use**: Agent-based tool calling with confirmation workflow

📄 **Context Understanding**
- Document analysis (PDF, DOCX, TXT)
- Image recognition and processing
- File content extraction and summarization
- User workspace isolation

🔐 **Enterprise-Grade Security**
- Allowlist-based command execution
- Workspace isolation (no system-wide file access)
- Human-in-the-loop confirmation for all mutations
- No credentials stored locally (environment-based config)

---

## 🛠️ Technical Stack

### Backend & Core Infrastructure

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Language** | Python 3.12+ | Primary development language |
| **Web Framework** | Flask | REST API & Dashboard backend |
| **UI Toolkit** | Tkinter | Desktop overlay & system integration |
| **Streaming UI** | Streamlit | Advanced analytics & monitoring |
| **Concurrency** | Threading | Async voice listening & reminders |

### AI & Language Processing

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **LLM Providers** | Anthropic, OpenAI, Google, Ollama | Large Language Models |
| **Speech Recognition** | SpeechRecognition + Google SR | Automatic Speech Recognition (ASR) |
| **Text-to-Speech** | gTTS + pyttsx3 | Voice output generation |
| **Agent Framework** | Custom Tool-Use Loop | Agentic reasoning & execution |

### Operating System Integration

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Desktop Automation** | PyAutoGUI | Keyboard/Mouse control |
| **Shell Integration** | subprocess | Command execution |
| **Web Navigation** | webbrowser | URL handling |
| **File Operations** | os, shutil | File management |

### Data & Persistence

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Database** | Firebase / MySQL | Chat history & user authentication |
| **Local Storage** | JSON | Reminders & configuration cache |
| **State Management** | In-memory objects | Real-time conversation state |

---

## 🏗️ System Architecture

### High-Level Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                     JAGUAR AI PROCESSING LOOP                     │
└─────────────────────────────────────────────────────────────────┘

  🎤 Voice Input (Microphone)
    ↓
  🗣️ Speech-to-Text (ASR)
    ↓
  🔀 Command Router (Keyword + NLP)
    ↓
  🧠 LLM Reasoning & Tool Planning
    ↓
  🛠️ Tool Executor (Planned Actions)
    ↓
  ⏳ User Confirmation Envelope
    ↓
  💻 OS Side-Effect Execution
    ↓
  🔊 Text-to-Speech Response (TTS)
    ↓
  📊 State Update & History Logging
```

### Component Breakdown

#### 1. **Voice Listener** (`listener.py`)
- Continuously monitors microphone input
- Detects wake words or activation signals
- Captures and buffers audio frames
- Thread-based non-blocking operation

#### 2. **Speech-to-Text** (`listener.py`, `languages.py`)
- Converts audio to text using Google SR API
- Supports multiple languages
- Implements retry logic for robustness
- Handles audio preprocessing

#### 3. **Command Router** (`router.py`, `agents.py`)
- Hybrid keyword + LLM-based routing
- Identifies command intent
- Routes to specialized handlers
- Maintains conversation context

#### 4. **LLM Client** (`llm_client.py`)
- Abstraction layer for multiple AI providers
- Handles authentication & API calls
- Implements retry & caching strategies
- Supports tool-use/function-calling

#### 5. **Tool Executor** (`tool_executor.py`, `tools.py`)
- Executes planned actions safely
- Implements confirmation before mutations
- Captures output and errors
- Maintains audit trail

#### 6. **Confirmation System** (`confirmations.py`)
- Prompts user for approval on risky operations
- Voice-based yes/no confirmation
- Visual feedback via overlay
- Timeout handling for safety

#### 7. **Text-to-Speech** (`speaker.py`)
- Converts text responses to speech
- Supports multiple TTS engines
- Implements audio streaming
- Thread-safe audio output

#### 8. **Reminder Manager** (`reminder_manager.py`)
- Background task scheduler
- Proactive alert generation
- Time-based trigger evaluation
- Persistent state across sessions

#### 9. **Desktop Overlay** (`overlay.py`, `control_gui.py`)
- Real-time status visualization
- State indicators (Idle, Listening, Processing)
- Quick control buttons
- Always-on-top window management

#### 10. **State Manager** (`state.py`, `db.py`)
- Maintains conversation history
- Stores user preferences
- Manages session data
- Database synchronization

---

## 📦 Installation & Setup

### Prerequisites

- **Python 3.12+** (Download from [python.org](https://www.python.org/))
- **Windows OS** (Primary support; Linux/macOS support in progress)
- **Microphone** for voice input
- **Speaker** for audio output
- **8GB RAM** minimum (16GB+ recommended)

### Step 1: Clone Repository

```bash
git clone https://github.com/Aravindra2007/JAGUAR_AI.git
cd JAGUAR_AI
```

### Step 2: Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Environment Configuration

Create a `.env` file in the project root:

```env
# Flask Configuration
JAGUAR_SECRET_KEY=your-secure-random-key-here
FLASK_ENV=production

# LLM Provider Keys
ANTHROPIC_API_KEY=sk-ant-xxxxx
OPENAI_API_KEY=sk-xxxx
GOOGLE_API_KEY=xxxxx
OLLAMA_BASE_URL=http://localhost:11434  # If using local Ollama

# Database Configuration
FIREBASE_CREDENTIALS_PATH=path/to/serviceAccountKey.json
# OR
DATABASE_URL=mysql://user:password@localhost:3306/jaguar_ai

# Voice Settings
DEFAULT_LANGUAGE=en-US
TTS_ENGINE=gtts  # Options: gtts, pyttsx3, azure

# Security
WORKSPACE_PATH=./workspace
MAX_FILE_SIZE=52428800  # 50MB in bytes
ALLOWED_COMMANDS=dir,ipconfig,tasklist,systeminfo
```

### Step 5: Verify Installation

```bash
python -c "import jaguar_core; print('Installation successful!')"
```

---

## ⚙️ Configuration

### LLM Provider Selection

Edit the active provider in your code or environment:

```python
# Use Anthropic Claude
os.environ["LLM_PROVIDER"] = "anthropic"

# Use OpenAI GPT
os.environ["LLM_PROVIDER"] = "openai"

# Use Local Ollama (Privacy-first)
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
os.environ["OLLAMA_MODEL"] = "llama2"
```

### Voice & Language Settings

```python
# Supported languages
LANGUAGE_CODES = {
    "en-US": "English (US)",
    "en-GB": "English (UK)",
    "es-ES": "Spanish",
    "fr-FR": "French",
    # ... more languages
}

# Configure in .env
DEFAULT_LANGUAGE=es-ES
```

### Security Allowlist

Modify `os_bridge.py` to customize allowed shell commands:

```python
ALLOWED_COMMANDS = {
    "file_operations": ["dir", "copy", "move", "delete"],
    "system_info": ["ipconfig", "tasklist", "systeminfo"],
    "network": ["ping", "ipconfig"],
}
```

### Workspace Isolation

```python
# All file operations restricted to:
WORKSPACE_PATH = "./workspace"

# This prevents accidental system-wide changes
```

---

## 🚀 Usage

### Quick Start - Command Line

```bash
# Start the agent (voice mode)
python main.py

# The agent will:
# 1. Listen for voice input
# 2. Process your command
# 3. Request confirmation if needed
# 4. Execute and respond with voice feedback
```

### Web Dashboard

```bash
# Start Flask server
python app.py

# Access dashboard at: http://localhost:5000
```

### Streamlit Interface (Advanced)

```bash
streamlit run streamlit_app.py
```

### Example Commands

| Command | Result |
|---------|--------|
| "Open Visual Studio Code" | Launches VS Code |
| "What's the weather?" | Fetches and speaks weather |
| "Create a reminder at 3 PM to call mom" | Schedules reminder |
| "Search for Python tutorials" | Opens search in browser |
| "What's in this PDF?" | Analyzes uploaded document |
| "Set volume to 50%" | Controls system audio |

---

## 📁 Project Structure

```
JAGUAR_AI/
├── jaguar_core/              # Core modules
│   ├── __init__.py
│   ├── state.py             # State management
│   ├── db.py                # Database operations
│   └── config.py            # Configuration loader
│
├── jaguar_ai/               # AI & NLP modules
│   ├── llm_client.py        # LLM provider abstraction
│   ├── agents.py            # Agent logic
│   └── tools.py             # Available tools
│
├── listener.py              # Speech recognition
├── speaker.py               # Text-to-speech
├── router.py                # Command routing
├── tool_executor.py         # Tool execution engine
├── confirmations.py         # User confirmation logic
├── reminder_manager.py      # Background reminders
├── overlay.py               # Desktop overlay UI
├── control_gui.py           # GUI components
├── os_bridge.py             # OS automation layer
├── os_tools.py              # System utilities
├── file_reader.py           # File parsing
├── languages.py             # Language support
│
├── main.py                  # CLI entry point
├── app.py                   # Flask web server
├── streamlit_app.py         # Streamlit dashboard
├── wsgi.py                  # WSGI configuration
├── auth.py                  # Authentication
├── commands.py              # Command definitions
│
├── api/                     # REST API endpoints
├── static/                  # Web assets (CSS, JS, images)
├── templates/               # HTML templates
├── deploy/                  # Deployment configs
│
├── Dockerfile               # Docker containerization
├── docker-compose.yml       # Multi-container setup
├── requirements.txt         # Python dependencies
├── .env.example            # Environment template
└── README.md               # This file
```

---

## 🔐 Security

### Core Principles

1. **Zero Trust Execution**: No action executes without explicit user confirmation
2. **Sandboxed Operations**: All file I/O restricted to workspace directory
3. **Allowlist-Based Commands**: Only pre-approved shell commands permitted
4. **No Local Credential Storage**: API keys via environment variables only
5. **Audit Trail**: All actions logged with timestamps

### Implementation Details

#### Confirmation Envelope Pattern

```python
# Example: File deletion requires approval
action = {
    "type": "delete_file",
    "path": "./workspace/document.txt",
    "description": "Delete document.txt from workspace"
}

# Prompt user
if user_confirms(action):
    execute_action(action)
else:
    cancel_action(action)
```

#### Command Allowlist

```python
SAFE_COMMANDS = [
    "dir",          # List directory
    "ipconfig",     # Network info
    "tasklist",     # Running processes
    "systeminfo"    # System details
]

# Dangerous commands blocked
BLOCKED_PATTERNS = [
    "rm -rf /",     # Recursive deletion
    "format C:",    # Disk formatting
    "del *.* /s"    # Mass deletion
]
```

---

## 🐳 Deployment

### Docker Container

```bash
# Build image
docker build -t jaguar-ai .

# Run container
docker run -it \
  -e ANTHROPIC_API_KEY=sk-ant-xxxxx \
  -e OPENAI_API_KEY=sk-xxxx \
  -v $(pwd)/workspace:/app/workspace \
  jaguar-ai
```

### Docker Compose (Multi-Service)

```bash
docker-compose up -d
```

Includes:
- Jaguar AI service
- Firebase emulator (optional)
- MySQL database (optional)

### Cloud Deployment

#### Fly.io (Recommended)

```bash
flyctl deploy
# Uses fly.toml configuration
```

#### Render

```bash
# Deploy via Render dashboard
# Uses render.yaml configuration
```

#### Heroku

```bash
# Uses Procfile configuration
git push heroku main
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Microphone Not Detected

```bash
# Check available audio devices
python -c "import speech_recognition as sr; print(sr.Microphone.list_microphone_indexes())"

# Set specific microphone in .env
MIC_DEVICE_INDEX=0
```

#### 2. API Authentication Failed

```bash
# Verify API keys
python -c "import os; print(os.getenv('ANTHROPIC_API_KEY'))"

# Check .env file exists and is properly formatted
```

#### 3. Slow Response Times

- **Solution 1**: Use local Ollama model for faster inference
- **Solution 2**: Reduce conversation history length
- **Solution 3**: Upgrade to higher-tier API plan

#### 4. Database Connection Error

```bash
# Test database connection
python -c "from jaguar_core.db import test_connection; test_connection()"

# Check DATABASE_URL format
DATABASE_URL=mysql://user:pass@host:3306/dbname
```

#### 5. Desktop Overlay Not Appearing

```bash
# Ensure tkinter is installed
python -m tkinter  # Should open a window

# Restart Jaguar with overlay enabled
ENABLE_OVERLAY=true python main.py
```

---

## 🤝 Contributing

We welcome contributions! Here's how to help:

### Development Setup

```bash
git clone https://github.com/Aravindra2007/JAGUAR_AI.git
cd JAGUAR_AI
git checkout -b feature/your-feature-name
pip install -r requirements-dev.txt
```

### Contribution Workflow

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Make** your changes
4. **Test** thoroughly (`pytest tests/`)
5. **Commit** with clear messages (`git commit -m 'Add amazing feature'`)
6. **Push** to branch (`git push origin feature/amazing-feature`)
7. **Open** a Pull Request

### Guidelines

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide
- Add docstrings to all functions
- Include unit tests for new features
- Update README if adding new capabilities
- Keep commits atomic and logical

### Areas for Contribution

- [ ] Linux/macOS support
- [ ] Additional LLM providers
- [ ] Enhanced voice recognition
- [ ] Mobile app integration
- [ ] Web UI improvements
- [ ] Documentation & tutorials
- [ ] Plugin ecosystem

---

## 📊 Performance Metrics

| Metric | Value |
|--------|-------|
| Voice Recognition Latency | 2-3 seconds (depends on audio length) |
| LLM Response Time | 1-10 seconds (varies by provider) |
| Confirmation Response | <500ms (local execution) |
| Memory Footprint | 200-400MB (baseline) |
| CPU Usage (Idle) | <2% |
| Database Query Time | <100ms (typical) |

---

## 📝 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

**You are free to:**
- ✅ Use commercially
- ✅ Modify and distribute
- ✅ Use privately
- ✅ Include in your projects

**Conditions:**
- 📋 Include original license and copyright notice

---

## 🙏 Acknowledgments

- **Speech Recognition**: Google Speech-to-Text API
- **TTS Providers**: Google Text-to-Speech, pyttsx3
- **LLM Providers**: OpenAI, Anthropic, Google, Ollama
- **Community**: All contributors and users

---

## 📞 Support & Contact

### Getting Help

1. **Documentation**: Check [SETUP_NEW_FEATURES.md](SETUP_NEW_FEATURES.md)
2. **Issues**: [GitHub Issues](https://github.com/Aravindra2007/JAGUAR_AI/issues)
3. **Discussions**: [GitHub Discussions](https://github.com/Aravindra2007/JAGUAR_AI/discussions)
4. **Email**: Contact via GitHub issues

### Report Security Issues

🔒 **Please report security vulnerabilities privately** by emailing maintainers rather than using public issue tracker.

---

## 📈 Roadmap

### Version 2.0 (Planned)

- [ ] Full Linux & macOS support
- [ ] Whisper API for improved STT
- [ ] Web interface improvements
- [ ] Plugin system for custom tools
- [ ] Multi-user support
- [ ] Advanced conversation memory (RAG)
- [ ] Mobile companion app
- [ ] Integration with smart home devices

### Version 1.5 (Current)

- ✅ Multi-LLM provider support
- ✅ Voice-first interface
- ✅ Desktop automation
- ✅ Reminder system
- ✅ Web dashboard
- ✅ Docker support

---

## ⭐ Show Your Support

If JAGUAR AI helped you, please:

- ⭐ **Star this repository** on GitHub
- 📢 **Share** with your network
- 🐛 **Report issues** or suggest improvements
- 🤝 **Contribute** to the project
- 💬 **Provide feedback** via discussions

---

<div align="center">

**Made with ❤️ by the JAGUAR AI Community**

[![GitHub Stars](https://img.shields.io/github/stars/Aravindra2007/JAGUAR_AI?style=social)](https://github.com/Aravindra2007/JAGUAR_AI/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/Aravindra2007/JAGUAR_AI?style=social)](https://github.com/Aravindra2007/JAGUAR_AI/network/members)
[![GitHub Issues](https://img.shields.io/github/issues/Aravindra2007/JAGUAR_AI?style=social)](https://github.com/Aravindra2007/JAGUAR_AI/issues)

</div>
