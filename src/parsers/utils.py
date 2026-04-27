"""
Вспомогательные функции, используемые всеми парсерами проекта.
"""

import re

# =============================================================================
# КОНСТАНТЫ
# =============================================================================
KIND_LEVEL = {
    's': 1,  # Section
    't': 2,  # Subsection
    'c': 3,  # Class
    'u': 4,  # Subclass
    'm': 5,  # Main group / Subgroup
    # Цифровые kind для подгрупп
    '1': 5, '2': 5, '3': 5, '4': 5, '5': 5,
    '6': 5, '7': 5, '8': 5, '9': 5,
    'g': 2,  # Guide heading
    'i': 2,  # Informative
    'n': 2,  # Note
}

KIND_TYPE = {
    's': 'Section',
    't': 'Subsection',
    'c': 'Class',
    'u': 'Subclass',
    'm': 'Group',
    'g': 'GuideHeading',
    'i': 'Informative',
    'n': 'Note',
}


# =============================================================================
# ФОРМАТИРОВАНИЕ WIPO-СИМВОЛОВ
# =============================================================================
def format_wipo_symbol(raw_symbol: str) -> str:
    """
    Форматирует символ из внутреннего формата WIPO в читаемый.
    
    Примеры:
    H02M0007758000 → H02M 7/758
    A01B0001000000 → A01B 1/00
    A01B0001020000 → A01B 1/02
    A01B0001100000 → A01B 1/10
    A01 → A01 (без изменений)
    """
    if not raw_symbol:
        return raw_symbol
    
    # Если уже содержит пробел — значит уже отформатирован
    if ' ' in raw_symbol:
        return raw_symbol
    
    # Паттерн: [A-H] + 2 цифры + опциональная буква + 4 цифры + 2+ цифр
    match = re.match(r'^([A-H]\d{2}[A-Z]?)(\d{4})(\d{2,})$', raw_symbol)
    if match:
        subclass = match.group(1)       # H02M или A01B
        main_group = match.group(2)     # 0001 или 0007
        subgroup = match.group(3)       # 000000, 020000, 100000, 758000
        
        main_num = str(int(main_group))  # "1" или "7"
        
        # Если все цифры subgroup — нули, это основная группа
        if set(subgroup) == {'0'}:
            return f"{subclass} {main_num}/00"
        
        # Убираем trailing пары нулей (каждый уровень вложенности — 2 цифры)
        # 020000 → "02" (убираем "0000")
        # 100000 → "10" (убираем "0000")
        # 758000 → "7580" (убираем "00")
        # 001200 → "0012" (ничего не убираем)
        trimmed = subgroup
        while len(trimmed) >= 4 and trimmed[-2:] == '00':
            trimmed = trimmed[:-2]
        
        return f"{subclass} {main_num}/{trimmed}"
    
    return raw_symbol


# =============================================================================
# РАЗБОР СИМВОЛА МПК
# =============================================================================
def parse_symbol(symbol: str):
    """
    Разбирает полный индекс МПК на составные части.
    Принимает символы в обоих форматах (WIPO и читаемый).
    
    Returns:
        tuple: (section, class_code, subclass, main_group)
    """
    section = ""
    class_code = ""
    subclass = ""
    main_group = ""
    
    if not symbol:
        return section, class_code, subclass, main_group
    
    # Приводим к читаемому формату
    formatted = format_wipo_symbol(symbol)
    
    section = formatted[0] if len(formatted) >= 1 else ""
    
    if '/' in formatted:
        before_slash = formatted.split('/')[0].strip()  # "H02M 7"
        parts = before_slash.split()
        
        if len(parts) >= 1:
            subclass = parts[0]  # "H02M" или "A01B"
            
            # Определяем класс
            if len(subclass) >= 4 and subclass[3].isalpha():
                class_code = subclass[:3]
            elif len(subclass) >= 3:
                class_code = subclass[:3]
            else:
                class_code = subclass
        
        if len(parts) >= 2:
            main_group = f"{subclass} {parts[1]}/00"
    else:
        # Без слеша — это подкласс или выше
        subclass = formatted
        
        if len(subclass) >= 4 and subclass[3].isalpha():
            class_code = subclass[:3]
        elif len(subclass) >= 3:
            class_code = subclass[:3]
        else:
            class_code = subclass
    
    return section, class_code, subclass, main_group


# =============================================================================
# ОПРЕДЕЛЕНИЕ ТИПА РУБРИКИ
# =============================================================================
def determine_group_type(symbol: str, kind: str) -> str:
    """Определяет уточнённый тип рубрики."""
    if kind and kind.isdigit():
        return 'Subgroup'
    
    if kind == 'm' and symbol:
        formatted = format_wipo_symbol(symbol)
        if '/' in formatted:
            subgroup_part = formatted.split('/')[-1]
            if subgroup_part == '00':
                return 'MainGroup'
        return 'Subgroup'
    
    return KIND_TYPE.get(kind, 'Unknown')


# =============================================================================
# ОПРЕДЕЛЕНИЕ ОСТАТОЧНОЙ РУБРИКИ
# =============================================================================
def is_residual(symbol: str, clean_text: str) -> bool:
    """Определяет, является ли рубрика остаточной."""
    if not symbol:
        return False
    
    symbol_upper = symbol.upper()
    text_lower = clean_text.lower() if clean_text else ""
    
    return (
        '99/00' in symbol_upper or
        '99Z' in symbol_upper or
        'not provided for' in text_lower or
        'not otherwise provided for' in text_lower
    )