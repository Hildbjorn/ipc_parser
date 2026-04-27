"""
Все настройки проекта: пути, параметры API, параметры перевода.
Чувствительные данные (API_KEY) загружаются из файла .env в корне проекта.
"""

import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Базовые пути
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
JSON_DIR = OUTPUT_DIR / "json"
XLSX_DIR = OUTPUT_DIR / "xlsx"
CACHE_DIR = DATA_DIR / "cache"

for dir_path in [INPUT_DIR, OUTPUT_DIR, JSON_DIR, XLSX_DIR, CACHE_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Входной файл
XML_SCHEME = INPUT_DIR / "EN_ipc_scheme_20260101.xml"

# Выходные файлы
JSON_EN = JSON_DIR / "ipc_scheme_en.json"
JSON_RU = JSON_DIR / "ipc_scheme_ru.json"
XLSX_OUTPUT = XLSX_DIR / "IPC_Flat_20260101.xlsx"

# Кеш и прогресс перевода
TRANSLATION_CACHE = CACHE_DIR / "translation_cache.json"
PROGRESS_FILE = CACHE_DIR / "translation_progress.json"

# API
API_KEY = os.getenv("API_KEY", "")
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.timeweb.ai/v1")

# Параметры перевода
BATCH_SIZE = 20
DELAY_BETWEEN_BATCHES = 1
MAX_RETRIES = 3
TRANSLATION_MODEL = "deepseek/deepseek-chat"

VERBOSE = True
IPC_VERSION = "2026.01"