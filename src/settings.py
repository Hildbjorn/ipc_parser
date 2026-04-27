# Файлы
INPUT_XML = "ipc_scheme_20260101.xml"
OUTPUT_XLSX = "IPC_Flat_20260101.xlsx"
TRANSLATION_CACHE = "ipc_translation_cache.json"

# Параметры перевода
BATCH_SIZE = 30              # Фраз в одном запросе к API
DELAY_BETWEEN_BATCHES = 1    # Задержка между запросами (сек)
ENABLE_TRANSLATION = True    # Включить/выключить перевод

# API-ключ
API_KEY = "ваш-ключ"
API_BASE_URL = "https://api.timeweb.ai/v1"