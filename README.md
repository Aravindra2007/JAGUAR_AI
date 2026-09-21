# 🐆 Jaguar AI: Local OS Intelligence Agent

Jaguar AI is a sophisticated, voice-activated local agent designed to bridge the gap between Large Language Models (LLMs) and direct Operating System control. Unlike cloud chatbots, Jaguar operates as a local agent with the ability to launch applications, manage files, and execute system commands on a Windows environment.

![Python](https://img.shields.io/badge/Python-3.12-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)

## 🚀 Core Capabilities

- **Voice-to-Action Pipeline**: Integrated Speech-to-Text (STT) and Text-to-Speech (TTS) for a hands-free experience.
- **Agentic Tool-Use**: Utilizes a "Confirmation Envelope" pattern to safely execute mutating OS actions (e.g., writing files, launching apps) only after explicit user approval.
- **Proactive Intelligence**: Features a background reminder service that independently monitors and triggers alerts.
- **Contextual Awareness**: Maintains short-term conversation history and processes uploaded document/image context to answer specific queries about local data.
- **Visual Presence**: A dedicated desktop overlay (status pill) providing real-time feedback on the agent's state (Idle, Listening, Processing).

## 🛠️ Technical Stack

### Backend & Orchestration
- **Language**: Python 3.12
- **Web Framework**: Flask (API & Dashboard)
- **Concurrency**: Threading (for Voice Listener, Reminder Manager, and Overlay)

### AI & NLP
- **LLM Providers**: Anthropic (Claude 3.5 Sonnet), OpenAI (GPT-4o), Google (Gemini), and Ollama (Local Llama 3)
- **NLU**: Hybrid Keyword Routing + LLM Reasoning
- **Agent Loop**: Tool-calling loop with confirmation-based execution

### OS & Voice Integration
- **Speech Recognition**: `SpeechRecognition` (Google SR)
- **Text-to-Speech**: `gTTS` (Google TTS) and `pyttsx3` (Offline Fallback)
- **OS Automation**: `pyautogui` (Keyboard/Mouse), `subprocess` (Shell), `webbrowser`
- **UI/Overlay**: `tkinter` (Desktop Overlay)

### Data & Storage
- **Database**: Firebase / MySQL (Chat History & User Auth)
- **Local Storage**: JSON-based persistence for reminders and configuration

## 🔄 System Pipeline

**Voice Input** $\rightarrow$ **ASR (STT)** $\rightarrow$ **Command Router** $\rightarrow$ **LLM / Keyword Match** $\rightarrow$ **Tool Executor** $\rightarrow$ **User Confirmation** $\rightarrow$ **OS Side-Effect** $\rightarrow$ **TTS Feedback**

## 📦 Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/jaguar-ai.git
   cd jaguar-ai
   ```

2. **Setup Virtual Environment**:
   ```bash
   python -m venv myenv
   # On Windows:
   myenv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   Create a `.env` file in the root directory with your API keys:
   ```env
   JAGUAR_SECRET_KEY=your_secret_key
   ANTHROPIC_API_KEY=your_api_key
   OPENAI_API_KEY=your_api_key
   FIREBASE_CREDENTIALS_PATH=path/to/your/serviceAccountKey.json
   ```

4. **Run the Agent**:
   ```bash
   python main.py
   ```

## 🛡️ Security Implementation
- **Allowlist-based Shell**: Only pre-approved commands (e.g., `dir`, `ipconfig`) can be executed.
- **Workspace Isolation**: All file operations are restricted to a designated workspace directory to prevent system-wide corruption.
- **Human-in-the-Loop**: No mutating tool is executed without an explicit user "Yes" via voice or GUI.
