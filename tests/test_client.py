"""Сквозная проверка клиентских слоёв (use cases + репозитории + ViewModel) против настоящего сервера."""
import tempfile
import threading
import unittest

from client.di import build_container
from client.domain.entities import AdFilter
from client.presentation import viewmodels as vm
from server.http_api import make_server

HOME = "Кампус Север/Дом 1/Подъезд 1/Этаж 2"


def make_client(base, tmp):
    c = build_container(tmp)
    r = vm.sync_runner
    state = {"user": None}
    get_user, set_user = (lambda: state["user"]), (lambda u: state.update(user=u))
    auth = vm.AuthViewModel(r, c.auth)
    return c, r, state, get_user, set_user, auth


class ClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = make_server("127.0.0.1", 0, ":memory:")
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_scenarios(self):
        t1, t2 = tempfile.mkdtemp(), tempfile.mkdtemp()
        c1, r1, s1, gu1, su1, auth1 = make_client(self.base, t1)
        c2, r2, s2, gu2, su2, auth2 = make_client(self.base, t2)

        # регистрация: валидация на клиенте и загрузка локаций
        auth1.toggle_mode()
        auth1.load_locations(self.base)
        self.assertTrue(auth1.locations and auth1.locations[0]["children"])
        auth1.submit(self.base, "anna", "12", HOME)
        self.assertIn("Пароль", auth1.error)
        auth1.submit(self.base, "anna", "1234", "")
        self.assertIn("локацию", auth1.error)
        auth1.submit(self.base + "/", "anna", "1234", HOME)
        self.assertEqual((auth1.error, auth1.user.name), ("", "anna"))
        su1(auth1.user)
        auth2.toggle_mode()
        auth2.submit(self.base, "boris", "1234", "Кампус Север/Дом 1/Подъезд 2/Этаж 4")
        su2(auth2.user)

        # неверный вход и нет соединения
        auth3 = vm.AuthViewModel(r1, c1.auth)
        auth3.submit(self.base, "anna", "bad")
        self.assertEqual(auth3.error, "Неверное имя или пароль")
        auth3.submit("http://127.0.0.1:1", "anna", "1234")
        self.assertEqual(auth3.error, "Нет соединения с сервером")
        c1.auth.login(self.base, "anna", "1234")  # вернуть конфигурацию клиента 1

        # восстановление сессии
        c1b = build_container(t1)
        authr = vm.AuthViewModel(r1, c1b.auth)
        self.assertEqual(authr.server, self.base)
        authr.restore()
        self.assertEqual(authr.user.name, "anna")

        # создание объявления (UC-04/05) и фильтры (UC-07..10)
        create = vm.CreateAdViewModel(r1, c1.create_ad)
        create.start("need")
        create.publish("ab", "текст", "Ремонт")
        self.assertIn("заголовок", create.error)
        create.publish("Нужна дрель", "", "Ремонт")
        self.assertIn("текст", create.error)
        create.publish("Нужна дрель", "Верну сегодня", "Ремонт")
        self.assertEqual((create.error, create.created.status), ("", "open"))
        create.publish("Куплю ведро", "Заплачу 300 руб", "Другое")
        self.assertIn("Платные", create.error)
        create.start("offer")
        create.publish("Помогу с сумками", "Подъезд 1", "Доставка")

        feed = vm.FeedViewModel(r2, c2.feed)
        feed.refresh()
        self.assertEqual(len(feed.ads), 2)
        feed.set_filter(type="offer")
        self.assertEqual([a.title for a in feed.ads], ["Помогу с сумками"])
        feed.set_filter(type="", query="дрель")
        self.assertEqual(len(feed.ads), 1)
        feed.set_filter(query="", level=3)
        self.assertEqual(len(feed.ads), 0)  # boris в другом подъезде

        # отклик, чат, уведомления (UC-12/13/18)
        feed.set_filter(level=2)
        ad = next(a for a in feed.ads if a.title == "Нужна дрель")
        det = vm.AdDetailViewModel(r2, c2.feed, c2.respond, c2.close, c2.report, gu2)
        det.show(ad)
        self.assertTrue(det.can_respond and not det.is_author)
        got = []
        det.respond(got.append)
        chat = got[0]
        chatvm = vm.ChatViewModel(r2, c2.chats, c2.send, gu2)
        chatvm.open(chat)
        chatvm.send("   ")
        self.assertIn("сообщение", chatvm.error)
        chatvm.send("Привет, принесу!")
        self.assertEqual(len(chatvm.messages), 1)

        sess1 = vm.SessionViewModel(r1, c1.auth, c1.notifications)
        seen = []
        sess1.poll(seen.extend)
        self.assertTrue(any(n.kind == "response" for n in seen))
        self.assertTrue(any(n.kind == "message" for n in seen))

        lst = vm.ChatListViewModel(r1, c1.chats)
        lst.refresh()
        self.assertEqual(lst.chats[0].partner_name, "boris")
        chat1 = vm.ChatViewModel(r1, c1.chats, c1.send, gu1)
        chat1.open(lst.chats[0])
        chat1.send("Спасибо!")
        chatvm.refresh(silent=True)
        self.assertEqual([m.text for m in chatvm.messages], ["Привет, принесу!", "Спасибо!"])

        # «Решено» автором, архив (UC-15/17), жалоба и модерация (UC-20/21/22)
        det1 = vm.AdDetailViewModel(r1, c1.feed, c1.respond, c1.close, c1.report, gu1)
        det1.show(ad)
        self.assertTrue(det1.is_author and not det1.can_respond)
        det1.solve()
        self.assertEqual(det1.ad.status, "solved")
        det1.solve()
        self.assertEqual(det1.error, "Объявление уже закрыто")
        prof = vm.ProfileViewModel(r1, c1.auth, c1.feed, gu1, su1)
        prof.load_archive("solved")
        self.assertEqual(len(prof.my_ads), 1)
        prof.save("Anna K", HOME, False)
        self.assertEqual((s1["user"].name, s1["user"].notify), ("Anna K", False))

        offer = next(a for a in c2.feed.feed(AdFilter()) if a.type == "offer")
        det2 = vm.AdDetailViewModel(r2, c2.feed, c2.respond, c2.close, c2.report, gu2)
        det2.show(c1.feed.get(offer.id))
        det2.report("Спам")  # boris сам не автор? offer создан anna, значит можно
        self.assertEqual(det2.error, "")
        det2.report("Спам")
        self.assertEqual(det2.error, "Жалоба уже отправлена")

        cm, rm, sm, gum, sum_, authm = make_client(self.base, tempfile.mkdtemp())
        authm.submit(self.base, "moderator", "moderator")
        sum_(authm.user)
        self.assertTrue(authm.user.is_moderator)
        mod = vm.ModerationViewModel(rm, cm.moderate)
        mod.refresh()
        self.assertEqual(len(mod.reports), 1)
        author_id = mod.reports[0].author_id
        mod.block(author_id, True)
        mod.delete_ad(mod.reports[0].id)
        self.assertEqual(mod.reports, [])
        create.start("need")
        create.publish("Ещё одно", "текст", "Другое")
        self.assertIn("заблокированы", create.error)
        self.assertEqual(len(c1.feed.mine("removed")), 1)

        # загрузка справочника локаций не должна сбрасывать сессию (регрессия)
        c2.auth.locations(self.base)
        self.assertEqual(len(c2.feed.mine("")), 0)

        # выход и недействительная сессия
        sess = vm.SessionViewModel(r2, c2.auth, c2.notifications)
        sess.logout()
        self.assertEqual(c2.auth.users.store.load()["token"], "")
        c2.auth.login(self.base, "boris", "1234")
        c2.auth.users.net.token = "expired"
        lost = []
        vm.ViewModel.on_auth_lost = lambda: lost.append(1)
        try:
            vm.FeedViewModel(r2, c2.feed).refresh()
        finally:
            vm.ViewModel.on_auth_lost = None
        self.assertEqual(lost, [1])


if __name__ == "__main__":
    unittest.main()
