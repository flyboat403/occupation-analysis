#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ESCO / O*NET 索引生成与检索的离线单元测试"""

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import build_intl_index as bi  # noqa: E402
import doc_fetch  # noqa: E402
import search_intl as si  # noqa: E402

BASE = 'https://raw.githubusercontent.com/o/r/main'
ESCO_MD = """# linguistics lecturer

## Basic Information

| Field | Value |
|-------|-------|
| **URI** | [http://data.europa.eu/esco/occupation/x](http://data.europa.eu/esco/occupation/x) |
| **Status** | released |

## Alternative Terms

- professor of linguistics
- linguistics teacher

## Description

Sample.
"""

ONET_MD = """# 15-2051.01 - Business Intelligence Analysts

**Quick Facts:**
- SOC Code: 15-2051.01
- Also called: Business Analyst, BI Analyst
"""


class BuildFixtureTest(unittest.TestCase):
    def test_esco_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / '2310.1.23.md').write_text(ESCO_MD, encoding='utf-8')
            entries = bi.build_esco_index(d, BASE)
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry['esco_code'], '2310.1.23')
        self.assertEqual(entry['isco_code'], '2310')
        self.assertEqual(entry['title'], 'linguistics lecturer')
        self.assertEqual(entry['uri'], 'http://data.europa.eu/esco/occupation/x')
        self.assertEqual(entry['status'], 'released')
        self.assertIn('professor of linguistics', entry['alternative_terms'])
        self.assertEqual(entry['md_url'], f'{BASE}/esco_details_md/2310.1.23.md')

    def test_onet_parse_and_deprecated_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / '15-2051.01.md').write_text(ONET_MD, encoding='utf-8')
            (d / '15-1199.08.md').write_text(ONET_MD, encoding='utf-8')
            entries = {e['onet_code']: e for e in bi.build_onet_index(d, BASE)}
        self.assertFalse(entries['15-2051.01']['deprecated_alias'])
        self.assertTrue(entries['15-1199.08']['deprecated_alias'])
        self.assertEqual(entries['15-1199.08']['soc_code'], '15-2051.01')
        self.assertEqual(entries['15-2051.01']['also_called'], ['Business Analyst', 'BI Analyst'])


class IndexFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.esco = json.loads((ROOT / 'assets' / 'esco_final.json').read_text(encoding='utf-8'))
        cls.onet = json.loads((ROOT / 'assets' / 'onet_final.json').read_text(encoding='utf-8'))

    def test_counts_and_parity(self):
        self.assertEqual(len(self.esco), len(list((ROOT / 'assets' / 'esco_details_md').glob('*.md'))))
        self.assertEqual(len(self.onet), len(list((ROOT / 'assets' / 'onet_details_md').glob('*.md'))))
        self.assertEqual({e['esco_code'] for e in self.esco},
                         {p.stem for p in (ROOT / 'assets' / 'esco_details_md').glob('*.md')})
        self.assertEqual({e['onet_code'] for e in self.onet},
                         {p.stem for p in (ROOT / 'assets' / 'onet_details_md').glob('*.md')})

    def test_urls_and_aliases(self):
        for entry in self.esco:
            self.assertTrue(entry['md_url'].startswith(f'{bi.DEFAULT_BASE_URL}/esco_details_md/'))
            self.assertTrue(entry['title'])
        for entry in self.onet:
            self.assertTrue(entry['md_url'].startswith(f'{bi.DEFAULT_BASE_URL}/onet_details_md/'))
            self.assertTrue(entry['title'])
        self.assertGreater(sum(len(e['alternative_terms']) for e in self.esco), 15000)
        self.assertGreater(sum(len(e['also_called']) for e in self.onet), 7000)

    def test_deprecated_alias_count(self):
        self.assertEqual(sum(1 for e in self.onet if e['deprecated_alias']), 2)


class SearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.esco = si.load_index(ROOT / 'assets' / 'esco_final.json', 'esco')
        cls.onet = si.load_index(ROOT / 'assets' / 'onet_final.json', 'onet')

    def test_normalization(self):
        self.assertEqual(si.normalize_esco_code('ISCO-2310'), '2310')
        self.assertEqual(si.normalize_esco_code('2636.00'), '2636')
        self.assertEqual(si.normalize_onet_code('11-9051'), '11-9051.00')
        self.assertEqual(si.normalize_onet_code('11-9051.0'), '11-9051.00')

    def test_esco_code_matching(self):
        self.assertGreater(len(si.match_esco_code(self.esco, '2310')), 1)
        self.assertEqual([e['esco_code'] for e in si.match_esco_code(self.esco, '2310.1.23')],
                         ['2310.1.23'])
        self.assertEqual([e['esco_code'] for e in si.match_esco_code(self.esco, 'ISCO-2310.1.23')],
                         ['2310.1.23'])

    def test_onet_code_matching(self):
        self.assertEqual([e['onet_code'] for e in si.match_onet_code(self.onet, '11-9051')],
                         ['11-9051.00'])
        self.assertEqual([e['onet_code'] for e in si.match_onet_code(self.onet, '15-2051.01')],
                         ['15-2051.01'])
        self.assertEqual({e['onet_code'] for e in si.match_onet_code(self.onet, '15-2051.01', True)},
                         {'15-1199.08', '15-2051.01'})
        self.assertEqual([e['onet_code'] for e in si.match_onet_code(self.onet, '15-1199.08')],
                         ['15-1199.08'])

    def test_name_and_alias_search(self):
        results = si.search(self.esco, None, 'financial analyst', source='esco')
        self.assertEqual(results[0]['esco_code'], '2413.1')
        alias = si.search(self.esco, None, 'PROFESSOR OF LINGUISTICS', source='esco')
        self.assertEqual(alias[0]['esco_code'], '2310.1.23')
        self.assertEqual(alias[0]['matched_on'], 'alias')

    def test_local_availability(self):
        results = si.search(self.esco, '2310', None, source='esco')
        self.assertTrue(results)
        for entry in results:
            self.assertTrue(Path(entry['local_path']).exists())

    def test_local_path_respects_assets_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp)
            entries = si.load_index(ROOT / 'assets' / 'esco_final.json', 'esco', assets)
        entry = next(e for e in entries if e['esco_code'] == '2310.1.23')
        self.assertEqual(entry['local_path'], str(assets / 'esco_details_md' / '2310.1.23.md'))

    def test_load_index_defaults_to_index_directory(self):
        entries = si.load_index(ROOT / 'assets' / 'esco_final.json', 'esco')
        entry = next(e for e in entries if e['esco_code'] == '2310.1.23')
        self.assertEqual(entry['local_path'],
                         str(ROOT / 'assets' / 'esco_details_md' / '2310.1.23.md'))
        self.assertTrue(Path(entry['local_path']).exists())

    def test_cli_assets_dir_defaults_to_skill_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(ROOT / 'scripts' / 'search_intl.py'),
                 '--source', 'esco', '--code', '2310.1.23'],
                cwd=tmp, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('本地', result.stdout)


class DocFetchTest(unittest.TestCase):
    def test_warning_goes_to_stderr(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.assertIsNone(doc_fetch.fetch_cached('http://evil.example.com/x.md'))
        self.assertEqual(out.getvalue(), '')
        self.assertIn('[WARNING]', err.getvalue())

    def test_corrupt_cache_falls_back_to_download(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, size=-1):
                return b'# fresh'

        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / 'a.md').write_bytes(b'\xff\xfe')
            with patch('doc_fetch.urllib.request.urlopen', return_value=FakeResponse()):
                content = doc_fetch.fetch_cached(
                    'https://raw.githubusercontent.com/o/r/a.md', cache)
            self.assertEqual(content, '# fresh')
            self.assertEqual((cache / 'a.md').read_text(encoding='utf-8'), '# fresh')


class FetchTest(unittest.TestCase):
    def test_fetch_to_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'doc.md'
            results = [{'md_url': 'https://raw.githubusercontent.com/o/r/main/esco_details_md/2310.1.23.md'}]
            with patch.object(si, 'fetch_cached', return_value='# content') as mocked:
                si.fetch_results(results, str(out), None)
            self.assertEqual(out.read_text(encoding='utf-8'), '# content')
            self.assertEqual(results[0]['fetched_path'], str(out))
            mocked.assert_called_once()

    def test_fetch_multiple_with_output_rejected(self):
        results = [{'md_url': 'u1'}, {'md_url': 'u2'}]
        with self.assertRaises(SystemExit):
            si.fetch_results(results, 'out.md', None)

    def test_fetch_failure_marks_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = [{'md_url': 'https://raw.githubusercontent.com/o/r/main/x.md'}]
            with patch.object(si, 'fetch_cached', return_value=None):
                si.fetch_results(results, str(Path(tmp) / 'x.md'), Path(tmp))
            self.assertNotIn('fetched_path', results)

    def test_format_table(self):
        self.assertIn('未找到', si.format_table([]))
        table = si.format_table([{
            'source': 'esco', 'code': '2310.1.23', 'title': 'linguistics lecturer',
            'md_url': 'https://example/x.md', 'local_path': 'assets/esco_details_md/2310.1.23.md'
        }])
        self.assertIn('2310.1.23', table)


if __name__ == '__main__':
    unittest.main()
