"""Infrastructure: REST-клиент (SAD 5.2: NetworkClient)."""
import requests

from ..domain.errors import AppError, AuthError, NetworkError

TIMEOUT = 8


class NetworkClient:
    def __init__(self):
        self.base_url = ""
        self.token = ""

    def configure(self, base_url, token=""):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def request(self, method, path, body=None, params=None, base_url=None, auth=True):
        """base_url/auth=False — публичный запрос, не затрагивающий состояние сессии."""
        base = (base_url or self.base_url).rstrip("/")
        if not base:
            raise NetworkError("Не задан адрес сервера")
        token = self.token if auth else ""
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            resp = requests.request(method, f"{base}/api{path}", json=body, params=params,
                                    headers=headers, timeout=TIMEOUT)
        except requests.RequestException:
            raise NetworkError("Нет соединения с сервером")
        try:
            data = resp.json()
        except ValueError:
            raise AppError("Некорректный ответ сервера", resp.status_code)
        if resp.status_code >= 400:
            message = data.get("error", "Ошибка сервера") if isinstance(data, dict) else "Ошибка сервера"
            if resp.status_code == 401 and token:
                raise AuthError(message, 401)
            raise AppError(message, resp.status_code)
        return data
