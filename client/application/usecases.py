"""Application: сценарии (SAD 5.2). Не зависят от UI, ходят в репозитории Domain."""
from ..domain.entities import AD_TYPES, CATEGORIES, REPORT_REASONS, AdFilter
from ..domain.errors import ValidationError


class AuthUseCases:
    def __init__(self, users):
        self.users = users

    def locations(self, server):
        return self.users.locations(self._server(server))

    def register(self, server, name, password, location):
        name = (name or "").strip()
        if len(name) < 2:
            raise ValidationError("Введите имя (не менее 2 символов)")
        if len(password or "") < 4:
            raise ValidationError("Пароль: не менее 4 символов")
        if not location or "/" not in location:
            raise ValidationError("Укажите локацию (минимум до дома)")
        return self.users.register(self._server(server), name, password, location)

    def login(self, server, name, password):
        if not (name or "").strip() or not password:
            raise ValidationError("Введите имя и пароль")
        return self.users.login(self._server(server), name.strip(), password)

    def restore(self):
        return self.users.restore()

    def saved_server(self):
        return self.users.saved_server()

    def logout(self):
        return self.users.logout()

    def update_profile(self, name, location, notify):
        name = (name or "").strip()
        if len(name) < 2:
            raise ValidationError("Введите имя (не менее 2 символов)")
        if not location or "/" not in location:
            raise ValidationError("Укажите локацию (минимум до дома)")
        return self.users.update_profile(name, location, bool(notify))

    @staticmethod
    def _server(server):
        server = (server or "").strip().rstrip("/")
        if not server:
            raise ValidationError("Укажите адрес сервера")
        if not server.startswith(("http://", "https://")):
            server = "http://" + server
        return server


class CreateAdUseCase:
    def __init__(self, ads):
        self.ads = ads

    def execute(self, ad_type, title, description, category):
        if ad_type not in AD_TYPES:
            raise ValidationError("Неизвестный тип объявления")
        title, description = (title or "").strip(), (description or "").strip()
        if len(title) < 3:
            raise ValidationError("Введите заголовок (не менее 3 символов)")
        if not description:
            raise ValidationError("Введите текст объявления")
        if category not in CATEGORIES:
            raise ValidationError("Выберите категорию")
        return self.ads.create(ad_type, title, description, category)


class FeedUseCases:
    def __init__(self, ads):
        self.ads = ads

    def feed(self, flt: AdFilter):
        return self.ads.feed(flt)

    def get(self, ad_id):
        return self.ads.get(ad_id)

    def mine(self, status=""):
        return self.ads.mine(status)


class RespondToAdUseCase:
    def __init__(self, ads):
        self.ads = ads

    def execute(self, ad_id):
        return self.ads.respond(ad_id)


class CloseAdUseCase:
    def __init__(self, ads):
        self.ads = ads

    def solve(self, ad_id):
        return self.ads.set_status(ad_id, "solved")

    def cancel(self, ad_id):
        return self.ads.set_status(ad_id, "cancelled")


class ReportAdUseCase:
    def __init__(self, ads):
        self.ads = ads

    def execute(self, ad_id, reason):
        if reason not in REPORT_REASONS:
            raise ValidationError("Выберите причину жалобы")
        return self.ads.report(ad_id, reason)


class ChatUseCases:
    def __init__(self, chats):
        self.chats = chats

    def list(self):
        return self.chats.chats()

    def history(self, chat_id, after=0):
        return self.chats.messages(chat_id, after)


class SendMessageUseCase:
    def __init__(self, chats):
        self.chats = chats

    def execute(self, chat_id, text):
        text = (text or "").strip()
        if not text:
            raise ValidationError("Введите сообщение")
        if len(text) > 1000:
            raise ValidationError("Сообщение слишком длинное (максимум 1000 символов)")
        return self.chats.send(chat_id, text)


class ModerateAdUseCase:
    def __init__(self, moderation):
        self.moderation = moderation

    def reports(self):
        return self.moderation.reports()

    def delete_ad(self, report_id):
        return self.moderation.resolve(report_id, "delete")

    def reject(self, report_id):
        return self.moderation.resolve(report_id, "reject")

    def block(self, user_id, blocked=True):
        return self.moderation.block(user_id, blocked)


class PollNotificationsUseCase:
    def __init__(self, notifications):
        self.notifications = notifications

    def execute(self):
        return self.notifications.poll()
