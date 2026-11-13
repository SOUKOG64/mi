"""Presentation: экраны (View). Только отображение и передача действий в ViewModel."""
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.switch import Switch
from kivy.uix.widget import Widget

from ..domain.entities import (AD_TYPES, CATEGORIES, LEVELS, REPORT_REASONS, STATUS_LABELS, Chat)
from .widgets import (ACCENT, DANGER, MINE, MUTED, PRIMARY, Bar, Btn, Card, Choice, Field, Lbl, LocationPicker,
                      TapCard, VList, choose, confirm)

TYPE_COLORS = {"need": PRIMARY, "offer": ACCENT}
ALL_TYPES, ALL_CATS = "Все типы", "Все категории"
TYPE_BY_LABEL = {"Прошу помощь": "need", "Могу помочь": "offer"}
STATUS_FILTER = [("Все", ""), ("Открыто", "open"), ("Решено", "solved"), ("Отменено", "cancelled"),
                 ("Удалено модератором", "removed")]


def short_date(value):
    return (value or "")[:16]


def place(location):
    return (location or "").replace("/", " / ")


def status_lbl(vm):
    """Строка состояния ViewModel: загрузка / ошибка."""
    if vm.loading:
        return "Подождите…", MUTED
    return vm.error, DANGER


def ad_card(ad, on_tap):
    card = TapCard()
    card.bind(on_release=lambda *_: on_tap(ad))
    tag = AD_TYPES.get(ad.type, ad.type)
    if ad.status != "open":
        tag += f" · {STATUS_LABELS.get(ad.status, ad.status)}"
    card.add_widget(Lbl(tag, size=12, color=TYPE_COLORS.get(ad.type, MUTED), bold=True))
    card.add_widget(Lbl(ad.title, size=17, bold=True))
    text = ad.description if len(ad.description) <= 110 else ad.description[:107] + "…"
    card.add_widget(Lbl(text, size=14))
    card.add_widget(Lbl(f"{ad.category} · {ad.author_name} · {short_date(ad.created)}", size=12, color=MUTED))
    card.add_widget(Lbl(place(ad.location), size=12, color=MUTED))
    return card


# ===================================================================== вход / регистрация
class AuthScreen(Screen):
    def __init__(self, app, default_server, **kw):
        super().__init__(name="auth", **kw)
        self.app, self.vm = app, app.auth_vm
        root = BoxLayout(orientation="vertical")
        root.add_widget(Bar("Соседская помощь"))
        self.list = VList()
        root.add_widget(self.list)
        self.add_widget(root)
        self.server = Field("Адрес сервера", text=self.vm.server or default_server)
        self.name_field = Field("Имя (как вас видят соседи)")
        self.password = Field("Пароль (не менее 4 символов)", password=True)
        self.picker = LocationPicker()
        self.reload_btn = Btn("Обновить список локаций", self._reload_locations, kind="light")
        self.status = Lbl("", color=DANGER)
        self.submit = Btn("Войти", self._submit)
        self.toggle = Btn("Нет аккаунта? Зарегистрироваться", lambda: self.vm.toggle_mode(), kind="light")
        self._built_mode, self._tree, self._tried = None, None, False
        self.vm.bind(self.render)
        self.render()

    def _reload_locations(self):
        self._tried = True
        self.vm.load_locations(self.server.text)

    def _submit(self):
        reg = self.vm.mode == "register"
        self.vm.submit(self.server.text, self.name_field.text, self.password.text, self.picker.value if reg else "")

    def render(self):
        reg = self.vm.mode == "register"
        if self._built_mode != self.vm.mode:
            self._built_mode = self.vm.mode
            items = [Lbl("Просьбы и предложения помощи в вашем доме", color=MUTED), self.server, self.name_field,
                     self.password]
            if reg:
                items += [Lbl("Ваша локация (дом обязателен)", color=MUTED), self.picker, self.reload_btn]
            items += [self.status, self.submit, self.toggle]
            self.list.set_items(items)
        self.submit.text = "Зарегистрироваться" if reg else "Войти"
        self.toggle.text = "Уже есть аккаунт? Войти" if reg else "Нет аккаунта? Зарегистрироваться"
        self.submit.disabled = self.vm.loading
        self.status.text, self.status.color = status_lbl(self.vm)
        if self.vm.locations is not self._tree:
            self._tree = self.vm.locations
            self.picker.set_tree(self._tree, "")
        if reg and not self.vm.locations and not self.vm.loading and not self._tried:
            self._tried = True
            self.vm.load_locations(self.server.text)
        if self.vm.user is not None and self.app.user is None and not self.vm.loading:
            self.password.text = ""
            self.app.enter(self.vm.user)


# ===================================================================== лента
class FeedPanel(BoxLayout):
    def __init__(self, app, **kw):
        super().__init__(orientation="vertical", **kw)
        self.app, self.vm, self._busy = app, app.feed_vm, False
        head = BoxLayout(orientation="vertical", size_hint_y=None, padding=dp(8), spacing=dp(6))
        head.bind(minimum_height=head.setter("height"))
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        row.add_widget(Btn("Прошу помощь", lambda: app.open_create("need")))
        row.add_widget(Btn("Могу помочь", lambda: app.open_create("offer"), kind="accent"))
        head.add_widget(row)
        row2 = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        self.level = Choice(["Дом"], height=dp(40))
        self.type = Choice([ALL_TYPES] + list(TYPE_BY_LABEL), height=dp(40))
        self.cat = Choice([ALL_CATS] + CATEGORIES, height=dp(40))
        for s in (self.level, self.type, self.cat):
            s.bind(text=self._changed)
            row2.add_widget(s)
        head.add_widget(row2)
        row3 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.query = Field("Поиск по заголовку и описанию", height=dp(44))
        self.query.bind(on_text_validate=lambda *_: self._search())
        row3.add_widget(self.query)
        row3.add_widget(Btn("Найти", self._search, size_hint_x=None, width=dp(80), height=dp(44)))
        head.add_widget(row3)
        self.status = Lbl("", size=13, color=DANGER)
        head.add_widget(self.status)
        self.add_widget(head)
        self.list = VList()
        self.add_widget(self.list)
        self.vm.bind(self.render)

    def _search(self):
        self.vm.set_filter(query=self.query.text.strip())

    def _changed(self, *_):
        if self._busy:
            return
        level = {v: k for k, v in LEVELS.items()}.get(self.level.text, 2)
        self.vm.set_filter(level=level, type=TYPE_BY_LABEL.get(self.type.text, ""),
                           category="" if self.cat.text == ALL_CATS else self.cat.text)

    def on_show(self):
        depth = max(1, min(4, len(self.app.user.location.split("/"))))
        values = [LEVELS[i] for i in range(1, depth + 1)]
        self._busy = True
        if self.vm.filter.level > depth:
            self.vm.filter.level = depth
        self.level.values = values
        self.level.text = LEVELS[self.vm.filter.level]
        self._busy = False
        self.vm.refresh()

    def render(self):
        self.status.text, self.status.color = status_lbl(self.vm)
        empty = "" if (self.vm.loading or self.vm.error) else "Объявлений нет. Создайте первое!"
        self.list.set_items([ad_card(a, self.app.open_ad) for a in self.vm.ads], empty)


# ===================================================================== чаты
class ChatsPanel(BoxLayout):
    def __init__(self, app, **kw):
        super().__init__(orientation="vertical", **kw)
        self.app, self.vm = app, app.chat_list_vm
        self.status = Lbl("", size=13, color=DANGER, padding=(dp(8), 0))
        self.add_widget(self.status)
        self.list = VList()
        self.add_widget(self.list)
        self.vm.bind(self.render)

    def on_show(self):
        self.vm.refresh()

    def render(self):
        self.status.text, self.status.color = status_lbl(self.vm)
        cards = []
        for chat in self.vm.chats:
            card = TapCard()
            card.bind(on_release=lambda _w, c=chat: self.app.open_chat(c))
            card.add_widget(Lbl(chat.ad_title, size=16, bold=True))
            card.add_widget(Lbl(f"Собеседник: {chat.partner_name}", size=13, color=MUTED))
            if chat.last_text:
                card.add_widget(Lbl(chat.last_text[:80], size=14))
            cards.append(card)
        empty = "" if (self.vm.loading or self.vm.error) else "Чатов пока нет. Откликнитесь на объявление."
        self.list.set_items(cards, empty)


# ===================================================================== профиль и архив
class ProfilePanel(BoxLayout):
    def __init__(self, app, **kw):
        super().__init__(orientation="vertical", **kw)
        self.app, self.vm, self._tree = app, app.profile_vm, None
        self.list = VList()
        self.add_widget(self.list)
        self.info = Card()
        self.name_field = Field("Контактное имя")
        self.picker = LocationPicker()
        self.notify_switch = Switch(active=True, size_hint_x=None, width=dp(90))
        notify_row = BoxLayout(size_hint_y=None, height=dp(44))
        notify_row.add_widget(Lbl("Уведомления", size_hint_y=1))
        notify_row.add_widget(self.notify_switch)
        self.msg = Lbl("", size=13, color=DANGER)
        self.status_choice = Choice([label for label, _ in STATUS_FILTER])
        self.status_choice.bind(text=self._status_changed)
        self.archive = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        self.archive.bind(minimum_height=self.archive.setter("height"))
        self.list.set_items([
            self.info, Lbl("Редактирование профиля", size=16, bold=True), self.name_field, self.picker, notify_row,
            Btn("Сохранить", self._save), self.msg,
            Lbl("Мои объявления", size=16, bold=True), self.status_choice, self.archive,
            Btn("Выйти из аккаунта", lambda: app.logout(), kind="danger"),
        ])
        self.vm.bind(self.render)
        app.auth_vm.bind(self._tree_changed)

    def _save(self):
        self.vm.save(self.name_field.text, self.picker.value, self.notify_switch.active)

    def _status_changed(self, *_):
        value = dict(STATUS_FILTER).get(self.status_choice.text, "")
        if self.app.user and value != self.vm.status:
            self.vm.load_archive(value)

    def _tree_changed(self):
        tree = self.app.auth_vm.locations
        if self.app.user and tree and tree is not self._tree:
            self._tree = tree
            self.picker.set_tree(tree, self.app.user.location)

    def on_show(self):
        user = self.app.user
        self.name_field.text = user.name
        self.notify_switch.active = user.notify
        self.picker.set_value(user.location)
        if not self.app.auth_vm.locations and not self.app.auth_vm.loading:
            self.app.auth_vm.load_locations(self.app.auth_vm.server)
        else:
            self._tree_changed()
        self.vm.info = ""
        self.vm.load_archive()

    def render(self):
        user = self.app.user
        if user:
            self.info.clear_widgets()
            self.info.add_widget(Lbl(user.name, size=18, bold=True))
            role = "Модератор" if user.is_moderator else "Житель"
            self.info.add_widget(Lbl(f"{role}{' · заблокирован' if user.blocked else ''}", size=13, color=MUTED))
            self.info.add_widget(Lbl(place(user.location), size=14))
        text, color = status_lbl(self.vm)
        self.msg.text, self.msg.color = (text, color) if text else (self.vm.info, PRIMARY)
        self.archive.clear_widgets()
        if not self.vm.my_ads and not self.vm.loading:
            self.archive.add_widget(Lbl("Пока пусто", color=MUTED))
        for ad in self.vm.my_ads:
            self.archive.add_widget(ad_card(ad, self.app.open_ad))


# ===================================================================== модерация
class ModerationPanel(BoxLayout):
    def __init__(self, app, **kw):
        super().__init__(orientation="vertical", **kw)
        self.app, self.vm = app, app.moderation_vm
        self.status = Lbl("", size=13, color=DANGER, padding=(dp(8), 0))
        self.add_widget(self.status)
        self.list = VList()
        self.add_widget(self.list)
        self.vm.bind(self.render)

    def on_show(self):
        self.vm.refresh()

    def render(self):
        self.status.text, self.status.color = status_lbl(self.vm)
        cards = []
        for r in self.vm.reports:
            card = Card()
            card.add_widget(Lbl(f"Жалоба: {r.reason}", size=12, color=DANGER, bold=True))
            card.add_widget(Lbl(r.ad_title, size=16, bold=True))
            card.add_widget(Lbl(r.ad_description[:200], size=14))
            card.add_widget(Lbl(f"Автор: {r.author_name} · жалоба от {r.reporter_name} · {short_date(r.created)}",
                                size=12, color=MUTED))
            card.add_widget(Btn("Удалить объявление", lambda rid=r.id: confirm(
                "Удалить объявление? Автор получит уведомление.", lambda: self.vm.delete_ad(rid)), kind="danger"))
            card.add_widget(Btn("Отклонить жалобу", lambda rid=r.id: self.vm.reject(rid), kind="light"))
            if r.author_blocked:
                card.add_widget(Btn("Снять блокировку с автора",
                                    lambda uid=r.author_id: self.vm.block(uid, False), kind="light"))
            else:
                card.add_widget(Btn("Заблокировать автора", lambda uid=r.author_id, n=r.author_name: confirm(
                    f"Заблокировать пользователя {n}? Он не сможет публиковать объявления.",
                    lambda: self.vm.block(uid, True)), kind="accent"))
            cards.append(card)
        empty = "" if (self.vm.loading or self.vm.error) else "Новых жалоб нет"
        self.list.set_items(cards, empty)


# ===================================================================== главный экран
class MainScreen(Screen):
    TITLES = {"feed": "Лента", "chats": "Чаты", "profile": "Профиль", "moderation": "Модерация"}

    def __init__(self, app, **kw):
        super().__init__(name="main", **kw)
        self.app, self.tab = app, "feed"
        self.panels = {"feed": FeedPanel(app), "chats": ChatsPanel(app), "profile": ProfilePanel(app),
                       "moderation": ModerationPanel(app)}
        root = BoxLayout(orientation="vertical")
        self.bar = Bar("Лента")
        root.add_widget(self.bar)
        self.note = Btn("", self._hide_note, kind="accent", height=0, opacity=0)
        root.add_widget(self.note)
        self.content = BoxLayout()
        root.add_widget(self.content)
        self.nav = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(2))
        root.add_widget(self.nav)
        self.add_widget(root)
        self._hide_ev = None

    def tabs(self):
        base = ["feed", "chats", "profile"]
        return base + ["moderation"] if self.app.user and self.app.user.is_moderator else base

    def on_pre_enter(self, *_):
        if self.tab not in self.tabs():
            self.tab = "feed"
        self.show_tab(self.tab)

    def show_tab(self, name):
        self.tab = name
        self.bar.title.text = self.TITLES[name]
        self.content.clear_widgets()
        self.content.add_widget(self.panels[name])
        self.nav.clear_widgets()
        for t in self.tabs():
            self.nav.add_widget(Btn(self.TITLES[t], lambda tt=t: self.show_tab(tt),
                                    kind="primary" if t == name else "light", height=dp(52)))
        self.panels[name].on_show()

    def refresh_active(self):
        if self.tab in ("feed", "chats", "moderation"):
            self.panels[self.tab].on_show()

    def show_note(self, text):
        self.note.text = text[:90]
        self.note.height, self.note.opacity = dp(40), 1
        if self._hide_ev:
            self._hide_ev.cancel()
        self._hide_ev = Clock.schedule_once(lambda _dt: self._hide_note(), 6)

    def _hide_note(self):
        self.note.height, self.note.opacity = 0, 0


# ===================================================================== карточка объявления
class DetailScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="detail", **kw)
        self.app, self.vm = app, app.detail_vm
        root = BoxLayout(orientation="vertical")
        root.add_widget(Bar("Объявление", on_back=app.go_main))
        self.list = VList()
        root.add_widget(self.list)
        self.add_widget(root)
        self.vm.bind(self.render)

    def render(self):
        ad, vm = self.vm.ad, self.vm
        if ad is None:
            return
        card = Card()
        tag = AD_TYPES.get(ad.type, ad.type) + f" · {STATUS_LABELS.get(ad.status, ad.status)}"
        card.add_widget(Lbl(tag, size=12, color=TYPE_COLORS.get(ad.type, MUTED), bold=True))
        card.add_widget(Lbl(ad.title, size=20, bold=True))
        card.add_widget(Lbl(ad.description, size=15))
        card.add_widget(Lbl(f"Категория: {ad.category}", size=13, color=MUTED))
        card.add_widget(Lbl(f"Автор: {ad.author_name} · {short_date(ad.created)}", size=13, color=MUTED))
        card.add_widget(Lbl(place(ad.location), size=13, color=MUTED))
        items = [card]
        text, color = status_lbl(vm)
        if text:
            items.append(Lbl(text, size=13, color=color))
        elif vm.info:
            items.append(Lbl(vm.info, size=13, color=PRIMARY))
        if vm.is_author and ad.status == "open":
            items.append(Btn("Решено", vm.solve))
            items.append(Btn("Удалить объявление", lambda: confirm("Удалить объявление из ленты?", vm.cancel),
                             kind="danger"))
        elif vm.can_respond:
            if ad.my_chat_id:
                items.append(Btn("Открыть чат", lambda: self.app.open_chat(
                    Chat(ad.my_chat_id, ad.id, ad.title, ad.author_name))))
            else:
                label = "Помогу" if ad.type == "need" else "Хочу воспользоваться"
                items.append(Btn(label, lambda: vm.respond(self.app.open_chat)))
        if not vm.is_author and ad.status == "open":
            items.append(Btn("Пожаловаться", lambda: choose("Причина жалобы", REPORT_REASONS, vm.report),
                             kind="light"))
        self.list.set_items(items)


# ===================================================================== создание объявления
class CreateScreen(Screen):
    PLACEHOLDER = "Выберите категорию"

    def __init__(self, app, **kw):
        super().__init__(name="create", **kw)
        self.app, self.vm = app, app.create_vm
        root = BoxLayout(orientation="vertical")
        self.bar = Bar("Новое объявление", on_back=app.go_main)
        root.add_widget(self.bar)
        self.list = VList()
        root.add_widget(self.list)
        self.add_widget(root)
        self.title_field = Field("Коротко: что нужно или что предлагаете")
        self.desc = Field("Опишите детали: когда, где, что именно. Без цен — платные услуги запрещены.",
                          multiline=True, lines=5)
        self.category = Choice([self.PLACEHOLDER] + CATEGORIES)
        self.status = Lbl("", size=13, color=DANGER)
        self.publish = Btn("Опубликовать", self._publish)
        self.list.set_items([self.title_field, self.desc, self.category, self.status, self.publish,
                             Btn("Отмена", app.go_main, kind="light")])
        self.vm.bind(self.render)

    def prepare(self, ad_type):
        self.title_field.text, self.desc.text, self.category.text = "", "", self.PLACEHOLDER
        self.vm.start(ad_type)

    def _publish(self):
        cat = "" if self.category.text == self.PLACEHOLDER else self.category.text
        self.vm.publish(self.title_field.text, self.desc.text, cat, lambda _ad: self.app.go_main())

    def render(self):
        self.bar.title.text = AD_TYPES[self.vm.ad_type]
        self.status.text, self.status.color = status_lbl(self.vm)
        self.publish.disabled = self.vm.loading


# ===================================================================== чат
class ChatScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="chat", **kw)
        self.app, self.vm, self._ev = app, app.chat_vm, None
        root = BoxLayout(orientation="vertical")
        self.bar = Bar("Чат", on_back=app.go_main)
        root.add_widget(self.bar)
        self.status = Lbl("", size=13, color=DANGER, padding=(dp(8), 0))
        root.add_widget(self.status)
        self.list = VList()
        root.add_widget(self.list)
        row = BoxLayout(size_hint_y=None, height=dp(54), padding=dp(6), spacing=dp(6))
        self.input = Field("Сообщение", height=dp(42))
        self.input.bind(on_text_validate=lambda *_: self._send())
        row.add_widget(self.input)
        row.add_widget(Btn("Отпр.", self._send, size_hint_x=None, width=dp(76), height=dp(42)))
        root.add_widget(row)
        self.add_widget(root)
        self._count = -1
        self.vm.bind(self.render)

    def on_enter(self, *_):
        self._ev = Clock.schedule_interval(lambda _dt: self.vm.refresh(silent=True), 3)

    def on_leave(self, *_):
        if self._ev:
            self._ev.cancel()
            self._ev = None

    def _send(self):
        text = self.input.text
        if text.strip():
            self.vm.send(text, on_sent=lambda: setattr(self.input, "text", ""))

    def render(self):
        chat = self.vm.chat
        if chat is None:
            return
        self.bar.title.text = f"{chat.ad_title} · {chat.partner_name}"[:40]
        self.status.text, self.status.color = status_lbl(self.vm)
        if len(self.vm.messages) == self._count and not self.vm.loading:
            return
        self._count = len(self.vm.messages)
        rows = []
        for m in self.vm.messages:
            mine = m.sender_id == self.vm.my_id
            bubble = Card(bg=MINE if mine else (1, 1, 1, 1), size_hint_x=0.8)
            bubble.add_widget(Lbl("Вы" if mine else m.sender_name, size=11, color=MUTED, bold=True))
            bubble.add_widget(Lbl(m.text, size=15))
            bubble.add_widget(Lbl(short_date(m.created), size=10, color=MUTED))
            row = BoxLayout(size_hint_y=None)
            bubble.bind(height=row.setter("height"))
            if mine:
                row.add_widget(Widget(size_hint_x=0.2))
                row.add_widget(bubble)
            else:
                row.add_widget(bubble)
                row.add_widget(Widget(size_hint_x=0.2))
            rows.append(row)
        self.list.set_items(rows, "" if self.vm.loading else "Сообщений пока нет. Напишите первым!")
        self.list.scroll_bottom()
