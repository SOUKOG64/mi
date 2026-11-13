"""Domain: сущности и справочники (SAD 5.2: User, Ad, Chat, Message, Location, Category)."""
from dataclasses import dataclass
from typing import Optional

CATEGORIES = ["Ремонт", "Доставка", "Уборка", "Животные", "Другое"]
AD_TYPES = {"need": "Прошу помощь", "offer": "Могу помочь"}
STATUS_LABELS = {"open": "Открыто", "solved": "Решено", "cancelled": "Отменено", "removed": "Удалено модератором"}
LEVELS = {1: "Кампус", 2: "Дом", 3: "Подъезд", 4: "Этаж"}
REPORT_REASONS = ["Спам", "Платные услуги", "Оскорбления", "Другое"]
ROLE_MODERATOR = "moderator"


@dataclass
class User:
    id: int
    name: str
    role: str
    location: str
    notify: bool = True
    blocked: bool = False

    @property
    def is_moderator(self):
        return self.role == ROLE_MODERATOR


@dataclass
class Ad:
    id: int
    type: str
    title: str
    description: str
    category: str
    status: str
    location: str
    author_id: int
    author_name: str
    created: str
    my_chat_id: Optional[int] = None


@dataclass
class Chat:
    id: int
    ad_id: int
    ad_title: str
    partner_name: str
    last_text: str = ""


@dataclass
class Message:
    id: int
    chat_id: int
    sender_id: int
    sender_name: str
    text: str
    created: str


@dataclass
class Report:
    id: int
    reason: str
    created: str
    reporter_name: str
    ad_id: int
    ad_title: str
    ad_description: str
    author_id: int
    author_name: str
    author_blocked: bool


@dataclass
class Notification:
    id: int
    kind: str
    text: str
    ref_id: Optional[int] = None


@dataclass
class AdFilter:
    level: int = 2
    type: str = ""
    category: str = ""
    query: str = ""
