# build_all.py — Полный цикл: парсинг → перевод → Excel → SQLite
"""
Запускает последовательно:
1. xml_to_json_en.py — создание ipc_scheme_en.json
2. translate_json.py — перевод → ipc_scheme_ru.json (с докачкой)
3. json_to_xlsx.py  — создание IPC_Flat_20260101.xlsx
4. json_to_sqlite.py — создание ipc_202601.sqlite3
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from settings import JSON_EN, JSON_RU, XLSX_DIR, SQLITE_DIR, IPC_VERSION

PARSERS_DIR = Path(__file__).parent


def run_script(script_name: str, description: str) -> bool:
    """Запускает Python-скрипт и возвращает True при успехе."""
    script_path = PARSERS_DIR / script_name
    print(f"\n{'='*70}")
    print(f"  ▶ {description}")
    print(f"  ▶ Скрипт: {script_name}")
    print(f"{'='*70}")
    
    result = subprocess.run([sys.executable, str(script_path)])
    
    if result.returncode == 0:
        print(f"  ✅ {description} — Готово")
        return True
    else:
        print(f"  ❌ {description} — Ошибка (код {result.returncode})")
        return False


def main():
    start = datetime.now()
    
    print()
    print("=" * 70)
    print("  📚 IPC BUILDER — Полный цикл")
    print(f"  Версия МПК: {IPC_VERSION}")
    print(f"  Запуск:     {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    steps = [
        ("xml_to_json_en.py", "Парсинг XML → JSON (EN)"),
        ("translate_json.py", "Перевод JSON (EN → RU)"),
        ("json_to_xlsx.py", "Создание Excel (JSON → XLSX)"),
        ("json_to_sqlite.py", "Создание SQLite (JSON → DB)"),
    ]
    
    for script, desc in steps:
        if not run_script(script, desc):
            print(f"\n❌ Процесс остановлен на шаге: {desc}")
            print(f"   Исправьте ошибку и запустите build_all.py снова.")
            return
    
    # Итоги
    elapsed = datetime.now() - start
    version_str = IPC_VERSION.replace('.', '')
    
    print()
    print("=" * 70)
    print("  ✅ ПОЛНЫЙ ЦИКЛ ЗАВЕРШЁН!")
    print(f"  EN JSON:  {JSON_EN}")
    print(f"  RU JSON:  {JSON_RU}")
    print(f"  Excel:    {XLSX_DIR / 'IPC_Flat_20260101.xlsx'}")
    print(f"  SQLite:   {SQLITE_DIR / f'ipc_{version_str}.sqlite3'}")
    print(f"  Время:    {str(elapsed).split('.')[0]}")
    print("=" * 70)


if __name__ == "__main__":
    main()