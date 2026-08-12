# What's new in this build

1. **MySQL database** — accounts and chat history now persist in MySQL instead of living only in memory.
2. **Login page** — nobody can use Jaguar without an account. Passwords are hashed (never stored in plain text).
3. **Stop button actually stops speech** — clicking Stop (or the new "Stop speaking" button) interrupts Jaguar mid-sentence instead of just muting future replies.
4. **File/image upload for tasking** — attach a PDF, Word doc, text file, or image; Jaguar reads it and folds it into your very next question ("summarize this", "quiz me on chapter 3", etc).
5. **New chat UI** (`templates/index.html`) — a combined ChatGPT-style conversation view + Jarvis-style live status HUD, with your Jaguar branding.

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

On Windows, `PyAudio` may need a prebuilt wheel if `pip install` fails — use `pipwin install pyaudio`.

For image OCR (optional — uploads still work without it, just won't extract text from images), also install the Tesseract OCR engine itself:
- Windows: https://github.com/UB-Mannheim/tesseract/wiki
- macOS: `brew install tesseract`
- Linux: `sudo apt install tesseract-ocr`

## 2. Set up MySQL

Install MySQL Server if you don't already have it (https://dev.mysql.com/downloads/mysql/), then:

```bash
cp .env.example .env
```

Edit `.env` with your MySQL credentials:

```env
JAGUAR_DB_HOST=localhost
JAGUAR_DB_PORT=3306
JAGUAR_DB_USER=root
JAGUAR_DB_PASSWORD=your_mysql_password
JAGUAR_DB_NAME=jaguar_ai
JAGUAR_SECRET_KEY=<generate one, see below>
```

Generate a real secret key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

You do **not** need to manually create the database or tables — `app.py` calls `db.init_db()` on startup, which creates the `jaguar_ai` database and all tables (`users`, `chat_history`, `uploaded_files`) automatically if they don't exist.

## 3. Run it

```bash
python app.py
```

Then open `http://127.0.0.1:5000`. You'll land on the login page — click "Create an account" to register, then sign in.

## 4. What changed under the hood

| File | Change |
|---|---|
| `db.py` | **New.** All MySQL access — users, chat history, uploaded files. |
| `auth.py` | **New.** Flask-Login blueprint: `/login`, `/register`, `/logout`. |
| `file_reader.py` | **New.** Extracts text from uploaded PDFs/DOCX/TXT/images. |
| `speaker.py` | Rewritten so `stop_speaking()` genuinely interrupts audio already playing (pyttsx3 `.stop()` + pygame instead of the old blocking `playsound`). |
| `state.py` | Added `is_speaking()`, current-user tracking (so the voice thread can save to MySQL under the right account), and pending-attachment context for uploads. |
| `router.py` | Every finished exchange is now saved to MySQL under the logged-in user. Also folds in any pending upload context before asking the LLM. |
| `listener.py` | `stop_listening()` now calls `stop_speaking()` first, so voice-triggered Stop cuts off audio immediately. |
| `app.py` | Every route now requires login. Added `/upload` and `/stop-speaking`. History/clear now read/write MySQL. |
| `templates/login.html`, `templates/register.html`, `templates/index.html` | **New.** The whole frontend — dark, Jaguar-branded, ChatGPT-conversation + Jarvis-HUD styling. |

## 5. Notes on productionizing further

- Set `debug=False` (already done) and put this behind a real WSGI server (gunicorn/waitress) + reverse proxy (nginx) before shipping to real users.
- `state.py` is still a single global (one microphone, one "current speaker") — fine for a personal desktop assistant, but if you want *multiple people* using voice simultaneously from different machines, the voice pipeline needs to move to a per-session model.
- Rotate `JAGUAR_SECRET_KEY` and never commit `.env` to git (it's already what `.env.example` is for).
- Consider adding rate limiting (`flask-limiter`) on `/login` and `/register` before a public launch.
