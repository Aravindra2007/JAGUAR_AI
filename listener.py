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
        self._restart_microphone = threading.Event()
        self._source_lock = threading.RLock()
        self._source = None

    # -------------------------
    # Start Listening
    # -------------------------

    def start_listening(self):
        with self._source_lock:
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

        with self._source_lock:
            self.running = False
            self._restart_microphone.set()
            self._interrupt_microphone()
        state.set_status("Idle")
        speak("Stopping listening.", language=state.get_language())
        print("Voice Listener Stopped")

    def _interrupt_microphone(self):
        with self._source_lock:
            source = self._source
            if source is None:
                return

            stream = getattr(source.stream, "pyaudio_stream", None)
            if stream is None:
                return

            try:
                if not stream.is_stopped():
                    stream.stop_stream()
            except Exception as e:
                print("Could not interrupt microphone capture:", e)

    # -------------------------
    # Shutdown Thread
    # -------------------------

    def shutdown(self):
        with self._source_lock:
            self.running = False
            self.stop_event.set()
            self._restart_microphone.set()
            self._interrupt_microphone()

    # -------------------------
    # Main Loop
    # -------------------------
    def run(self):
        while not self.stop_event.is_set():
            if not self.running:
                self.stop_event.wait(0.2)
                continue

            with self._source_lock:
                if not self.running:
                    continue
                self._restart_microphone.clear()
            try:
                with sr.Microphone() as source:
                    with self._source_lock:
                        self._source = source

                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
                    print("Microphone Ready")

                    while self.running and not self.stop_event.is_set():
                        if self._restart_microphone.is_set():
                            break

                        try:
                            state.set_status("Listening...")

                            audio = self.recognizer.listen(
                                source,
                                timeout=2,
                                phrase_time_limit=8
                            )

                            sr_code = languages.get_sr_code(state.get_language())
                            command = self.recognizer.recognize_google(audio, language=sr_code).lower()

                            if self._restart_microphone.is_set() or not self.running:
                                break

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

                            # A multi-step plan may need approval more than once.
                            if isinstance(response, dict) and response.get("type") == "needs_confirmation":
                                yes_tokens = {"yes", "yeah", "yep", "sure", "confirm", "do it", "ok", "okay"}
                                no_tokens = {"no", "nope", "cancel", "don't", "dont", "stop"}
                                while isinstance(response, dict) and response.get("type") == "needs_confirmation":
                                    if self._restart_microphone.is_set() or not self.running:
                                        break

                                    envelope = response.get("envelope") or {}
                                    prompt = envelope.get("prompt", "Confirm this action?")
                                    token = envelope.get("token")

                                    state.set_status("Awaiting confirmation...")
                                    if not state.is_muted():
                                        speak(prompt + " Say yes or no.", language=state.get_language())

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
                                    except OSError:
                                        if self._restart_microphone.is_set() or not self.running:
                                            break
                                        raise
                                    except Exception:
                                        if self._restart_microphone.is_set() or not self.running:
                                            break
                                        decision = None

                                    if self._restart_microphone.is_set() or not self.running:
                                        break

                                    try:
                                        response = self.router.process_with_confirmation(
                                            token,
                                            decision or "no",
                                        )
                                    except Exception as e:
                                        response = f"Sorry Sir, something went wrong running that action: {e}"

                                if self._restart_microphone.is_set() or not self.running:
                                    break

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

                        except OSError:
                            if self._restart_microphone.is_set() or not self.running:
                                break
                            raise

                        except Exception as e:
                            if self._restart_microphone.is_set() or not self.running:
                                break
                            print("Listener Error:", e)
                            state.set_status("Listening...")

            except Exception as e:
                if self.stop_event.is_set():
                    break
                if self.running:
                    print("Microphone unavailable:", e)
                    state.set_status("No Microphone")
                    time.sleep(1)
            finally:
                with self._source_lock:
                    self._source = None