#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从本地文档查询ESCO和O*NET数据

根据映射信息文件，查询本地ESCO和O*NET文档，返回详细职业数据。

用法：
    python scripts/fetch_local.py --mapping temp/occupation_mapping_info.json --output temp/international_data.json

输入：
    occupation_mapping_info.json - 包含ESCO代码和O*NET代码的映射信息

输出：
    international_data.json - 包含ESCO和O*NET详细数据的JSON文件

注意：
    ESCO文件名格式为 {ISCO代码}.{序号}.md（如 7231.1.md）
    一个ISCO代码可能对应多个文件，本脚本会合并所有匹配的文件
"""

import json
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional


class LocalDocumentFetcher:
    """本地文档查询器"""
    
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
        """读取文件内容"""
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
    
    def parse_esco_content(self, content: str) -> Dict:
        """解析ESCO文档内容"""
        result = {
            'raw_content': content,
            'name': '',
            'code': '',
            'description': '',
            'skills': [],
            'knowledge': [],
            'alternative_terms': []
        }
        
        if not content:
            return result
        
        lines = content.split('\n')
        current_section = None
        
        for line in lines:
            stripped = line.strip()
            
            if stripped.startswith('# '):
                result['name'] = stripped[2:].strip()
            
            elif stripped.startswith('## '):
                section_name = stripped[3:].lower()
                if 'skill' in section_name:
                    current_section = 'skills'
                elif 'knowledge' in section_name:
                    current_section = 'knowledge'
                elif 'description' in section_name:
                    current_section = 'description'
                elif 'alternative' in section_name:
                    current_section = 'alternative_terms'
                else:
                    current_section = None
            
            elif stripped.startswith('| **ISCO Code**'):
                # 从表格提取代码
                if '|' in stripped:
                    parts = stripped.split('|')
                    for part in parts:
                        if '.' in part and any(c.isdigit() for c in part):
                            result['code'] = part.strip()
                            break
            
            elif stripped.startswith('| **') and 'Code' not in stripped:
                current_section = None
            
            elif current_section == 'description' and stripped and not stripped.startswith('#') and not stripped.startswith('|'):
                if not result['description']:
                    result['description'] = stripped
                elif len(result['description']) < 500:
                    result['description'] += ' ' + stripped
            
            elif current_section == 'alternative_terms' and stripped.startswith('- '):
                result['alternative_terms'].append(stripped[2:].strip())
            
            elif current_section in ['skills', 'knowledge'] and stripped.startswith('- **'):
                # 提取技能/知识点名称
                skill_name = stripped[3:].split('**')[0] if '**' in stripped else stripped[2:]
                result[current_section].append(skill_name.strip())
        
        return result
    
    def parse_onet_content(self, content: str) -> Dict:
        """解析O*NET文档内容"""
        result = {
            'raw_content': content,
            'code': '',
            'title': '',
            'summary': '',
            'tasks': [],
            'skills': [],
            'knowledge': [],
            'abilities': []
        }
        
        if not content:
            return result
        
        lines = content.split('\n')
        current_section = None
        in_table = False
        table_rows = []
        
        for line in lines:
            stripped = line.strip()
            
            if stripped.startswith('# '):
                result['title'] = stripped[2:].strip()
                if ' - ' in result['title']:
                    parts = result['title'].split(' - ')
                    result['code'] = parts[0].strip()
                    result['title'] = parts[1].strip() if len(parts) > 1 else result['title']
            
            elif stripped.startswith('## '):
                section_name = stripped[3:].lower()
                if 'task' in section_name:
                    current_section = 'tasks'
                elif 'skill' in section_name:
                    current_section = 'skills'
                elif 'knowledge' in section_name:
                    current_section = 'knowledge'
                elif 'abilit' in section_name:
                    current_section = 'abilities'
                elif 'summary' in section_name:
                    current_section = 'summary'
                else:
                    current_section = None
                in_table = False
                table_rows = []
            
            elif stripped.startswith('|') and current_section:
                in_table = True
                table_rows.append(stripped)
            
            elif current_section == 'summary' and stripped and not stripped.startswith('#'):
                if not result['summary']:
                    result['summary'] = stripped
        
        # 解析表格数据
        if table_rows and len(table_rows) > 2:
            for row in table_rows[2:]:
                cells = [c.strip() for c in row.split('|') if c.strip()]
                if len(cells) >= 2 and current_section:
                    result[current_section].append(cells[-1])
        
        return result
    
    def _convert_occupation_mapping_format(self, mapping_info: Dict) -> List[Dict]:
        """
        将occupation_mapping格式转换为mapping_results格式
        
        输入格式：
        {
            "major_code": "740201",
            "occupation_mapping": {
                "primary": {"code": "4-03-02-01", "name": "中式烹调师"},
                "esco_candidates": [{"code": "5120.1.3", "name": "grill cook", "file": "..."}],
                "onet_candidates": [{"code": "35-2014.00", "name": "Cooks, Restaurant", "file": "..."}]
            }
        }
        
        输出格式：
        [
            {"china_code": "4-03-02-01", "china_name": "中式烹调师", "esco_code": "5120.1.3", "onet_code": "35-2014.00"}
        ]
        """
        mapping_results = []
        occupation_mapping = mapping_info.get('occupation_mapping', {})
        
        primary = occupation_mapping.get('primary', {})
        if primary:
            china_code = primary.get('code', '')
            china_name = primary.get('name', '')
            
            esco_candidates = occupation_mapping.get('esco_candidates', [])
            onet_candidates = occupation_mapping.get('onet_candidates', [])
            
            esco_code = ''
            onet_code = ''
            
            if esco_candidates:
                best_esco = max(esco_candidates, key=lambda x: x.get('match_score', 0))
                esco_code = best_esco.get('code', '')
            
            if onet_candidates:
                best_onet = max(onet_candidates, key=lambda x: x.get('match_score', 0))
                onet_code = best_onet.get('code', '')
            
            if china_code:
                mapping_results.append({
                    'china_code': china_code,
                    'china_name': china_name,
                    'esco_code': esco_code,
                    'onet_code': onet_code,
                    'mapping_confidence': 'inferred'
                })
        
        return mapping_results
    
    def fetch(self, mapping_info: Dict) -> Dict:
        """
        根据映射信息获取数据
        
        Args:
            mapping_info: 包含mapping_results的字典，或直接数组，或包含results/mappings字段
        
        Returns:
            包含ESCO和O*NET数据的字典
        """
        result = {
            'occupations': [],
            'missing_documents': []
        }
        
        if isinstance(mapping_info, list):
            mapping_results = mapping_info
            print("[INFO] 输入为直接数组格式")
        elif 'mapping_results' in mapping_info:
            mapping_results = mapping_info['mapping_results']
        elif 'results' in mapping_info:
            mapping_results = mapping_info['results']
            print("[INFO] 使用 'results' 字段作为映射数据")
        elif 'mappings' in mapping_info:
            mapping_results = mapping_info['mappings']
            print("[INFO] 使用 'mappings' 字段作为映射数据")
        elif 'occupation_mapping' in mapping_info:
            mapping_results = self._convert_occupation_mapping_format(mapping_info)
            print("[INFO] 使用 'occupation_mapping' 字段格式")
        else:
            print("[WARNING] 未识别的输入格式，期望包含 'mapping_results'、'occupation_mapping' 字段或直接数组")
            mapping_results = []
        
        for mapping in mapping_results:
            occupation_data = {
                'china_code': mapping.get('china_code', ''),
                'china_name': mapping.get('china_name', ''),
                'esco': None,
                'onet': None,
                'mapping_confidence': mapping.get('mapping_confidence', 'unknown')
            }
            
            # 查询ESCO（使用ESCO代码）
            esco_code = mapping.get('esco_code', '')
            if esco_code:
                esco_files = self.find_esco_files(esco_code)
                if esco_files:
                    print(f"[OK] 找到 {len(esco_files)} 个ESCO文档 (代码: {esco_code})")
                    # 合并所有匹配的文件内容
                    all_esco_data = []
                    for esco_file in esco_files:
                        content = self.read_file(esco_file)
                        if content:
                            parsed = self.parse_esco_content(content)
                            parsed['source_file'] = str(esco_file.name)
                            all_esco_data.append(parsed)
                    
                    if all_esco_data:
                        occupation_data['esco'] = {
                            'code': esco_code,
                            'documents': all_esco_data,
                            'primary_name': all_esco_data[0].get('name', ''),
                            'total_documents': len(all_esco_data)
                        }
                else:
                    print(f"[WARNING] 未找到ESCO文档: {esco_code}")
                    result['missing_documents'].append({
                        'china_name': mapping['china_name'],
                        'type': 'ESCO',
                        'query': esco_code
                    })
            
            # 查询O*NET
            onet_code = mapping.get('onet_code', '')
            if onet_code:
                onet_file = self.find_onet_file(onet_code)
                if onet_file:
                    print(f"[OK] 找到O*NET文档: {onet_file.name}")
                    content = self.read_file(onet_file)
                    if content:
                        occupation_data['onet'] = self.parse_onet_content(content)
                        occupation_data['onet']['source_file'] = str(onet_file.name)
                else:
                    print(f"[WARNING] 未找到O*NET文档: {onet_code}")
                    result['missing_documents'].append({
                        'china_name': mapping['china_name'],
                        'type': 'O*NET',
                        'query': onet_code
                    })
            
            result['occupations'].append(occupation_data)
        
        return result


def main():
    parser = argparse.ArgumentParser(
        description='从本地文档查询ESCO和O*NET数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用映射文件查询
  python scripts/fetch_local.py --mapping temp/occupation_mapping_info.json --output temp/international_data.json
  
  # 单独查询ESCO（使用ISCO代码）
  python scripts/fetch_local.py --esco "7231" --output temp/esco_data.json
  
  # 单独查询O*NET
  python scripts/fetch_local.py --onet "49-3023.00" --output temp/onet_data.json

注意:
  ESCO文件名格式为 {ISCO代码}.{序号}.md（如 7231.1.md）
  一个ISCO代码可能对应多个文件
        """
    )
    
    parser.add_argument('--mapping', '-m', help='映射信息JSON文件路径')
    parser.add_argument('--esco', '-e', help='ESCO/ISCO代码（如 7231）')
    parser.add_argument('--onet', '-o', help='O*NET代码（如 49-3023.00）')
    parser.add_argument('--output', '-out', help='输出文件路径')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详细输出')
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    fetcher = LocalDocumentFetcher(project_root)
    
    result: Dict[str, Any] = {'occupations': [], 'missing_documents': []}
    
    # 单独查询模式
    if args.esco or args.onet:
        if args.esco:
            esco_files = fetcher.find_esco_files(args.esco)
            if esco_files:
                print(f"[OK] 找到 {len(esco_files)} 个ESCO文档")
                all_data = []
                for esco_file in esco_files:
                    content = fetcher.read_file(esco_file)
                    if content:
                        parsed = fetcher.parse_esco_content(content)
                        parsed['source_file'] = str(esco_file.name)
                        all_data.append(parsed)
                        print(f"  - {esco_file.name}")
                result['esco'] = {
                    'code': args.esco,
                    'documents': all_data
                }
            else:
                print(f"[ERROR] 未找到ESCO文档: {args.esco}")
                result['missing_documents'].append({'type': 'ESCO', 'query': args.esco})
        
        if args.onet:
            onet_file = fetcher.find_onet_file(args.onet)
            if onet_file:
                print(f"[OK] 找到O*NET文档: {onet_file}")
                content = fetcher.read_file(onet_file)
                if content:
                    result['onet'] = fetcher.parse_onet_content(content)
                    result['onet']['source_file'] = str(onet_file)
            else:
                print(f"[ERROR] 未找到O*NET文档: {args.onet}")
                result['missing_documents'].append({'type': 'O*NET', 'query': args.onet})
    
    # 映射文件查询模式
    elif args.mapping:
        mapping_path = Path(args.mapping)
        if not mapping_path.is_absolute():
            mapping_path = project_root / args.mapping
        
        if not mapping_path.exists():
            print(f"[ERROR] 映射文件不存在: {mapping_path}")
            return 1
        
        print(f"[INFO] 读取映射文件: {mapping_path}")
        with open(mapping_path, 'r', encoding='utf-8') as f:
            mapping_info = json.load(f)
        
        result = fetcher.fetch(mapping_info)
    
    else:
        parser.error('请提供 --mapping、--esco 或 --onet 参数')
        return 1
    
    # 显示缺失文档摘要
    if result.get('missing_documents'):
        print("\n" + "="*60)
        print("【警告】以下文档缺失：")
        print("="*60)
        for doc in result['missing_documents']:
            print(f"  - {doc.get('china_name', '')}: {doc.get('type')} ({doc.get('query')})")
        print("\n缺失的职业将使用已有数据进行补充分析，部分国际数据可能不完整。")
    
    # 保存结果
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = project_root / args.output
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n[OK] 数据已保存到: {output_path}")
    
    return 0


if __name__ == '__main__':
    exit(main())