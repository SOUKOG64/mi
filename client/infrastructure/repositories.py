"""Infrastructure: реализации репозиториев поверх REST API (SAD 5.2: *RepositoryImpl)."""
from ..domain import repositories as repo
from ..domain.entities import Ad, Chat, Message, Notification, Report, User
from ..domain.errors import AuthError


def _user(d):
    return User(d["id"], d["name"], d["role"], d["location"], d.get("notify", True), d.get("blocked", False))


def _ad(d):
    return Ad(d["id"], d["type"], d["title"], d["description"], d["category"], d["status"], d["location"],
              d["author_id"], d["author_name"], d["created"], d.get("my_chat_id"))


def _chat(d):
    return Chat(d["id"], d["ad_id"], d["ad_title"], d["partner_name"], d.get("last_text", ""))


def _message(d):
    return Message(d["id"], d["chat_id"], d["sender_id"], d["sender_name"], d["text"], d["created"])


class UserRepositoryImpl(repo.UserRepository):
    def __init__(self, net, store):
        self.net, self.store = net, store

    def locations(self, server):
        return self.net.request("GET", "/locations", base_url=server, auth=False)["tree"]

    def _enter(self, server, data):
        self.net.configure(server, data["token"])
        self.store.save(server, data["token"])
        return _user(data["user"])

    def register(self, server, name, password, location):
        self.net.configure(server)
        return self._enter(server, self.net.request(
            "POST", "/register", {"name": name, "password": password, "location": location}))

    def login(self, server, name, password):
        self.net.configure(server)
        return self._enter(server, self.net.request("POST", "/login", {"name": name, "password": password}))

    def saved_server(self):
        return self.store.load().get("server", "")

    def restore(self):
        data = self.store.load()
        if not data.get("token") or not data.get("server"):
            return None
        self.net.configure(data["server"], data["token"])
        try:
            return _user(self.net.request("GET", "/me")["user"])
        except AuthError:
            self.store.clear_token()
            self.net.configure(data["server"])
            return None

    def logout(self):
        try:
            self.net.request("POST", "/logout")
        except Exception:
            pass  # локальный выход выполняем в любом случае
        self.store.clear_token()
        self.net.configure(self.net.base_url)

    def update_profile(self, name, location, notify):
        return _user(self.net.request("PUT", "/me", {"name": name, "location": location, "notify": notify})["user"])


class AdRepositoryImpl(repo.AdRepository):
    def __init__(self, net):
        self.net = net

    def feed(self, flt):
        params = {"level": flt.level, "type": flt.type, "category": flt.category, "q": flt.query}
        return [_ad(a) for a in self.net.request("GET", "/ads", params={k: v for k, v in params.items() if v != ""})["ads"]]

    def get(self, ad_id):
        return _ad(self.net.request("GET", f"/ads/{ad_id}")["ad"])

    def create(self, ad_type, title, description, category):
        return _ad(self.net.request("POST", "/ads", {
            "type": ad_type, "title": title, "description": description, "category": category})["ad"])

    def set_status(self, ad_id, status):
        return _ad(self.net.request("POST", f"/ads/{ad_id}/status", {"status": status})["ad"])

    def mine(self, status):
        params = {"status": status} if status else None
        return [_ad(a) for a in self.net.request("GET", "/my/ads", params=params)["ads"]]

    def report(self, ad_id, reason):
        self.net.request("POST", f"/ads/{ad_id}/report", {"reason": reason})

    def respond(self, ad_id):
        return _chat(self.net.request("POST", f"/ads/{ad_id}/respond")["chat"])


class ChatRepositoryImpl(repo.ChatRepository):
    def __init__(self, net):
        self.net = net

    def chats(self):
        return [_chat(c) for c in self.net.request("GET", "/chats")["chats"]]

    def messages(self, chat_id, after):
        params = {"after": after} if after else None
        return [_message(m) for m in self.net.request("GET", f"/chats/{chat_id}/messages", params=params)["messages"]]

    def send(self, chat_id, text):
        return _message(self.net.request("POST", f"/chats/{chat_id}/messages", {"text": text})["message"])


class ModerationRepositoryImpl(repo.ModerationRepository):
    def __init__(self, net):
        self.net = net

    def reports(self):
        out = []
        for r in self.net.request("GET", "/reports")["reports"]:
            a = r["ad"]
            out.append(Report(r["id"], r["reason"], r["created"], r["reporter_name"], a["id"], a["title"],
                              a["description"], a["author_id"], a["author_name"], a["author_blocked"]))
        return out

    def resolve(self, report_id, action):
        self.net.request("POST", f"/reports/{report_id}/resolve", {"action": action})

    def block(self, user_id, blocked):
        self.net.request("POST", f"/users/{user_id}/block", {"blocked": blocked})


class NotificationRepositoryImpl(repo.NotificationRepository):
    """Push-замена для MVP: клиент опрашивает сервер (PushService из SAD требует FCM/APNs)."""

    def __init__(self, net):
        self.net = net

    def poll(self):
        return [Notification(n["id"], n["kind"], n["text"], n.get("ref_id"))
                for n in self.net.request("POST", "/notifications/poll")["notifications"]]
