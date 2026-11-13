"""Корень приложения: сборка слоёв (DI), навигация, фоновый опрос уведомлений."""
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.utils import platform

from .di import build_container
from .presentation import viewmodels as vm
from .presentation.views import (AuthScreen, ChatScreen, CreateScreen, DetailScreen, MainScreen)
from .presentation.widgets import BG

POLL_SECONDS = 5


def kivy_runner(work, ok, fail):
    """Сетевые вызовы — в фоновом потоке, результат — в главном потоке Kivy."""
    def target():
        try:
            result = work()
        except Exception as exc:  # noqa: BLE001
            Clock.schedule_once(lambda _dt, e=exc: fail(e), 0)
            return
        Clock.schedule_once(lambda _dt, r=result: ok(r), 0)

    threading.Thread(target=target, daemon=True).start()


class TeaGuardianApp(App):
    title = "Соседская помощь"

    def build(self):
        Window.clearcolor = BG
        self.user = None
        c = self.container = build_container(self.user_data_dir)
        r, get_user = kivy_runner, (lambda: self.user)

        self.auth_vm = vm.AuthViewModel(r, c.auth)
        self.session_vm = vm.SessionViewModel(r, c.auth, c.notifications)
        self.feed_vm = vm.FeedViewModel(r, c.feed)
        self.create_vm = vm.CreateAdViewModel(r, c.create_ad)
        self.detail_vm = vm.AdDetailViewModel(r, c.feed, c.respond, c.close, c.report, get_user)
        self.chat_list_vm = vm.ChatListViewModel(r, c.chats)
        self.chat_vm = vm.ChatViewModel(r, c.chats, c.send, get_user)
        self.profile_vm = vm.ProfileViewModel(r, c.auth, c.feed, get_user, self._set_user)
        self.moderation_vm = vm.ModerationViewModel(r, c.moderate)
        vm.ViewModel.on_auth_lost = self.on_auth_lost

        # 10.0.2.2 — адрес компьютера-хоста из эмулятора Android; на телефоне введите IP сервера в сети
        default_server = "http://10.0.2.2:8000" if platform == "android" else "http://127.0.0.1:8000"
        self.sm = ScreenManager(transition=SlideTransition(duration=0.15))
        self.sm.add_widget(AuthScreen(self, default_server))
        self.main_screen = MainScreen(self)
        self.sm.add_widget(self.main_screen)
        self.detail_screen = DetailScreen(self)
        self.sm.add_widget(self.detail_screen)
        self.create_screen = CreateScreen(self)
        self.sm.add_widget(self.create_screen)
        self.sm.add_widget(ChatScreen(self))
        Window.bind(on_keyboard=self._on_keyboard)
        return self.sm

    def on_start(self):
        self.auth_vm.restore()
        Clock.schedule_interval(self._tick, POLL_SECONDS)

    # ------------------------------------------------------------ состояние
    def _set_user(self, user):
        self.user = user
        self.profile_vm.notify()

    def enter(self, user):
        self.user = user
        self.feed_vm.filter.level = 2
        self._go("main", "left")

    def logout(self):
        self.session_vm.logout(self._after_logout)

    def on_auth_lost(self):
        if self.user is not None:
            self._after_logout()
            self.auth_vm.error = "Сессия истекла. Войдите снова."
            self.auth_vm.notify()

    def _after_logout(self):
        self.user = None
        self.auth_vm.user = None
        self.auth_vm.error = ""
        self.auth_vm.mode = "login"
        self.auth_vm.notify()
        self._go("auth", "right")

    # ------------------------------------------------------------ навигация
    def _go(self, name, direction):
        self.sm.transition.direction = direction
        self.sm.current = name

    def go_main(self, *_):
        self._go("main", "right")

    def open_ad(self, ad):
        self.detail_vm.show(ad)
        self._go("detail", "left")

    def open_create(self, ad_type):
        self.create_screen.prepare(ad_type)
        self._go("create", "left")

    def open_chat(self, chat):
        self.chat_vm.open(chat)
        self._go("chat", "left")

    def _on_keyboard(self, _window, key, *_args):
        if key != 27:  # кнопка «Назад» Android / Esc
            return False
        if self.sm.current in ("detail", "create", "chat"):
            self.go_main()
            return True
        if self.sm.current == "main" and self.main_screen.tab != "feed":
            self.main_screen.show_tab("feed")
            return True
        return False

    # ------------------------------------------------------------ уведомления
    def _tick(self, _dt):
        if self.user is not None:
            self.session_vm.poll(self._on_notifications)

    def _on_notifications(self, items):
        if self.sm.current == "main":
            self.main_screen.show_note(items[-1].text)
            self.main_screen.refresh_active()
        elif self.sm.current == "chat":
            self.chat_vm.refresh(silent=True)
