"""Тестовые данные (Vision, п. 9.4): демо-жильцы и несколько объявлений."""
from .services import ApiError

DEMO_USERS = [
    ("anna", "1234", "Кампус Север/Дом 1/Подъезд 1/Этаж 2"),
    ("boris", "1234", "Кампус Север/Дом 1/Подъезд 2/Этаж 4"),
    ("clara", "1234", "Кампус Юг/Дом 1/Подъезд 1/Этаж 1"),
]
DEMO_ADS = [
    ("anna", "need", "Нужна дрель на вечер", "Повесить полку, верну сегодня же.", "Ремонт"),
    ("boris", "offer", "Помогу донести покупки", "Живу на 4 этаже, могу помочь с сумками.", "Доставка"),
    ("anna", "need", "Покормить кота на выходных", "Уезжаю на два дня, кот спокойный.", "Животные"),
]


def seed_demo(service):
    users = {}
    for name, pw, location in DEMO_USERS:
        try:
            users[name] = service.register(name, pw, location)["user"]
        except ApiError:
            return  # демо-данные уже есть
    for author, t, title, desc, cat in DEMO_ADS:
        row = service.db.one("SELECT * FROM users WHERE id=?", (users[author]["id"],))
        service.create_ad(row, {"type": t, "title": title, "description": desc, "category": cat})
