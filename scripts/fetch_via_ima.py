#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过IMA知识库API访问ESCO和O*NET数据

优先级：
1. IMA知识库（如果已配置且ID有效）
2. 直接API访问（作为fallback）

注意：当前配置的知识库ID格式可能已过时，请先调用get_addable_knowledge_base_list()获取有效的知识库ID
"""

import requests
import json
import os
import argparse
from typing import Dict, List, Optional
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

class IMAKnowledgeClient:
    """通过IMA知识库API访问ESCO和O*NET数据"""
    
    # IMA API基础URL（根据最新文档）
    BASE_URL = "https://ima.qq.com"
    WIKI_BASE_PATH = "/openapi/wiki/v1"
    
    # 知识库ID（注意：这些ID格式可能已过时，需要先获取有效的ID）
    # 调用get_addable_knowledge_base_list()获取可用的知识库列表
    KNOWLEDGE_BASES = {
        'ESCO': 'Q24d1kxoo9_Ol2q7ytoyf2rplNtQ2tuo9qx42XZ3JTk=',  # ⚠️ 需要更新
        'ONET': 'aDOXtI4_MqUf-UtdLPVERaX4IeIfn88VdYI4VC85QcI='  # ⚠️ 需要更新
    }
    
    def __init__(self):
        self.client_id = os.environ.get('IMA_OPENAPI_CLIENTID')
        self.api_key = os.environ.get('IMA_OPENAPI_APIKEY')
        self.session = requests.Session()
        
        if self.client_id and self.api_key:
            self.session.headers.update({
                'ima-openapi-clientid': self.client_id,
                'ima-openapi-apikey': self.api_key,
                'Content-Type': 'application/json'
            })
    
    def is_available(self) -> bool:
        """检查IMA是否可用"""
        return bool(self.client_id and self.api_key)
    
    def get_addable_knowledge_bases(self, limit: int = 50) -> List[Dict]:
        """
        获取可添加内容的知识库列表
        
        这是获取有效知识库ID的正确方法
        
        Returns:
            知识库列表，每个包含id和name字段
        """
        if not self.is_available():
            print("[ERROR] IMA凭证未配置")
            return []
        
        url = f"{self.BASE_URL}{self.WIKI_BASE_PATH}/get_addable_knowledge_base_list"
        
        data = {
            'cursor': '',
            'limit': limit
        }
        
        try:
            response = self.session.post(url, json=data, timeout=30)
            result = response.json()
            
            # 兼容两种返回格式: code 或 retcode
            code = result.get('code', result.get('retcode'))
            
            if code == 0:
                kb_list = result.get('data', {}).get('addable_knowledge_base_list', [])
                print(f"[INFO] 找到 {len(kb_list)} 个可访问的知识库")
                return kb_list
            else:
                error_msg = result.get('msg', result.get('errmsg', 'Unknown error'))
                print(f"[ERROR] 获取知识库列表失败: {error_msg}")
                return []
                
        except Exception as e:
            print(f"[ERROR] 请求异常: {e}")
            return []
    
    def search_knowledge(self, query: str, knowledge_base_id: str, limit: int = 10) -> List[Dict]:
        """
        在指定知识库中搜索
        
        API端点: POST /openapi/wiki/v1/search_knowledge
        
        Args:
            query: 搜索查询（支持自然语言描述）
            knowledge_base_id: 知识库ID（需要从get_addable_knowledge_bases获取）
            limit: 返回结果数量限制
        
        Returns:
            搜索结果列表
        """
        if not self.is_available():
            return []
        
        url = f"{self.BASE_URL}{self.WIKI_BASE_PATH}/search_knowledge"
        
        data = {
            'query': query,
            'knowledge_base_id': knowledge_base_id,
            'cursor': '',
            'limit': limit
        }
        
        try:
            response = self.session.post(url, json=data, timeout=30)
            result = response.json()
            
            # 兼容两种返回格式: code 或 retcode
            code = result.get('code', result.get('retcode'))
            
            if code == 0:
                info_list = result.get('data', {}).get('info_list', [])
                print(f"[INFO] 在知识库中找到 {len(info_list)} 条结果")
                return info_list
            else:
                error_msg = result.get('msg', result.get('errmsg', 'Unknown error'))
                print(f"[ERROR] 搜索失败: {error_msg}")
                
                # 特殊错误码处理
                if code == 51:
                    print("[HINT] 知识库ID格式错误，请先调用get_addable_knowledge_bases()获取有效的知识库ID")
                
                return []
                
        except Exception as e:
            print(f"[ERROR] 请求异常: {e}")
            return []
    
    def close(self) -> None:
        """关闭Session，释放资源"""
        if hasattr(self, 'session'):
            self.session.close()
    
    def __enter__(self):
        """支持上下文管理器"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时自动关闭Session"""
        self.close()
        return False
    
    def list_notebooks(self, limit: int = 20) -> List[Dict]:
        """列出所有笔记本"""
        if not self.is_available():
            return []
        
        url = f"{self.BASE_URL}/list_note_folder_by_cursor"
        data = {
            "cursor": "0",
            "limit": limit
        }
        
        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            result = response.json()
            
            if result.get('errcode') == 0:
                notebooks = []
                for item in result.get('note_book_folders', []):
                    folder_info = item.get('folder', {}).get('basic_info', {})
                    notebooks.append({
                        'folder_id': folder_info.get('folder_id'),
                        'name': folder_info.get('name'),
                        'note_number': folder_info.get('note_number'),
                        'folder_type': folder_info.get('folder_type')
                    })
                return notebooks
        except Exception as e:
            print(f"列出笔记本失败: {e}")
        
        return []
    
    def find_knowledge_base(self, name_keyword: str) -> Optional[Dict]:
        """
        查找知识库笔记本
        
        Args:
            name_keyword: 笔记本名称关键词（如"ESCO"、"O*NET"）
        
        Returns:
            找到的笔记本信息，或None
        """
        # 优先使用预设的知识库ID
        if name_keyword.upper() in self.KNOWLEDGE_BASES:
            folder_id = self.KNOWLEDGE_BASES[name_keyword.upper()]
            print(f"[OK] 使用预设知识库ID: {name_keyword} ({folder_id[:20]}...)")
            return {
                'folder_id': folder_id,
                'name': f"{name_keyword}知识库",
                'note_number': '未知',
                'folder_type': 0
            }
        
        # 如果没有预设ID，从笔记本列表查找
        notebooks = self.list_notebooks()
        
        for notebook in notebooks:
            if name_keyword.upper() in notebook['name'].upper():
                return notebook
        
        return None
    
    def search_notes(self, query: str, search_type: int = 1, limit: int = 20) -> List[Dict]:
        """
        搜索笔记
        
        Args:
            query: 搜索关键词
            search_type: 0=标题检索，1=正文检索
            limit: 返回结果数量
        
        Returns:
            笔记列表
        """
        if not self.is_available():
            return []
        
        url = f"{self.BASE_URL}/search_note_book"
        data = {
            "search_type": search_type,
            "query_info": {"content": query} if search_type == 1 else {"title": query},
            "start": 0,
            "end": limit
        }
        
        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            result = response.json()
            
            if result.get('errcode') == 0:
                notes = []
                for item in result.get('docs', []):
                    doc_info = item.get('doc', {}).get('basic_info', {})
                    notes.append({
                        'doc_id': doc_info.get('docid'),
                        'title': doc_info.get('title'),
                        'summary': doc_info.get('summary'),
                        'folder_name': doc_info.get('folder_name'),
                        'modify_time': doc_info.get('modify_time')
                    })
                return notes
        except Exception as e:
            print(f"搜索笔记失败: {e}")
        
        return []
    
    def get_note_content(self, doc_id: str) -> Optional[str]:
        """
        获取笔记内容
        
        Args:
            doc_id: 笔记ID
        
        Returns:
            笔记内容（纯文本格式）
        """
        if not self.is_available():
            return None
        
        url = f"{self.BASE_URL}/get_doc_content"
        data = {
            "doc_id": doc_id,
            "target_content_format": 0  # 纯文本
        }
        
        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            result = response.json()
            
            if result.get('errcode') == 0:
                return result.get('content')
        except Exception as e:
            print(f"获取笔记内容失败: {e}")
        
        return None
    
    def search_occupation_in_knowledge_base(
        self, 
        occupation_name: str, 
        knowledge_base: str = "ESCO"
    ) -> Optional[Dict]:
        """
        在知识库中搜索职业信息
        
        Args:
            occupation_name: 职业名称
            knowledge_base: 知识库名称（"ESCO" 或 "ONET"）
        
        Returns:
            职业信息，包含 title, media_id, highlight_content 等
        """
        # 获取知识库ID
        kb_id = self.KNOWLEDGE_BASES.get(knowledge_base.upper())
        
        if not kb_id:
            print(f"未找到 {knowledge_base} 知识库配置")
            return None
        
        print(f"搜索 {knowledge_base} 知识库 (ID: {kb_id[:20]}...)")
        
        # 使用wiki API搜索知识库
        items = self.search_knowledge(
            query=occupation_name,
            knowledge_base_id=kb_id,
            limit=10
        )
        
        if not items:
            print(f"在 {knowledge_base} 知识库中未找到 '{occupation_name}' 相关内容")
            return None
        
        print(f"找到 {len(items)} 条相关内容")
        
        # 返回搜索结果列表
        return {
            'source': f'IMA-{knowledge_base}',
            'query': occupation_name,
            'total': len(items),
            'results': [
                {
                    'media_id': item.get('media_id'),
                    'title': item.get('title'),
                    'highlight_content': item.get('highlight_content', ''),
                    'media_type': item.get('media_type')
                }
                for item in items[:5]  # 返回前5条结果
            ],
            'knowledge_base_name': knowledge_base
        }
        # 查找知识库笔记本
        notebook = self.find_knowledge_base(knowledge_base)
        
        if not notebook:
            print(f"未找到 {knowledge_base} 知识库笔记本")
            return None
        
        print(f"找到知识库: {notebook['name']}")
        
        # 搜索职业
        notes = self.search_notes(occupation_name, search_type=1)  # 正文检索
        
        if not notes:
            print(f"在 {knowledge_base} 知识库中未找到 '{occupation_name}' 相关笔记")
            return None
        
        print(f"找到 {len(notes)} 条相关笔记")
        
        # 获取最相关的笔记内容
        first_note = notes[0]
        print(f"读取笔记: {first_note['title']}")
        
        content = self.get_note_content(first_note['doc_id'])
        
        if content:
            return {
                'source': f'IMA-{knowledge_base}',
                'doc_id': first_note['doc_id'],
                'title': first_note['title'],
                'content': content,
                'raw': first_note
            }
        
        return None

def fetch_esco_api(occupation_name: str) -> Optional[Dict]:
    """
    从ESCO API获取职业数据
    
    Args:
        occupation_name: 职业名称（英文）
    
    Returns:
        职业数据字典
    """
    search_url = "https://ec.europa.eu/esco/api/search"
    params = {
        "text": occupation_name,
        "language": "en",
        "type": "occupation",
        "limit": 5
    }
    
    try:
        response = requests.get(search_url, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if result.get('_embedded', {}).get('results'):
            first_result = result['_embedded']['results'][0]
            return {
                'source': 'ESCO-API',
                'uri': first_result.get('uri'),
                'title': first_result.get('title'),
                'description': first_result.get('description', {}).get('en', ''),
                'code': first_result.get('code'),
                'raw': first_result
            }
    except Exception as e:
        print(f"ESCO API调用失败: {e}")
    
    return None

def fetch_onet_api(occupation_name: str) -> Optional[Dict]:
    """
    从O*NET API获取职业数据
    
    注意：需要设置ONET_API_KEY环境变量
    
    Args:
        occupation_name: 职业名称（英文）
    
    Returns:
        职业数据字典
    """
    api_key = os.environ.get('ONET_API_KEY')
    if not api_key:
        print("提示：未配置ONET_API_KEY环境变量，无法访问O*NET API")
        return None
    
    base_url = "https://api.onetcenter.org/v1"
    
    try:
        # 先搜索职业代码
        search_url = f"{base_url}/online/search"
        headers = {'Accept': 'application/json'}
        params = {'keyword': occupation_name}
        auth = (api_key, '')
        
        response = requests.get(search_url, headers=headers, params=params, auth=auth, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if result.get('occupation'):
            first_occ = result['occupation'][0]
            code = first_occ.get('code')
            
            # 获取详细信息
            detail_url = f"{base_url}/occupations/{code}/summary"
            detail_response = requests.get(detail_url, headers=headers, auth=auth, timeout=30)
            detail_response.raise_for_status()
            detail = detail_response.json()
            
            return {
                'source': 'ONET-API',
                'code': code,
                'title': first_occ.get('title'),
                'summary': detail,
                'raw': first_occ
            }
    except Exception as e:
        print(f"O*NET API调用失败: {e}")
    
    return None

def fetch_occupation_data_hybrid(
    occupation_name: str,
    source: str = "all",
    prefer_ima: bool = True,
    output_path: Optional[str] = None
) -> Dict:
    """
    混合模式获取职业数据
    
    优先级：
    1. IMA知识库（如果可用且prefer_ima=True）
    2. 直接API访问（作为fallback）
    
    Args:
        occupation_name: 职业名称
        source: 数据源（"ESCO"、"ONET" 或 "all"）
        prefer_ima: 是否优先使用IMA
        output_path: 输出文件路径
    
    Returns:
        职业数据
    """
    result = {
        'occupation_name': occupation_name,
        'sources': {}
    }
    
    # 尝试IMA知识库
    ima_client = IMAKnowledgeClient()
    
    if prefer_ima and ima_client.is_available():
        print("\n[OK] IMA已配置，优先使用知识库")
        
        if source in ['ESCO', 'all']:
            print(f"\n=== 从IMA-ESCO知识库获取 ===")
            esco_data = ima_client.search_occupation_in_knowledge_base(
                occupation_name, 'ESCO'
            )
            if esco_data:
                result['sources']['IMA-ESCO'] = esco_data
        
        if source in ['ONET', 'all']:
            print(f"\n=== 从IMA-O*NET知识库获取 ===")
            onet_data = ima_client.search_occupation_in_knowledge_base(
                occupation_name, 'ONET'
            )
            if onet_data:
                result['sources']['IMA-ONET'] = onet_data
    else:
        if prefer_ima:
            print("\n[INFO] IMA未配置，使用API方式")
    
    # 如果IMA没有获取到数据，使用API fallback
    if not result['sources'] or source == 'all':
        # ESCO API
        if source in ['ESCO', 'all'] and 'IMA-ESCO' not in result['sources']:
            print(f"\n=== 从ESCO API获取 ===")
            try:
                esco_data = fetch_esco_api(occupation_name)
                if esco_data:
                    result['sources']['ESCO-API'] = esco_data
            except Exception as e:
                print(f"ESCO API获取失败: {e}")
        
        # O*NET API
        if source in ['ONET', 'all'] and 'IMA-ONET' not in result['sources']:
            print(f"\n=== 从O*NET获取 ===")
            try:
                onet_data = fetch_onet_api(occupation_name)
                if onet_data:
                    result['sources']['ONET-API'] = onet_data
            except Exception as e:
                print(f"O*NET获取失败: {e}")
    
    # 保存结果
    if output_path and result['sources']:
        script_dir = Path(__file__).parent
        project_root = script_dir.parent  # scripts/ -> occupation-analysis/
        output_full_path = project_root / output_path
        output_full_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_full_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n数据已保存到: {output_full_path}")
    
    return result

# 物联网相关职业搜索提示词映射
IOT_OCCUPATION_PROMPTS = {
    # 中国职业名称 -> 多语言搜索关键词
    "物联网系统安装调试员": [
        "network installer",
        "system administrator",
        "ICT installer",
        "ISCO 3512",
        "15-1244.00",  # Network and Computer Systems Administrators
        "设备安装调试"
    ],
    "物联网应用开发员": [
        "software developer",
        "web developer",
        "application developer",
        "ISCO 2512",
        "15-1252.00",  # Software Developers
        "15-1254.00",  # Web Developers
        "软件开发"
    ],
    "物联网系统运维员": [
        "system administrator",
        "network administrator",
        "system operator",
        "ISCO 2631",
        "15-1244.00",  # Network and Computer Systems Administrators
        "系统运维"
    ],
    "计算机网络工程技术人员": [
        "network engineer",
        "network architect",
        "ISCO 2631",
        "15-1244.00",
        "网络工程师"
    ],
    "嵌入式系统开发人员": [
        "embedded system",
        "electronics engineer",
        "ISCO 2151",
        "ISCO 3114",
        "17-2072.00",  # Electronics Engineers
        "嵌入式开发"
    ]
}

def search_iot_occupation(
    occupation_name: str,
    ima_client: IMAKnowledgeClient,
    max_results: int = 5
) -> List[Dict]:
    """
    使用多关键词搜索物联网相关职业
    
    Args:
        occupation_name: 中国职业名称
        ima_client: IMA客户端
        max_results: 最大返回结果数
    
    Returns:
        找到的笔记列表
    """
    # 获取搜索提示词
    prompts = IOT_OCCUPATION_PROMPTS.get(occupation_name, [occupation_name])
    
    all_results = []
    seen_doc_ids = set()
    
    for prompt in prompts:
        print(f"  尝试关键词: {prompt}")
        notes = ima_client.search_notes(prompt, search_type=1, limit=10)
        
        for note in notes:
            doc_id = note.get('doc_id', '')
            if doc_id and doc_id not in seen_doc_ids:
                seen_doc_ids.add(doc_id)
                all_results.append({
                    'doc_id': doc_id,
                    'title': note.get('title', ''),
                    'prompt_used': prompt,
                    'summary': note.get('summary', '')
                })
                
                if len(all_results) >= max_results:
                    return all_results
    
    return all_results

def fetch_iot_occupation_data(
    occupation_name: str,
    prefer_ima: bool = True,
    output_path: Optional[str] = None
) -> Dict:
    """
    获取物联网相关职业数据（使用优化的搜索提示词）
    
    Args:
        occupation_name: 职业名称
        prefer_ima: 是否优先使用IMA
        output_path: 输出文件路径
    
    Returns:
        职业数据
    """
    result = {
        'occupation_name': occupation_name,
        'sources': {}
    }
    
    ima_client = IMAKnowledgeClient()
    
    if prefer_ima and ima_client.is_available():
        print(f"\n[OK] IMA已配置，搜索职业: {occupation_name}")
        
        # 使用多关键词搜索
        notes = search_iot_occupation(occupation_name, ima_client)
        
        if notes:
            print(f"\n找到 {len(notes)} 条相关笔记")
            
            # 获取最相关笔记的内容
            for note in notes[:3]:  # 最多获取前3条
                doc_id = note['doc_id']
                content = ima_client.get_note_content(doc_id)
                
                if content:
                    # 检查是否包含O*NET代码
                    has_onet = 'O*NET' in content or 'SOC Code' in content
                    has_isco = 'ISCO' in content
                    
                    result['sources'][f'IMA-{doc_id}'] = {
                        'doc_id': doc_id,
                        'title': note['title'],
                        'content': content,
                        'prompt_used': note['prompt_used'],
                        'has_onet_code': has_onet,
                        'has_isco_code': has_isco
                    }
                    
                    print(f"  获取: {note['title'][:50]} ({len(content)} chars)")
                    if has_onet:
                        print(f"    [!] 包含O*NET数据")
        else:
            print("IMA中未找到相关数据")
    
    # 如果IMA没有找到数据，使用API fallback
    if not result['sources']:
        print("\n使用API fallback...")
        # 这里可以调用ESCO API或O*NET API
        
        # 获取搜索提示词用于API查询
        prompts = IOT_OCCUPATION_PROMPTS.get(occupation_name, [occupation_name])
        result['search_prompts'] = prompts
    
    # 保存结果
    if output_path and result['sources']:
        script_dir = Path(__file__).parent
        project_root = script_dir.parent  # scripts/ -> occupation-analysis/
        output_full_path = project_root / output_path
        output_full_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_full_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n数据已保存到: {output_full_path}")
    
    return result

def main():
    parser = argparse.ArgumentParser(
        description='通过IMA知识库或API获取职业数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 优先使用IMA知识库
  python fetch_via_ima.py --occupation "motor vehicle mechanic"
  
  # 仅使用ESCO
  python fetch_via_ima.py --occupation "automotive technician" --source ONET
  
  # 强制使用API（不使用IMA）
  python fetch_via_ima.py --occupation "mechanic" --no-ima
  
  # 搜索物联网职业（使用优化提示词）
  python fetch_via_ima.py --iot "物联网系统安装调试员"
        """
    )
    parser.add_argument('--occupation', '-o', help='职业名称（通用模式）')
    parser.add_argument('--iot', '-i', help='物联网职业名称（使用优化提示词）')
    parser.add_argument('--source', '-s', default='all', choices=['ESCO', 'ONET', 'all'],
                        help='数据源（默认all）')
    parser.add_argument('--no-ima', action='store_true', help='不使用IMA，强制使用API')
    parser.add_argument('--output', '-out', help='输出文件路径')
    
    args = parser.parse_args()
    
    # 必须提供occupation或iot参数
    if not args.occupation and not args.iot:
        parser.error('请提供 --occupation 或 --iot 参数')
    
    # 根据参数选择处理方式
    if args.iot:
        # 物联网职业模式（使用优化提示词）
        result = fetch_iot_occupation_data(
            occupation_name=args.iot,
            prefer_ima=not args.no_ima,
            output_path=args.output
        )
    else:
        # 通用模式
        result = fetch_occupation_data_hybrid(
            occupation_name=args.occupation,
            source=args.source,
            prefer_ima=not args.no_ima,
            output_path=args.output
        )
    
    # 显示结果摘要
    if result['sources']:
        print("\n=== 获取结果摘要 ===")
        for source_name, data in result['sources'].items():
            print(f"\n{source_name}:")
            if isinstance(data, dict):
                if 'title' in data:
                    print(f"  标题: {data['title']}")
                if 'content' in data:
                    print(f"  内容长度: {len(data['content'])} 字符")
                if 'essential_skills' in data:
                    print(f"  必备技能: {len(data['essential_skills'])} 项")
                if 'tasks' in data:
                    print(f"  任务: {len(data['tasks'])} 项")
    else:
        print("\n未获取到职业数据")

if __name__ == '__main__':
    main()