import threading
import unittest

import requests

from server.http_api import make_server

HOME = "Кампус Север/Дом 1/Подъезд 1/Этаж 2"


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = make_server("127.0.0.1", 0, ":memory:")
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}/api"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def call(self, method, path, token=None, **body):
        h = {"Authorization": f"Bearer {token}"} if token else {}
        r = requests.request(method, self.base + path, json=body or None, headers=h, timeout=5)
        return r.status_code, r.json()

    def reg(self, name, loc=HOME):
        st, d = self.call("POST", "/register", name=name, password="1234", location=loc)
        self.assertEqual(st, 200, d)
        return d["token"], d["user"]

    def test_full_flow(self):
        ta, ua = self.reg("ann")
        tb, ub = self.reg("bob", "Кампус Север/Дом 1/Подъезд 2/Этаж 4")
        tc, _ = self.reg("carl", "Кампус Север/Дом 2/Подъезд 1/Этаж 1")
        td, _ = self.reg("dina", "Кампус Юг/Дом 1")

        # дубликат имени, пустая локация, неверный пароль
        self.assertEqual(self.call("POST", "/register", name="ANN", password="1234", location=HOME)[0], 409)
        self.assertEqual(self.call("POST", "/register", name="zed", password="1234", location="")[0], 400)
        self.assertEqual(self.call("POST", "/login", name="ann", password="bad")[0], 401)
        self.assertEqual(self.call("POST", "/login", name="Ann", password="1234")[0], 200)

        # платные услуги запрещены, пустой текст
        bad = dict(type="need", title="Помогите", description="Заплачу 500 руб", category="Ремонт")
        self.assertEqual(self.call("POST", "/ads", ta, **bad)[0], 400)
        self.assertEqual(self.call("POST", "/ads", ta, type="need", title="Дрель", description="  ", category="Ремонт")[0], 400)
        ok = dict(type="need", title="Нужна дрель", description="Бесплатно верну, рубашки не трогаю", category="Ремонт")
        st, d = self.call("POST", "/ads", ta, **ok)
        self.assertEqual(st, 200, d)
        ad = d["ad"]

        # видимость: тот же дом видит, другой дом при уровне «дом» нет, на уровне кампуса да, чужой кампус нет
        self.assertEqual(len(self.call("GET", "/ads", tb)[1]["ads"]), 1)
        self.assertEqual(len(self.call("GET", "/ads?level=3", tb)[1]["ads"]), 0)
        self.assertEqual(len(self.call("GET", "/ads", tc)[1]["ads"]), 0)
        self.assertEqual(len(self.call("GET", "/ads?level=1", tc)[1]["ads"]), 1)
        self.assertEqual(len(self.call("GET", "/ads?level=1", td)[1]["ads"]), 0)
        self.assertEqual(self.call("GET", f"/ads/{ad['id']}", td)[0], 404)
        # фильтры и поиск по кириллице без учёта регистра
        self.assertEqual(len(self.call("GET", "/ads?q=ДРЕЛЬ", tb)[1]["ads"]), 1)
        self.assertEqual(len(self.call("GET", "/ads?type=offer", tb)[1]["ads"]), 0)
        self.assertEqual(len(self.call("GET", "/ads?category=Уборка", tb)[1]["ads"]), 0)

        # уведомление соседу по дому (UC-19), у соседа из другого дома его нет
        self.assertEqual(len(self.call("POST", "/notifications/poll", tb)[1]["notifications"]), 1)
        self.assertEqual(self.call("POST", "/notifications/poll", tb)[1]["notifications"], [])
        self.assertEqual(self.call("POST", "/notifications/poll", tc)[1]["notifications"], [])

        # отклик: на своё нельзя, повтор возвращает тот же чат, автор получает уведомление
        self.assertEqual(self.call("POST", f"/ads/{ad['id']}/respond", ta)[0], 400)
        st, c1 = self.call("POST", f"/ads/{ad['id']}/respond", tb)
        self.assertEqual(st, 200)
        self.assertEqual(self.call("POST", f"/ads/{ad['id']}/respond", tb)[1]["chat"]["id"], c1["chat"]["id"])
        self.assertEqual(self.call("POST", "/notifications/poll", ta)[1]["notifications"][0]["kind"], "response")

        # чат: участники, история, посторонний
        cid = c1["chat"]["id"]
        self.assertEqual(self.call("POST", f"/chats/{cid}/messages", tb, text="Привет!")[0], 200)
        self.assertEqual(self.call("POST", f"/chats/{cid}/messages", tb, text="  ")[0], 400)
        self.assertEqual(self.call("POST", f"/chats/{cid}/messages", tc, text="hi")[0], 404)
        msgs = self.call("GET", f"/chats/{cid}/messages", ta)[1]["messages"]
        self.assertEqual([m["text"] for m in msgs], ["Привет!"])
        self.assertEqual(self.call("GET", f"/chats/{cid}/messages?after={msgs[0]['id']}", ta)[1]["messages"], [])
        self.assertEqual(len(self.call("GET", "/chats", ta)[1]["chats"]), 1)

        # жалобы и модерация
        self.assertEqual(self.call("POST", f"/ads/{ad['id']}/report", tb, reason="Спам")[0], 200)
        self.assertEqual(self.call("POST", f"/ads/{ad['id']}/report", tb, reason="Спам")[0], 409)
        self.assertEqual(self.call("GET", "/reports", tb)[0], 403)
        tm = self.call("POST", "/login", name="moderator", password="moderator")[1]["token"]
        reps = self.call("GET", "/reports", tm)[1]["reports"]
        self.assertEqual(len(reps), 1)
        self.assertEqual(self.call("POST", f"/reports/{reps[0]['id']}/resolve", tm, action="delete")[0], 200)
        self.assertEqual(self.call("POST", f"/reports/{reps[0]['id']}/resolve", tm, action="delete")[0], 409)
        self.assertEqual(self.call("GET", "/ads", tb)[1]["ads"], [])
        self.assertEqual(self.call("POST", "/notifications/poll", ta)[1]["notifications"][-1]["kind"], "moderation")

        # блокировка
        self.assertEqual(self.call("POST", f"/users/{ua['id']}/block", tb)[0], 403)
        mid = self.call("GET", "/me", tm)[1]["user"]["id"]
        self.assertEqual(self.call("POST", f"/users/{mid}/block", tm)[0], 400)
        self.assertEqual(self.call("POST", f"/users/{ua['id']}/block", tm, blocked=True)[0], 200)
        self.assertEqual(self.call("POST", "/ads", ta, **ok)[0], 403)
        self.call("POST", f"/users/{ua['id']}/block", tm, blocked=False)
        self.assertEqual(self.call("POST", "/ads", ta, **ok)[0], 200)

    def test_status_and_profile(self):
        t, u = self.reg("eva")
        ad = self.call("POST", "/ads", t, type="offer", title="Могу помочь", description="С сумками", category="Доставка")[1]["ad"]
        t2, _ = self.reg("fil")
        cid = self.call("POST", f"/ads/{ad['id']}/respond", t2)[1]["chat"]["id"]
        self.assertEqual(self.call("POST", f"/ads/{ad['id']}/status", t2, status="solved")[0], 403)
        self.assertEqual(self.call("POST", f"/ads/{ad['id']}/status", t, status="solved")[1]["ad"]["status"], "solved")
        self.assertEqual(self.call("POST", f"/ads/{ad['id']}/status", t, status="cancelled")[0], 409)
        self.assertEqual(self.call("POST", f"/ads/{ad['id']}/respond", self.reg("gus")[0])[0], 409)
        self.assertEqual([a["id"] for a in self.call("GET", "/ads", t2)[1]["ads"] if a["id"] == ad["id"]], [])
        self.assertEqual(self.call("GET", "/my/ads?status=solved", t)[1]["ads"][0]["id"], ad["id"])
        self.assertTrue(any(n["kind"] == "solved" for n in self.call("POST", "/notifications/poll", t2)[1]["notifications"]))
        # профиль, отключение уведомлений
        st, d = self.call("PUT", "/me", t, name="Eva K", location="Кампус Север/Дом 2", notify=False)
        self.assertEqual((st, d["user"]["notify"]), (200, False))
        self.assertEqual(self.call("PUT", "/me", t, name="Eva K", location="Нет/такой")[0], 400)
        self.assertEqual(self.call("GET", "/me")[0], 401)
        self.assertEqual(self.call("POST", "/logout", t)[0], 200)
        self.assertEqual(self.call("GET", "/me", t)[0], 401)


if __name__ == "__main__":
    unittest.main()
