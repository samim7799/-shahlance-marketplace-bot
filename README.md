# Telegram Marketplace Bot

Buyer + seller marketplace starter for lawful, authorized digital products/services.

## Run
pip install -r requirements.txt
python main.py

## Render
Use a Background Worker.
Build: pip install -r requirements.txt
Start: python main.py

Environment variables:
BOT_TOKEN = your BotFather token (keep secret)
ADMIN_ID = 8987680232
CURRENCY = USD
SUPPORT_USERNAME = your support username

For production, replace SQLite with PostgreSQL/durable storage and connect only lawful, supported payment providers.
Do not upload your real .env or BotFather token to GitHub.
