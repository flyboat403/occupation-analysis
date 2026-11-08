#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用文档下载与磁盘缓存：HTTPS + 域名白名单 + TTL + 原子写入。"""

import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional, Sequence

DEFAULT_CACHE_TTL = 7 * 24 * 3600
DEFAULT_URL_HOSTS = ('raw.githubusercontent.com', 'github.com')
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024


def fetch_cached(
    url: str,
    cache_dir: Optional[Path] = None,
    ttl: int = DEFAULT_CACHE_TTL,
    hosts: Sequence[str] = DEFAULT_URL_HOSTS,
    timeout: int = 30,
    label: str = '文档',
    max_bytes: int = MAX_DOWNLOAD_BYTES,
) -> Optional[str]:
    """下载文本内容并缓存；URL 非法、下载失败或内容为空时返回 None。"""
    if not url:
        return None
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme != 'https' or parsed_url.hostname not in hosts:
        print(f"[WARNING] 拒绝非白名单URL: {url[:80]}")
        return None

    filename = Path(urllib.parse.unquote(url.rsplit('/', 1)[-1])).name or 'document.md'
    if cache_dir is not None:
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cached = cache_dir / filename
            if cached.exists():
                stat = cached.stat()
                if stat.st_size > 0 and (time.time() - stat.st_mtime) < ttl:
                    return cached.read_text(encoding='utf-8')
        except OSError as e:
            print(f"[WARNING] {label}缓存读取异常: {e}")

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'occupation-analysis/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        if len(raw) > max_bytes:
            print(f"[WARNING] {label}超过大小上限 {max_bytes} 字节: {url[:60]}...")
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
                print(f"[WARNING] {label}缓存写入失败: {e}")
        return content
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, UnicodeDecodeError) as e:
        print(f"[WARNING] {label}下载失败 ({url[:60]}...): {e}")
        return None
