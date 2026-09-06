# core/personality.py

from config import DEFAULT_MODE

class Personality:
    def __init__(self):
        self.mode = DEFAULT_MODE

    def build_prompt(self):
        if self.mode == "friend":
            return "Talk like a chill best friend."
        elif self.mode == "brother":
            return "Talk like a protective older brother."
        elif self.mode == "assistant":
            return "Be precise and helpful."
        elif self.mode == "companion":
            return "Be emotionally supportive."
        return ""
