import asyncio
import edge_tts


class NeuralTTS:
    def __init__(
        self,
        voice="en-US-AriaNeural"
    ):
        self.voice = voice

    def speak(
        self,
        text,
        output_path="output.mp3"
    ):
        asyncio.run(
            self._generate(
                text,
                output_path
            )
        )

        return output_path

    async def _generate(
        self,
        text,
        output_path
    ):
        communicate = (
            edge_tts.Communicate(
                text=text,
                voice=self.voice
            )
        )

        await communicate.save(
            output_path
        )