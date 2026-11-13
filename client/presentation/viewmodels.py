"""Presentation: ViewModel'и (MVVM). Не зависят от Kivy: View подписывается через bind()
и перерисовывается по notify(). Сетевые вызовы идут через runner (в приложении — фоновый поток)."""
from ..domain.entities import AdFilter
from ..domain.errors import AppError, AuthError


def sync_runner(work, ok, fail):
    """Синхронный runner — для тестов."""
    try:
        result = work()
    except Exception as exc:  # noqa: BLE001
        fail(exc)
        return
    ok(result)


class Observable:
    def __init__(self):
        self._subscribers = []

    def bind(self, callback):
        self._subscribers.append(callback)

    def notify(self):
        for cb in list(self._subscribers):
            cb()


class ViewModel(Observable):
    on_auth_lost = None  # задаётся приложением: вернуть пользователя на экран входа

    def __init__(self, runner):
        super().__init__()
        self.runner = runner
        self.loading = False
        self.error = ""

    def run(self, work, on_ok=None, on_fail=None):
        self.loading, self.error = True, ""
        self.notify()

        def ok(result):
            self.loading = False
            if on_ok:
                on_ok(result)
            self.notify()

        def fail(exc):
            self.loading = False
            if isinstance(exc, AuthError):
                if ViewModel.on_auth_lost:
                    ViewModel.on_auth_lost()
                self.error = str(exc)
            else:
                self.error = str(exc) if isinstance(exc, AppError) else "Непредвиденная ошибка"
            if on_fail:
                on_fail(exc)
            self.notify()

        self.runner(work, ok, fail)


class AuthViewModel(ViewModel):
    def __init__(self, runner, auth):
        super().__init__(runner)
        self.auth = auth
        self.mode = "login"  # login | register
        self.locations = []
        self.user = None
        self.server = auth.saved_server()

    def toggle_mode(self):
        self.mode = "register" if self.mode == "login" else "login"
        self.error = ""
        self.notify()

    def restore(self):
        self.run(self.auth.restore, self._set_user)

    def load_locations(self, server):
        self.run(lambda: self.auth.locations(server), self._set_locations)

    def submit(self, server, name, password, location=""):
        self.server = server
        if self.mode == "register":
            work = lambda: self.auth.register(server, name, password, location)  # noqa: E731
        else:
            work = lambda: self.auth.login(server, name, password)  # noqa: E731
        self.run(work, self._set_user)

    def _set_user(self, user):
        self.user = user

    def _set_locations(self, tree):
        self.locations = tree


class SessionViewModel(ViewModel):
    """Текущий пользователь, выход и опрос уведомлений (замена push для MVP)."""

    def __init__(self, runner, auth, notifications):
        super().__init__(runner)
        self.auth, self.notifications = auth, notifications
        self.user = None
        self.new_notifications = []

    def logout(self, on_done=None):
        self.run(self.auth.logout, lambda _: on_done and on_done())

    def poll(self, on_new=None):
        # опрос не должен показывать «загрузку» или ошибки
        def ok(items):
            self.new_notifications = items
            if items and on_new:
                on_new(items)

        self.runner(self.notifications.execute, ok, lambda exc: self._poll_failed(exc))

    @staticmethod
    def _poll_failed(exc):
        if isinstance(exc, AuthError) and ViewModel.on_auth_lost:
            ViewModel.on_auth_lost()


class FeedViewModel(ViewModel):
    def __init__(self, runner, feed):
        super().__init__(runner)
        self.feed_uc = feed
        self.filter = AdFilter()
        self.ads = []

    def set_filter(self, **kw):
        for k, v in kw.items():
            setattr(self.filter, k, v)
        self.refresh()

    def refresh(self):
        flt = AdFilter(**vars(self.filter))
        self.run(lambda: self.feed_uc.feed(flt), self._set_ads)

    def _set_ads(self, ads):
        self.ads = ads


class CreateAdViewModel(ViewModel):
    def __init__(self, runner, create_ad):
        super().__init__(runner)
        self.create_ad = create_ad
        self.ad_type = "need"
        self.created = None

    def start(self, ad_type):
        self.ad_type, self.created, self.error = ad_type, None, ""
        self.notify()

    def publish(self, title, description, category, on_done=None):
        self.run(lambda: self.create_ad.execute(self.ad_type, title, description, category),
                 lambda ad: self._done(ad, on_done))

    def _done(self, ad, on_done):
        self.created = ad
        if on_done:
            on_done(ad)


class AdDetailViewModel(ViewModel):
    def __init__(self, runner, feed, respond, close, report, get_user):
        super().__init__(runner)
        self.feed_uc, self.respond_uc, self.close_uc, self.report_uc = feed, respond, close, report
        self.get_user = get_user
        self.ad = None
        self.info = ""

    @property
    def is_author(self):
        u = self.get_user()
        return bool(self.ad and u and self.ad.author_id == u.id)

    @property
    def can_respond(self):
        u = self.get_user()
        return bool(self.ad and u and self.ad.status == "open" and not self.is_author)

    def show(self, ad):
        """Показать уже загруженное объявление и освежить его с сервера (UC-11, исключение: объявление удалено)."""
        self.ad, self.info, self.error = ad, "", ""
        self.notify()
        self.run(lambda: self.feed_uc.get(ad.id), self._set)

    def _set(self, ad):
        self.ad = ad

    def respond(self, on_chat):
        self.run(lambda: self.respond_uc.execute(self.ad.id), on_chat)

    def solve(self):
        self.run(lambda: self.close_uc.solve(self.ad.id), self._set)

    def cancel(self):
        self.run(lambda: self.close_uc.cancel(self.ad.id), self._set)

    def report(self, reason):
        self.run(lambda: self.report_uc.execute(self.ad.id, reason),
                 lambda _: setattr(self, "info", "Жалоба отправлена модератору"))


class ChatListViewModel(ViewModel):
    def __init__(self, runner, chats):
        super().__init__(runner)
        self.chats_uc = chats
        self.chats = []

    def refresh(self):
        self.run(self.chats_uc.list, self._set)

    def _set(self, chats):
        self.chats = chats


class ChatViewModel(ViewModel):
    def __init__(self, runner, chats, send, get_user):
        super().__init__(runner)
        self.chats_uc, self.send_uc, self.get_user = chats, send, get_user
        self.chat = None
        self.messages = []

    @property
    def my_id(self):
        u = self.get_user()
        return u.id if u else 0

    def open(self, chat):
        self.chat, self.messages, self.error = chat, [], ""
        self.notify()
        self.refresh()

    def refresh(self, silent=False):
        if not self.chat:
            return
        chat_id, after = self.chat.id, self.messages[-1].id if self.messages else 0
        if silent:  # фоновое обновление без индикатора загрузки
            self.runner(lambda: self.chats_uc.history(chat_id, after), self._append_notify, lambda e: None)
        else:
            self.run(lambda: self.chats_uc.history(chat_id, after), self._append)

    def _append(self, new):
        known = {m.id for m in self.messages}
        self.messages.extend(m for m in new if m.id not in known)

    def _append_notify(self, new):
        before = len(self.messages)
        self._append(new)
        if len(self.messages) != before:
            self.notify()

    def send(self, text, on_sent=None):
        chat_id = self.chat.id
        self.run(lambda: self.send_uc.execute(chat_id, text),
                 lambda m: (self._append([m]), on_sent and on_sent()))


class ProfileViewModel(ViewModel):
    def __init__(self, runner, auth, feed, get_user, set_user):
        super().__init__(runner)
        self.auth, self.feed_uc, self.get_user, self.set_user = auth, feed, get_user, set_user
        self.my_ads = []
        self.status = ""
        self.info = ""

    def load_archive(self, status=None):
        if status is not None:
            self.status = status
        flt = self.status
        self.run(lambda: self.feed_uc.mine(flt), self._set_ads)

    def _set_ads(self, ads):
        self.my_ads = ads

    def save(self, name, location, notify):
        self.info = ""
        self.run(lambda: self.auth.update_profile(name, location, notify), self._saved)

    def _saved(self, user):
        self.set_user(user)
        self.info = "Профиль сохранён"


class ModerationViewModel(ViewModel):
    def __init__(self, runner, moderate):
        super().__init__(runner)
        self.moderate = moderate
        self.reports = []

    def refresh(self):
        self.run(self.moderate.reports, self._set)

    def _set(self, reports):
        self.reports = reports

    def delete_ad(self, report_id):
        self.run(lambda: self.moderate.delete_ad(report_id), lambda _: self.refresh())

    def reject(self, report_id):
        self.run(lambda: self.moderate.reject(report_id), lambda _: self.refresh())

    def block(self, user_id, blocked=True):
        self.run(lambda: self.moderate.block(user_id, blocked), lambda _: self.refresh())
