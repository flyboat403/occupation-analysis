#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专业教学标准检索脚本

数据源优先级（更新）：
1. 主数据源：assets/moe_pdfs_final.json（PDF索引，仅索引不含内容）
   - 找到专业且有PDF URL → 下载并解析PDF获取完整内容
   - 找到专业但PDF不可解析 → 用专业简介索引补全职业面向/培养目标
2. 备选数据源：assets/moe_jianjie_final_github.json（专业简介索引）
   - 按专业代码查 md_url → 下载并解析专业简介（GitHub镜像）
3. 离线兜底：assets/moe_pdfs_md/{类代码}*.md
   - 简介索引缺失或下载失败时，扫描本地类级MD文件

流程：
1. 从 moe_pdfs_final.json 查找专业 → 得到 PDF URL
2. 如果有 PDF URL，下载并解析 PDF
3. PDF 不可用时，从 moe_jianjie_final_github.json 查 md_url 下载解析专业简介
4. 若主索引中没有该专业，则用简介索引检索；索引不可用再降级本地 moe_pdfs_md 目录
"""

import json
import re
import argparse
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from major_catalog_mapper import get_catalog, get_category_from_major_code, get_md_file_path
from doc_fetch import fetch_cached

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

def load_major_data(json_path: Path) -> List[Dict]:
    """
    加载专业教学标准JSON数据
    
    Args:
        json_path: JSON文件路径
        
    Returns:
        专业数据列表
        
    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON解析失败
    """
    if not json_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {json_path}")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"JSON解析失败: {json_path}", e.doc, e.pos)

def search_by_code(data: List[Dict], code: str) -> Optional[Dict]:
    """按专业代码检索"""
    for item in data:
        if item.get('major_code') == code:
            return item
    return None

def search_by_name(data: List[Dict], name: str) -> List[Dict]:
    """按专业名称检索（支持模糊匹配）"""
    results = []
    for item in data:
        if name in item.get('major_name', ''):
            results.append(item)
    return results

def search_by_level(data: List[Dict], level: str) -> List[Dict]:
    """按教育层次筛选"""
    results = []
    
    level_aliases = {
        '中职': ['中等职业教育', '中职学校', '中职教育', '职高', '中专', '技校'],
        '高职': ['高等职业教育', '高职专科', '专科','高职院校'],
        '职教本科': ['职业教育本科', '职教本科', '本科']
    }
    
    aliases = level_aliases.get(level, [level])
    
    for item in data:
        edu_level = item.get('education_level', '')
        if any(alias in edu_level for alias in aliases):
            results.append(item)
    
    return results

def search_major(
    query: str,
    level: Optional[str] = None,
    json_path: str = "assets/moe_pdfs_final.json",
    output_path: Optional[str] = None,
    use_fallback: bool = True,
    parse_pdf: bool = True,
    cache_dir: Optional[str] = "temp/pdf_cache",
    jianjie_json_path: str = "assets/moe_jianjie_final_github.json",
    md_cache_dir: Optional[str] = "temp/md_cache"
) -> Dict:
    """
    检索专业教学标准

    数据源优先级：
    1. 主数据源：moe_pdfs_final.json
       - 找到专业且有PDF URL → 下载并解析PDF获取完整内容
       - 找到专业但PDF不可解析 → 用专业简介索引补全职业面向/培养目标
    2. 备选数据源：moe_jianjie_final_github.json（专业简介索引）
       - 按专业代码查 md_url → 下载并解析专业简介
    3. 离线兜底：moe_pdfs_md/{类代码}*.md
       - 简介索引缺失或下载失败时使用

    Args:
        query: 专业名称或代码
        level: 教育层次（可选）
        json_path: JSON数据文件路径
        output_path: 输出文件路径（可选）
        use_fallback: 是否使用备用数据源（默认True）
        parse_pdf: 是否解析PDF获取完整内容（默认True）
        cache_dir: PDF缓存目录（默认temp/pdf_cache）
        jianjie_json_path: 专业简介索引路径（默认assets/moe_jianjie_final_github.json）
        md_cache_dir: 专业简介MD缓存目录（默认temp/md_cache）

    Returns:
        检索结果字典
    """
    # 输入验证
    if not query or not query.strip():
        return {"query": query, "level": level, "total": 0, "results": [], "error": "查询参数不能为空"}
    
    # 确定项目根目录（指向skill/occupation-analysis目录）
    script_dir = Path(__file__).parent
    project_root = script_dir.parent  # scripts/ -> occupation-analysis/
    json_full_path = project_root / json_path
    
    # 如果主数据源不存在，尝试备选数据源
    if not json_full_path.exists():
        json_full_path = project_root / "assets/moe_pdfs_new.json"
    
    # 主数据源检索
    results = []
    data_source = "primary"
    pdf_parsed = False
    
    if json_full_path.exists():
        try:
            data = load_major_data(json_full_path)
            
            # 尝试按代码检索（兼容 K 后缀国控专业）
            code_query = query.strip().upper()
            if re.fullmatch(r'\d{6}K?', code_query):
                result = search_by_code(data, code_query)
                if not result and code_query.endswith('K'):
                    result = search_by_code(data, code_query[:-1])
                if not result and len(code_query) == 6 and code_query.isdigit():
                    result = search_by_code(data, code_query + 'K')
                if result:
                    results = [result]
            else:
                # 按名称检索
                results = search_by_name(data, query)
            
            # 按层次筛选
            if level and results:
                results = search_by_level(results, level)
            
            # 尝试解析PDF获取完整内容
            if results and parse_pdf:
                for i, result in enumerate(results):
                    pdf_url = result.get('pdf_url', '')
                    major_code = result.get('major_code', '')
                    
                    if pdf_url:
                        print(f"[INFO] 找到PDF URL，尝试解析: {major_code}")
                        pdf_result = parse_pdf_to_result(pdf_url, major_code, project_root, cache_dir)
                        
                        if pdf_result:
                            # 合并PDF解析结果到基本信息
                            result.update(pdf_result)
                            result['pdf_parsed'] = True
                            pdf_parsed = True
                            print(f"[OK] PDF解析成功: {major_code}")
                        else:
                            result['pdf_parsed'] = False
                            result['pdf_parse_error'] = "PDF解析失败"
                            print(f"[WARNING] PDF解析失败，仅返回基本信息: {major_code}")
                    else:
                        result['pdf_parsed'] = False
                        result['pdf_parse_error'] = "无PDF URL"
                
        except (FileNotFoundError, json.JSONDecodeError) as e:
            error_msg = f"主数据源加载失败: {e}"
            print(f"[ERROR] {error_msg}")
            return {
                "query": query,
                "level": level,
                "total": 0,
                "results": [],
                "error": error_msg,
                "data_source": "failed"
            }
    
    # PDF不可解析时用专业简介索引补全内容（仅填空字段，失败静默）
    if results and parse_pdf and not pdf_parsed:
        jianjie_index = load_jianjie_index(project_root / jianjie_json_path)
        if jianjie_index:
            md_cache_path = (project_root / md_cache_dir) if md_cache_dir else None
            for result in results:
                if fill_result_from_jianjie(result, jianjie_index, md_cache_path):
                    print(f"[OK] 已用专业简介补全内容: {result.get('major_code')}")

    # 备用数据源检索（仅当主数据源未找到时）
    if not results and use_fallback:
        print(f"[INFO] 主数据源未找到结果，尝试备用数据源...")
        jianjie_index = load_jianjie_index(project_root / jianjie_json_path)
        md_cache_path = (project_root / md_cache_dir) if md_cache_dir else None
        fallback_results = search_from_fallback(
            query,
            level,
            project_root,
            jianjie_index=jianjie_index,
            md_cache_dir=md_cache_path,
        )
        if fallback_results:
            results = fallback_results
            data_source = "fallback"
    
    # 准备输出
    output = {
        "query": query,
        "level": level,
        "total": len(results),
        "results": results,
        "data_source": data_source
    }
    
    # 保存到文件
    if output_path:
        try:
            output_full_path = project_root / output_path
            output_full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_full_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            print(f"[OK] 结果已保存到: {output_full_path}")
        except IOError as e:
            print(f"[ERROR] 保存文件失败: {e}")
    
    return output


def parse_pdf_to_result(
    pdf_url: str,
    major_code: str,
    project_root: Path,
    cache_dir: Optional[str] = "temp/pdf_cache"
) -> Optional[Dict]:
    """
    解析PDF获取专业教学标准完整内容
    
    Args:
        pdf_url: PDF文档URL
        major_code: 专业代码
        project_root: 项目根目录
        cache_dir: 缓存目录
    
    Returns:
        解析结果字典，失败返回None
    """
    try:
        # 尝试导入PDF解析模块
        from pdf_parser import fetch_and_parse_pdf, to_dict
        
        # 确定缓存目录
        cache_path = project_root / cache_dir if cache_dir else None
        
        # 调用PDF解析
        standard = fetch_and_parse_pdf(
            url=pdf_url,
            major_code=major_code,
            cache_dir=cache_path,
            use_cache=True
        )
        
        if standard:
            return to_dict(standard)
        
        return None
        
    except ImportError:
        print("[WARNING] PDF解析模块未安装，跳过PDF解析")
        print("[HINT] 请安装依赖: pip install pdfplumber 或 pip install pypdf")
        return None
    except Exception as e:
        print(f"[ERROR] PDF解析异常: {e}")
        return None


def load_jianjie_index(json_path: Path) -> List[Dict]:
    """加载专业简介索引（字段：major_code / major_name / education_level / md_url）"""
    if not json_path.exists():
        return []
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        print(f"[WARNING] 专业简介索引加载失败: {e}")
        return []


def _normalize_major_code(code: str) -> str:
    code = str(code or '').strip().upper()
    return code[:-1] if code.endswith('K') else code


def build_jianjie_lookup(index: List[Dict]) -> Dict[str, Dict]:
    """构建 normalized_code -> entry 的索引字典，避免重复线性扫描"""
    return {_normalize_major_code(item.get('major_code', '')): item for item in index}


def find_jianjie_entry(
    index: List[Dict],
    major_code: str,
    category_code: str = '',
    lookup: Optional[Dict[str, Dict]] = None
) -> Optional[Dict]:
    """在简介索引中定位条目：6位代码（忽略K）精确匹配 → 4位专业类前缀首个条目"""
    target = _normalize_major_code(major_code)
    if target:
        if lookup is not None:
            item = lookup.get(target)
            if item:
                return item
        else:
            for item in index:
                if _normalize_major_code(item.get('major_code', '')) == target:
                    return item
    if category_code:
        prefix = _normalize_major_code(category_code)[:4]
        for item in index:
            if _normalize_major_code(item.get('major_code', '')).startswith(prefix):
                return item
    return None


def download_md_content(md_url: str, cache_dir: Optional[Path] = None, timeout: int = 30) -> Optional[str]:
    """下载简介MD内容（磁盘缓存+TTL+原子写入），失败返回None"""
    return fetch_cached(md_url, cache_dir=cache_dir, timeout=timeout, label='简介')


def parse_md_content(content: str, target_code: str, source_file: str = '') -> Optional[Dict]:
    """解析专业简介MD文本，提取指定专业代码的段落（兼容K后缀国控专业）"""
    if not content:
        return None

    result = {
        'major_code': target_code,
        'major_name': '',
        'education_level': '',
        'career_orientation': '',
        'training_goal': '',
        'raw_text': '',
        'source_file': source_file,
        'pdf_url': ''
    }

    target = _normalize_major_code(target_code)
    major_section_pattern = rf'专业代码\s*{re.escape(target)}K?\s*\n(.*?)(?=专业代码\s*\d{{6}}K?|$)'
    major_match = re.search(major_section_pattern, content, re.DOTALL)
    if not major_match:
        return result

    major_section = major_match.group(1)
    result['raw_text'] = re.sub(r'\n{3,}', '\n\n', major_section.strip())

    name_match = re.search(r'专业名称\s*([^\n]+)', major_section)
    if name_match:
        result['major_name'] = name_match.group(1).strip()

    orientation_match = re.search(r'#\s*职业面向\s*\n+(.*?)(?=\n#|\Z)', major_section, re.DOTALL)
    if orientation_match:
        result['career_orientation'] = orientation_match.group(1).strip()

    goal_match = re.search(r'#\s*培养目标定位?\s*\n+(.*?)(?=\n#|\Z)', major_section, re.DOTALL)
    if goal_match:
        result['training_goal'] = goal_match.group(1).strip()

    first = target[:1]
    if first in ('2', '3'):
        result['education_level'] = '职业教育本科'
    elif first in ('4', '5'):
        result['education_level'] = '高等职业教育'
    elif first in ('6', '7'):
        result['education_level'] = '中等职业教育'

    return result


def parse_md_file(md_path: Path, target_code: str) -> Optional[Dict]:
    """解析本地类级专业简介MD文件，提取指定专业代码的段落"""
    if not md_path.exists():
        return None
    try:
        content = md_path.read_text(encoding='utf-8')
        return parse_md_content(content, target_code, source_file=md_path.name)
    except OSError as e:
        print(f"[ERROR] 解析MD文件失败 {md_path}: {e}")
        return None


def resolve_jianjie_content(
    major_code: str,
    jianjie_index: List[Dict],
    category_code: str = '',
    md_cache_dir: Optional[Path] = None,
    lookup: Optional[Dict[str, Dict]] = None
) -> Optional[Dict]:
    """从简介索引解析指定专业内容；未命中/下载失败/段落缺失时返回None"""
    entry = find_jianjie_entry(jianjie_index, major_code, category_code, lookup=lookup)
    if not entry:
        return None
    content = download_md_content(entry.get('md_url', ''), md_cache_dir)
    if not content:
        return None
    parsed = parse_md_content(
        content,
        major_code or entry.get('major_code', ''),
        source_file=urllib.parse.unquote(entry.get('md_url', '').rsplit('/', 1)[-1]),
    )
    if not parsed or not parsed.get('raw_text'):
        return None
    parsed['content_source'] = 'moe_jianjie_github'
    parsed['md_url'] = entry.get('md_url', '')
    if not parsed.get('major_name'):
        parsed['major_name'] = entry.get('major_name', '')
    if not parsed.get('education_level'):
        parsed['education_level'] = entry.get('education_level', '')
    return parsed


def fill_result_from_jianjie(result: Dict, jianjie_index: List[Dict], cache_dir: Optional[Path] = None) -> bool:
    """PDF不可解析时，用专业简介索引补全职业面向/培养目标等空字段"""
    if not jianjie_index:
        return False
    if result.get('career_orientation') and result.get('training_goal'):
        return False
    major_code = str(result.get('major_code', ''))
    parsed = resolve_jianjie_content(major_code, jianjie_index, md_cache_dir=cache_dir)
    if not parsed:
        return False
    filled = False
    for key in ('career_orientation', 'training_goal', 'raw_text'):
        if not result.get(key) and parsed.get(key):
            result[key] = parsed[key]
            filled = True
    if not result.get('major_name'):
        result['major_name'] = parsed.get('major_name', '')
    if not result.get('education_level'):
        result['education_level'] = parsed.get('education_level', '')
    if filled:
        result['content_source'] = 'moe_jianjie_github'
        result['md_url'] = parsed.get('md_url', '')
        result['md_file'] = urllib.parse.unquote(parsed.get('md_url', '').rsplit('/', 1)[-1])
    return filled


def search_from_fallback(
    query: str,
    level: Optional[str],
    project_root: Path,
    jianjie_index: Optional[List[Dict]] = None,
    md_cache_dir: Optional[Path] = None
) -> List[Dict]:
    """
    从备用数据源检索专业信息

    优先级：专业简介索引（md_url下载） → 本地 moe_pdfs_md 目录（离线兜底）

    Args:
        query: 专业名称或代码
        level: 教育层次
        project_root: 项目根目录
        jianjie_index: 专业简介索引（None时直接走本地目录）
        md_cache_dir: 简介MD缓存目录

    Returns:
        检索结果列表
    """
    results = []
    try:
        catalog = get_catalog()
        moe_pdfs_md_dir = project_root / "assets/moe_pdfs_md"

        candidates: List[Tuple[str, Optional[Dict]]] = []
        query_code = _normalize_major_code(query)
        if query_code.isdigit() and len(query_code) == 6:
            info = get_category_from_major_code(catalog, query_code)
            candidates.append((str(query).strip(), info))
        else:
            from major_catalog_mapper import search_major_in_catalog
            for match in search_major_in_catalog(query, catalog)[:5]:
                code = str(match.get('专业代码', ''))
                info = get_category_from_major_code(catalog, code)
                candidates.append((code, info))

            if jianjie_index:
                seen = {code for code, _ in candidates}
                for item in jianjie_index:
                    name = str(item.get('major_name', ''))
                    code = str(item.get('major_code', ''))
                    if query in name and code not in seen:
                        candidates.append((code, None))
                        seen.add(code)
                        if len(candidates) >= 5:
                            break

        if jianjie_index:
            lookup = build_jianjie_lookup(jianjie_index)
            for code, info in candidates:
                category_code = str(info.get('类代码', '')) if info else ''
                parsed = resolve_jianjie_content(
                    code,
                    jianjie_index,
                    category_code=category_code,
                    md_cache_dir=md_cache_dir,
                    lookup=lookup,
                )
                if not parsed:
                    continue
                parsed['source'] = 'moe_jianjie_github'
                results.append(parsed)
            if not results:
                print("[WARNING] 简介索引未命中或下载失败，降级为本地目录兜底")

        if not results:
            for code, info in candidates:
                if not info:
                    continue
                md_path = get_md_file_path(info, moe_pdfs_md_dir)
                if not md_path:
                    continue
                parsed = parse_md_file(md_path, code)
                if parsed and parsed.get('raw_text'):
                    parsed['source'] = 'moe_pdfs_md'
                    results.append(parsed)

        deduped = []
        seen_codes = set()
        for item in results:
            key = _normalize_major_code(item.get('major_code', ''))
            if key in seen_codes:
                continue
            seen_codes.add(key)
            deduped.append(item)
        results = deduped

        if level and results:
            level_prefix = {
                '中职': ('6', '7'),
                '中等职业教育': ('6', '7'),
                '高职': ('4', '5'),
                '高等职业教育': ('4', '5'),
                '专科': ('4', '5'),
                '职教本科': ('2', '3'),
                '职业教育本科': ('2', '3'),
                '本科': ('2', '3'),
            }
            prefixes = level_prefix.get(level)
            if prefixes:
                results = [r for r in results if str(r.get('major_code', '')).startswith(prefixes)]

    except Exception as e:
        print(f"[ERROR] 备用数据源检索失败: {e}")

    return results


# ==================== 专业-职业对照表查询 ====================

def get_mapping_sheet_name(level: Optional[str] = None) -> str:
    """
    根据教育层次获取对照表工作表名称
    
    Args:
        level: 教育层次字符串（可选）
        
    Returns:
        工作表名称
    """
    level_lower = (level or '').lower()
    
    if '中职' in level_lower or '中等' in level_lower:
        return '中职-专业职业对照'
    elif '高职' in level_lower or '专科' in level_lower or '高等' in level_lower:
        return '高职专业-专业职业对照'
    elif '本科' in level_lower:
        return '职教本科-专业职业对照'
    else:
        # 默认尝试中职
        return '中职-专业职业对照'


def query_occupation_mapping(
    major_code: str,
    level: Optional[str] = None,
    xlsx_path: str = "assets/专业-职业对照表.xlsx"
) -> List[Dict]:
    """
    从专业-职业对照表查询职业编码
    
    Args:
        major_code: 专业代码（如 740202）
        level: 教育层次（用于确定工作表）
        xlsx_path: 对照表文件路径
        
    Returns:
        职业信息列表 [{"code": "4-03-02-03", "name": "西式烹调师"}, ...]
    """
    if not HAS_OPENPYXL:
        print("[WARNING] openpyxl未安装，无法查询对照表")
        return []
    
    results = []
    
    try:
        from pathlib import Path
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        full_path = project_root / xlsx_path
        
        if not full_path.exists():
            print(f"[WARNING] 对照表文件不存在: {full_path}")
            return []
        
        wb = openpyxl.load_workbook(full_path)
        
        # 获取工作表名称
        sheet_name = get_mapping_sheet_name(level)
        
        if sheet_name not in wb.sheetnames:
            # 尝试其他工作表
            for name in wb.sheetnames:
                if '中职' in name or '高职' in name or '本科' in name:
                    sheet_name = name
                    break
        
        ws = wb[sheet_name]
        
        # 专业代码可能在第2列（B列），职业编码在第4列（D列），职业名称在第5列（E列）
        # 遍历查找
        for row in ws.iter_rows(min_row=2, values_only=True):
            if len(row) >= 5:
                row_major_code = row[1]  # 专业代码
                
                # 处理专业代码格式（可能是整数或字符串）
                if isinstance(row_major_code, int):
                    row_major_code = str(row_major_code)
                
                # 匹配专业代码
                if row_major_code == str(major_code):
                    occupation_code = row[3]  # 职业编码
                    occupation_name = row[4]  # 职业名称
                    
                    if occupation_code and occupation_name:
                        results.append({
                            "code": str(occupation_code) if isinstance(occupation_code, int) else occupation_code,
                            "name": occupation_name
                        })
        
        if results:
            print(f"[OK] 从对照表查询到 {len(results)} 个职业")
        else:
            print(f"[INFO] 对照表中未找到专业代码 {major_code} 对应的职业")
            
    except Exception as e:
        print(f"[ERROR] 对照表查询失败: {e}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description='检索专业教学标准')
    parser.add_argument('--major', '-m', required=True, help='专业名称或代码')
    parser.add_argument('--level', '-l', help='教育层次（中职/高职/职教本科）')
    parser.add_argument('--json', '-j', default='assets/moe_pdfs_final.json', help='JSON数据文件路径')
    parser.add_argument('--output', '-o', help='输出文件路径')
    parser.add_argument('--no-pdf', action='store_true', help='不解析PDF（仍会尝试专业简介索引/本地MD兜底）')
    parser.add_argument('--cache-dir', default='temp/pdf_cache', help='PDF缓存目录')
    parser.add_argument('--jianjie-json', default='assets/moe_jianjie_final_github.json',
                        help='专业简介索引路径（GitHub镜像）')
    parser.add_argument('--md-cache-dir', default='temp/md_cache', help='专业简介MD缓存目录')
    parser.add_argument('--no-md-cache', action='store_true', help='禁用专业简介MD缓存（强制联网拉取）')
    parser.add_argument('--include-occupations', action='store_true', 
                        help='同时输出专业-职业对照表中的职业编码')
    
    args = parser.parse_args()
    
    result = search_major(
        query=args.major,
        level=args.level,
        json_path=args.json,
        output_path=args.output,
        parse_pdf=not args.no_pdf,
        cache_dir=args.cache_dir,
        jianjie_json_path=args.jianjie_json,
        md_cache_dir=None if args.no_md_cache else args.md_cache_dir
    )
    
    # 保存完整raw_text到结果中（确保数据完整性）
    if result['results']:
        for item in result['results']:
            # 从PDF缓存读取完整raw_text
            if item.get('major_code') and item.get('pdf_parsed'):
                cache_file = Path(__file__).parent.parent / args.cache_dir / f"{item['major_code']}.json"
                if args.cache_dir and cache_file.exists():
                    try:
                        cache_data = json.loads(cache_file.read_text(encoding='utf-8'))
                        if cache_data.get('raw_text'):
                            item['raw_text'] = cache_data['raw_text']
                    except (json.JSONDecodeError, IOError, OSError):
                        pass
    
    if args.include_occupations and result['results']:
        for item in result['results']:
            major_code = item.get('major_code')
            if major_code:
                occupations = query_occupation_mapping(major_code, args.level)
                
                career_orientation = item.get('career_orientation', '') or item.get('raw_text', '')
                pdf_occ_codes = []
                pdf_occ_names = []
                
                if career_orientation:
                    codes = re.findall(r'[（(]([0-9]+-[0-9]+-[0-9]+-[0-9]+)[）)]', career_orientation)
                    names_match = re.search(r'主要职业类别[（(]代码[）)]\s*(.+?)(?:\n|主要岗位)', career_orientation)
                    
                    if codes:
                        pdf_occ_codes = codes
                    
                    if names_match:
                        names_text = names_match.group(1)
                        name_pattern = r'([^（(]+)[（(]([0-9]+-[0-9]+-[0-9]+-[0-9]+)[）)]'
                        pdf_occ_names = [(re.sub(r'^[、，,\s]+', '', m[0]), m[1]) for m in re.findall(name_pattern, names_text)]
                
                merged_occupations = []
                seen_codes = set()
                
                for occ in occupations:
                    occ_code = occ.get('code', '')
                    occ_name = occ.get('name', '')
                    if occ_code and occ_code not in seen_codes:
                        seen_codes.add(occ_code)
                        merged_occ = {'code': occ_code, 'name': occ_name, 'source': '对照表.xlsx'}
                        
                        pdf_codes_prefix = [c for c in pdf_occ_codes if c[:5] == occ_code[:5]]
                        if pdf_codes_prefix:
                            merged_occ['validation'] = 'prefix_matched'
                        else:
                            merged_occ['validation'] = '对照表仅'
                        
                        merged_occupations.append(merged_occ)
                
                for name, code in pdf_occ_names:
                    if code and code not in seen_codes:
                        seen_codes.add(code)
                        merged_occ = {'code': code, 'name': name.strip(), 'source': 'PDF解析'}
                        
                        mapping_codes = [o.get('code', '') for o in occupations]
                        if any(mc[:5] == code[:5] for mc in mapping_codes):
                            merged_occ['validation'] = 'prefix_matched'
                        else:
                            merged_occ['validation'] = 'PDF新增'
                        
                        merged_occupations.append(merged_occ)
                
                item['occupations_from_mapping'] = merged_occupations
                item['pdf_occupation_codes'] = pdf_occ_codes
                item['occupation_merge_summary'] = {
                    'pdf_count': len(pdf_occ_codes),
                    'mapping_count': len(occupations),
                    'merged_count': len(merged_occupations)
                }
        
        if args.output:
            script_dir = Path(__file__).parent
            project_root = script_dir.parent
            output_full_path = project_root / args.output
            output_full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_full_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"[OK] 结果已保存到: {output_full_path}")
    
    print(f"\n检索结果：共找到 {result['total']} 条记录 (数据源: {result['data_source']})")
    for i, item in enumerate(result['results'], 1):
        print(f"\n[{i}] {item['major_name']}")
        print(f"    专业代码: {item['major_code']}")
        print(f"    教育层次: {item['education_level']}")
        print(f"    PDF链接: {item['pdf_url']}")
        if item.get('pdf_parsed'):
            print(f"    PDF解析: ✅ 已解析")
        elif item.get('pdf_parse_error'):
            print(f"    PDF解析: ❌ {item['pdf_parse_error']}")
        if item.get('content_source') == 'moe_jianjie_github':
            print(f"    内容来源: 专业简介（GitHub镜像）")
        elif item.get('source') == 'moe_pdfs_md':
            print(f"    内容来源: 专业简介（本地MD兜底）")
        if item.get('career_orientation'):
            print(f"    职业面向: {item['career_orientation'][:100]}...")
        
        # 输出职业对照信息
        if item.get('occupations_from_mapping'):
            print(f"    职业对照: {len(item['occupations_from_mapping'])} 个职业")
            for occ in item['occupations_from_mapping']:
                print(f"      - {occ['name']} ({occ['code']})")

if __name__ == '__main__':
    main()
