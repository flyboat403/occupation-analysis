#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""search_major.py 简介索引与兜底逻辑的离线单元测试"""

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import search_major as sm  # noqa: E402
from major_catalog_mapper import get_catalog, get_category_from_major_code  # noqa: E402

MD_DIR = ROOT / 'assets' / 'moe_pdfs_md'
JIANJIE_JSON = ROOT / 'assets' / 'moe_jianjie_final_github.json'


class FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._data


def read_md(name: str) -> str:
    return (MD_DIR / name).read_text(encoding='utf-8')


class ParseMdTest(unittest.TestCase):
    def test_parse_existing_major(self):
        parsed = sm.parse_md_content(read_md('2101农业类.md'), '210101')
        self.assertEqual(parsed['major_name'], '现代种业技术')
        self.assertTrue(parsed['raw_text'])
        self.assertTrue(parsed['career_orientation'])

    def test_parse_missing_major_returns_empty(self):
        parsed = sm.parse_md_content(read_md('7102计算机类.md'), '710212')
        self.assertEqual(parsed['major_name'], '')
        self.assertEqual(parsed['raw_text'], '')

    def test_parse_k_suffix_both_forms(self):
        content = read_md('5701教育类.md')
        for code in ('570104K', '570104', '570104k'):
            parsed = sm.parse_md_content(content, code)
            self.assertEqual(parsed['major_name'], '小学语文教育', code)
            self.assertEqual(parsed['education_level'], '高等职业教育', code)


class JianjieIndexTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = sm.load_jianjie_index(JIANJIE_JSON)
        cls.lookup = sm.build_jianjie_lookup(cls.index)

    def test_load_index(self):
        self.assertGreater(len(self.index), 1000)

    def test_exact_and_prefix_lookup(self):
        exact = sm.find_jianjie_entry(self.index, '210101')
        self.assertEqual(exact['major_code'], '210101')
        prefix = sm.find_jianjie_entry(self.index, '710212', category_code='7102')
        self.assertTrue(prefix['major_code'].startswith('7102'))

    def test_lookup_dict_matches(self):
        for code, category in (('210101', ''), ('710212', '7102'), ('570104K', '5701')):
            self.assertEqual(
                sm.find_jianjie_entry(self.index, code, category),
                sm.find_jianjie_entry(self.index, code, category, lookup=self.lookup),
            )


class FallbackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = sm.load_jianjie_index(JIANJIE_JSON)

    def test_local_fallback_missing_major_returns_nothing(self):
        results = sm.search_from_fallback('710212', '中职', ROOT, jianjie_index=None)
        self.assertEqual(results, [])

    def test_local_fallback_valid_major(self):
        results = sm.search_from_fallback('210101', '职教本科', ROOT, jianjie_index=None)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['major_name'], '现代种业技术')
        self.assertEqual(results[0]['source'], 'moe_pdfs_md')

    def test_jianjie_fallback_skips_empty_section(self):
        content = read_md('7102计算机类.md')
        with patch.object(sm, 'download_md_content', return_value=content):
            results = sm.search_from_fallback('710212', '中职', ROOT, jianjie_index=self.index)
        self.assertEqual(results, [])

    def test_jianjie_fallback_valid_major(self):
        content = read_md('2101农业类.md')
        with patch.object(sm, 'download_md_content', return_value=content):
            results = sm.search_from_fallback('210101', '职教本科', ROOT, jianjie_index=self.index)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['major_name'], '现代种业技术')
        self.assertEqual(results[0]['source'], 'moe_jianjie_github')

    def test_dedupe(self):
        content = read_md('2101农业类.md')
        with patch.object(sm, 'download_md_content', return_value=content):
            results = sm.search_from_fallback('现代种业技术', None, ROOT, jianjie_index=self.index)
        codes = [sm._normalize_major_code(r['major_code']) for r in results]
        self.assertEqual(len(codes), len(set(codes)))


class FillResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = sm.load_jianjie_index(JIANJIE_JSON)

    def test_fill_on_pdf_failure(self):
        content = read_md('3302金融类.md')
        with patch.object(sm, 'download_md_content', return_value=content):
            result = {
                'major_code': '330201',
                'major_name': '金融管理',
                'education_level': '',
                'career_orientation': '',
                'training_goal': '',
                'raw_text': '',
            }
            filled = sm.fill_result_from_jianjie(result, self.index)
        self.assertTrue(filled)
        self.assertEqual(result['content_source'], 'moe_jianjie_github')
        self.assertTrue(result['career_orientation'])
        self.assertTrue(result['training_goal'])

    def test_fill_skips_missing_section(self):
        content = read_md('7102计算机类.md')
        with patch.object(sm, 'download_md_content', return_value=content):
            result = {
                'major_code': '710212',
                'major_name': '',
                'education_level': '',
                'career_orientation': '',
                'training_goal': '',
                'raw_text': '',
            }
            filled = sm.fill_result_from_jianjie(result, self.index)
        self.assertFalse(filled)
        self.assertNotIn('content_source', result)


class DownloadGuardTest(unittest.TestCase):
    def test_rejects_non_whitelisted_urls(self):
        self.assertIsNone(sm.download_md_content('http://raw.githubusercontent.com/a/b.md'))
        self.assertIsNone(sm.download_md_content('https://evil.example.com/a/b.md'))
        self.assertIsNone(sm.download_md_content(''))

    def test_cache_filename_is_sanitized(self):
        import tempfile
        payload = b'# test'
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            url = 'https://raw.githubusercontent.com/o/r/..%2F..%2Fevil.md'
            with patch.object(sm.urllib.request, 'urlopen', return_value=FakeResponse(payload)):
                content = sm.download_md_content(url, cache)
            self.assertEqual(content, '# test')
            self.assertTrue((cache / 'evil.md').exists())
            self.assertFalse((cache.parent / 'evil.md').exists())

    def test_cache_ttl_refresh(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            cached = cache / 'a.md'
            cached.write_text('old', encoding='utf-8')
            stale = time.time() - sm.MD_CACHE_TTL - 60
            os.utime(cached, (stale, stale))
            url = 'https://raw.githubusercontent.com/o/r/a.md'
            with patch.object(sm.urllib.request, 'urlopen', return_value=FakeResponse(b'new')) as mock:
                content = sm.download_md_content(url, cache)
            self.assertEqual(content, 'new')
            mock.assert_called_once()
            self.assertEqual(cached.read_text(encoding='utf-8'), 'new')

    def test_cache_hit_skips_download(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / 'a.md').write_text('cached', encoding='utf-8')
            url = 'https://raw.githubusercontent.com/o/r/a.md'
            with patch.object(sm.urllib.request, 'urlopen', return_value=FakeResponse(b'new')) as mock:
                content = sm.download_md_content(url, cache)
            self.assertEqual(content, 'cached')
            mock.assert_not_called()


class CatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = get_catalog()

    def test_catalog_superset(self):
        self.assertGreaterEqual(len(self.catalog), 1490)

    def test_k_code_both_forms(self):
        for code in ('570104K', '570104', '570104k', ' 570104 '):
            info = get_category_from_major_code(self.catalog, code)
            self.assertIsNotNone(info, code)
            self.assertEqual(info['专业代码'], '570104K')
            self.assertEqual(info['专业名称'], '小学语文教育')


if __name__ == '__main__':
    unittest.main()
