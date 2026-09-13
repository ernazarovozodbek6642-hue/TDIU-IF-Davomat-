import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

ADMINS_RAW = os.getenv("ADMINS", "5589013665")
ADMINS: list[int] = [int(a.strip()) for a in ADMINS_RAW.split(",") if a.strip().isdigit()]

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    ""
).strip()
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = 'postgresql+asyncpg://' + DATABASE_URL.removeprefix('postgres://')
elif DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = 'postgresql+asyncpg://' + DATABASE_URL.removeprefix('postgresql://')

SPREADSHEET_ID: str = os.getenv("SPREADSHEET_ID", "").strip()
SPREADSHEET_NAME: str = os.getenv("SPREADSHEET_NAME", "Dars jadvali 2025")

_cred_file = os.getenv("GOOGLE_CREDENTIALS", "credentials.json")
if not os.path.isabs(_cred_file):
    GOOGLE_CREDENTIALS = str(BASE_DIR / _cred_file)
else:
    GOOGLE_CREDENTIALS = _cred_file

# Agar ko'rsatilgan nomdagi fayl bo'lmasa, json fayllardan avtomatik qidirish
if not os.path.exists(GOOGLE_CREDENTIALS):
    json_files = list(BASE_DIR.glob("*.json"))
    for jf in json_files:
        if "dars-jadvali" in jf.name or "credentials" in jf.name:
            GOOGLE_CREDENTIALS = str(jf)
            break


def validate_runtime_config() -> None:
    """Fail early with a readable message when server secrets are incomplete."""
    errors = []
    if not BOT_TOKEN or ':' not in BOT_TOKEN:
        errors.append('BOT_TOKEN kiritilmagan yoki noto‘g‘ri')
    if not ADMINS:
        errors.append('ADMINS ichida kamida bitta Telegram ID bo‘lishi kerak')
    if not DATABASE_URL.startswith('postgresql+asyncpg://'):
        errors.append('DATABASE_URL PostgreSQL/asyncpg manzili emas')
    if not SPREADSHEET_ID:
        errors.append('SPREADSHEET_ID kiritilmagan')
    if not os.getenv('GOOGLE_CREDENTIALS_JSON', '').strip() and not os.path.isfile(GOOGLE_CREDENTIALS):
        errors.append(f'Google credentials topilmadi: {GOOGLE_CREDENTIALS}')
    if errors:
        raise RuntimeError('Server konfiguratsiyasi xato:\n- ' + '\n- '.join(errors))
