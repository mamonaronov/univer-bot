# Справочник Еврейского университета

Telegram-бот с кнопками по материалам [j-univer.ru](https://j-univer.ru/). Только справочник: без пользователей, админки и статистики. Данные лежат в SQLite и рассчитаны на правку в [DB Browser for SQLite](https://sqlitebrowser.org/).

Бот и **mihomo** (Clash Meta) работают **в одном контейнере**. Telegram с VPS в России недоступен напрямую: aiogram ходит в Bot API через SOCKS5 mihomo (`aiohttp-socks`).

## Запуск

```bash
cp .env.example .env
# впишите BOT_TOKEN от @BotFather

mkdir -p data mihomo-data
docker compose up -d --build
docker compose logs -f bot
```

Локально, если Telegram доступен без прокси:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m catalog.seed data/catalog.seed.sqlite3
cp data/catalog.seed.sqlite3 data/catalog.sqlite3
BOT_TOKEN=... TELEGRAM_PROXY_URL= DB_PATH=data/catalog.sqlite3 SEED_DB_PATH=data/catalog.seed.sqlite3 python bot.py
```

## База данных

Файл тома: `data/catalog.sqlite3` (при первом старте копируется из `catalog.seed.sqlite3`).

| Таблица | Назначение |
|---|---|
| `pages` | Дерево разделов. `parent_id` пустой — кнопки главного меню |
| `links` | URL-кнопки под текстом (сайт, PDF, формы) |
| `meta` | `root_page_id`, источник, версия схемы |

Колонки `pages`, которые правят вручную:

- `title` — текст кнопки и заголовок
- `body` — текст сообщения, HTML Telegram (`<b>`, `<i>`, `<a href="...">`)
- `sort_order` — чем меньше, тем выше кнопка
- `is_visible` — `1` показать, `0` скрыть
- `source_url` — откуда спарсено, бот не показывает
- `notes` — заметка редактора, бот не показывает

После правок в DB Browser бота перезапускать не нужно: каждый запрос читает SQLite заново. Не держите файл открытым на запись одновременно с ботом без WAL; WAL уже включён.

Обновить каталог с сайта (перезапишет `data/catalog.seed.sqlite3`, текущий `catalog.sqlite3` не трогает, пока не скопируете сами):

```bash
python -m catalog.seed data/catalog.seed.sqlite3
```

## Прокси

Внутри контейнера:

1. стартует `mihomo -d /app/mihomo` (конфиг `deploy/mihomo/config.yaml`);
2. mixed-port `127.0.0.1:11808`;
3. бот использует `TELEGRAM_PROXY_URL=socks5://127.0.0.1:11808`.

Группа `AUTO` — **fallback**, не url-test. Health-check: `https://api.telegram.org/bot`, `expected-status: 404`. Белые списки (sub4/sub5) в AUTO не входят.

Polling и probe/ping — **разные** HTTP-сессии. Зависший SOCKS: коннектор бросается, сессия пересоздаётся, backoff, процесс не падает.

Подписки mihomo кэшируются в `./mihomo-data`. `network_mode: host` не нужен: прокси слушает localhost внутри того же контейнера.

## Команды

- `/start`, `/menu` — корень справочника
- любое другое сообщение — то же главное меню
- кнопки — разделы, «Назад», «В начало», PDF и страницы сайта
