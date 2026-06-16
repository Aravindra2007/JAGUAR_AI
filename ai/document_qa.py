import fitz


class DocumentQA:
    def ask(
        self,
        path,
        question,
        assistant
    ):
        document = fitz.open(path)

        text = ""

        for page in document:
            text += page.get_text()

        prompt = f"""
        Document:

        {text[:12000]}

        Question:

        {question}
        """

        return assistant.ask_ai(
            prompt
        )