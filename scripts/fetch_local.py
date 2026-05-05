#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从本地文档查询ESCO和O*NET数据（Markdown格式输出）

根据映射信息文件，查询本地ESCO和O*NET文档，返回原始Markdown内容。

用法：
    python scripts/fetch_local.py --mapping temp/occupation_mapping_info.json --output temp/international_data.md

输入：
    occupation_mapping_info.json - 包含ESCO代码和O*NET代码的映射信息

输出：
    international_data.md - 包含ESCO和O*NET原始Markdown内容的Markdown文件

注意：
    ESCO文件名格式为 {ISCO代码}.{序号}.md（如 7231.1.md）
    一个ISCO代码可能对应多个文件，本脚本会合并所有匹配的文件
    
    步骤5（本脚本）不解析MD文件，直接保留原始Markdown格式供大模型分析
"""

import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class LocalDocumentFetcher:
    """本地文档查询器（直接输出Markdown格式）"""
    
    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            script_dir = Path(__file__).parent
            project_root = script_dir.parent
        
        self.project_root = project_root
        self.esco_dir = project_root / "assets" / "esco_details_md"
        self.onet_dir = project_root / "assets" / "onet_details_md"
        
        self._esco_index = None
        self._onet_index = None
    
    def _build_esco_index(self) -> Dict[str, List[Path]]:
        """构建ESCO文件名索引（一个代码可能对应多个文件）"""
        if self._esco_index is not None:
            return self._esco_index
        
        self._esco_index = {}
        if self.esco_dir.exists():
            for f in self.esco_dir.glob("*.md"):
                # 文件名格式: {ISCO代码}.{序号}.md（如 7231.1.md）
                # 提取ISCO代码（点号前的部分）
                stem = f.stem
                if '.' in stem:
                    isco_code = stem.split('.')[0]
                else:
                    isco_code = stem
                
                if isco_code not in self._esco_index:
                    self._esco_index[isco_code] = []
                self._esco_index[isco_code].append(f)
        return self._esco_index
    
    def _build_onet_index(self) -> Dict[str, Path]:
        """构建O*NET文件名索引"""
        if self._onet_index is not None:
            return self._onet_index
        
        self._onet_index = {}
        if self.onet_dir.exists():
            for f in self.onet_dir.glob("*.md"):
                code = f.stem
                self._onet_index[code] = f
        return self._onet_index
    
    def find_esco_files(self, esco_code: str) -> List[Path]:
        """
        查找ESCO文件（一个代码可能对应多个文件）
        
        Args:
            esco_code: ESCO/ISCO代码（如 7231 或 2512.9）
        
        Returns:
            文件路径列表
        """
        index = self._build_esco_index()
        code = esco_code.strip()
        
        exact_file = self.esco_dir / f"{code}.md"
        if exact_file.exists():
            return [exact_file]
        
        if '.' in code:
            isco_code = code.split('.')[0]
            if isco_code in index:
                return sorted(index[isco_code])
        
        if code in index:
            return sorted(index[code])
        
        return []
    
    def find_onet_file(self, onet_code: str) -> Optional[Path]:
        """
        查找O*NET文件
        
        Args:
            onet_code: O*NET代码（如 49-3023.00）
        
        Returns:
            文件路径，如果未找到返回None
        """
        index = self._build_onet_index()
        code = onet_code.strip()
        
        if code in index:
            return index[code]
        
        return None
    
    def read_file(self, file_path: Path) -> Optional[str]:
        """读取文件内容（原始Markdown）"""
        if not file_path or not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except (IOError, OSError, UnicodeDecodeError, PermissionError) as e:
            print(f"[ERROR] 读取文件失败 {file_path}: {e}")
            return None
        except Exception as e:
            print(f"[ERROR] 未知错误读取文件 {file_path}: {e}")
            raise
    
    def fetch_as_markdown(self, mapping_info: Dict) -> str:
        """
        根据映射信息获取数据（输出Markdown格式）
        
        Args:
            mapping_info: 包含mapping_results的字典
        
        Returns:
            包含ESCO和O*NET原始Markdown内容的字符串
        """
        # 解析输入格式
        if isinstance(mapping_info, list):
            mapping_results = mapping_info
        elif 'mapping_results' in mapping_info:
            mapping_results = mapping_info['mapping_results']
        elif 'results' in mapping_info:
            mapping_results = mapping_info['results']
        elif 'mappings' in mapping_info:
            mapping_results = mapping_info['mappings']
        elif 'occupation_mapping' in mapping_info:
            # 兼容occupation_mapping格式
            mapping_results = self._convert_occupation_mapping_format(mapping_info)
        else:
            print("[WARNING] 未识别的输入格式")
            mapping_results = []
        
        md_sections = []
        missing_documents = []
        
        for mapping in mapping_results:
            china_name = mapping.get('china_name', '')
            china_code = mapping.get('china_code', '')
            
            # 构建单个职业的Markdown章节
            occupation_md = f"## 职业：{china_name}\n\n"
            occupation_md += f"**职业代码**: {china_code}\n\n"
            
            # ESCO文档部分
            esco_code = mapping.get('esco_code', '')
            if esco_code:
                occupation_md += "### ESCO文档\n\n"
                esco_files = self.find_esco_files(esco_code)
                
                if esco_files:
                    print(f"[OK] 找到 {len(esco_files)} 个ESCO文档 (职业: {china_name}, 代码: {esco_code})")
                    occupation_md += f"**ESCO代码**: {esco_code}\n\n"
                    
                    for esco_file in esco_files:
                        content = self.read_file(esco_file)
                        if content:
                            occupation_md += f"#### 文档 {esco_file.name}\n\n"
                            occupation_md += content + "\n\n"
                else:
                    print(f"[WARNING] 未找到ESCO文档: {esco_code}")
                    occupation_md += f"**状态**: 未找到文档（代码: {esco_code})\n\n"
                    missing_documents.append({
                        'china_name': china_name,
                        'type': 'ESCO',
                        'query': esco_code
                    })
            
            # O*NET文档部分
            onet_code = mapping.get('onet_code', '')
            if onet_code:
                occupation_md += "### O*NET文档\n\n"
                onet_file = self.find_onet_file(onet_code)
                
                if onet_file:
                    print(f"[OK] 找到O*NET文档 (职业: {china_name}, 代码: {onet_code})")
                    occupation_md += f"**O*NET代码**: {onet_code}\n\n"
                    
                    content = self.read_file(onet_file)
                    if content:
                        occupation_md += f"#### 文档 {onet_file.name}\n\n"
                        occupation_md += content + "\n\n"
                else:
                    print(f"[WARNING] 未找到O*NET文档: {onet_code}")
                    occupation_md += f"**状态**: 未找到文档（代码: {onet_code})\n\n"
                    missing_documents.append({
                        'china_name': china_name,
                        'type': 'O*NET',
                        'query': onet_code
                    })
            
            md_sections.append(occupation_md)
        
        # 合并所有职业的Markdown内容
        combined_md = "---\n\n".join(md_sections)
        
        # 添加缺失文档列表（如果有）
        if missing_documents:
            combined_md += "\n\n---\n\n## 缺失文档列表\n\n"
            for item in missing_documents:
                combined_md += f"- {item['china_name']}: {item['type']} ({item['query']})\n"
        
        return combined_md
    
    def _convert_occupation_mapping_format(self, mapping_info: Dict) -> List[Dict]:
        """
        兼容occupation_mapping格式的转换
        
        Args:
            mapping_info: 包含occupation_mapping字段的字典
        
        Returns:
            转换后的mapping_results列表
        """
        occupation_mapping = mapping_info.get('occupation_mapping', {})
        mapping_results = []
        
        for china_code, mapping_data in occupation_mapping.items():
            if isinstance(mapping_data, dict):
                mapping_results.append({
                    'china_code': china_code,
                    'china_name': mapping_data.get('china_name', ''),
                    'esco_code': mapping_data.get('esco_code', ''),
                    'onet_code': mapping_data.get('onet_code', ''),
                    'mapping_confidence': mapping_data.get('mapping_confidence', 'unknown')
                })
        
        return mapping_results


def main():
    parser = argparse.ArgumentParser(
        description='从本地文档查询ESCO和O*NET数据（Markdown格式输出）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用映射文件查询（输出Markdown）
  python scripts/fetch_local.py --mapping temp/occupation_mapping_info.json --output temp/international_data.md
  
  # 单独查询ESCO（输出Markdown）
  python scripts/fetch_local.py --esco "7231" --output temp/esco_data.md
  
  # 单独查询O*NET（输出Markdown）
  python scripts/fetch_local.py --onet "49-3023.00" --output temp/onet_data.md

注意:
  ESCO文件名格式为 {ISCO代码}.{序号}.md（如 7231.1.md）
  一个ISCO代码可能对应多个文件
  输出格式为Markdown，供大模型直接分析
        """
    )
    
    parser.add_argument('--mapping', '-m', help='映射信息JSON文件路径')
    parser.add_argument('--esco', '-e', help='ESCO/ISCO代码（如 7231）')
    parser.add_argument('--onet', '-o', help='O*NET代码（如 49-3023.00）')
    parser.add_argument('--output', '-out', required=True, help='输出Markdown文件路径')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详细输出')
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    fetcher = LocalDocumentFetcher(project_root)
    
    md_content = ""
    
    # 单独查询模式
    if args.esco or args.onet:
        if args.esco:
            esco_files = fetcher.find_esco_files(args.esco)
            if esco_files:
                print(f"[OK] 找到 {len(esco_files)} 个ESCO文档")
                md_content = f"# ESCO文档\n\n**ESCO代码**: {args.esco}\n\n"
                
                for esco_file in esco_files:
                    content = fetcher.read_file(esco_file)
                    if content:
                        md_content += f"## 文档 {esco_file.name}\n\n{content}\n\n"
                        print(f"  - {esco_file.name}")
            else:
                print(f"[ERROR] 未找到ESCO文档: {args.esco}")
                md_content = f"# ESCO文档\n\n**状态**: 未找到文档（代码: {args.esco})\n\n"
        
        if args.onet:
            onet_file = fetcher.find_onet_file(args.onet)
            if onet_file:
                print(f"[OK] 找到O*NET文档: {onet_file.name}")
                md_content = f"# O*NET文档\n\n**O*NET代码**: {args.onet}\n\n"
                
                content = fetcher.read_file(onet_file)
                if content:
                    md_content += f"## 文档 {onet_file.name}\n\n{content}\n\n"
            else:
                print(f"[ERROR] 未找到O*NET文档: {args.onet}")
                md_content = f"# O*NET文档\n\n**状态**: 未找到文档（代码: {args.onet})\n\n"
    
    # 使用映射文件查询
    elif args.mapping:
        mapping_path = Path(args.mapping)
        if not mapping_path.exists():
            print(f"[ERROR] 映射文件不存在: {mapping_path}")
            return
        
        # 读取JSON格式的映射文件
        import json
        with open(mapping_path, 'r', encoding='utf-8') as f:
            mapping_info = json.load(f)
        
        print(f"[INFO] 读取映射文件: {mapping_path}")
        md_content = fetcher.fetch_as_markdown(mapping_info)
    
    else:
        print("[ERROR] 必须提供 --mapping 或 (--esco/--onet) 参数")
        parser.print_help()
        return
    
    # 添加元数据头
    metadata = f"---\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n数据格式: Markdown\n---\n\n"
    full_md = metadata + md_content
    
    # 确保输出路径的后缀是.md
    output_path = Path(args.output)
    if output_path.suffix != '.md':
        output_path = output_path.with_suffix('.md')
    
    # 保存Markdown文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(full_md)
    
    print(f"\n[OK] Markdown文件已保存: {output_path}")
    print(f"     文件大小: {len(full_md)} 字符")


if __name__ == '__main__':
    main()