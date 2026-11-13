import argparse

from .http_api import make_server


def main():
    ap = argparse.ArgumentParser(description="Сервер «Соседская помощь»")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--db", default="neighbors.db")
    ap.add_argument("--demo", action="store_true", help="добавить демо-жильцов и объявления")
    a = ap.parse_args()
    srv = make_server(a.host, a.port, a.db, a.demo)
    print(f"Сервер: http://{a.host}:{a.port}  (БД: {a.db}); модератор: moderator / moderator")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
