from commands import Commands
from llm_client import ask, ask_claude_with_tools, LLMError
import agents
import state
from tool_executor import ToolExecutor
from tools import TOOLS


class CommandRouter:

    def __init__(self):

        self.cmd = Commands()

        self.routes = {

            # Browser
            "open google": self.cmd.open_google,
            "close google": self.cmd.close_tab,

            "open youtube": self.cmd.open_youtube,
            "close youtube": self.cmd.close_tab,

            "play": self.cmd.play_youtube,
            "search youtube": self.cmd.search_youtube,
            "search": self.cmd.search_google,

            # Websites
            "open chat gpt": self.cmd.open_chatgpt,
            "chatgpt": self.cmd.open_chatgpt,
            "close chatgpt": self.cmd.close_tab,

            "open github": self.cmd.open_github,
            "github": self.cmd.open_github,
            "close github": self.cmd.close_tab,

            # Windows Apps
            "open note pad": self.cmd.open_notepad,
            "close note pad": self.cmd.close,

            "open calculator": self.cmd.open_calculator,
            "close calculator": self.cmd.close,

            "open paint": self.cmd.open_paint,
            "close paint": self.cmd.close,

            "open command prompt": self.cmd.open_cmd,
            "close command prompt": self.cmd.close,

            "open vs code": self.cmd.open_vscode,
            "close vs code": self.cmd.close,

            # System
            "time": self.cmd.get_time,
            "date": self.cmd.get_date,

            "shutdown": self.cmd.shutdown,
            "restart": self.cmd.restart,

            # Exit
            "exit": self.cmd.exit,
            "quit": self.cmd.exit,
            "goodbye": self.cmd.exit,
        }

    def process(self, text):

        if not text:
            return "I didn't hear any command."

        text = text.lower().strip()

        for command, function in self.routes.items():

            if text.startswith(command):
                return function(text)

        # No built-in command matched - hand it off to the LLM instead
        # of just saying "I didn't understand". This is what makes
        # Jaguar able to hold a real conversation, whether the text
        # came from typing or from the voice listener.
        return self._ask_llm(text)

    # -------------------------
    # LLM fallback
    # -------------------------

    def _ask_llm(self, text):

        cfg = state.get_llm_config()

        if not cfg.get("enabled", True):
            return "Sorry Sir, I didn't understand that command."

        provider = cfg.get("provider", "OpenAI")
        api_key = cfg.get("api_key", "")
        model = cfg.get("model", "")
        temperature = cfg.get("temperature", 0.7)
        base_system_prompt = cfg.get("system_prompt", "")
        ollama_host = cfg.get("ollama_host") or None

        # Pick a specialist agent (Study Buddy, Planner, Notes, Quiz
        # Maker, Research Assistant, Wellness check-in, or general
        # fallback) based on the message, and layer its system prompt
        # on top of the user's own Jaguar persona.

        agent_key = agents.pick_agent(text)
        system_prompt = agents.system_prompt_for(agent_key, base_system_prompt)

        language = state.get_language()
        if language != "English":
            system_prompt += (
                f"\n\nRespond only in {language}, regardless of what "
                "language this prompt or the user's message is written "
                f"in. Do not mix in English unless the user explicitly "
                f"asks a question in English."
            )

        state.set_text(f"[{agents.AGENTS[agent_key]['label']}] thinking...")

        messages = [{"role": "system", "content": system_prompt}]

        # Give the model a little short-term memory of the recent
        # conversation (typed + spoken) so follow-up questions work.
        for entry in state.get_history()[-5:]:
            messages.append({"role": "user", "content": entry["user"]})
            messages.append({"role": "assistant", "content": entry["assistant"]})

        messages.append({"role": "user", "content": text})

        # --- Phase 1: Claude tool-use path ---
        # Only fires when the user has explicitly enabled tool-use and
        # the configured provider is Anthropic. OpenAI/Gemini/Ollama
        # fall through to the existing ask() path.
        if (
            provider == "Claude (Anthropic)"
            and cfg.get("tools_enabled", False)
            and api_key
        ):
            workspace_dir = cfg.get("workspace_dir", "") or ""
            executor = ToolExecutor(workspace_dir=workspace_dir)
            try:
                result = ask_claude_with_tools(
                    messages=messages,
                    api_key=api_key,
                    model=model or "claude-sonnet-5",
                    tools=TOOLS,
                    executor=executor,
                    temperature=temperature,
                )
                if result.get("needs_confirmation"):
                    envelope = result["envelope"]
                    state.set_text("[Awaiting confirmation]")
                    return envelope
                text_reply = (result.get("text") or "").strip()
                if text_reply:
                    return text_reply
                return "Done."
            except LLMError as e:
                return f"Sorry Sir, I couldn't reach the language model: {e}"
            except Exception as e:
                return f"Sorry Sir, something went wrong talking to the model: {e}"

        # --- Existing chat path (OpenAI / Gemini / Ollama / no-tools Claude) ---
        try:
            reply = ask(
                provider,
                messages,
                api_key=api_key,
                model=model,
                temperature=temperature,
                stream=False,
                ollama_host=ollama_host,
            )
            return reply.strip() if reply else "I'm not sure how to respond to that."

        except LLMError as e:
            return f"Sorry Sir, I couldn't reach the language model: {e}"

        except Exception as e:
            return f"Sorry Sir, something went wrong talking to the model: {e}"

    # -------------------------
    # Confirmation resolution (Phase 1, tool-use)
    # -------------------------

    def process_with_confirmation(self, token, decision):
        """Resolve a pending tool-use confirmation envelope.

        Returns the assistant's plain-text reply (after either executing
        the action on 'yes' or cancelling on 'no'). UI surfaces call this
        from the Approve/Deny buttons and from the voice listener's
        yes/no follow-up.
        """
        cfg = state.get_llm_config()
        workspace_dir = cfg.get("workspace_dir", "") or ""
        executor = ToolExecutor(workspace_dir=workspace_dir)
        try:
            return executor.execute_confirmed(token, decision)
        except Exception as e:
            return f"Sorry Sir, something went wrong running that action: {e}"
