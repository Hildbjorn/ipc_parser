import pandas as pd
from lxml import etree
import re
import warnings
from datetime import datetime
from openai import OpenAI
import json
import time
from pathlib import Path

warnings.filterwarnings('ignore')

# =============================================================================
# НАСТРОЙКИ
# =============================================================================
INPUT_XML = "EN_ipc_scheme_20260101.xml"
OUTPUT_XLSX = "IPC_Flat_20260101.xlsx"
TRANSLATION_CACHE = "ipc_translation_cache.json"
BATCH_SIZE = 50  # Количество фраз для перевода за один запрос
DELAY_BETWEEN_BATCHES = 2  # Задержка между запросами в секундах

print(f"Чтение файла: {INPUT_XML}...")
tree = etree.parse(INPUT_XML)
root = tree.getroot()

ns = root.nsmap
default_ns = ns.get(None, 'http://www.wipo.int/classifications/ipc/masterfiles')
print(f"Пространство имен: {default_ns}")

# =============================================================================
# КЛИЕНТ OPENAI
# =============================================================================
client = OpenAI(
    api_key="sk-J7kne9iitlZZWGjaCVbbhg",
    base_url="https://api.timeweb.ai/v1",
)

# =============================================================================
# КОНСТАНТЫ
# =============================================================================
KIND_LEVEL = {
    's': 1, 't': 2, 'c': 3, 'u': 4, 'm': 5, 'g': 2, 'i': 2, 'n': 2,
}

KIND_TYPE = {
    's': 'Section', 't': 'Subsection', 'c': 'Class', 'u': 'Subclass',
    'm': 'Group', 'g': 'GuideHeading', 'i': 'Informative', 'n': 'Note',
}

# =============================================================================
# ФУНКЦИИ ИЗВЛЕЧЕНИЯ ЗАГОЛОВКОВ
# =============================================================================
def extract_title_text(ipc_entry):
    """Извлекает текст заголовка и считает точки."""
    ns_prefix = f'{{{default_ns}}}'
    
    text_body = ipc_entry.find(f'{ns_prefix}textBody')
    if text_body is None:
        return "", 0, ""
    
    title_elem = text_body.find(f'{ns_prefix}title')
    if title_elem is None:
        full_text = "".join(text_body.itertext()).strip()
        full_text = re.sub(r'\s+', ' ', full_text)
        return full_text, 0, full_text
    
    title_parts = title_elem.findall(f'{ns_prefix}titlePart')
    
    if not title_parts:
        full_text = "".join(title_elem.itertext()).strip()
        full_text = re.sub(r'\s+', ' ', full_text)
        return full_text, 0, full_text
    
    all_text = ""
    for tp in title_parts:
        tp_text = "".join(tp.itertext())
        all_text += tp_text
    
    all_text = all_text.strip()
    all_text = re.sub(r'\s+', ' ', all_text)
    
    if not all_text:
        return "", 0, ""
    
    dot_count = 0
    clean_text = all_text
    
    dot_match = re.match(r'^(\. )+', all_text)
    if dot_match:
        dot_str = dot_match.group()
        dot_count = len(dot_str.split())
        clean_text = all_text[dot_match.end():].strip()
    
    return all_text, dot_count, clean_text


def determine_group_type(symbol, kind):
    """Определяет тип группы."""
    if kind != 'm' or symbol is None:
        return KIND_TYPE.get(kind, 'Unknown')
    
    if '/' not in symbol:
        return 'Group'
    
    parts = symbol.split('/')
    subgroup_part = parts[-1] if len(parts) > 1 else ""
    
    if re.match(r'^\d{1,3}00$', subgroup_part):
        return 'MainGroup'
    else:
        return 'Subgroup'


# =============================================================================
# ПАРСИНГ XML (сбор всех записей + уникальных фраз)
# =============================================================================
records = []
unique_phrases = set()  # Для сбора уникальных английских фраз

print("Парсинг XML и сбор уникальных фраз...")

def process_ipc_entry(elem, parent_symbol, parent_title_parts, parent_kind):
    """Рекурсивный обход ipcEntry."""
    symbol = elem.get('symbol')
    kind = elem.get('kind')
    entry_type = determine_group_type(symbol, kind)
    
    raw_title, dot_count, clean_text = extract_title_text(elem)
    
    # Формируем иерархический заголовок (только для 'm' групп)
    title_parts = parent_title_parts.copy()
    
    if dot_count == 0:
        if clean_text:
            title_parts = [clean_text]
        else:
            title_parts = []
    else:
        title_parts = title_parts[:dot_count]
        if clean_text:
            title_parts.append(clean_text)
    
    full_title = " → ".join(title_parts) if title_parts else ""
    
    # Определяем родительский символ
    my_parent = parent_symbol if symbol else ""
    
    # Разбираем символ на части
    section = ""
    class_code = ""
    subclass = ""
    main_group = ""
    
    if symbol:
        section = symbol[0] if len(symbol) > 0 else ""
        if len(symbol) >= 3:
            class_code = symbol[:3]
        if '/' in symbol:
            subclass = symbol.split('/')[0]
            parts = symbol.split('/')
            if len(parts) == 2:
                main_group = f"{parts[0]}/00"
    
    # Определяем остаточную рубрику
    is_residual = (
        '99/00' in (symbol or '') or
        '99Z' in (symbol or '') or
        'not provided for' in clean_text.lower() or
        'not otherwise provided for' in clean_text.lower()
    )
    
    # Добавляем запись (только для значимых kind)
    if kind in ('s', 't', 'c', 'u', 'm') and symbol:
        # Сохраняем отдельные части заголовка для перевода
        title_parts_for_record = []
        if dot_count == 0:
            if clean_text:
                title_parts_for_record = [clean_text]
        else:
            title_parts_for_record = title_parts
        
        records.append({
            'Level': KIND_LEVEL.get(kind, 0),
            'Kind': kind,
            'Type': entry_type,
            'Symbol': symbol,
            'ParentSymbol': my_parent,
            'FullTitle_EN': full_title,
            'TitleParts_EN': '|||'.join(title_parts_for_record),  # Разделитель для частей
            'RawTitle_EN': clean_text,
            'DotCount': dot_count,
            'Section': section,
            'Class': class_code,
            'Subclass': subclass,
            'MainGroup': main_group if entry_type == 'Subgroup' else symbol,
            'IsResidual': is_residual
        })
        
        # Собираем уникальные фразы
        for part in title_parts_for_record:
            if part and len(part.strip()) > 1:  # Исключаем пустые и однобуквенные
                unique_phrases.add(part.strip())
    
    # Рекурсивно обрабатываем дочерние элементы
    for child in elem:
        if child.tag.endswith('ipcEntry'):
            process_ipc_entry(child, symbol or parent_symbol, title_parts, kind)


# Запускаем парсинг
process_ipc_entry(root, '', [], '')

print(f"Обработано записей: {len(records)}")
print(f"Уникальных фраз для перевода: {len(unique_phrases)}")

# =============================================================================
# ПЕРЕВОД УНИКАЛЬНЫХ ФРАЗ
# =============================================================================
def load_translation_cache():
    """Загружает кеш переводов из файла."""
    if Path(TRANSLATION_CACHE).exists():
        with open(TRANSLATION_CACHE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_translation_cache(cache):
    """Сохраняет кеш переводов в файл."""
    with open(TRANSLATION_CACHE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def translate_batch(phrases_batch):
    """Переводит батч фраз через API."""
    if not phrases_batch:
        return {}
    
    # Формируем промпт
    phrases_list = "\n".join([f"{i+1}. {phrase}" for i, phrase in enumerate(phrases_batch)])
    
    prompt = f"""Переведи следующие технические термины и фразы Международной патентной классификации (МПК) с английского на русский язык.
    
Важно:
- Сохраняй техническую точность перевода
- Используй стандартную терминологию Роспатента
- Переводи ТОЛЬКО фразы, не добавляй пояснений
- Верни результат в формате JSON: {{"оригинал": "перевод"}}

Фразы для перевода:
{phrases_list}"""

    try:
        response = client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[
                {"role": "system", "content": "Ты - профессиональный переводчик технических текстов в области патентоведения. Переводи точно и лаконично."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4000
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Пытаемся извлечь JSON из ответа
        # Ищем JSON в фигурных скобках
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            try:
                translations = json.loads(json_match.group())
                return translations
            except json.JSONDecodeError:
                pass
        
        # Если не получилось - пробуем построчно
        print(f"  Предупреждение: не удалось распарсить JSON, пробую построчный разбор")
        translations = {}
        lines = result_text.split('\n')
        for line in lines:
            line = line.strip()
            # Пропускаем пустые строки и маркеры
            if not line or line.startswith('```') or line.startswith('{') or line.startswith('}'):
                continue
            # Ищем пары "оригинал": "перевод" или оригинал - перевод
            if '":' in line or '": ' in line:
                parts = line.split('":', 1)
                if len(parts) == 2:
                    key = parts[0].strip().strip('"').strip()
                    value = parts[1].strip().strip('"').strip().rstrip(',')
                    if key and value:
                        translations[key] = value
            elif ' - ' in line:
                parts = line.split(' - ', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    if key and value:
                        translations[key] = value
        
        return translations
    
    except Exception as e:
        print(f"  Ошибка при переводе: {e}")
        return {}

# Загружаем кеш переводов
translation_cache = load_translation_cache()
print(f"Загружено переводов из кеша: {len(translation_cache)}")

# Определяем фразы, которые нужно перевести
phrases_to_translate = [p for p in unique_phrases if p not in translation_cache]
print(f"Нужно перевести: {len(phrases_to_translate)} фраз")

if phrases_to_translate:
    # Разбиваем на батчи
    batches = [phrases_to_translate[i:i + BATCH_SIZE] for i in range(0, len(phrases_to_translate), BATCH_SIZE)]
    print(f"Всего батчей: {len(batches)}")
    
    for batch_num, batch in enumerate(batches, 1):
        print(f"Перевод батча {batch_num}/{len(batches)} ({len(batch)} фраз)...")
        
        translations = translate_batch(batch)
        
        if translations:
            translation_cache.update(translations)
            print(f"  Переведено: {len(translations)} фраз")
        else:
            print(f"  Ошибка: пустой ответ от API")
        
        # Сохраняем кеш после каждого батча (на случай сбоя)
        save_translation_cache(translation_cache)
        
        # Задержка между запросами
        if batch_num < len(batches):
            print(f"  Ожидание {DELAY_BETWEEN_BATCHES} сек...")
            time.sleep(DELAY_BETWEEN_BATCHES)
    
    print(f"Перевод завершен. Всего в кеше: {len(translation_cache)} фраз")
else:
    print("Все фразы уже есть в кеше, перевод не требуется.")

# =============================================================================
# ПРИМЕНЕНИЕ ПЕРЕВОДОВ К ЗАПИСЯМ
# =============================================================================
print("Применение переводов к записям...")

def translate_title_parts(parts_str, cache):
    """Переводит части заголовка."""
    if not parts_str:
        return "", ""
    
    parts = parts_str.split('|||')
    translated_parts = []
    
    for part in parts:
        part = part.strip()
        if part in cache:
            translated_parts.append(cache[part])
        else:
            translated_parts.append(part)  # Если перевода нет - оставляем оригинал
    
    full_title_ru = " → ".join(translated_parts)
    raw_title_ru = translated_parts[-1] if translated_parts else ""
    
    return full_title_ru, raw_title_ru

for record in records:
    full_ru, raw_ru = translate_title_parts(record['TitleParts_EN'], translation_cache)
    record['FullTitle_RU'] = full_ru
    record['RawTitle_RU'] = raw_ru

# =============================================================================
# СОЗДАНИЕ ДАТАФРЕЙМОВ ДЛЯ ОБЕИХ ВКЛАДОК
# =============================================================================
# Общие столбцы для обеих вкладок
common_columns = ['Level', 'Kind', 'Type', 'Symbol', 'ParentSymbol', 'DotCount',
                  'Section', 'Class', 'Subclass', 'MainGroup', 'IsResidual']

# Английская вкладка
df_en = pd.DataFrame(records)
df_en['FullTitle'] = df_en['FullTitle_EN']
df_en['RawTitle'] = df_en['RawTitle_EN']
df_en = df_en[common_columns + ['FullTitle', 'RawTitle']]
df_en = df_en.sort_values(by=['Symbol']).reset_index(drop=True)

# Русская вкладка
df_ru = pd.DataFrame(records)
df_ru['FullTitle'] = df_ru['FullTitle_RU']
df_ru['RawTitle'] = df_ru['RawTitle_RU']
df_ru = df_ru[common_columns + ['FullTitle', 'RawTitle']]
df_ru = df_ru.sort_values(by=['Symbol']).reset_index(drop=True)

# Статистика
print(f"\nСтатистика:")
print(f"  Всего записей: {len(df_en)}")
print(f"  Подклассов: {len(df_en[df_en['Type'] == 'Subclass'])}")
print(f"  Основных групп: {len(df_en[df_en['Type'] == 'MainGroup'])}")
print(f"  Подгрупп: {len(df_en[df_en['Type'] == 'Subgroup'])}")

# Проверка качества перевода
empty_ru = df_ru['FullTitle'].isna().sum() + (df_ru['FullTitle'] == '').sum()
print(f"  Записей без русского перевода: {empty_ru}")

# =============================================================================
# СОХРАНЕНИЕ В XLSX С ДВУМЯ ВКЛАДКАМИ
# =============================================================================
print(f"\nСохранение в {OUTPUT_XLSX}...")

with pd.ExcelWriter(OUTPUT_XLSX, engine='openpyxl') as writer:
    # Вкладка EN
    df_en.to_excel(writer, sheet_name='IPC_Scheme_EN', index=False)
    
    # Вкладка RU
    df_ru.to_excel(writer, sheet_name='IPC_Scheme_RU', index=False)
    
    # Настройка ширины столбцов для обеих вкладок
    for sheet_name in ['IPC_Scheme_EN', 'IPC_Scheme_RU']:
        worksheet = writer.sheets[sheet_name]
        
        column_widths = {
            'A': 8,   # Level
            'B': 8,   # Kind
            'C': 14,  # Type
            'D': 20,  # Symbol
            'E': 20,  # ParentSymbol
            'F': 10,  # DotCount
            'G': 10,  # Section
            'H': 10,  # Class
            'I': 14,  # Subclass
            'J': 14,  # MainGroup
            'K': 12,  # IsResidual
            'L': 80,  # FullTitle
            'M': 50,  # RawTitle
        }
        
        for col_letter, width in column_widths.items():
            worksheet.column_dimensions[col_letter].width = width
        
        # Закрепляем первую строку
        worksheet.freeze_panes = 'A2'
        
        # Автофильтр
        last_col = 'M'
        worksheet.auto_filter.ref = f'A1:{last_col}{len(df_en) + 1}'

print(f"Готово! Файл: {OUTPUT_XLSX}")
print(f"Дата/время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Файл кеша переводов: {TRANSLATION_CACHE}")