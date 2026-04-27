"""
Запускает последовательно:
1. xml_to_json_en.py — создание ipc_scheme_en.json
2. translate_json.py — перевод → ipc_scheme_ru.json
3. json_to_xlsx.py  — создание IPC_Flat_20260101.xlsx с вкладками EN и RU
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from settings import JSON_EN, JSON_RU, XLSX_DIR, IPC_VERSION

PARSERS_DIR = Path(__file__).parent


def run_script(script_name: str, description: str) -> bool:
    """Запускает Python-скрипт и возвращает True при успехе."""
    script_path = PARSERS_DIR / script_name
    print(f"\n{'='*70}")
    print(f"  ▶ {description}")
    print(f"  ▶ Скрипт: {script_name}")
    print(f"{'='*70}")
    
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=False,
        text=True
    )
    
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
    
    # Этап 1: Парсинг XML → JSON (EN)
    if not run_script("xml_to_json_en.py", "Парсинг XML → JSON (EN)"):
        print("\n❌ Парсинг не удался. Выход.")
        return
    
    # Проверяем, что JSON_EN создан
    if not JSON_EN.exists():
        print(f"\n❌ Файл не создан: {JSON_EN}")
        return
    
    # Этап 2: Перевод JSON (EN → RU)
    if not run_script("translate_json.py", "Перевод JSON (EN → RU)"):
        print("\n⚠️  Перевод прерван. Запустите translate_json.py ещё раз.")
        print(f"   Прогресс сохранён, можно продолжить.")
        return
    
    # Проверяем, что JSON_RU создан
    if not JSON_RU.exists():
        print(f"\n❌ Файл не создан: {JSON_RU}")
        return
    
    # Этап 3: JSON → XLSX
    if not run_script("json_to_xlsx.py", "Создание Excel (JSON → XLSX)"):
        print("\n❌ Создание Excel не удалось.")
        return
    
    # Итоги
    elapsed = datetime.now() - start
    xlsx_path = XLSX_DIR / "IPC_Flat_20260101.xlsx"
    
    print()
    print("=" * 70)
    print("  ✅ ПОЛНЫЙ ЦИКЛ ЗАВЕРШЁН!")
    print(f"  EN JSON:  {JSON_EN}")
    print(f"  RU JSON:  {JSON_RU}")
    print(f"  Excel:    {xlsx_path}")
    print(f"  Время:    {str(elapsed).split('.')[0]}")
    print("=" * 70)


if __name__ == "__main__":
    main()