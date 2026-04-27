# IPC Parser — Парсер Международной патентной классификации (МПК)

Инструмент для парсинга XML-файлов МПК с сайта [WIPO](https://www.wipo.int/classifications/ipc/) и преобразования в **JSON**, **Excel** (двуязычный).

---

## 🚀 Установка

```bash
git clone https://github.com/Hildbjorn/ipc-parser.git
cd ipc-parser
pip install -r requirements.txt
```

Скачайте XML с [WIPO](https://www.wipo.int/classifications/ipc/en/ITsupport/Version20260101/) и положите в `src/data/input/EN_ipc_scheme_20260101.xml`.

Создайте `.env` файл в `src/`:
```
API_KEY=ваш-api-ключ
API_BASE_URL=https://api.timeweb.ai/v1
```

---

## ⚡ Быстрый старт

```bash
python src/parsers/build_all.py
```

Этапы:
1. **Парсинг XML** → `ipc_scheme_en.json`
2. **Перевод через API** → `ipc_scheme_ru.json` (с кешированием, можно прерывать)
3. **Excel** → `IPC_Flat_20260101.xlsx` (вкладки EN и RU)

---

## 📁 Структура проекта

```
src/
├── parsers/
│   ├── build_all.py         # Полный цикл: XML → JSON → перевод → Excel
│   ├── xml_to_json_en.py    # Парсинг XML в английский JSON
│   ├── translate_json.py    # Перевод JSON через LLM API
│   ├── json_to_xlsx.py      # Конвертация JSON в Excel (две вкладки)
│   └── utils.py             # Общие функции
├── data/
│   ├── input/               # Исходный XML
│   ├── output/
│   │   ├── json/            # ipc_scheme_en.json, ipc_scheme_ru.json
│   │   └── xlsx/            # IPC_Flat_20260101.xlsx
│   └── cache/               # Кеш переводов и прогресс
├── .env                     # API_KEY
└── settings.py              # Настройки
```

---

## 📊 Excel-файл

Две вкладки: `IPC_Scheme_EN` и `IPC_Scheme_RU` (заголовки и значения Type переведены).

| Столбец | Описание |
|---------|----------|
| Symbol | Индекс МПК (ключ для ВПР) |
| FullTitle | Полный иерархический заголовок |
| Type | Тип рубрики (Раздел, Класс, Подкласс...) |
| Section, Class, Subclass | Составные части индекса |

**Формула ВПР:**
```
=ВПР(D2; '[IPC_Flat_20260101.xlsx]IPC_Scheme_RU'!$D:$F; 3; ЛОЖЬ)
```

---

## 🔧 Отдельные запуски

```bash
python src/parsers/xml_to_json_en.py      # Только парсинг XML
python src/parsers/translate_json.py      # Только перевод (продолжит с места)
python src/parsers/json_to_xlsx.py        # Только создание Excel
```

---

## ⚙️ Настройки (settings.py)

```python
BATCH_SIZE = 20              # Записей в одном запросе к API
DELAY_BETWEEN_BATCHES = 1    # Пауза между запросами (сек)
MAX_RETRIES = 3              # Повторных попыток при ошибке
TRANSLATION_MODEL = "deepseek/deepseek-chat"
```

---

## 📄 Лицензия

MIT License.