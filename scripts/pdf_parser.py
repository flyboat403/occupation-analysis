#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF下载和解析脚本

功能：
1. 从URL下载PDF文件
2. 解析PDF提取文本内容
3. 将内容转换为结构化数据

依赖：
- requests: 下载PDF
- pdfplumber: 解析PDF（推荐，支持表格提取）
- pypdf: 备选解析库

安装：
pip install requests pdfplumber pypdf
"""

import json
import re
import argparse
import tempfile
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
import os

# 尝试导入PDF解析库
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

import requests


@dataclass
class MajorStandard:
    """专业教学标准数据结构"""
    major_code: str = ""
    major_name: str = ""
    education_level: str = ""
    career_orientation: str = ""
    training_goal: str = ""
    main_courses: List[str] = None
    graduation_requirements: List[str] = None
    source_url: str = ""
    raw_text: str = ""
    
    def __post_init__(self):
        if self.main_courses is None:
            self.main_courses = []
        if self.graduation_requirements is None:
            self.graduation_requirements = []


def download_pdf(url: str, output_path: Optional[Path] = None, timeout: int = 30) -> Optional[Path]:
    """
    从URL下载PDF文件
    
    Args:
        url: PDF文件URL
        output_path: 输出路径（可选，默认使用临时文件）
        timeout: 请求超时时间（秒）
    
    Returns:
        下载的PDF文件路径，失败返回None
    """
    if not url:
        print("[ERROR] URL为空")
        return None
    
    try:
        print(f"[INFO] 正在下载PDF: {url[:80]}...")
        
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        
        # 检查是否为PDF
        content_type = response.headers.get('Content-Type', '')
        if 'pdf' not in content_type.lower() and not url.lower().endswith('.pdf'):
            print(f"[WARNING] 响应可能不是PDF文件: {content_type}")
        
        # 确定输出路径
        if output_path is None:
            # 创建临时文件
            fd, temp_path = tempfile.mkstemp(suffix='.pdf', prefix='major_standard_')
            output_path = Path(temp_path)
            os.close(fd)
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 下载文件
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        file_size = output_path.stat().st_size
        print(f"[OK] PDF下载完成: {output_path} ({file_size / 1024:.1f} KB)")
        
        return output_path
        
    except requests.exceptions.Timeout:
        print(f"[ERROR] 下载超时 ({timeout}秒)")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 下载失败: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 未知错误: {e}")
        return None


def extract_text_with_pdfplumber(pdf_path: Path) -> str:
    """
    使用pdfplumber提取PDF文本
    
    Args:
        pdf_path: PDF文件路径
    
    Returns:
        提取的文本内容
    """
    if not HAS_PDFPLUMBER:
        raise ImportError("pdfplumber未安装，请运行: pip install pdfplumber")
    
    text_parts = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(f"--- 第{i+1}页 ---\n{page_text}")
    
    return "\n\n".join(text_parts)


def extract_text_with_pypdf(pdf_path: Path) -> str:
    """
    使用pypdf提取PDF文本（备选方案）
    
    Args:
        pdf_path: PDF文件路径
    
    Returns:
        提取的文本内容
    """
    if not HAS_PYPDF:
        raise ImportError("pypdf未安装，请运行: pip install pypdf")
    
    reader = PdfReader(pdf_path)
    text_parts = []
    
    for i, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        if page_text.strip():
            text_parts.append(f"--- 第{i+1}页 ---\n{page_text}")
    
    return "\n\n".join(text_parts)


def extract_text(pdf_path: Path, preferred_library: str = "pdfplumber") -> str:
    """
    从PDF提取文本（自动选择可用库）
    
    Args:
        pdf_path: PDF文件路径
        preferred_library: 首选库 ("pdfplumber" 或 "pypdf")
    
    Returns:
        提取的文本内容
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
    
    errors = []
    
    # 首选库
    if preferred_library == "pdfplumber" and HAS_PDFPLUMBER:
        try:
            return extract_text_with_pdfplumber(pdf_path)
        except Exception as e:
            errors.append(f"pdfplumber: {e}")
    
    if preferred_library == "pypdf" and HAS_PYPDF:
        try:
            return extract_text_with_pypdf(pdf_path)
        except Exception as e:
            errors.append(f"pypdf: {e}")
    
    # 尝试备选库
    if preferred_library != "pdfplumber" and HAS_PDFPLUMBER:
        try:
            return extract_text_with_pdfplumber(pdf_path)
        except Exception as e:
            errors.append(f"pdfplumber: {e}")
    
    if preferred_library != "pypdf" and HAS_PYPDF:
        try:
            return extract_text_with_pypdf(pdf_path)
        except Exception as e:
            errors.append(f"pypdf: {e}")
    
    raise RuntimeError(f"PDF解析失败，无可用库。错误: {'; '.join(errors)}")


def parse_major_standard(text: str, major_code: str = "") -> MajorStandard:
    """
    从PDF文本解析专业教学标准
    
    Args:
        text: PDF提取的文本
        major_code: 专业代码（可选，用于校验）
    
    Returns:
        MajorStandard对象
    """
    standard = MajorStandard()
    standard.raw_text = text
    standard.major_code = major_code
    
    # 提取专业名称
    name_match = re.search(r'专业名称[：:\s]*([^\n]+)', text)
    if name_match:
        standard.major_name = name_match.group(1).strip()
    
    # 提取专业代码（文本中的）
    code_match = re.search(r'专业代码[：:\s]*(\d{6})', text)
    if code_match:
        text_code = code_match.group(1)
        if not major_code:
            standard.major_code = text_code
    
    # 判断教育层次
    if standard.major_code:
        if standard.major_code.startswith('7'):
            standard.education_level = '中等职业教育'
        elif standard.major_code.startswith('5'):
            standard.education_level = '高等职业教育专科'
        elif standard.major_code.startswith('3'):
            standard.education_level = '高等职业教育本科'
        elif standard.major_code.startswith('2'):
            standard.education_level = '职业教育本科'
    
    # 提取职业面向
    orientation_match = re.search(
        r'(?:职业面向|面向.*职业)[：:\s]*\n?(.*?)(?=\n\s*\n|\n#|\n二、|\n三、|\n【|$)',
        text, re.DOTALL
    )
    if orientation_match:
        standard.career_orientation = orientation_match.group(1).strip()[:1000]
    
    # 提取培养目标
    goal_match = re.search(
        r'(?:培养目标|培养目标定位)[：:\s]*\n?(.*?)(?=\n\s*\n|\n#|\n二、|\n三、|\n【|$)',
        text, re.DOTALL
    )
    if goal_match:
        standard.training_goal = goal_match.group(1).strip()[:1500]
    
    # 提取主要课程
    courses_match = re.search(
        r'(?:主要课程|专业课程|核心课程)[：:\s]*\n?(.*?)(?=\n\s*\n|\n#|\n二、|\n三、|\n【|$)',
        text, re.DOTALL
    )
    if courses_match:
        courses_text = courses_match.group(1)
        # 提取课程列表
        courses = re.findall(r'[\d、．.]*([^\n、，,]+(?:技术|基础|实务|设计|管理|操作|应用)[^\n]*)', courses_text)
        standard.main_courses = [c.strip() for c in courses[:15] if c.strip()]
    
    return standard


def fetch_and_parse_pdf(
    url: str,
    major_code: str = "",
    cache_dir: Optional[Path] = None,
    use_cache: bool = True
) -> Optional[MajorStandard]:
    """
    从URL获取PDF并解析专业教学标准
    
    Args:
        url: PDF的URL
        major_code: 专业代码
        cache_dir: 缓存目录（可选）
        use_cache: 是否使用缓存
    
    Returns:
        MajorStandard对象，失败返回None
    """
    # 检查缓存
    if use_cache and cache_dir:
        cache_file = cache_dir / f"{major_code or 'unknown'}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                print(f"[INFO] 使用缓存: {cache_file}")
                return MajorStandard(**cached)
            except:
                pass
    
    # 下载PDF
    if cache_dir and use_cache:
        pdf_path = cache_dir / f"{major_code or 'temp'}.pdf"
    else:
        pdf_path = None
    
    downloaded_path = download_pdf(url, pdf_path)
    if not downloaded_path:
        return None
    
    try:
        # 提取文本
        text = extract_text(downloaded_path)
        print(f"[OK] 文本提取完成，共 {len(text)} 字符")
        
        # 解析内容
        standard = parse_major_standard(text, major_code)
        standard.source_url = url
        
        # 保存缓存
        if use_cache and cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = cache_dir / f"{major_code or 'unknown'}.json"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(standard), f, ensure_ascii=False, indent=2)
            print(f"[OK] 已缓存: {cache_file}")
        
        return standard
        
    except Exception as e:
        print(f"[ERROR] PDF解析失败: {e}")
        return None
    finally:
        # 清理临时文件
        if pdf_path is None and downloaded_path.exists():
            try:
                downloaded_path.unlink()
            except:
                pass


def to_dict(standard: MajorStandard) -> Dict:
    """将MajorStandard转换为字典"""
    return {
        "major_code": standard.major_code,
        "major_name": standard.major_name,
        "education_level": standard.education_level,
        "career_orientation": standard.career_orientation,
        "training_goal": standard.training_goal,
        "main_courses": standard.main_courses,
        "graduation_requirements": standard.graduation_requirements,
        "source_url": standard.source_url,
        "data_source": "pdf"
    }


def main():
    parser = argparse.ArgumentParser(description='PDF下载和解析工具')
    parser.add_argument('--url', '-u', required=True, help='PDF文件URL')
    parser.add_argument('--code', '-c', default='', help='专业代码')
    parser.add_argument('--output', '-o', help='输出JSON文件路径')
    parser.add_argument('--cache-dir', default='temp/pdf_cache', help='PDF缓存目录')
    parser.add_argument('--no-cache', action='store_true', help='不使用缓存')
    parser.add_argument('--library', choices=['pdfplumber', 'pypdf'], default='pdfplumber', help='PDF解析库')
    
    args = parser.parse_args()
    
    # 确定缓存目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    cache_dir = project_root / args.cache_dir if args.cache_dir else None
    
    # 检查依赖
    if args.library == 'pdfplumber' and not HAS_PDFPLUMBER:
        print("[ERROR] pdfplumber未安装，请运行: pip install pdfplumber")
        if HAS_PYPDF:
            print("[INFO] 将使用pypdf作为备选")
        else:
            return
    
    # 获取和解析PDF
    standard = fetch_and_parse_pdf(
        url=args.url,
        major_code=args.code,
        cache_dir=cache_dir,
        use_cache=not args.no_cache
    )
    
    if standard:
        # 输出结果
        print(f"\n{'='*50}")
        print(f"专业代码: {standard.major_code}")
        print(f"专业名称: {standard.major_name}")
        print(f"教育层次: {standard.education_level}")
        print(f"职业面向: {standard.career_orientation[:100]}...")
        print(f"培养目标: {standard.training_goal[:100]}...")
        
        # 保存输出
        if args.output:
            output_path = project_root / args.output
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(to_dict(standard), f, ensure_ascii=False, indent=2)
            print(f"\n[OK] 结果已保存到: {output_path}")


if __name__ == '__main__':
    main()