# json_to_xlsx.py — Конвертер JSON → XLSX с двумя вкладками EN и RU
"""
Создаёт IPC_Flat_20260101.xlsx с вкладками:
- IPC_Scheme_EN — английская версия (заголовки EN, значения EN)
- IPC_Scheme_RU — русская версия (заголовки RU, значения RU)

Формат оптимизирован для ВПР():
- Symbol (ключ для поиска)
- ParentSymbol (родительская рубрика)
- FullTitle (полный заголовок)
- Section, Class, Subclass, MainGroup (для фильтрации)
"""

import json
from datetime import datetime
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from settings import JSON_EN, JSON_RU, XLSX_DIR, IPC_VERSION


# Перевод значений Type
TYPE_TRANSLATION = {
    'Section': 'Раздел',
    'Subsection': 'Подраздел',
    'Class': 'Класс',
    'Subclass': 'Подкласс',
    'MainGroup': 'Основная группа',
    'Subgroup': 'Подгруппа',
    'Group': 'Группа',
    'GuideHeading': 'Информационный заголовок',
    'Informative': 'Информационный',
    'Note': 'Примечание',
    'Unknown': 'Неизвестно'
}

# Заголовки столбцов
EN_COLUMNS = {
    'Level': 'Level',
    'Kind': 'Kind',
    'Type': 'Type',
    'Symbol': 'Symbol',
    'ParentSymbol': 'ParentSymbol',
    'FullTitle': 'FullTitle',
    'RawTitle': 'RawTitle',
    'DotCount': 'DotCount',
    'Section': 'Section',
    'Class': 'Class',
    'Subclass': 'Subclass',
    'MainGroup': 'MainGroup',
    'IsResidual': 'IsResidual'
}

RU_COLUMNS = {
    'Level': 'Уровень',
    'Kind': 'Тип (код)',
    'Type': 'Тип рубрики',
    'Symbol': 'Индекс МПК',
    'ParentSymbol': 'Родительский индекс',
    'FullTitle': 'Полный заголовок',
    'RawTitle': 'Краткий заголовок',
    'DotCount': 'Уровень вложенности',
    'Section': 'Раздел',
    'Class': 'Класс',
    'Subclass': 'Подкласс',
    'MainGroup': 'Основная группа',
    'IsResidual': 'Остаточная рубрика'
}


def load_json(path: Path) -> list:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def json_to_dataframe(records: list, lang: str = 'EN') -> pd.DataFrame:
    """Преобразует записи JSON в DataFrame для Excel."""
    columns = EN_COLUMNS if lang == 'EN' else RU_COLUMNS
    
    rows = []
    for r in tqdm(records, desc=f"   Обработка записей ({lang})", unit="зап."):
        type_value = r.get('Type', '')
        if lang == 'RU':
            type_value = TYPE_TRANSLATION.get(type_value, type_value)
        
        rows.append({
            columns['Level']: r.get('Level', ''),
            columns['Kind']: r.get('Kind', ''),
            columns['Type']: type_value,
            columns['Symbol']: r.get('Symbol', ''),
            columns['ParentSymbol']: r.get('ParentSymbol', ''),
            columns['FullTitle']: r.get('FullTitle', ''),
            columns['RawTitle']: r.get('RawTitle', ''),
            columns['DotCount']: r.get('DotCount', 0),
            columns['Section']: r.get('Section', ''),
            columns['Class']: r.get('Class', ''),
            columns['Subclass']: r.get('Subclass', ''),
            columns['MainGroup']: r.get('MainGroup', ''),
            columns['IsResidual']: 'Да' if r.get('IsResidual', False) else 'Нет' if lang == 'RU' else r.get('IsResidual', False)
        })
    return pd.DataFrame(rows)


def create_xlsx(en_path: Path, ru_path: Path, output_path: Path):
    """Создаёт XLSX с двумя вкладками."""
    print(f"\n📖 Загрузка EN: {en_path.name}")
    en_records = load_json(en_path)
    df_en = json_to_dataframe(en_records, 'EN')
    df_en = df_en.sort_values(EN_COLUMNS['Symbol']).reset_index(drop=True)
    
    print(f"\n📖 Загрузка RU: {ru_path.name}")
    ru_records = load_json(ru_path)
    df_ru = json_to_dataframe(ru_records, 'RU')
    df_ru = df_ru.sort_values(RU_COLUMNS['Symbol']).reset_index(drop=True)
    
    print(f"\n💾 Сохранение Excel: {output_path.name}...")
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_en.to_excel(writer, sheet_name='IPC_Scheme_EN', index=False)
        df_ru.to_excel(writer, sheet_name='IPC_Scheme_RU', index=False)
        
        # Настройка ширины столбцов
        widths = {
            'A': 10,  # Level / Уровень
            'B': 12,  # Kind / Тип (код)
            'C': 22,  # Type / Тип рубрики
            'D': 22,  # Symbol / Индекс МПК
            'E': 22,  # ParentSymbol / Родительский индекс
            'F': 80,  # FullTitle / Полный заголовок
            'G': 50,  # RawTitle / Краткий заголовок
            'H': 14,  # DotCount / Уровень вложенности
            'I': 10,  # Section / Раздел
            'J': 10,  # Class / Класс
            'K': 14,  # Subclass / Подкласс
            'L': 16,  # MainGroup / Основная группа
            'M': 18,  # IsResidual / Остаточная рубрика
        }
        
        for sheet_name in ['IPC_Scheme_EN', 'IPC_Scheme_RU']:
            ws = writer.sheets[sheet_name]
            
            for col_letter, width in widths.items():
                ws.column_dimensions[col_letter].width = width
            
            ws.freeze_panes = 'A2'
            ws.auto_filter.ref = f'A1:M{len(df_en) + 1}'
    
    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"   Размер: {size_mb:.1f} МБ")
    print(f"   Строк EN: {len(df_en):,}")
    print(f"   Строк RU: {len(df_ru):,}")


def main():
    start = datetime.now()
    
    print()
    print("=" * 70)
    print("  📊 JSON → XLSX")
    print(f"  Запуск: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    if not JSON_EN.exists():
        print(f"\n❌ Нет {JSON_EN}")
        return
    if not JSON_RU.exists():
        print(f"\n❌ Нет {JSON_RU}")
        return
    
    output_path = XLSX_DIR / "IPC_Flat_20260101.xlsx"
    create_xlsx(JSON_EN, JSON_RU, output_path)
    
    print(f"\n{'='*70}")
    print(f"  ✅ ГОТОВО! Файл: {output_path}")
    print(f"  Время: {str(datetime.now() - start).split('.')[0]}")
    print("=" * 70)


if __name__ == "__main__":
    main()