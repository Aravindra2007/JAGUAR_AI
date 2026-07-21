from commands import Commands
from llm_client import ask, LLMError
import agents
import state


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
        state.set_text(f"[{agents.AGENTS[agent_key]['label']}] thinking...")

        messages = [{"role": "system", "content": system_prompt}]

        # Give the model a little short-term memory of the recent
        # conversation (typed + spoken) so follow-up questions work.
        for entry in state.get_history()[-5:]:
            messages.append({"role": "user", "content": entry["user"]})
            messages.append({"role": "assistant", "content": entry["assistant"]})

        messages.append({"role": "user", "content": text})

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
