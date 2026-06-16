import fitz


class PDFSummarizer:
    def extract_text(self, path):
        document = fitz.open(path)

        text = ""

        for page in document:
            text += page.get_text()

        return text

    def summarize(
        self,
        path,
        assistant
    ):
        text = self.extract_text(path)

        prompt = f"""
        Summarize this document:

        {text[:10000]}
        """

        return assistant.ask_ai(
            prompt
        )