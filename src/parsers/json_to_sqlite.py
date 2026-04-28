# json_to_sqlite.py — Конвертер JSON → SQLite3
"""
Создаёт ipc_20260101.sqlite3 из готовых JSON-файлов.

Особенности:
- Берёт перевод из ipc_scheme_ru.json (не переводит заново)
- Уникальность по (symbol, kind) — поддерживает разные kind для одного symbol
- При повторном запуске полностью пересоздаёт таблицы
- Полнотекстовый поиск (FTS5)
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from tqdm import tqdm
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from settings import JSON_EN, JSON_RU, SQLITE_DIR, IPC_VERSION


def load_json(path: Path) -> list:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_type_id(kind: str) -> int:
    """Определяет type_id по kind."""
    if kind == 's': return 1
    if kind == 't': return 2
    if kind == 'c': return 3
    if kind == 'u': return 4
    if kind == 'm': return 5
    return 6  # subgroup


def create_database(en_path: Path, ru_path: Path, db_path: Path):
    """Создаёт/обновляет базу данных SQLite."""
    
    print(f"\n📖 Загрузка EN: {en_path.name}")
    en_records = load_json(en_path)
    print(f"   Записей: {len(en_records):,}")
    
    print(f"\n📖 Загрузка RU: {ru_path.name}")
    ru_records = load_json(ru_path)
    print(f"   Записей: {len(ru_records):,}")
    
    # Словарь русских записей по (symbol, kind)
    ru_dict = {(r['Symbol'], r.get('Kind', '')): r for r in ru_records}
    
    # Подключаем базу
    print(f"\n🗄️  Создание базы: {db_path.name}")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    
    # Удаляем старые таблицы
    for table in ['ipc_entries', 'ipc_fts', 'main_groups', 'subclasses', 'classes', 'sections', 'types']:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    
    # ================================================================
    # СОЗДАНИЕ ТАБЛИЦ
    # ================================================================
    
    cursor.execute("""
        CREATE TABLE types (
            id INTEGER PRIMARY KEY,
            kind_code TEXT NOT NULL,
            name_en TEXT NOT NULL,
            name_ru TEXT NOT NULL
        )
    """)
    
    cursor.executemany("INSERT INTO types VALUES (?, ?, ?, ?)", [
        (1, 's', 'Section', 'Раздел'),
        (2, 't', 'Subsection', 'Подраздел'),
        (3, 'c', 'Class', 'Класс'),
        (4, 'u', 'Subclass', 'Подкласс'),
        (5, 'm', 'MainGroup', 'Основная группа'),
        (6, '*', 'Subgroup', 'Подгруппа'),
    ])
    
    cursor.execute("""
        CREATE TABLE sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            title_en TEXT,
            title_ru TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            section_id INTEGER REFERENCES sections(id),
            title_en TEXT,
            title_ru TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE subclasses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            class_id INTEGER REFERENCES classes(id),
            title_en TEXT,
            title_ru TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE main_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            subclass_id INTEGER REFERENCES subclasses(id),
            title_en TEXT,
            title_ru TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE ipc_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            parent_symbol TEXT,
            level INTEGER,
            kind TEXT NOT NULL,
            dot_count INTEGER,
            type_id INTEGER REFERENCES types(id),
            section_id INTEGER REFERENCES sections(id),
            class_id INTEGER REFERENCES classes(id),
            subclass_id INTEGER REFERENCES subclasses(id),
            main_group_id INTEGER REFERENCES main_groups(id),
            full_title_en TEXT,
            full_title_ru TEXT,
            raw_title_en TEXT,
            raw_title_ru TEXT,
            is_residual INTEGER DEFAULT 0,
            ipc_version TEXT,
            UNIQUE(symbol, kind)
        )
    """)
    
    # ================================================================
    # СПРАВОЧНИКИ
    # ================================================================
    
    print("\n📝 Заполнение справочников...")
    
    sections_data = {}
    classes_data = {}
    subclasses_data = {}
    main_groups_data = {}
    
    for en_r in tqdm(en_records, desc="   Сбор", unit="зап."):
        sym = en_r['Symbol']
        kind = en_r.get('Kind', '')
        ru_key = (sym, kind)
        ru_r = ru_dict.get(ru_key, {})
        
        title_en = en_r.get('FullTitle', '') or en_r.get('RawTitle', '')
        title_ru = ru_r.get('FullTitle', '') or ru_r.get('RawTitle', '') or title_en
        
        t = en_r.get('Type', '')
        
        if t == 'Section':
            sections_data[sym] = (sym, title_en, title_ru)
        elif t == 'Class':
            sections_data.setdefault(en_r.get('Section', ''), (en_r.get('Section', ''), '', ''))
            classes_data[sym] = (sym, en_r.get('Section', ''), title_en, title_ru)
        elif t == 'Subclass':
            classes_data.setdefault(en_r.get('Class', ''), (en_r.get('Class', ''), '', '', ''))
            subclasses_data[sym] = (sym, en_r.get('Class', ''), title_en, title_ru)
        elif t == 'MainGroup':
            subclasses_data.setdefault(en_r.get('Subclass', ''), (en_r.get('Subclass', ''), '', '', ''))
            main_groups_data[sym] = (sym, en_r.get('Subclass', ''), title_en, title_ru)
    
    # Разделы
    for sym, (_, title_en, title_ru) in sections_data.items():
        if sym:
            cursor.execute("INSERT INTO sections (symbol, title_en, title_ru) VALUES (?, ?, ?)", (sym, title_en, title_ru))
    print(f"   Разделов: {len(sections_data)}")
    
    cursor.execute("SELECT id, symbol FROM sections")
    section_ids = {row[1]: row[0] for row in cursor.fetchall()}
    
    # Классы
    for sym, (_, section, title_en, title_ru) in classes_data.items():
        if sym:
            cursor.execute("INSERT INTO classes (symbol, section_id, title_en, title_ru) VALUES (?, ?, ?, ?)", (sym, section_ids.get(section), title_en, title_ru))
    print(f"   Классов: {len(classes_data)}")
    
    cursor.execute("SELECT id, symbol FROM classes")
    class_ids = {row[1]: row[0] for row in cursor.fetchall()}
    
    # Подклассы
    for sym, (_, class_sym, title_en, title_ru) in subclasses_data.items():
        if sym:
            cursor.execute("INSERT INTO subclasses (symbol, class_id, title_en, title_ru) VALUES (?, ?, ?, ?)", (sym, class_ids.get(class_sym), title_en, title_ru))
    print(f"   Подклассов: {len(subclasses_data)}")
    
    cursor.execute("SELECT id, symbol FROM subclasses")
    subclass_ids = {row[1]: row[0] for row in cursor.fetchall()}
    
    # Основные группы
    for sym, (_, subclass_sym, title_en, title_ru) in main_groups_data.items():
        if sym:
            cursor.execute("INSERT INTO main_groups (symbol, subclass_id, title_en, title_ru) VALUES (?, ?, ?, ?)", (sym, subclass_ids.get(subclass_sym), title_en, title_ru))
    print(f"   Основных групп: {len(main_groups_data)}")
    
    cursor.execute("SELECT id, symbol FROM main_groups")
    main_group_ids = {row[1]: row[0] for row in cursor.fetchall()}
    
    # ================================================================
    # ОСНОВНАЯ ТАБЛИЦА
    # ================================================================
    
    print("\n📝 Заполнение основной таблицы...")
    
    batch = []
    batch_size = 2000
    
    for en_r in tqdm(en_records, desc="   Записи", unit="зап."):
        sym = en_r['Symbol']
        kind = en_r.get('Kind', '')
        ru_r = ru_dict.get((sym, kind), {})
        
        batch.append((
            sym,
            en_r.get('ParentSymbol', ''),
            en_r.get('Level', 0),
            kind,
            en_r.get('DotCount', 0),
            get_type_id(kind),
            section_ids.get(en_r.get('Section', '')),
            class_ids.get(en_r.get('Class', '')),
            subclass_ids.get(en_r.get('Subclass', '')),
            main_group_ids.get(en_r.get('MainGroup', '')),
            en_r.get('FullTitle', ''),
            ru_r.get('FullTitle', ''),
            en_r.get('RawTitle', ''),
            ru_r.get('RawTitle', ''),
            1 if en_r.get('IsResidual') else 0,
            IPC_VERSION
        ))
        
        if len(batch) >= batch_size:
            cursor.executemany("""
                INSERT OR REPLACE INTO ipc_entries (
                    symbol, parent_symbol, level, kind, dot_count,
                    type_id, section_id, class_id, subclass_id, main_group_id,
                    full_title_en, full_title_ru, raw_title_en, raw_title_ru,
                    is_residual, ipc_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            batch = []
    
    if batch:
        cursor.executemany("""
            INSERT OR REPLACE INTO ipc_entries (
                symbol, parent_symbol, level, kind, dot_count,
                type_id, section_id, class_id, subclass_id, main_group_id,
                full_title_en, full_title_ru, raw_title_en, raw_title_ru,
                is_residual, ipc_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch)
    
    # ================================================================
    # ИНДЕКСЫ
    # ================================================================
    
    print("\n📊 Создание индексов...")
    
    indexes = [
        ("idx_entries_symbol_kind", "ipc_entries(symbol, kind)"),
        ("idx_entries_parent", "ipc_entries(parent_symbol)"),
        ("idx_entries_type", "ipc_entries(type_id)"),
        ("idx_entries_section", "ipc_entries(section_id)"),
        ("idx_entries_class", "ipc_entries(class_id)"),
        ("idx_entries_subclass", "ipc_entries(subclass_id)"),
        ("idx_entries_main_group", "ipc_entries(main_group_id)"),
        ("idx_sections_symbol", "sections(symbol)"),
        ("idx_classes_symbol", "classes(symbol)"),
        ("idx_subclasses_symbol", "subclasses(symbol)"),
        ("idx_main_groups_symbol", "main_groups(symbol)"),
    ]
    
    for name, columns in indexes:
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {columns}")
    
    # ================================================================
    # FTS
    # ================================================================
    
    print("🔍 Создание полнотекстового индекса...")
    
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS ipc_fts USING fts5(
            symbol,
            full_title_en,
            full_title_ru,
            content='ipc_entries',
            content_rowid='id'
        )
    """)
    cursor.execute("INSERT INTO ipc_fts(ipc_fts) VALUES('rebuild')")
    
    conn.commit()
    
    # ================================================================
    # СТАТИСТИКА
    # ================================================================
    
    print()
    for table in ['types', 'sections', 'classes', 'subclasses', 'main_groups', 'ipc_entries']:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"   {table}: {cursor.fetchone()[0]:,}")
    
    conn.close()
    
    size_mb = db_path.stat().st_size / 1024 / 1024
    print(f"\n   Размер базы: {size_mb:.1f} МБ")


def main():
    start = datetime.now()
    
    print()
    print("=" * 70)
    print("  🗄️  JSON → SQLite")
    print(f"  Запуск: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    if not JSON_EN.exists():
        print(f"\n❌ Нет {JSON_EN}")
        return
    if not JSON_RU.exists():
        print(f"\n❌ Нет {JSON_RU}")
        return
    
    version_str = IPC_VERSION.replace('.', '')
    db_path = SQLITE_DIR / f"ipc_{version_str}.sqlite3"
    create_database(JSON_EN, JSON_RU, db_path)
    
    print(f"\n{'='*70}")
    print(f"  ✅ ГОТОВО! База: {db_path}")
    print(f"  Время: {str(datetime.now() - start).split('.')[0]}")
    print("=" * 70)


if __name__ == "__main__":
    main()