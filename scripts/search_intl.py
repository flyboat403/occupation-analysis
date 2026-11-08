#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按代码或名称检索 ESCO / O*NET 文档索引，可选下载原文。

用法：
    python scripts/search_intl.py --source esco --code 2310
    python scripts/search_intl.py --source onet --code 11-9051
    python scripts/search_intl.py --source both --name "financial analyst"
    python scripts/search_intl.py --source esco --code 2310.1.23 --fetch --output temp/esco_doc.md
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

from doc_fetch import fetch_cached

ESCO_DIR = 'esco_details_md'
ONET_DIR = 'onet_details_md'


def load_index(path: Path, source: str) -> List[Dict]:
    entries = json.loads(path.read_text(encoding='utf-8'))
    for entry in entries:
        entry['source'] = source
        entry['code'] = entry.get('esco_code') if source == 'esco' else entry.get('onet_code')
        code = entry['code']
        local_dir = ESCO_DIR if source == 'esco' else ONET_DIR
        entry['local_path'] = f"assets/{local_dir}/{code}.md"
    return entries


def normalize_esco_code(raw: str) -> str:
    code = str(raw).strip().upper()
    code = re.sub(r'^ISCO[-_ ]?', '', code)
    if re.fullmatch(r'\d{4}\.00', code):
        code = code[:-3]
    return code


def normalize_onet_code(raw: str) -> str:
    code = str(raw).strip().upper()
    match = re.fullmatch(r'(\d{2}-\d{4})(?:\.(\d{1,2}))?', code)
    if match:
        return f"{match.group(1)}.{int(match.group(2) or 0):02d}"
    return code


def match_esco_code(entries: List[Dict], query: str) -> List[Dict]:
    code = normalize_esco_code(query)
    if not code:
        return []
    exact = [e for e in entries if e['esco_code'] == code]
    if exact:
        return exact
    if re.fullmatch(r'\d{4}', code):
        return [e for e in entries if e['isco_code'] == code]
    return [e for e in entries if e['esco_code'].startswith(code + '.')]


def match_onet_code(entries: List[Dict], query: str, include_deprecated: bool = False) -> List[Dict]:
    code = normalize_onet_code(query)
    if not code:
        return []
    exact = [e for e in entries if e['onet_code'] == code]
    if exact:
        if include_deprecated:
            exact = exact + [e for e in entries
                             if e.get('soc_code') == code and e['onet_code'] != code]
        return exact
    matched = [e for e in entries if e.get('soc_code') == code]
    if not include_deprecated:
        matched = [e for e in matched if not e.get('deprecated_alias')]
    return matched


def _name_score(entry: Dict, query: str) -> tuple:
    needle = query.strip().casefold()
    if not needle:
        return 0, ''
    title = (entry.get('title') or '').casefold()
    if title == needle:
        return 100, 'title'
    if title.startswith(needle):
        return 80, 'title'
    if needle in title:
        return 60, 'title'
    aliases = entry.get('alternative_terms') or entry.get('also_called') or []
    if any(a.casefold() == needle for a in aliases):
        return 50, 'alias'
    if any(needle in a.casefold() for a in aliases):
        return 30, 'alias'
    return 0, ''


def search(entries: List[Dict], code: Optional[str], name: Optional[str],
           include_deprecated: bool = False) -> List[Dict]:
    if code:
        if entries and entries[0]['source'] == 'esco':
            return match_esco_code(entries, code)
        return match_onet_code(entries, code, include_deprecated)
    scored = []
    for entry in entries:
        score, matched_on = _name_score(entry, name or '')
        if score:
            item = dict(entry)
            item['score'] = score
            item['matched_on'] = matched_on
            scored.append(item)
    scored.sort(key=lambda e: (-e['score'], e['code']))
    return scored


def format_table(results: List[Dict]) -> str:
    if not results:
        return "未找到匹配结果"
    lines = [f"共找到 {len(results)} 条记录："]
    for item in results:
        local = '本地' if Path(item['local_path']).exists() else '仅镜像'
        extra = ''
        if item['source'] == 'onet' and item.get('deprecated_alias'):
            extra = ' [已废弃别名]'
        lines.append(f"[{item['source'].upper()}] {item['code']}  {item['title']}  ({local}){extra}")
        lines.append(f"  {item['md_url']}")
    return '\n'.join(lines)


def fetch_results(results: List[Dict], output: Optional[str], cache_dir: Optional[Path]) -> None:
    if output and len(results) != 1:
        raise SystemExit("[ERROR] --output 仅在恰好 1 条结果时可用")
    for item in results:
        content = fetch_cached(item['md_url'], cache_dir=cache_dir, label='文档')
        if content is None:
            continue
        if output:
            target = Path(output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')
            item['fetched_path'] = str(target)
        else:
            target_dir = cache_dir if cache_dir is not None else Path('temp/intl_docs')
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / Path(item['md_url'].rsplit('/', 1)[-1]).name
            target.write_text(content, encoding='utf-8')
            item['fetched_path'] = str(target)


def main() -> int:
    parser = argparse.ArgumentParser(description='检索 ESCO/O*NET 文档索引')
    parser.add_argument('--source', choices=['esco', 'onet', 'both'], default='both')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--code', help='ESCO 代码（4位ISCO或完整子码）或 O*NET 代码')
    group.add_argument('--name', help='按名称/别名检索（忽略大小写）')
    parser.add_argument('--limit', type=int, default=20, help='最多返回条数')
    parser.add_argument('--json', action='store_true', help='输出 JSON')
    parser.add_argument('--fetch', action='store_true', help='下载匹配文档原文')
    parser.add_argument('--output', help='--fetch 时的输出文件（仅限单条结果）')
    parser.add_argument('--md-cache-dir', default='temp/intl_cache', help='文档缓存目录')
    parser.add_argument('--no-cache', action='store_true', help='禁用缓存（写入 temp/intl_docs）')
    parser.add_argument('--include-deprecated', action='store_true', help='包含 O*NET 已废弃别名条目')
    parser.add_argument('--assets-dir', default='assets', help='assets 目录')
    args = parser.parse_args()

    if args.output and not args.fetch:
        parser.error('--output 需与 --fetch 一起使用')

    assets = Path(args.assets_dir)
    sources = ['esco', 'onet'] if args.source == 'both' else [args.source]
    results: List[Dict] = []
    for source in sources:
        index_path = assets / f'{source}_final.json'
        if not index_path.exists():
            print(f"[ERROR] 索引不存在: {index_path}", file=sys.stderr)
            return 1
        entries = load_index(index_path, source)
        results.extend(search(entries, args.code, args.name, args.include_deprecated))
    if args.name:
        results.sort(key=lambda e: (-e.get('score', 0), e['source'], e['code']))
    results = results[:args.limit]

    if not results:
        print(f"未找到匹配结果: {'代码=' + args.code if args.code else '名称=' + args.name}")

    if args.fetch and results:
        cache_dir = None if args.no_cache else Path(args.md_cache_dir)
        fetch_results(results, args.output, cache_dir)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_table(results))
        if args.fetch:
            for item in results:
                if item.get('fetched_path'):
                    print(f"  已下载: {item['fetched_path']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
