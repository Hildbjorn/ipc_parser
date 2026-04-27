# translate_json.py — Перевод ipc_scheme_en.json → ipc_scheme_ru.json
"""
Переводит английский JSON схемы МПК на русский язык через OpenAI API.
Переводит: FullTitle, RawTitle, TitleParts
НЕ переводит: символы, индексы, References
При обрыве продолжает с места остановки.
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from tqdm import tqdm
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from settings import (
    JSON_EN, JSON_RU, TRANSLATION_CACHE, PROGRESS_FILE,
    API_KEY, API_BASE_URL, BATCH_SIZE, DELAY_BETWEEN_BATCHES,
    MAX_RETRIES, TRANSLATION_MODEL, VERBOSE
)


def load_json(path: Path) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Translator:
    def __init__(self, client: OpenAI):
        self.client = client
        self.cache = load_json(TRANSLATION_CACHE) if TRANSLATION_CACHE.exists() else {}
        self.progress = load_json(PROGRESS_FILE) if PROGRESS_FILE.exists() else {}
        self.done = set(self.progress.get('done', []))

    def translate(self, en_path: Path, ru_path: Path):
        records = load_json(en_path)
        total = len(records)
        print(f"\n📖 Записей: {total:,}")

        if self.done:
            print(f"   Уже переведено: {len(self.done):,}")
            print(f"   Осталось: {total - len(self.done):,}")

        if len(self.done) >= total:
            print("   ✅ Всё переведено!")
            self._apply(records)
            self._save_ru(records, ru_path)
            return

        remaining = [i for i in range(total) if i not in self.done]
        batches = [remaining[i:i + BATCH_SIZE] for i in range(0, len(remaining), BATCH_SIZE)]
        print(f"   Батчей: {len(batches)} по {BATCH_SIZE}")

        with tqdm(total=total, initial=len(self.done), desc="   Перевод", unit="зап.") as pbar:
            for batch_indices in batches:
                # Сбор фраз
                phrases = {}
                for i in batch_indices:
                    r = records[i]
                    for f in ['FullTitle', 'RawTitle']:
                        t = r.get(f, '')
                        if t and t not in self.cache:
                            phrases[t] = t
                    for p in r.get('TitleParts', []):
                        if p and p not in self.cache:
                            phrases[p] = p

                # Перевод новых фраз
                new = {k: v for k, v in phrases.items() if k not in self.cache}
                if new:
                    tr = self._translate(new)
                    if tr:
                        self.cache.update(tr)

                # Применение перевода
                for i in batch_indices:
                    r = records[i]
                    for f in ['FullTitle', 'RawTitle']:
                        en = r.get(f, '')
                        r[f] = self.cache.get(en, en)
                    r['TitleParts'] = [self.cache.get(p, p) for p in r.get('TitleParts', [])]

                self.done.update(batch_indices)
                self._save_progress()
                pbar.update(len(batch_indices))
                time.sleep(DELAY_BETWEEN_BATCHES)

        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()

        self._save_ru(records, ru_path)

    def _translate(self, phrases: dict, attempt: int = 1) -> dict:
        if not phrases:
            return {}

        items = list(phrases.values())
        numbered = "\n".join(f'{i+1}. "{p}"' for i, p in enumerate(items))

        prompt = f"""Ты — эксперт-переводчик патентной документации Роспатента.
Переведи технические термины МПК с английского на русский.
Правила:
1. Терминология Роспатента
2. Регистр как в оригинале
3. Ответ — ТОЛЬКО JSON: {{"оригинал": "перевод"}}

{numbered}"""

        try:
            resp = self.client.chat.completions.create(
                model=TRANSLATION_MODEL,
                messages=[
                    {"role": "system", "content": "Только валидный JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4000
            )
            text = resp.choices[0].message.content.strip()

            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass

            # Fallback: построчный парсинг
            result = {}
            for line in text.split('\n'):
                line = line.strip().strip(',"')
                if '":' in line:
                    parts = line.split('":', 1)
                    if len(parts) == 2:
                        k = parts[0].strip().strip('"')
                        v = parts[1].strip().strip('"')
                        if k and v and k in phrases:
                            result[k] = v
            return result

        except Exception as e:
            if attempt < MAX_RETRIES:
                if VERBOSE:
                    tqdm.write(f"      Повтор {attempt + 1}: {e}")
                time.sleep(3 * attempt)
                return self._translate(phrases, attempt + 1)
            if VERBOSE:
                tqdm.write(f"      ❌ Ошибка: {e}")
            return {}

    def _apply(self, records):
        for r in records:
            for f in ['FullTitle', 'RawTitle']:
                en = r.get(f, '')
                r[f] = self.cache.get(en, en)
            r['TitleParts'] = [self.cache.get(p, p) for p in r.get('TitleParts', [])]

    def _save_progress(self):
        save_json(TRANSLATION_CACHE, self.cache)
        save_json(PROGRESS_FILE, {
            'done': sorted(self.done),
            'cache_size': len(self.cache),
            'timestamp': datetime.now().isoformat()
        })

    def _save_ru(self, records, path):
        print(f"\n💾 Сохранение: {path.name}...")
        out = []
        with tqdm(total=len(records), desc="   Сохранение", unit="зап.") as pbar:
            for r in records:
                out.append({
                    'Level': r['Level'],
                    'Kind': r['Kind'],
                    'Type': r['Type'],
                    'Symbol': r['Symbol'],
                    'ParentSymbol': r['ParentSymbol'],
                    'FullTitle': r.get('FullTitle', ''),
                    'TitleParts': r.get('TitleParts', []),
                    'RawTitle': r.get('RawTitle', ''),
                    'References': r.get('References', []),
                    'DotCount': r['DotCount'],
                    'Section': r['Section'],
                    'Class': r['Class'],
                    'Subclass': r['Subclass'],
                    'MainGroup': r['MainGroup'],
                    'IsResidual': r['IsResidual'],
                    'IPC_Version': r['IPC_Version'],
                    'Source': r['Source']
                })
                pbar.update(1)
        save_json(path, out)
        print(f"   Записей: {len(out):,}")


def main():
    start = datetime.now()
    print(f"\n{'='*70}\n  🌐 IPC TRANSLATOR — EN → RU\n  Запуск: {start.strftime('%Y-%m-%d %H:%M:%S')}\n{'='*70}")

    if not JSON_EN.exists():
        print(f"\n❌ Нет {JSON_EN}")
        return
    if not API_KEY:
        print("\n❌ Нет API_KEY")
        return

    client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)
    print(f"✅ API: {API_BASE_URL}")

    Translator(client).translate(JSON_EN, JSON_RU)

    print(f"\n{'='*70}\n  ✅ ГОТОВО!\n  RU: {JSON_RU}\n  Кеш: {TRANSLATION_CACHE}\n  Время: {str(datetime.now() - start).split('.')[0]}\n{'='*70}")


if __name__ == "__main__":
    main()