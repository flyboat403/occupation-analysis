#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用文档下载与磁盘缓存：HTTPS + 域名白名单 + TTL + 原子写入。"""

import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

DEFAULT_CACHE_TTL = 7 * 24 * 3600
DEFAULT_URL_HOSTS = ('raw.githubusercontent.com', 'github.com')
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024


def cache_filename(url: str) -> str:
    """从 URL 提取安全的缓存文件名。"""
    return Path(urllib.parse.unquote(url.rsplit('/', 1)[-1])).name or 'document.md'


def fetch_cached(
    url: str,
    cache_dir: Optional[Path] = None,
    ttl: int = DEFAULT_CACHE_TTL,
    timeout: int = 30,
    label: str = '文档',
) -> Optional[str]:
    """下载文本内容并缓存；URL 非法、下载失败或内容为空时返回 None。"""
    if not url:
        return None
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme != 'https' or parsed_url.hostname not in DEFAULT_URL_HOSTS:
        print(f"[WARNING] 拒绝非白名单URL: {url[:80]}", file=sys.stderr)
        return None

    filename = cache_filename(url)
    if cache_dir is not None:
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cached = cache_dir / filename
            if cached.exists():
                stat = cached.stat()
                if stat.st_size > 0 and (time.time() - stat.st_mtime) < ttl:
                    return cached.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError) as e:
            print(f"[WARNING] {label}缓存读取异常: {e}", file=sys.stderr)

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'occupation-analysis/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(MAX_DOWNLOAD_BYTES + 1)
        if len(raw) > MAX_DOWNLOAD_BYTES:
            print(f"[WARNING] {label}超过大小上限 {MAX_DOWNLOAD_BYTES} 字节: {url[:60]}...",
                  file=sys.stderr)
            return None
        content = raw.decode('utf-8', errors='replace')
        if not content.strip():
            return None
        if cache_dir is not None:
            try:
                tmp = cache_dir / f".{filename}.{os.getpid()}.tmp"
                tmp.write_text(content, encoding='utf-8')
                tmp.replace(cache_dir / filename)
            except OSError as e:
                print(f"[WARNING] {label}缓存写入失败: {e}", file=sys.stderr)
        return content
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, UnicodeDecodeError) as e:
        print(f"[WARNING] {label}下载失败 ({url[:60]}...): {e}", file=sys.stderr)
        return None
