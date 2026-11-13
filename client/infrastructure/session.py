import json
import os


class SessionStore:
    """Сохранённая сессия (UC-02, альтернативный поток: вход по сохранённой сессии)."""

    def __init__(self, directory):
        self.path = os.path.join(directory, "session.json")

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save(self, server, token):
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"server": server, "token": token}, f)
        except OSError:
            pass

    def clear_token(self):
        data = self.load()
        self.save(data.get("server", ""), "")
