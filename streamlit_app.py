import os
import streamlit as st
import base64
from streamlit_autorefresh import st_autorefresh
from router import CommandRouter
from listener import VoiceListener
import agents
import state
import languages
from datetime import datetime 

# ---------------------------------------------------------------
# UI CONFIG
# ---------------------------------------------------------------
st.set_page_config(
    page_title="Jaguar AI",
    page_icon="icon.png",
    layout="centered",
)

# ---------------------------------------------------------------
# GLOBAL STYLES (Futuristic UI)
# ---------------------------------------------------------------

def set_bg(image_file):
    with open(image_file, "rb") as f:
        data = base64.b64encode(f.read()).decode()

    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: linear-gradient(rgba(0,0,0,0.75), rgba(0,0,0,0.75)),
                              url("data:image/jpg;base64,{data}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}

        /* Hide default UI */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}

        /* Glass effect container */
        .block-container {{
            backdrop-filter: blur(10px);
        }}

        /* Chat bubbles */
        .stChatMessage {{
            background: rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 12px;
            margin-bottom: 10px;
            box-shadow: 0 0 10px rgba(0,255,255,0.2);
        }}

        /* Input box */
        .stChatInput > div {{
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
        }}

        /* Title glow */
        h1 {{
            text-align: center;
            color: #00FFFF;
            text-shadow: 0 0 20px #00FFFF;
        }}

        /* Typing cursor animation */
        .typing {{
            border-right: 2px solid #00FFFF;
            animation: blink 1s infinite;
        }}

        @keyframes blink {{
            0% {{ border-color: transparent; }}
            50% {{ border-color: #00FFFF; }}
            100% {{ border-color: transparent; }}
        }}

        /* Mic pulse animation */
        .mic {{
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: rgba(0,255,255,0.2);
            margin: 10px auto;
            animation: pulse 1.5s infinite;
        }}

        @keyframes pulse {{
            0% {{ transform: scale(1); opacity: 0.7; }}
            50% {{ transform: scale(1.2); opacity: 1; }}
            100% {{ transform: scale(1); opacity: 0.7; }}
        }}

        </style>
        """,
        unsafe_allow_html=True
    )

# 👉 your JPG file
set_bg("back.png")

# ---------------------------------------------------------------
# Sidebar Logo (Circle + Glow)
# ---------------------------------------------------------------
def get_base64(img_path):
    with open(img_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

img_base64 = get_base64("logo1.jpg")

st.sidebar.markdown(
    f"""
    <div style="text-align:center;">
        <img src="data:image/jpg;base64,{img_base64}" 
             style="width:120px;height:120px;border-radius:50%;
             object-fit:cover;border:3px solid #00FFFF;
             box-shadow:0 0 20px #00FFFF;">
        <h2 style="color:white;">Jaguar AI</h2>
    </div>
    """,
    unsafe_allow_html=True
)

# ---------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------
@st.cache_resource
def get_router():
    return CommandRouter()

@st.cache_resource
def get_listener():
    vl = VoiceListener()
    vl.start()
    return vl

router = get_router()
listener = get_listener()

# ---------------------------------------------------------------
# Optional auto refresh
# ---------------------------------------------------------------
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=1500, key="jaguar_autorefresh")
except ImportError:
    st.sidebar.caption("Tip: pip install streamlit-autorefresh")

# ---------------------------------------------------------------
# Sidebar Controls
# ---------------------------------------------------------------
current_status, current_text = state.get_status()

# 🎙️ MIC ANIMATION WHEN LISTENING
if current_status == "Listening...":
    st.sidebar.markdown('<div class="mic"></div>', unsafe_allow_html=True)

status_icons = {
    "Idle": "🟢",
    "Listening...": "🎙️",
    "Processing...": "🟡",
    "Offline": "🔴",
    "No Microphone": "🔴",
}

st.sidebar.markdown(
    f"**Status:** {status_icons.get(current_status, '⚪')} {current_status}"
)

col1, col2 = st.sidebar.columns(2)

if col1.button("🎤 Start", use_container_width=True):
    listener.start_listening()
    st.rerun()

if col2.button("⏹️ Stop", use_container_width=True):
    listener.stop_listening()
    st.rerun()

muted = st.sidebar.toggle("Mute voice responses", value=state.is_muted())
if muted != state.is_muted():
    state.set_muted(muted)

if st.sidebar.button("🗑️ Clear History", use_container_width=True):
    state.clear_history()
    state.set_text("Conversation Cleared.")
    st.rerun()

st.sidebar.divider()
st.sidebar.caption("Last response")
st.sidebar.info(current_text)

# ---------------------------------------------------------------
# LLM SETTINGS (unchanged)
# ---------------------------------------------------------------

# ---------------------------------------------------------------
# LLM SETTINGS
# ---------------------------------------------------------------

st.sidebar.divider()

with st.sidebar.expander("🧠 LLM settings", expanded=False):

    cfg = state.get_llm_config()

    # Enable / Disable LLM
    llm_enabled = st.toggle(
        "Enable LLM",
        value=cfg["enabled"]
    )

    # Provider list
    provider_options = [
        "OpenAI",
        "Gemini",
        "Claude (Anthropic)",
        "Ollama (local)"
    ]

    provider = st.selectbox(
        "Provider",
        provider_options,
        index=(
            provider_options.index(cfg["provider"])
            if cfg["provider"] in provider_options
            else 0
        )
    )

    # ===========================================================
    # OPENAI
    # ===========================================================

    if provider == "OpenAI":

        api_key = st.text_input(
            "OpenAI API key",
            value=cfg.get("api_key", ""),
            type="password"
        )

        model = st.selectbox(
            "OpenAI Model",
            [
                "gpt-4o-mini",
                "gpt-4o",
                "gpt-4.1-mini",
                "gpt-4.1"
            ],
            index=0
        )

        ollama_host = cfg.get("ollama_host", "")

    # ===========================================================
    # GOOGLE AI STUDIO / GEMINI
    # ===========================================================

    elif provider == "Gemini":

        api_key = st.text_input(
            "Google AI Studio API key",
            value=cfg.get("api_key", ""),
            type="password",
            help="Create your Gemini API key in Google AI Studio."
        )

        model = st.selectbox(
            "Gemini Model",
            [
                "gemini-2.0-flash",
                "gemini-3.5-flash",
                "gemini-3.5-pro",
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-1.5-flash",
                "gemini-1.5-pro"
            ],
            index=0
        )

        ollama_host = cfg.get("ollama_host", "")

    # ===========================================================
    # CLAUDE
    # ===========================================================

    elif provider == "Claude (Anthropic)":

        api_key = st.text_input(
            "Anthropic API key",
            value=cfg.get("api_key", ""),
            type="password"
        )

        model = st.selectbox(
            "Claude Model",
            [
                "claude-sonnet-5",
                "claude-opus-4-8",
                "claude-haiku-4-5-20251001"
            ],
            index=0,
            help=(
                "Claude Mythos is not publicly available. "
                "It is invite-only."
            )
        )

        ollama_host = cfg.get("ollama_host", "")

    # ===========================================================
    # OLLAMA
    # ===========================================================

    else:

        # Ollama does not require an API key
        api_key = ""

        model = st.text_input(
            "Ollama Model",
            value=cfg.get("model") or "llama3"
        )

        ollama_host = st.text_input(
            "Ollama Host",
            value=cfg.get("ollama_host") or "http://localhost:11434"
        )

    # ===========================================================
    # COMMON SETTINGS
    # ===========================================================

    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.5,
        value=float(cfg.get("temperature", 0.7)),
        step=0.1
    )

    system_prompt = st.text_area(
        "System prompt",
        value=cfg.get(
            "system_prompt",
            "You are Jaguar AI, a helpful personal AI assistant."
        )
    )

    # Save configuration
    state.set_llm_config(
        enabled=llm_enabled,
        provider=provider,
        api_key=api_key,
        model=model,
        temperature=temperature,
        system_prompt=system_prompt,
        ollama_host=ollama_host,
    )

st.sidebar.divider()
st.sidebar.caption("🌐 Language")

current_language = state.get_language()
lang_options = languages.list_languages()

selected_language = st.sidebar.selectbox(
    "Assistant language",
    lang_options,
    index=lang_options.index(current_language) if current_language in lang_options else 0,
    label_visibility="collapsed",
)

if selected_language != current_language:
    state.set_language(selected_language)
    st.rerun()


# ---------------------------------------------------------------
# AGENTS (new)
# ---------------------------------------------------------------
st.sidebar.divider()
with st.sidebar.expander("🤖 Student agents", expanded=False):
    st.caption(
        "Jaguar automatically picks one of these based on what you say - "
        "no need to select one manually."
    )
    for a in agents.list_agents():
        if a["key"] != "general":
            st.markdown(f"- {a['label']}")

# ---------------------------------------------------------------
# MAIN CHAT
# ---------------------------------------------------------------
st.title("Jaguar AI Assistant")

now = datetime.now()
current_time = now.strftime("%I:%M %p")   # 12-hour format
current_date = now.strftime("%A, %d %B %Y")

st.markdown(
    f"""
    <div style="
        display:flex;
        justify-content:space-between;
        align-items:center;
        padding:5px 10px;
        margin-bottom:5px;
        background: rgba(255,255,255,0.08);
        border-radius:10px;
        font-size:14px;
        color:#00FFFF;
        box-shadow:0 0 10px rgba(0,255,255,0.2);
    ">
        <span>🗓️ {current_date}</span>
        <span>⏰ {current_time}</span>
    </div>
    """,
    unsafe_allow_html=True
)





for entry in state.get_history():
    with st.chat_message("user"):
        st.write(entry["user"])

    with st.chat_message("assistant"):
        st.write(entry["assistant"])

prompt = st.chat_input("Type or speak...")

if prompt:
    text = prompt.strip()

    with st.chat_message("user"):
        st.write(text)

    state.set_status("Processing...")

    # 🤖 TYPING ANIMATION
    typing_placeholder = st.empty()
    typing_placeholder.markdown(
        '<div class="typing"><span></span><span></span><span></span></div>',
        unsafe_allow_html=True
    )

    response = router.process(text)

    typing_placeholder.empty()

    state.set_status("Idle")
    state.set_text(response)
    state.add_history(text, response)

    with st.chat_message("assistant"):
        st.write(response)

    st.rerun()