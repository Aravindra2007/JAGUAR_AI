WAKE_WORDS = [
    "jaguar",
    "hey jaguar",
    "ok jaguar",
    "wake up jaguar"
]


def is_wake_word(text):
    text = text.lower()

    for word in WAKE_WORDS:
        if word in text:
            return True

    return False