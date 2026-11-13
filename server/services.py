"""Бизнес-логика сервера «Соседская помощь».

Правила из SAD (раздел 2, Business Rules):
  * объявления видят только жильцы той же локации (кампус/дом/подъезд/этаж);
  * платные услуги запрещены;
  * модерация обязательна (жалобы, удаление, блокировка).
"""
import hashlib
import hmac
import re
import secrets

from . import locations as loc

CATEGORIES = ["Ремонт", "Доставка", "Уборка", "Животные", "Другое"]
AD_TYPES = ("need", "offer")
REPORT_REASONS = ["Спам", "Платные услуги", "Оскорбления", "Другое"]
ROLE_USER, ROLE_MODERATOR = "user", "moderator"

# Признаки платных услуг: цена с валютой, «за плату», «платно» и т.п.
# («бесплатно» не срабатывает: перед «платно» нет границы слова)
PAID_RE = re.compile(
    r"(\d\s*(₽|р\b|руб|\$|€)|₽|\bза плату\b|\bза деньги\b|\bплатно\b|\bоплат[аыуе]\b)",
    re.IGNORECASE,
)


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _text(value, field, lo, hi):
    if not isinstance(value, str):
        value = ""
    value = value.strip()
    if len(value) < lo:
        raise ApiError(400, f"Поле «{field}» не заполнено" if lo <= 1 else f"Поле «{field}»: минимум {lo} симв.")
    if len(value) > hi:
        raise ApiError(400, f"Поле «{field}»: максимум {hi} симв.")
    return value


def _hash(password, salt_hex):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 60_000).hex()


def public_user(u):
    return {
        "id": u["id"], "name": u["name"], "role": u["role"], "location": u["location"],
        "notify": bool(u["notify"]), "blocked": bool(u["blocked"]),
    }


class Service:
    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------ users
    def ensure_moderator(self, name="moderator", password="moderator", location="Кампус Север/Дом 1"):
        if not self.db.one("SELECT id FROM users WHERE name_key=?", (name.lower(),)):
            self._insert_user(name, password, location, ROLE_MODERATOR)

    def _insert_user(self, name, password, location, role=ROLE_USER):
        salt = secrets.token_hex(16)
        uid = self.db.execute(
            "INSERT INTO users(name,name_key,salt,pass_hash,role,location) VALUES(?,?,?,?,?,?)",
            (name, name.lower(), salt, _hash(password, salt), role, location),
        )
        return self.db.one("SELECT * FROM users WHERE id=?", (uid,))

    def _new_session(self, user):
        token = secrets.token_hex(24)
        self.db.execute("INSERT INTO sessions(token,user_id) VALUES(?,?)", (token, user["id"]))
        return {"token": token, "user": public_user(user)}

    def register(self, name, password, location):
        name = _text(name, "Имя", 2, 30)
        if not isinstance(password, str) or len(password) < 4:
            raise ApiError(400, "Пароль: минимум 4 символа")
        if not loc.is_valid_path(location):
            raise ApiError(400, "Укажите локацию (минимум до дома)")
        if self.db.one("SELECT id FROM users WHERE name_key=?", (name.lower(),)):
            raise ApiError(409, "Это имя уже занято")
        return self._new_session(self._insert_user(name, password, location))

    def login(self, name, password):
        user = self.db.one("SELECT * FROM users WHERE name_key=?", (str(name or "").strip().lower(),))
        ok = user and hmac.compare_digest(_hash(str(password or ""), user["salt"]), user["pass_hash"])
        if not ok:
            raise ApiError(401, "Неверное имя или пароль")
        return self._new_session(user)

    def authenticate(self, token):
        row = self.db.one(
            "SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id WHERE token=?", (token,))
        if not row:
            raise ApiError(401, "Требуется вход")
        return row

    def logout(self, token):
        self.db.execute("DELETE FROM sessions WHERE token=?", (token,))
        return {"ok": True}

    def update_profile(self, user, data):
        name = _text(data.get("name", user["name"]), "Имя", 2, 30)
        location = data.get("location", user["location"])
        if not loc.is_valid_path(location):
            raise ApiError(400, "Укажите локацию (минимум до дома)")
        other = self.db.one("SELECT id FROM users WHERE name_key=? AND id<>?", (name.lower(), user["id"]))
        if other:
            raise ApiError(409, "Это имя уже занято")
        notify = 1 if data.get("notify", bool(user["notify"])) else 0
        self.db.execute("UPDATE users SET name=?, name_key=?, location=?, notify=? WHERE id=?",
                        (name, name.lower(), location, notify, user["id"]))
        return public_user(self.db.one("SELECT * FROM users WHERE id=?", (user["id"],)))

    # --------------------------------------------------------- notifications
    def _notify(self, user_id, kind, text, ref_id=None, force=False):
        target = self.db.one("SELECT notify FROM users WHERE id=?", (user_id,))
        if target and (force or target["notify"]):
            self.db.execute("INSERT INTO notifications(user_id,kind,text,ref_id) VALUES(?,?,?,?)",
                            (user_id, kind, text, ref_id))

    def poll_notifications(self, user):
        with self.db.lock:
            rows = self.db.query(
                "SELECT id,kind,text,ref_id FROM notifications WHERE user_id=? AND is_read=0 ORDER BY id",
                (user["id"],))
            if rows:
                self.db.execute("UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0", (user["id"],))
        return rows

    # -------------------------------------------------------------------- ads
    def _ad_view(self, row, user):
        chat = self.db.one("SELECT id FROM chats WHERE ad_id=? AND helper_id=?", (row["id"], user["id"]))
        return {
            "id": row["id"], "type": row["type"], "title": row["title"], "description": row["description"],
            "category": row["category"], "status": row["status"], "location": row["location"],
            "author_id": row["author_id"], "author_name": row["author_name"], "created": row["created"],
            "my_chat_id": chat["id"] if chat else None,
        }

    _AD_SELECT = "SELECT ads.*, users.name AS author_name FROM ads JOIN users ON users.id=ads.author_id "

    def _get_ad_row(self, ad_id):
        row = self.db.one(self._AD_SELECT + "WHERE ads.id=?", (ad_id,))
        if not row:
            raise ApiError(404, "Объявление не найдено")
        return row

    def create_ad(self, user, data):
        if user["blocked"]:
            raise ApiError(403, "Вы заблокированы и не можете публиковать объявления")
        ad_type = data.get("type")
        if ad_type not in AD_TYPES:
            raise ApiError(400, "Неизвестный тип объявления")
        title = _text(data.get("title"), "Заголовок", 3, 80)
        description = _text(data.get("description"), "Описание", 1, 1000)
        category = data.get("category")
        if category not in CATEGORIES:
            raise ApiError(400, "Выберите категорию")
        if PAID_RE.search(title) or PAID_RE.search(description):
            raise ApiError(400, "Платные услуги запрещены правилами платформы")
        ad_id = self.db.execute(
            "INSERT INTO ads(author_id,type,title,description,category,location) VALUES(?,?,?,?,?,?)",
            (user["id"], ad_type, title, description, category, user["location"]))
        # UC-19: уведомить соседей по дому
        house = loc.prefix_for_level(user["location"], 2)
        label = "просит помощи" if ad_type == "need" else "предлагает помощь"
        for n in self.db.query("SELECT id, location FROM users WHERE id<>?", (user["id"],)):
            if loc.in_scope(n["location"], house):
                self._notify(n["id"], "new_ad", f"{user['name']} {label}: {title}", ad_id)
        return self._ad_view(self._get_ad_row(ad_id), user)

    def feed(self, user, params):
        try:
            level = int(params.get("level") or 2)
        except ValueError:
            raise ApiError(400, "Некорректный уровень локации")
        prefix = loc.prefix_for_level(user["location"], level)
        sql, args = self._AD_SELECT + "WHERE ads.status='open'", []
        if params.get("type"):
            sql += " AND ads.type=?"
            args.append(params["type"])
        if params.get("category"):
            sql += " AND ads.category=?"
            args.append(params["category"])
        rows = self.db.query(sql + " ORDER BY ads.id DESC LIMIT 500", args)
        q = (params.get("q") or "").strip().lower()
        result = []
        for r in rows:
            if not loc.in_scope(r["location"], prefix):
                continue
            if q and q not in r["title"].lower() and q not in r["description"].lower():
                continue
            result.append(self._ad_view(r, user))
        return result

    def get_ad(self, user, ad_id):
        row = self._get_ad_row(ad_id)
        is_mod = user["role"] == ROLE_MODERATOR
        participant = self.db.one("SELECT id FROM chats WHERE ad_id=? AND (author_id=? OR helper_id=?)",
                                  (ad_id, user["id"], user["id"]))
        same_campus = loc.in_scope(row["location"], loc.prefix_for_level(user["location"], 1))
        if not (is_mod or row["author_id"] == user["id"] or participant
                or (row["status"] == "open" and same_campus)):
            raise ApiError(404, "Объявление удалено или недоступно")
        return self._ad_view(row, user)

    def my_ads(self, user, status=None):
        sql, args = self._AD_SELECT + "WHERE ads.author_id=?", [user["id"]]
        if status:
            sql += " AND ads.status=?"
            args.append(status)
        return [self._ad_view(r, user) for r in self.db.query(sql + " ORDER BY ads.id DESC", args)]

    def set_status(self, user, ad_id, status):
        """UC-15 «Решено» и UC-16 «Отмена»."""
        if status not in ("solved", "cancelled"):
            raise ApiError(400, "Недопустимый статус")
        with self.db.lock:
            row = self._get_ad_row(ad_id)
            if row["author_id"] != user["id"]:
                raise ApiError(403, "Менять статус может только автор")
            if row["status"] != "open":
                raise ApiError(409, "Объявление уже закрыто")
            self.db.execute("UPDATE ads SET status=? WHERE id=?", (status, ad_id))
            if status == "solved":
                for c in self.db.query("SELECT id, helper_id FROM chats WHERE ad_id=?", (ad_id,)):
                    self._notify(c["helper_id"], "solved", f"Объявление «{row['title']}» отмечено как решённое", c["id"])
        return self._ad_view(self._get_ad_row(ad_id), user)

    # ------------------------------------------------------------ chats (UC-12/13/14)
    def _chat_view(self, c, user):
        partner_id = c["helper_id"] if c["author_id"] == user["id"] else c["author_id"]
        partner = self.db.one("SELECT name FROM users WHERE id=?", (partner_id,))
        last = self.db.one("SELECT text FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 1", (c["id"],))
        ad = self.db.one("SELECT title FROM ads WHERE id=?", (c["ad_id"],))
        return {"id": c["id"], "ad_id": c["ad_id"], "ad_title": ad["title"],
                "partner_name": partner["name"], "last_text": last["text"] if last else ""}

    def respond(self, user, ad_id):
        with self.db.lock:
            row = self._get_ad_row(ad_id)
            if row["author_id"] == user["id"]:
                raise ApiError(400, "Нельзя откликнуться на своё объявление")
            if row["status"] != "open":
                raise ApiError(409, "Автор закрыл объявление")
            if not loc.in_scope(row["location"], loc.prefix_for_level(user["location"], 1)):
                raise ApiError(404, "Объявление недоступно")
            chat = self.db.one("SELECT * FROM chats WHERE ad_id=? AND helper_id=?", (ad_id, user["id"]))
            if not chat:
                cid = self.db.execute("INSERT INTO chats(ad_id,author_id,helper_id) VALUES(?,?,?)",
                                      (ad_id, row["author_id"], user["id"]))
                chat = self.db.one("SELECT * FROM chats WHERE id=?", (cid,))
                self._notify(row["author_id"], "response",
                             f"{user['name']} откликнулся на «{row['title']}»", cid)
        return self._chat_view(chat, user)

    def _chat_for(self, user, chat_id):
        chat = self.db.one("SELECT * FROM chats WHERE id=?", (chat_id,))
        if not chat or user["id"] not in (chat["author_id"], chat["helper_id"]):
            raise ApiError(404, "Чат не найден")
        return chat

    def chats(self, user):
        rows = self.db.query("SELECT * FROM chats WHERE author_id=? OR helper_id=? ORDER BY id DESC",
                             (user["id"], user["id"]))
        return [self._chat_view(c, user) for c in rows]

    def messages(self, user, chat_id, after=0):
        self._chat_for(user, chat_id)
        return self.db.query(
            "SELECT messages.id, chat_id, sender_id, users.name AS sender_name, text, messages.created "
            "FROM messages JOIN users ON users.id=sender_id WHERE chat_id=? AND messages.id>? ORDER BY messages.id",
            (chat_id, int(after or 0)))

    def send_message(self, user, chat_id, text):
        chat = self._chat_for(user, chat_id)
        text = _text(text, "Сообщение", 1, 1000)
        mid = self.db.execute("INSERT INTO messages(chat_id,sender_id,text) VALUES(?,?,?)",
                              (chat_id, user["id"], text))
        other = chat["helper_id"] if chat["author_id"] == user["id"] else chat["author_id"]
        self._notify(other, "message", f"{user['name']}: {text[:60]}", chat_id)
        return self.messages(user, chat_id, mid - 1)[0]

    # ------------------------------------------------------- moderation (UC-20/21/22)
    def report(self, user, ad_id, reason):
        row = self._get_ad_row(ad_id)
        if reason not in REPORT_REASONS:
            raise ApiError(400, "Выберите причину жалобы")
        if row["author_id"] == user["id"]:
            raise ApiError(400, "Нельзя пожаловаться на своё объявление")
        if self.db.one("SELECT id FROM reports WHERE ad_id=? AND reporter_id=?", (ad_id, user["id"])):
            raise ApiError(409, "Жалоба уже отправлена")
        self.db.execute("INSERT INTO reports(ad_id,reporter_id,reason) VALUES(?,?,?)", (ad_id, user["id"], reason))
        return {"ok": True}

    @staticmethod
    def _require_moderator(user):
        if user["role"] != ROLE_MODERATOR:
            raise ApiError(403, "Только для модераторов")

    def reports(self, user):
        self._require_moderator(user)
        rows = self.db.query(
            "SELECT r.id, r.reason, r.created, rep.name AS reporter_name, a.id AS ad_id, a.title, a.description, "
            "a.status AS ad_status, au.id AS author_id, au.name AS author_name, au.blocked AS author_blocked "
            "FROM reports r JOIN ads a ON a.id=r.ad_id JOIN users au ON au.id=a.author_id "
            "JOIN users rep ON rep.id=r.reporter_id WHERE r.status='new' ORDER BY r.id")
        return [{
            "id": r["id"], "reason": r["reason"], "created": r["created"], "reporter_name": r["reporter_name"],
            "ad": {"id": r["ad_id"], "title": r["title"], "description": r["description"], "status": r["ad_status"],
                   "author_id": r["author_id"], "author_name": r["author_name"],
                   "author_blocked": bool(r["author_blocked"])},
        } for r in rows]

    def resolve_report(self, user, report_id, action):
        self._require_moderator(user)
        if action not in ("delete", "reject"):
            raise ApiError(400, "Недопустимое действие")
        with self.db.lock:
            rep = self.db.one("SELECT * FROM reports WHERE id=?", (report_id,))
            if not rep:
                raise ApiError(404, "Жалоба не найдена")
            ad = self._get_ad_row(rep["ad_id"])
            if action == "reject":
                self.db.execute("UPDATE reports SET status='rejected' WHERE id=?", (report_id,))
                return {"ok": True}
            if ad["status"] == "removed":
                self.db.execute("UPDATE reports SET status='resolved' WHERE ad_id=?", (ad["id"],))
                raise ApiError(409, "Объявление уже удалено")
            self.db.execute("UPDATE ads SET status='removed' WHERE id=?", (ad["id"],))
            self.db.execute("UPDATE reports SET status='resolved' WHERE ad_id=? AND status='new'", (ad["id"],))
            self._notify(ad["author_id"], "moderation",
                         f"Ваше объявление «{ad['title']}» удалено модератором", ad["id"], force=True)
        return {"ok": True}

    def block_user(self, user, target_id, blocked):
        self._require_moderator(user)
        if target_id == user["id"]:
            raise ApiError(400, "Нельзя заблокировать себя")
        target = self.db.one("SELECT * FROM users WHERE id=?", (target_id,))
        if not target:
            raise ApiError(404, "Пользователь не найден")
        if target["role"] == ROLE_MODERATOR:
            raise ApiError(400, "Нельзя заблокировать модератора")
        self.db.execute("UPDATE users SET blocked=? WHERE id=?", (1 if blocked else 0, target_id))
        return {"ok": True, "blocked": bool(blocked)}
