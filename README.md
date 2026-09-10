# Справочник Еврейского университета

Telegram-бот с кнопками по материалам [j-univer.ru](https://j-univer.ru/). Только справочник: без пользователей, админки и статистики. Данные лежат в SQLite в репозитории и рассчитаны на правку в [DB Browser for SQLite](https://sqlitebrowser.org/).

Бот и **mihomo** (Clash Meta) работают **в одном контейнере**. Telegram с VPS в России недоступен напрямую: aiogram ходит в Bot API через SOCKS5 mihomo (`aiohttp-socks`).

## Запуск

На другой машине достаточно клонировать репозиторий и вписать токен:

```bash
git clone <url> univer-bot
cd univer-bot
cp .env.example .env
# впишите BOT_TOKEN от @BotFather

docker compose up -d --build
```

Справочник, конфиг mihomo и остальное уже в git. В `.env` нужен только `BOT_TOKEN`.

Локально, если Telegram доступен без прокси:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
BOT_TOKEN=... TELEGRAM_PROXY_URL= python bot.py
```

База по умолчанию: `data/catalog.sqlite3`.

## База данных

Файл в репозитории: `data/catalog.sqlite3`. Его же читает бот.

| Таблица | Назначение |
|---|---|
| `pages` | Дерево разделов. `parent_id` пустой — кнопки главного меню |
| `links` | Необязательные URL-кнопки, если добавить вручную |
| `meta` | `root_page_id`, источник, версия схемы |

Колонки `pages`, которые правят вручную:

- `title` — текст кнопки и заголовок
- `body` — текст сообщения, HTML Telegram (`<b>`, `<i>`, `mailto`)
- `sort_order` — чем меньше, тем выше кнопка
- `is_visible` — `1` показать, `0` скрыть
- `source_url` — откуда спарсено, бот не показывает
- `notes` — заметка редактора, бот не показывает

После правок в DB Browser бота перезапускать не нужно: каждый запрос читает SQLite заново. Не держите файл открытым на запись одновременно с ботом без WAL; WAL уже включён.

Обновить каталог с сайта (перезапишет `data/catalog.sqlite3`):

```bash
python -m catalog.seed
```

## Прокси

Внутри контейнера:

1. стартует `mihomo -d /app/mihomo` (конфиг `deploy/mihomo/config.yaml`);
2. mixed-port `127.0.0.1:11808`;
3. бот использует `TELEGRAM_PROXY_URL=socks5://127.0.0.1:11808`.

Подписки mihomo качаются при старте (кэш `./mihomo-data`, в git не нужен).

## Команды

- `/start`, `/menu` — корень справочника
- любое другое сообщение — то же главное меню
- кнопки — разделы, «Назад», «В начало»
