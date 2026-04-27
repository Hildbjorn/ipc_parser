import os
from pathlib import Path

def print_tree(directory, prefix="", exclude_dirs={"env"}):
    """
    Рекурсивно выводит структуру папок и файлов, исключая указанные папки.
    """
    try:
        items = sorted(os.listdir(directory))
    except PermissionError:
        return

    # Разделяем папки и файлы
    dirs = []
    files = []
    
    for item in items:
        full_path = os.path.join(directory, item)
        if os.path.isdir(full_path):
            if item not in exclude_dirs:
                dirs.append(item)
        else:
            files.append(item)
    
    # Сортируем: сначала папки, потом файлы
    dirs.sort()
    files.sort()
    
    # Объединяем для отображения
    all_items = dirs + files
    
    for i, item in enumerate(all_items):
        path = os.path.join(directory, item)
        is_last = (i == len(all_items) - 1)
        
        # Выбор символов для отображения
        connector = "└── " if is_last else "├── "
        print(prefix + connector + item)
        
        # Если это папка - рекурсивно обходим её содержимое
        if os.path.isdir(path):
            extension = "    " if is_last else "│   "
            print_tree(path, prefix + extension, exclude_dirs)

if __name__ == "__main__":
    current_dir = os.getcwd()
    print(f"Структура в: {current_dir}")
    print(".")
    print_tree(current_dir, exclude_dirs={"env", "__pycache__", ".git", "node_modules"})