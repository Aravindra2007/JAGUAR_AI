import random


class AudioLevel:

    def __init__(self):

        self.level = 0

    def get_level(self):

        return random.randint(0,100)