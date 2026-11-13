"""Presentation: небольшой набор Kivy-виджетов в едином стиле (без kv-файлов)."""
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

PRIMARY = (0.10, 0.48, 0.42, 1)
PRIMARY_DARK = (0.06, 0.34, 0.30, 1)
ACCENT = (0.85, 0.50, 0.12, 1)
DANGER = (0.76, 0.22, 0.20, 1)
BG = (0.95, 0.96, 0.95, 1)
CARD = (1, 1, 1, 1)
MINE = (0.84, 0.94, 0.90, 1)
TEXT = (0.12, 0.14, 0.14, 1)
MUTED = (0.42, 0.46, 0.45, 1)
WHITE = (1, 1, 1, 1)
NONE_LABEL = "—"


class Lbl(Label):
    """Подпись с переносом строк; высота подстраивается под текст."""

    def __init__(self, text="", size=15, color=TEXT, bold=False, **kw):
        kw.setdefault("halign", "left")
        kw.setdefault("valign", "middle")
        kw.setdefault("size_hint_y", None)
        super().__init__(text=text, font_size=sp(size), color=color, bold=bold, **kw)
        self.bind(width=self._wrap, texture_size=self._fit)

    def _wrap(self, *_):
        self.text_size = (self.width, None)

    def _fit(self, *_):
        if self.size_hint_y is None:
            self.height = self.texture_size[1] + dp(4)


class Btn(Button):
    KINDS = {"primary": (PRIMARY, WHITE), "accent": (ACCENT, WHITE), "danger": (DANGER, WHITE),
             "light": ((0.86, 0.89, 0.88, 1), TEXT)}

    def __init__(self, text, on_press=None, kind="primary", **kw):
        bg, fg = self.KINDS[kind]
        self._bg = bg
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(46))
        super().__init__(text=text, background_normal="", background_down="", background_color=bg,
                         color=fg, font_size=sp(15), **kw)
        self.bind(state=self._state)
        if on_press:
            self.bind(on_release=lambda *_: on_press())

    def _state(self, _inst, value):
        k = 0.8 if value == "down" else 1
        self.background_color = (self._bg[0] * k, self._bg[1] * k, self._bg[2] * k, 1)


class Field(TextInput):
    def __init__(self, hint="", multiline=False, password=False, lines=1, **kw):
        kw.setdefault("height", dp(46) if not multiline else dp(24) * max(lines, 2) + dp(22))
        super().__init__(hint_text=hint, multiline=multiline, password=password, size_hint_y=None,
                         padding=[dp(10), dp(12)], write_tab=False, font_size=sp(15), **kw)


class Choice(Spinner):
    def __init__(self, values, text=None, **kw):
        values = list(values)
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(44))
        super().__init__(text=text if text is not None else values[0], values=values, background_normal="",
                         background_color=(0.86, 0.89, 0.88, 1), color=TEXT, font_size=sp(14), **kw)


class Card(BoxLayout):
    def __init__(self, bg=CARD, **kw):
        kw.setdefault("orientation", "vertical")
        kw.setdefault("padding", dp(12))
        kw.setdefault("spacing", dp(6))
        kw.setdefault("size_hint_y", None)
        super().__init__(**kw)
        self.bind(minimum_height=self.setter("height"), pos=self._redraw, size=self._redraw)
        with self.canvas.before:
            Color(*bg)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])

    def _redraw(self, *_):
        self._rect.pos, self._rect.size = self.pos, self.size


class TapCard(ButtonBehavior, Card):
    pass


class Bar(BoxLayout):
    """Верхняя панель: необязательная кнопка «назад» и заголовок."""

    def __init__(self, title, on_back=None, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(52), padding=[dp(8), dp(4)],
                         spacing=dp(8), **kw)
        with self.canvas.before:
            Color(*PRIMARY)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self._redraw, size=self._redraw)
        if on_back:
            self.add_widget(Btn("Назад", on_back, kind="light", size_hint_x=None, width=dp(84), height=dp(42),
                                pos_hint={"center_y": 0.5}))
        self.title = Lbl(title, size=18, color=WHITE, bold=True, size_hint_y=1)
        self.add_widget(self.title)

    def _redraw(self, *_):
        self._rect.pos, self._rect.size = self.pos, self.size


class VList(ScrollView):
    """Вертикальный прокручиваемый список виджетов."""

    def __init__(self, **kw):
        super().__init__(do_scroll_x=False, **kw)
        self.box = GridLayout(cols=1, spacing=dp(8), padding=dp(8), size_hint_y=None)
        self.box.bind(minimum_height=self.box.setter("height"))
        self.add_widget(self.box)

    def set_items(self, widgets, empty_text=""):
        self.box.clear_widgets()
        if not widgets and empty_text:
            self.box.add_widget(Lbl(empty_text, halign="center", color=MUTED))
        for w in widgets:
            self.box.add_widget(w)

    def scroll_bottom(self):
        Clock.schedule_once(lambda _dt: setattr(self, "scroll_y", 0), 0.05)


class LocationPicker(BoxLayout):
    """Каскад: кампус -> дом -> подъезд -> этаж (дом обязателен, глубже — по желанию)."""

    HINTS = ["Кампус", "Дом", "Подъезд", "Этаж"]

    def __init__(self, tree=None, value="", **kw):
        super().__init__(orientation="vertical", size_hint_y=None, spacing=dp(6), **kw)
        self.height = dp(44) * 4 + dp(6) * 3
        self.tree, self._busy = tree or [], False
        self.spinners = [Choice([NONE_LABEL]) for _ in range(4)]
        for lvl, s in enumerate(self.spinners):
            s.bind(text=lambda _i, _v, l=lvl: self._on_change(l))
            self.add_widget(s)
        self.set_value(value)

    def set_tree(self, tree, value=None):
        keep = self.value if value is None else value
        self.tree = tree or []
        self.set_value(keep)

    def _children(self, path):
        nodes = self.tree
        for name in path:
            nodes = next((n["children"] for n in nodes if n["name"] == name), [])
        return [n["name"] for n in nodes]

    def _fill(self, from_level):
        path, dead = [], False
        for lvl in range(4):
            s = self.spinners[lvl]
            if lvl >= from_level:
                vals = [] if dead else self._children(path)
                if lvl >= 2:
                    vals = [NONE_LABEL] + vals
                vals = vals or [NONE_LABEL]
                s.values, s.text = vals, vals[0]
            if s.text == NONE_LABEL:
                dead = True
            elif not dead:
                path.append(s.text)

    def _on_change(self, lvl):
        if self._busy:
            return
        self._busy = True
        self._fill(lvl + 1)
        self._busy = False

    def set_value(self, value):
        parts = value.split("/") if value else []
        self._busy = True
        for lvl in range(4):
            self._fill(lvl)
            if lvl < len(parts) and parts[lvl] in self.spinners[lvl].values:
                self.spinners[lvl].text = parts[lvl]
        self._busy = False

    @property
    def value(self):
        parts = []
        for s in self.spinners:
            if s.text == NONE_LABEL:
                break
            parts.append(s.text)
        return "/".join(parts)


# ----------------------------------------------------------------------- диалоги
def _popup(title, content, height):
    popup = Popup(title=title, content=content, size_hint=(0.88, None), height=height, auto_dismiss=True)
    popup.open()
    return popup


def notice(text, title="Сообщение"):
    box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))
    box.add_widget(Lbl(text, size_hint_y=1))
    popup = _popup(title, box, dp(200))
    box.add_widget(Btn("OK", popup.dismiss))


def confirm(text, on_yes, yes_text="Да", kind="danger"):
    box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))
    box.add_widget(Lbl(text, size_hint_y=1))
    popup = _popup("Подтверждение", box, dp(220))
    row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
    row.add_widget(Btn("Отмена", popup.dismiss, kind="light"))
    row.add_widget(Btn(yes_text, lambda: (popup.dismiss(), on_yes()), kind=kind))
    box.add_widget(row)


def choose(title, options, on_pick):
    box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
    popup = _popup(title, box, dp(130) + dp(54) * len(options))
    for opt in options:
        box.add_widget(Btn(opt, lambda o=opt: (popup.dismiss(), on_pick(o)), kind="light"))
    box.add_widget(Btn("Отмена", popup.dismiss, kind="light"))
