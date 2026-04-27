# xml_to_json_en.py — Парсер XML МПК → чистый английский JSON
"""
Парсит официальный XML-файл МПК и создаёт:
1. ipc_scheme_en.json — полная английская версия схемы

Особенности:
- Правильно склеивает titlePart: через "; " для альтернативных заголовков
- Отделяет основной текст от entryReference (ссылок)
- Сохраняет иерархию через DotCount (из атрибута kind)
- Форматирует WIPO-символы в читаемый вид (H02M0007758000 → H02M 7/758)
"""

import json
import re
from datetime import datetime
from pathlib import Path
from lxml import etree
from tqdm import tqdm
import sys
from typing import Dict, List, Set, Tuple, Optional, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from settings import (
    XML_SCHEME, JSON_DIR, IPC_VERSION
)
from parsers.utils import (
    KIND_LEVEL, KIND_TYPE,
    parse_symbol, is_residual, format_wipo_symbol
)

# =============================================================================
# КОНСТАНТЫ
# =============================================================================
NAMESPACE = 'http://www.wipo.int/classifications/ipc/masterfiles'

Record = Dict[str, Any]
Records = List[Record]


# =============================================================================
# ИЗВЛЕЧЕНИЕ ЗАГОЛОВКОВ И ССЫЛОК
# =============================================================================
def extract_title_and_references(ipc_entry) -> Tuple[str, int, str, List[Dict[str, str]]]:
    """
    Извлекает заголовок и ссылки из XML-элемента ipcEntry.
    
    Точки вложенности определяются из атрибута 'kind'.
    Разделитель между titlePart: "; " для всех случаев.
    
    Returns:
        tuple: (raw_title, dot_count, clean_text, references)
    """
    ns_prefix = f'{{{NAMESPACE}}}'
    
    # Определяем количество точек
    kind = ipc_entry.get('kind', '')
    dot_count = int(kind) if kind and kind.isdigit() else 0
    
    # Ищем textBody
    text_body = ipc_entry.find(f'{ns_prefix}textBody')
    if text_body is None:
        return "", dot_count, "", []
    
    # Ищем title
    title_elem = text_body.find(f'{ns_prefix}title')
    if title_elem is None:
        full_text = "".join(text_body.itertext()).strip()
        full_text = re.sub(r'\s+', ' ', full_text)
        return full_text, dot_count, full_text, []
    
    title_parts = title_elem.findall(f'{ns_prefix}titlePart')
    
    if not title_parts:
        full_text = "".join(title_elem.itertext()).strip()
        full_text = re.sub(r'\s+', ' ', full_text)
        return full_text, dot_count, full_text, []
    
    # Собираем текст заголовка (только <text>)
    all_text = ""
    for i, tp in enumerate(title_parts):
        text_elements = tp.findall(f'{ns_prefix}text')
        texts = []
        for t in text_elements:
            text_content = "".join(t.itertext()).strip()
            if text_content:
                texts.append(text_content)
        
        tp_text = " ".join(texts)
        
        if tp_text:
            if i > 0 and all_text:
                all_text += '; '
            all_text += tp_text
    
    all_text = re.sub(r'\s+', ' ', all_text).strip()
    
    # Извлекаем ссылки
    references = []
    for tp in title_parts:
        entry_refs = tp.findall(f'{ns_prefix}entryReference')
        for ref in entry_refs:
            ref_text_parts = []
            if ref.text:
                ref_text_parts.append(ref.text)
            for child in ref:
                if child.tail:
                    ref_text_parts.append(child.tail)
            
            ref_text = "".join(ref_text_parts).strip()
            ref_text = re.sub(r'\s+', ' ', ref_text).strip(', ')
            
            symbols = []
            for sref in ref.findall(f'{ns_prefix}sref'):
                ref_symbol = sref.get('ref', '')
                if ref_symbol:
                    symbols.append(format_wipo_symbol(ref_symbol))
            for mref in ref.findall(f'{ns_prefix}mref'):
                ref_start = mref.get('ref', '')
                ref_end = mref.get('endRef', '')
                if ref_start:
                    symbols.append(format_wipo_symbol(ref_start))
                if ref_end:
                    symbols.append(format_wipo_symbol(ref_end))
            
            if ref_text or symbols:
                references.append({'text': ref_text, 'symbols': symbols})
    
    return all_text, dot_count, all_text, references


# =============================================================================
# ПАРСЕР СХЕМЫ
# =============================================================================
class IPCSchemeParser:
    """Парсер основного файла схемы МПК."""
    
    def __init__(self, xml_path: Path):
        self.xml_path = xml_path
        self.records: Records = []
        self.stats = {
            'sections': 0, 'subsections': 0, 'classes': 0,
            'subclasses': 0, 'main_groups': 0, 'subgroups': 0,
            'total': 0
        }
    
    def count_elements(self) -> int:
        """Подсчитывает количество элементов ipcEntry."""
        print("   Подсчёт элементов в XML...")
        count = 0
        for event, elem in etree.iterparse(str(self.xml_path), tag=f'{{{NAMESPACE}}}ipcEntry'):
            count += 1
            elem.clear()
            if count % 100000 == 0:
                print(f"   ... {count:,}")
        return count
    
    def parse(self) -> Tuple[Records, Dict]:
        """Главный метод парсинга."""
        print(f"\n{'='*70}")
        print(f"  📖 ПАРСИНГ СХЕМЫ МПК: {self.xml_path.name}")
        print(f"{'='*70}")
        print(f"   Размер файла: {self.xml_path.stat().st_size / 1024 / 1024:.1f} МБ")
        
        total = self.count_elements()
        print(f"   Элементов ipcEntry: {total:,}")
        
        tree = etree.parse(str(self.xml_path))
        root = tree.getroot()
        
        with tqdm(total=total, desc="   Парсинг схемы", unit="эл.",
                  bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]') as pbar:
            self._process_element(root, '', [], '')
            remaining = total - pbar.n
            if remaining > 0:
                pbar.update(remaining)
        
        self._print_stats()
        return self.records, self.stats
    
    def _process_element(self, elem, parent_symbol: str, parent_title_parts: List[str], parent_kind: str) -> None:
        """Рекурсивно обходит дерево ipcEntry."""
        symbol = elem.get('symbol')
        kind = elem.get('kind')
        entry_type = self._determine_entry_type(symbol, kind)
        
        raw_title, dot_count, clean_text, references = extract_title_and_references(elem)
        title_parts = self._build_title_chain(parent_title_parts, clean_text, dot_count)
        full_title = " → ".join(title_parts) if title_parts else ""
        
        display_symbol = format_wipo_symbol(symbol) if symbol else ""
        parent = format_wipo_symbol(parent_symbol) if parent_symbol else ""
        
        section, class_code, subclass, main_group = parse_symbol(symbol)
        residual = is_residual(symbol, clean_text)
        
        valid_kinds = {'s', 't', 'c', 'u', 'm'} | {str(i) for i in range(1, 20)}
        if kind in valid_kinds and symbol:
            parts_for_record = [clean_text] if dot_count == 0 and clean_text else title_parts
            
            self.records.append({
                'Level': KIND_LEVEL.get(kind, 0),
                'Kind': kind,
                'Type': entry_type,
                'Symbol': display_symbol,
                'ParentSymbol': parent,
                'FullTitle_EN': full_title,
                'TitleParts_EN': parts_for_record,
                'RawTitle_EN': clean_text,
                'References_EN': references,
                'DotCount': dot_count,
                'Section': section,
                'Class': class_code,
                'Subclass': subclass,
                'MainGroup': main_group if entry_type == 'Subgroup' else display_symbol,
                'IsResidual': residual,
                'IPC_Version': IPC_VERSION,
                'Source': 'scheme'
            })
            
            self._update_stats(entry_type)
        
        # Рекурсия
        for child in elem:
            if child.tag.endswith('ipcEntry'):
                self._process_element(child, symbol or parent_symbol, title_parts, kind)
    
    def _determine_entry_type(self, symbol: str, kind: str) -> str:
        """Определяет тип рубрики."""
        if kind and kind.isdigit():
            return 'Subgroup'
        if kind == 'm' and symbol:
            formatted = format_wipo_symbol(symbol)
            if '/' in formatted and formatted.split('/')[-1] == '00':
                return 'MainGroup'
            return 'Subgroup'
        return KIND_TYPE.get(kind, 'Unknown')
    
    def _build_title_chain(self, parent_parts: List[str], clean_text: str, dot_count: int) -> List[str]:
        """Строит цепочку заголовков с учётом уровня вложенности."""
        if dot_count == 0:
            return [clean_text] if clean_text else []
        parts = parent_parts[:dot_count]
        if clean_text:
            parts.append(clean_text)
        return parts
    
    def _update_stats(self, entry_type: str) -> None:
        """Обновляет статистику."""
        self.stats['total'] += 1
        key = {
            'Section': 'sections', 'Subsection': 'subsections',
            'Class': 'classes', 'Subclass': 'subclasses',
            'MainGroup': 'main_groups', 'Subgroup': 'subgroups'
        }.get(entry_type)
        if key:
            self.stats[key] += 1
    
    def _print_stats(self) -> None:
        """Выводит статистику."""
        print(f"\n   ✅ Схема обработана:")
        print(f"   Записей всего:      {self.stats['total']:,}")
        print(f"   Разделов (A-H):     {self.stats['sections']}")
        print(f"   Классов:            {self.stats['classes']}")
        print(f"   Подклассов:         {self.stats['subclasses']}")
        print(f"   Основных групп:     {self.stats['main_groups']}")
        print(f"   Подгрупп:           {self.stats['subgroups']}")


# =============================================================================
# СОХРАНЕНИЕ
# =============================================================================
def save_json(path: Path, data: Any) -> None:
    """Сохраняет данные в JSON."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_scheme_json(records: Records, path: Path) -> None:
    """Сохраняет схему в JSON."""
    print(f"\n💾 Сохранение схемы: {path.name}...")
    
    output = []
    with tqdm(total=len(records), desc="   Сохранение", unit="зап.",
              bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]') as pbar:
        for r in records:
            entry = {
                'Level': r['Level'],
                'Kind': r['Kind'],
                'Type': r['Type'],
                'Symbol': r['Symbol'],
                'ParentSymbol': r['ParentSymbol'],
                'FullTitle': r['FullTitle_EN'],
                'TitleParts': r['TitleParts_EN'],
                'RawTitle': r['RawTitle_EN'],
                'References': r['References_EN'],
                'DotCount': r['DotCount'],
                'Section': r['Section'],
                'Class': r['Class'],
                'Subclass': r['Subclass'],
                'MainGroup': r['MainGroup'],
                'IsResidual': r['IsResidual'],
                'IPC_Version': r['IPC_Version'],
                'Source': r['Source']
            }
            output.append(entry)
            pbar.update(1)
    
    save_json(path, output)
    print(f"   Записей: {len(output):,}")
    print(f"   Размер:  {path.stat().st_size / 1024 / 1024:.1f} МБ")


# =============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =============================================================================
def main():
    """Парсит XML и создаёт английский JSON."""
    start_time = datetime.now()
    
    print()
    print("=" * 70)
    print("  📚 IPC PARSER — XML → JSON (EN)")
    print(f"  Версия МПК: {IPC_VERSION}")
    print(f"  Запуск:     {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    if not XML_SCHEME.exists():
        print(f"\n❌ Файл не найден: {XML_SCHEME}")
        return
    
    parser = IPCSchemeParser(XML_SCHEME)
    records, stats = parser.parse()
    
    if not records:
        print("\n❌ Ошибка: схема не распарсена!")
        return
    
    scheme_path = JSON_DIR / "ipc_scheme_en.json"
    save_scheme_json(records, scheme_path)
    
    elapsed = datetime.now() - start_time
    print()
    print("=" * 70)
    print("  ✅ ГОТОВО!")
    print(f"  Схема:    {scheme_path}")
    print(f"  Время:    {str(elapsed).split('.')[0]}")
    print("=" * 70)


if __name__ == "__main__":
    main()