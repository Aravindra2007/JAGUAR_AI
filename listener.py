import threading
import time
import speech_recognition as sr

from router import CommandRouter
from speaker import speak, stop_speaking
import languages    
import state


class VoiceListener(threading.Thread):

    def __init__(self):
        super().__init__(daemon=True)

        self.router = CommandRouter()
        self.recognizer = sr.Recognizer()

        self.running = False
        self.stop_event = threading.Event()

    # -------------------------
    # Start Listening
    # -------------------------

    def start_listening(self):
        self.running = True
        state.set_status("Listening...")
        speak("Jaguar is online. How can I help you?",language=state.get_language())
        print("Voice Listener Started")

    # -------------------------
    # Stop Listening
    # -------------------------

    def stop_listening(self):
        # Interrupt anything Jaguar is currently saying FIRST, before
        # the mic loop even has a chance to queue up another response.
        # This is what makes the Stop button actually stop speech
        # instead of just muting future turns.
        stop_speaking()

        self.running = False
        state.set_status("Idle")
        speak("Stopping listening.", language=state.get_language())
        print("Voice Listener Stopped")

    # -------------------------
    # Shutdown Thread
    # -------------------------

    def shutdown(self):
        self.running = False
        self.stop_event.set()

    # -------------------------
    # Main Loop
    # -------------------------

    # def run(self):

    #     try:
    #         with sr.Microphone() as source:

    #             self.recognizer.adjust_for_ambient_noise(source, duration=1)

    #             print("Microphone Ready")

    #             while not self.stop_event.is_set():

    #                 if not self.running:
    #                     time.sleep(0.2)
    #                     continue

    #                 try:

    #                     state.set_status("Listening...")

    #                     audio = self.recognizer.listen(
    #                         source,
    #                         timeout=2,
    #                         phrase_time_limit=8
    #                     )

    #                     sr_code = languages.get_sr_code(state.get_language())
    #                     command = self.recognizer.recognize_google(audio, language=sr_code).lower()
                        
    #                     if not state.is_muted():
    #                         speak(response, language=state.get_language())
    #                     # command = self.recognizer.recognize_google(audio).lower()

    #                     print(f"User: {command}")
    #                     response = self.router.process(command)

    #                     # Optional voice command to stop listening
    #                     if command in [
    #                         "stop listening",
    #                         "go idle",
    #                         "sleep",
    #                         "stop"
    #                     ]:
    #                         self.stop_listening()
    #                         continue

    #                     state.set_status("Processing...")

    #                     response = self.router.process(command)

    #                     if not response:
    #                         response = "Done."

    #                     print(f"Jaguar: {response}")

    #                     state.set_text(response)
    #                     state.add_history(command, response)

    #                     if not state.is_muted():
    #                         speak(response)

    #                     state.set_status("Listening...")

    #                 except sr.WaitTimeoutError:
    #                     continue

    #                 except sr.UnknownValueError:
    #                     continue

    #                 except sr.RequestError:
    #                     print("Speech Recognition Offline")
    #                     state.set_status("Offline")
    #                     time.sleep(1)

    #                 except Exception as e:
    #                     print("Listener Error:", e)
    #                     state.set_status("Listening...")

    #     except OSError:
    #         print("No microphone found.")
    #         state.set_status("No Microphone")



    def run(self):

        try:
            with sr.Microphone() as source:

                self.recognizer.adjust_for_ambient_noise(source, duration=1)

                print("Microphone Ready")

                while not self.stop_event.is_set():

                    if not self.running:
                        time.sleep(0.2)
                        continue

                    try:

                        state.set_status("Listening...")

                        audio = self.recognizer.listen(
                            source,
                            timeout=2,
                            phrase_time_limit=8
                        )

                        sr_code = languages.get_sr_code(state.get_language())
                        command = self.recognizer.recognize_google(audio, language=sr_code).lower()

                        print(f"User: {command}")

                        # Optional voice command to stop listening
                        if command in [
                            "stop listening",
                            "go idle",
                            "sleep",
                            "stop"
                        ]:
                            self.stop_listening()
                            continue

                        state.set_status("Processing...")

                        response = self.router.process(command)

                        # --- Phase 1: tool-use confirmation ---
                        # If the router returned a confirmation envelope,
                        # speak the prompt, listen once for yes/no, then
                        # resolve via router.process_with_confirmation.
                        if isinstance(response, dict) and response.get("type") == "needs_confirmation":
                            envelope = response.get("envelope") or {}
                            prompt = envelope.get("prompt", "Confirm this action?")
                            token = envelope.get("token")

                            state.set_status("Awaiting confirmation...")
                            if not state.is_muted():
                                speak(prompt + " Say yes or no.", language=state.get_language())

                            yes_tokens = {"yes", "yeah", "yep", "sure", "confirm", "do it", "ok", "okay"}
                            no_tokens = {"no", "nope", "cancel", "don't", "dont", "stop"}
                            decision = None
                            try:
                                confirmation_audio = self.recognizer.listen(
                                    source,
                                    timeout=4,
                                    phrase_time_limit=3,
                                )
                                confirmation_sr = languages.get_sr_code(state.get_language())
                                confirmation_text = self.recognizer.recognize_google(
                                    confirmation_audio, language=confirmation_sr
                                ).lower()
                                tokens = set(confirmation_text.split())
                                if tokens & yes_tokens:
                                    decision = "yes"
                                elif tokens & no_tokens:
                                    decision = "no"
                            except (sr.WaitTimeoutError, sr.UnknownValueError, sr.RequestError):
                                decision = None
                            except Exception:
                                decision = None

                            try:
                                if decision == "yes":
                                    response = self.router.process_with_confirmation(token, "yes")
                                elif decision == "no":
                                    response = self.router.process_with_confirmation(token, "no")
                                else:
                                    # Default to denying if we can't parse
                                    # the user's answer - safer than running
                                    # an unconfirmed action.
                                    response = "Cancelled."
                            except Exception as e:
                                response = f"Sorry Sir, something went wrong running that action: {e}"

                            if not state.is_muted():
                                speak(response, language=state.get_language())

                            state.add_history(command, response)
                            state.set_text(response)
                            state.set_status("Listening...")
                            continue
                        # --- end confirmation branch ---

                        if not response:
                            response = "Done."

                        print(f"Jaguar: {response}")

                        state.set_text(response)
                        state.add_history(command, response)

                        if not state.is_muted():
                            speak(response, language=state.get_language())

                        state.set_status("Listening...")

                    except sr.WaitTimeoutError:
                        continue

                    except sr.UnknownValueError:
                        continue

                    except sr.RequestError:
                        print("Speech Recognition Offline")
                        state.set_status("Offline")
                        time.sleep(1)

                    except Exception as e:
                        print("Listener Error:", e)
                        state.set_status("Listening...")

        except OSError:
            print("No microphone found.")
            state.set_status("No Microphone")