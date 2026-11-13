Neighborly-assistance-main

Мобильный клиент (Kivy → APK через Buildozer) + REST-сервер на стандартной библиотеке Python.
Основа — документы Vision и SAD: Clean Architecture + MVVM.

## Структура
```
main.py                  точка входа Android/desktop
buildozer.spec           сборка APK
client/
  domain/                сущности, справочники, интерфейсы репозиториев   (SAD: Domain)
  application/usecases.py сценарии (CreateAd, RespondToAd, CloseAd, …)     (SAD: Application)
  infrastructure/        NetworkClient (requests), репозитории, сессия     (SAD: Infrastructure)
  presentation/          ViewModel'и (без Kivy) + экраны Kivy              (SAD: Presentation)
  di.py, app.py          сборка зависимостей, навигация, опрос уведомлений
server/                  REST API + SQLite + бизнес-правила
tests/                   сквозные тесты сервера и клиентских слоёв
```

## Запуск сервера
```
python -m server --demo          # http://0.0.0.0:8000, БД neighbors.db
```
Демо-жильцы: anna / boris / clara (пароль 1234). Модератор: **moderator / moderator**.

## Запуск клиента на ПК
```
pip install kivy==2.3.0 requests
python main.py
```
Адрес сервера вводится на экране входа (по умолчанию http://127.0.0.1:8000;
в эмуляторе Android — http://10.0.2.2:8000; на телефоне — IP компьютера в Wi-Fi).

## Сборка APK
```
buildozer android debug
```
Android 9+ по умолчанию запрещает HTTP без TLS. Для тестов по http:// добавьте в `buildozer.spec`
`android.extra_manifest_application_arguments` (файл с `android:usesCleartextTraffic="true"`)
либо поднимите сервер за HTTPS.

## Тесты
```
python -m unittest discover -s tests -t .
```
