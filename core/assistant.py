# from core.speech_engine import SpeechEngine
# from core.command_router import CommandRouter
# from core.wake_word import is_wake_word

# from ai.chatgpt_client import ChatGPTClient
# from ai.local_llm import LocalLLM
# from ai.conversation_memory import (
#     ConversationMemory
# )
# from ai.vision import VisionAI

# from automation.app_manager import AppManager
# from automation.browser import Browser
# from automation.file_manager import FileManager
# from automation.system_control import SystemControl
# from automation.keyboard_mouse import KeyboardMouse
# from automation.clipboard import Clipboard

# from plugins.manager import PluginManager
# from scheduler.task_scheduler import TaskScheduler
# from skills.skill_manager import SkillManager
# from agents.planner_agent import PlannerAgent
# from agents.executor_agent import ExecutorAgent

# from ai.pdf_summarizer import (
#     PDFSummarizer
# )

# from ai.document_qa import (
#     DocumentQA
# )

# from ai.image_understanding import (
#     ImageUnderstanding
# )

# from ai.file_understanding import (
#     FileUnderstanding
# )

# from ai.multimodal_router import (
#     MultimodalRouter
# )

# from voice.voice_clone import (
#     NeuralTTS
# )


# class JaguarAssistant:
#     def __init__(self):
#         self.voice = SpeechEngine()
#         self.router = CommandRouter(self)
#         self.memory = ConversationMemory()
#         try:
#             self.chatgpt = ChatGPTClient()
#         except Exception:
#             self.chatgpt = None
#         self.local_llm = LocalLLM()
#         self.vision = VisionAI()
#         self.app_manager = AppManager()
#         self.browser = Browser()
#         self.files = FileManager()
#         self.system = SystemControl()
#         self.keyboard = KeyboardMouse()
#         self.clipboard = Clipboard()

#         self.plugins = PluginManager()
#         self.scheduler = TaskScheduler()
#         self.skills = SkillManager()
#         self.planner = PlannerAgent()
#         self.executor = ExecutorAgent()

#         self.pdf = PDFSummarizer()

#         self.document_qa = DocumentQA()

#         self.image_ai = None

#         self.files = FileUnderstanding()

#         self.multimodal = (
#             MultimodalRouter()
#         )

#         self.voice_clone = (
#             NeuralTTS()
#             # None
#         )

        



#     def speak(self, text):
#         self.voice.speak(text)

#     def listen(self):
#         return self.voice.listen()

#     def startup(self):
#         self.speak(
#             "Initializing Jaguar Artificial Intelligence."
#         )

#         self.speak(
#             "All systems are online."
#         )

#         self.speak(
#             "How can I help you today?"
#         )

#     def run(self):
#         self.startup()

#         while True:
#             command = self.listen()

#             if not command:
#                 continue

#             if is_wake_word(command):
#                 self.speak(
#                     "Yes, I am listening."
#                 )
#                 continue

#             self.router.execute(command)



#     def ask_ai(self, prompt):
#         history = self.memory.last_messages()

#         if (
#             self.chatgpt
#             and
#             self.chatgpt.available()
#         ):
#             try:
#                 return self.chatgpt.ask(history)
#             except Exception:
#                 pass

#         return self.local_llm.ask(prompt)















































import json
import os
import webbrowser
from rapidfuzz import process
from core.speaker import speak

class JaguarAssistant:
    def __init__(self):
        with open("memory/apps.json", "r") as f:
            self.apps = json.load(f)

    def clean_command(self, text):
        text = text.lower()

        words_to_remove = [
            "open",
            "launch",
            "start",
            "run",
            "please",
            "can you",
            "could you",
            "jaguar",
            "assistant"
        ]

        for word in words_to_remove:
            text = text.replace(word, "")

        return " ".join(text.split())

    

    def find_app(self, command):
        command = command.lower().strip()

        # aliases
        aliases = {
            "chrome": "google chrome",
            "edge": "microsoft edge",
            "vscode": "visual studio code",
            "vs code": "visual studio code",
            "cmd": "command prompt",
            "terminal": "command prompt",
            "explorer": "file explorer",
        }

        if command in aliases:
            command = aliases[command]

        # exact match
        if command in self.apps:
            return self.apps[command]

        # fuzzy match
        match = process.extractOne(command, self.apps.keys())

        if match:
            app_name, score, _ = match
            print(f"Matched '{command}' -> '{app_name}' ({score}%)")

            if score >= 70:
                return self.apps[app_name]

        return None

    def open_app(self, path):
        try:
            print("Opening:", path)   # debug
            os.startfile(path)
        except Exception as e:
            print("Failed to open app:", e)

    def handle_command(self, text):
        command = self.clean_command(text)

        print("Cleaned command:", command)

        if command == "test":
            self.open_app(r"C:\Windows\System32\notepad.exe")
            return "opened"

        if command == "youtube":
            speak("Opening YouTube")
            webbrowser.open("https://youtube.com")
            return "opened"

        if command == "github":
            speak("Opening github")
            webbrowser.open("https://github.com")
            return "opened"

        if command == "chatgpt":
            speak("Opening chatgpt")
            webbrowser.open("https://chat.openai.com")
            return "opened"

        if "exit" in command:
            speak("Goodbye")
            return "exit"

        path = self.find_app(command)

        print("Matched path:", path)

        if path:
            self.open_app(path)
            speak(f"Opening {command}")
            return "opened"

        speak("Sorry, I couldn't find that.")
        return "not found"