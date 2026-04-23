Система «Snapshot Freeze» для Tableau
О чем проект:
Инструмент для фиксации («заморозки») данных из витрин в архивные таблицы Vertica. Это позволяет сохранять состояние отчетов на момент закрытия периода, исключая проблему изменения исторических данных.

Как запустить разработчику:

Клонировать репозиторий.
Создать и активировать окружение: python -m venv venv.
Установить зависимости: pip install -r requirements.txt.
Создать .env на основе .env.example.
Запустить бэкенд: python main.py.

Выбор БД через флаг

Поддерживаются 2 backend-режима через переменную окружения FREEZER_DB_BACKEND:

- vertica (боевой режим)
- sqlite (локальный режим без Vertica)

Пример для Vertica:

FREEZER_DB_BACKEND=vertica
VERTICA_HOST=...
VERTICA_PORT=5433
VERTICA_USER=...
VERTICA_PASSWORD=...
VERTICA_DB=...
VERTICA_SCHEMA=DM

Пример для локального запуска без Vertica:

FREEZER_DB_BACKEND=sqlite
FREEZER_SQLITE_PATH=workflow_freeze.db

Логика:

Инициатор запрашивает заморозку через Tableau Extension.
Система проверяет права и отправляет уведомление в Telegram.
После аппрува формируется SQL на базе шаблонов из report_registry.py и данные уходят в SANDBOX.FROZEN_DATA.

Тестирование локально
В Tableau детальный отчет выгрузить в Tableau Desktop. Далее добавить через extention локальный файл trex на страницу. 