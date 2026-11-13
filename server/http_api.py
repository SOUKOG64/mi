"""REST API (JSON поверх HTTP) на стандартной библиотеке."""
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import locations
from .db import Database
from .services import AD_TYPES, CATEGORIES, REPORT_REASONS, ApiError, Service, public_user

MAX_BODY = 64 * 1024

# (метод, шаблон, нужна ли авторизация, обработчик(service, user, p, q, b))
ROUTES = [
    ("GET", r"/api/health", False, lambda s, u, p, q, b: {"ok": True}),
    ("GET", r"/api/locations", False, lambda s, u, p, q, b: {"tree": locations.TREE}),
    ("GET", r"/api/meta", False, lambda s, u, p, q, b: {
        "categories": CATEGORIES, "types": list(AD_TYPES), "report_reasons": REPORT_REASONS}),
    ("POST", r"/api/register", False, lambda s, u, p, q, b: s.register(b.get("name"), b.get("password"), b.get("location"))),
    ("POST", r"/api/login", False, lambda s, u, p, q, b: s.login(b.get("name"), b.get("password"))),
    ("GET", r"/api/me", True, lambda s, u, p, q, b: {"user": public_user(u)}),
    ("PUT", r"/api/me", True, lambda s, u, p, q, b: {"user": s.update_profile(u, b)}),
    ("GET", r"/api/ads", True, lambda s, u, p, q, b: {"ads": s.feed(u, q)}),
    ("POST", r"/api/ads", True, lambda s, u, p, q, b: {"ad": s.create_ad(u, b)}),
    ("GET", r"/api/my/ads", True, lambda s, u, p, q, b: {"ads": s.my_ads(u, q.get("status"))}),
    ("GET", r"/api/ads/(\d+)", True, lambda s, u, p, q, b: {"ad": s.get_ad(u, int(p[0]))}),
    ("POST", r"/api/ads/(\d+)/status", True, lambda s, u, p, q, b: {"ad": s.set_status(u, int(p[0]), b.get("status"))}),
    ("POST", r"/api/ads/(\d+)/respond", True, lambda s, u, p, q, b: {"chat": s.respond(u, int(p[0]))}),
    ("POST", r"/api/ads/(\d+)/report", True, lambda s, u, p, q, b: s.report(u, int(p[0]), b.get("reason"))),
    ("GET", r"/api/chats", True, lambda s, u, p, q, b: {"chats": s.chats(u)}),
    ("GET", r"/api/chats/(\d+)/messages", True, lambda s, u, p, q, b: {"messages": s.messages(u, int(p[0]), q.get("after"))}),
    ("POST", r"/api/chats/(\d+)/messages", True, lambda s, u, p, q, b: {"message": s.send_message(u, int(p[0]), b.get("text"))}),
    ("POST", r"/api/notifications/poll", True, lambda s, u, p, q, b: {"notifications": s.poll_notifications(u)}),
    ("POST", r"/api/logout", True, None),  # обрабатывается отдельно (нужен токен)
    ("GET", r"/api/reports", True, lambda s, u, p, q, b: {"reports": s.reports(u)}),
    ("POST", r"/api/reports/(\d+)/resolve", True, lambda s, u, p, q, b: s.resolve_report(u, int(p[0]), b.get("action"))),
    ("POST", r"/api/users/(\d+)/block", True, lambda s, u, p, q, b: s.block_user(u, int(p[0]), bool(b.get("blocked", True)))),
]
_COMPILED = [(m, re.compile("^" + pat + "$"), auth, fn) for m, pat, auth, fn in ROUTES]


class Handler(BaseHTTPRequestHandler):
    service = None
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt, *args):  # тише в консоли
        pass

    def _send(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, method):
        try:
            parsed = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ApiError(413, "Слишком большой запрос")
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
            except ValueError:
                raise ApiError(400, "Некорректный JSON")
            if not isinstance(body, dict):
                raise ApiError(400, "Ожидается JSON-объект")
            path_known = False
            for m, rx, auth, fn in _COMPILED:
                match = rx.match(parsed.path)
                if not match:
                    continue
                path_known = True
                if m != method:
                    continue
                user = None
                token = (self.headers.get("Authorization") or "").replace("Bearer ", "", 1).strip()
                if auth:
                    user = self.service.authenticate(token)
                if parsed.path == "/api/logout":
                    self._send(200, self.service.logout(token))
                else:
                    self._send(200, fn(self.service, user, match.groups(), query, body))
                return
            raise ApiError(405 if path_known else 404, "Метод не поддерживается" if path_known else "Не найдено")
        except ApiError as e:
            self._send(e.status, {"error": e.message})
        except Exception:  # непредвиденная ошибка не должна ронять сервер
            self._send(500, {"error": "Внутренняя ошибка сервера"})

    def do_GET(self): self._handle("GET")
    def do_POST(self): self._handle("POST")
    def do_PUT(self): self._handle("PUT")


def make_server(host="127.0.0.1", port=8000, db_path="neighbors.db", demo=False):
    service = Service(Database(db_path))
    service.ensure_moderator()
    if demo:
        from .seed import seed_demo
        seed_demo(service)
    handler = type("BoundHandler", (Handler,), {"service": service})
    server = ThreadingHTTPServer((host, port), handler)
    server.service = service
    return server
