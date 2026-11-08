#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 ESCO / O*NET 文档索引 JSON（代码、名称、别名、镜像 md_url）。

用法：
    python scripts/build_intl_index.py            # 生成并校验
    python scripts/build_intl_index.py --check    # 仅校验已有 JSON
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

DEFAULT_BASE_URL = 'https://raw.githubusercontent.com/flyboat403/vocational-education-standard-system/main'
ESCO_DIR = 'esco_details_md'
ONET_DIR = 'onet_details_md'
ONET_RE = re.compile(r'^(\d{2}-\d{4}\.\d{2}) - (.+)$')


def _read_lines(path: Path) -> List[str]:
    return path.read_text(encoding='utf-8').splitlines()


def _extract_table_field(lines: List[str], field: str) -> str:
    pattern = re.compile(r'\|\s*\*\*' + re.escape(field) + r'\*\*\s*\|\s*(.+?)\s*\|')
    for line in lines[:20]:
        match = pattern.search(line)
        if match:
            value = match.group(1)
            link = re.search(r'\]\(([^)]+)\)', value)
            return (link.group(1) if link else value).strip()
    return ''


def build_esco_index(esco_dir: Path, base_url: str) -> List[Dict]:
    files = sorted(esco_dir.glob('*.md'), key=lambda p: tuple(int(x) for x in p.stem.split('.')))
    entries = []
    for path in files:
        lines = _read_lines(path)
        if not lines or not lines[0].startswith('# '):
            raise ValueError(f"首行标题格式异常: {path}")
        alt_terms = []
        try:
            start = lines.index('## Alternative Terms')
            for line in lines[start + 1:]:
                if line.startswith('## '):
                    break
                if line.startswith('- '):
                    alt_terms.append(line[2:].strip())
        except ValueError:
            pass
        entries.append({
            'esco_code': path.stem,
            'isco_code': path.stem.split('.')[0],
            'title': lines[0][2:].strip(),
            'uri': _extract_table_field(lines, 'URI'),
            'status': _extract_table_field(lines, 'Status'),
            'alternative_terms': alt_terms,
            'md_url': f"{base_url}/{ESCO_DIR}/{path.name}",
        })
    return entries


def build_onet_index(onet_dir: Path, base_url: str) -> List[Dict]:
    files = sorted(onet_dir.glob('*.md'))
    entries = []
    for path in files:
        lines = _read_lines(path)
        if not lines or not lines[0].startswith('# '):
            raise ValueError(f"首行标题格式异常: {path}")
        match = ONET_RE.match(lines[0][2:].strip())
        if match:
            soc_code, title = match.group(1), match.group(2)
        else:
            soc_code, title = path.stem, lines[0][2:].strip()
        also_called = []
        for line in lines[:10]:
            if line.startswith('- Also called:'):
                also_called = [x.strip() for x in line.split(':', 1)[1].split(',') if x.strip()]
                break
        entries.append({
            'onet_code': path.stem,
            'soc_code': soc_code,
            'title': title,
            'also_called': also_called,
            'deprecated_alias': soc_code != path.stem,
            'md_url': f"{base_url}/{ONET_DIR}/{path.name}",
        })
    return entries


def _validate(entries: List[Dict], source_dir: Path, dirname: str, code_key: str,
              base_url: str, label: str) -> None:
    if not entries:
        raise ValueError(f"{label} 索引为空")
    codes = [e[code_key] for e in entries]
    if len(codes) != len(set(codes)):
        duplicated = sorted({c for c in codes if codes.count(c) > 1})
        raise ValueError(f"{label} 代码重复: {duplicated[:5]}")
    expected_files = {p.stem for p in source_dir.glob('*.md')}
    if set(codes) != expected_files:
        raise ValueError(f"{label} 索引与本地文件不一致: "
                         f"缺 {len(expected_files - set(codes))}，多 {len(set(codes) - expected_files)}")
    prefix = f"{base_url}/{dirname}/"
    for entry in entries:
        if not entry.get('title'):
            raise ValueError(f"{label} 标题为空: {entry[code_key]}")
        url = entry.get('md_url', '')
        if not (url.startswith(prefix) and url.endswith('.md')):
            raise ValueError(f"{label} md_url 非法: {url}")


def validate_files(esco_path: Path, onet_path: Path, esco_dir: Path, onet_dir: Path,
                   base_url: str) -> None:
    esco = json.loads(esco_path.read_text(encoding='utf-8'))
    onet = json.loads(onet_path.read_text(encoding='utf-8'))
    _validate(esco, esco_dir, ESCO_DIR, 'esco_code', base_url, 'ESCO')
    _validate(onet, onet_dir, ONET_DIR, 'onet_code', base_url, 'O*NET')
    print(f"[OK] ESCO {len(esco)} 条，O*NET {len(onet)} 条，校验通过")


def _write(path: Path, entries: List[Dict]) -> None:
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='生成 ESCO/O*NET 索引 JSON')
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL, help='镜像仓库 raw 基础 URL')
    parser.add_argument('--assets-dir', default='assets', help='assets 目录')
    parser.add_argument('--check', action='store_true', help='仅校验已有索引，不重新生成')
    args = parser.parse_args()

    assets = Path(args.assets_dir)
    esco_dir = assets / ESCO_DIR
    onet_dir = assets / ONET_DIR
    esco_path = assets / 'esco_final.json'
    onet_path = assets / 'onet_final.json'
    base_url = args.base_url.rstrip('/')

    for directory in (esco_dir, onet_dir):
        if not directory.is_dir():
            print(f"[ERROR] 目录不存在: {directory}", file=sys.stderr)
            return 1

    if args.check:
        if not (esco_path.exists() and onet_path.exists()):
            print("[ERROR] 索引文件不存在，请先运行生成", file=sys.stderr)
            return 1
        validate_files(esco_path, onet_path, esco_dir, onet_dir, base_url)
        return 0

    esco = build_esco_index(esco_dir, base_url)
    onet = build_onet_index(onet_dir, base_url)
    _validate(esco, esco_dir, ESCO_DIR, 'esco_code', base_url, 'ESCO')
    _validate(onet, onet_dir, ONET_DIR, 'onet_code', base_url, 'O*NET')
    _write(esco_path, esco)
    _write(onet_path, onet)
    print(f"[OK] 已生成 {esco_path} ({len(esco)} 条)")
    print(f"[OK] 已生成 {onet_path} ({len(onet)} 条)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
