#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据整合脚本

整合专业教学标准、职业信息、映射信息、国际数据等多方面数据

功能：
1. 合并所有基础数据到一个统一的JSON文件
2. 支持SKILL.md中描述的参数格式
3. 输出base_data.json供后续语义分析使用

用法（SKILL.md描述的参数格式）：
    python scripts/integrate_data.py \
        --major temp/major_info.json \
        --occupation temp/occupation_info.json \
        --mapping temp/occupation_mapping_info.json \
        --international temp/international_data.json \
        --output temp/base_data.json
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


INTERNATIONAL_DATA_DIR = "temp/international_data"
OCCUPATIONS_DIR = f"{INTERNATIONAL_DATA_DIR}/occupations"


def load_json(file_path: Path) -> Dict:
    """
    加载JSON文件
    
    Args:
        file_path: JSON文件路径
        
    Returns:
        解析后的字典，失败返回空字典
    """
    if not file_path.exists():
        print(f"[WARNING] 文件不存在: {file_path}")
        return {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON解析失败 {file_path}: {e}")
        return {}
    except IOError as e:
        print(f"[ERROR] 读取文件失败 {file_path}: {e}")
        return {}

def merge_tasks(china_data: Dict, esco_data: Dict, onet_data: Dict) -> List[Dict]:
    """合并工作任务"""
    tasks = []
    
    # 从中国职业大典提取
    if china_data.get('occupations'):
        for occ in china_data['occupations']:
            if occ.get('main_tasks'):
                for task in occ['main_tasks']:
                    tasks.append({
                        "source": "中国职业大典",
                        "task": task,
                        "occupation": occ.get('name')
                    })
    
    # 从ESCO提取
    if esco_data.get('tasks'):
        for task in esco_data['tasks']:
            tasks.append({
                "source": "ESCO",
                "task": task.get('description', task.get('task', '')),
                "occupation": esco_data.get('occupation_name')
            })
    
    # 从O*NET提取
    if onet_data.get('tasks'):
        for task in onet_data['tasks']:
            tasks.append({
                "source": "O*NET",
                "task": task.get('task', ''),
                "occupation": onet_data.get('occupation_name')
            })
    
    return tasks

def merge_skills(esco_data: Dict, onet_data: Dict) -> Dict:
    """合并技能要求"""
    skills = {
        "esco": [],
        "onet": []
    }
    
    if esco_data.get('skills'):
        skills['esco'] = esco_data['skills']
    
    if onet_data.get('skills'):
        skills['onet'] = onet_data['skills']
    
    return skills

def merge_knowledge(esco_data: Dict, onet_data: Dict) -> Dict:
    """合并知识要求"""
    knowledge = {
        "esco": [],
        "onet": []
    }
    
    if esco_data.get('knowledge'):
        knowledge['esco'] = esco_data['knowledge']
    
    if onet_data.get('knowledge'):
        knowledge['onet'] = onet_data['knowledge']
    
    return knowledge

def merge_work_context(esco_data: Dict, onet_data: Dict) -> Dict:
    """合并工作情境"""
    context = {
        "esco": [],
        "onet": []
    }
    
    if esco_data.get('work_context'):
        context['esco'] = esco_data['work_context']
    
    if onet_data.get('work_context'):
        context['onet'] = onet_data['work_context']
    
    return context


def save_international_data(
    occupation_code: str,
    occupation_name: str,
    esco_data: Dict,
    onet_data: Dict,
    project_root: Path
) -> Dict:
    """
    保存国际职业数据到独立临时文件
    
    将 ESCO 和 O*NET 详细数据保存到 temp/international_data/occupations/ 目录，
    便于后续工作任务分析、能力分析等过程提取使用。
    
    Args:
        occupation_code: 中国职业代码
        occupation_name: 中国职业名称
        esco_data: ESCO 数据
        onet_data: O*NET 数据
        project_root: 项目根目录
    
    Returns:
        包含文件路径和摘要信息的字典
    """
    result = {
        "china_code": occupation_code,
        "china_name": occupation_name,
        "isco_code": "",
        "onet_code": "",
        "esco_file": None,
        "onet_file": None,
        "key_skills": [],
        "key_tasks": [],
        "key_knowledge": []
    }
    
    # 创建目录
    occupations_dir = project_root / OCCUPATIONS_DIR
    occupations_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存 ESCO 数据
    if esco_data and esco_data.get('sources'):
        esco_file_path = f"{OCCUPATIONS_DIR}/{occupation_code}_esco.json"
        esco_full_path = project_root / esco_file_path
        
        # 提取 ESCO 相关信息
        esco_source = esco_data['sources'].get('ESCO-API') or esco_data['sources'].get('IMA-ESCO') or {}
        
        # 构建 ESCO 数据结构
        esco_structured = {
            "source": "ESCO",
            "occupation": {
                "china_code": occupation_code,
                "china_name": occupation_name,
                "isco_code": esco_source.get('code', '')
            },
            "title": esco_source.get('title', ''),
            "description": esco_source.get('description', ''),
            "essential_skills": extract_skills(esco_source, 'esco'),
            "tasks": extract_tasks(esco_source, 'esco'),
            "knowledge": extract_knowledge(esco_source, 'esco'),
            "raw": esco_source
        }
        
        with open(esco_full_path, 'w', encoding='utf-8') as f:
            json.dump(esco_structured, f, ensure_ascii=False, indent=2)
        
        result["esco_file"] = esco_file_path
        result["isco_code"] = esco_source.get('code', '')
        result["key_skills"].extend([s.get('name', s) if isinstance(s, dict) else s for s in esco_structured["essential_skills"][:8]])
        result["key_tasks"].extend([t.get('description', t) if isinstance(t, dict) else t for t in esco_structured["tasks"][:5]])
    
    # 保存 O*NET 数据
    if onet_data and onet_data.get('sources'):
        onet_file_path = f"{OCCUPATIONS_DIR}/{occupation_code}_onet.json"
        onet_full_path = project_root / onet_file_path
        
        # 提取 O*NET 相关信息
        onet_source = onet_data['sources'].get('ONET-API') or onet_data['sources'].get('IMA-ONET') or {}
        
        # 构建 O*NET 数据结构
        onet_structured = {
            "source": "O*NET",
            "occupation": {
                "china_code": occupation_code,
                "china_name": occupation_name,
                "onet_code": onet_source.get('code', '')
            },
            "title": onet_source.get('title', ''),
            "description": onet_source.get('summary', {}).get('description', '') if isinstance(onet_source.get('summary'), dict) else '',
            "tasks": extract_tasks(onet_source, 'onet'),
            "skills": extract_skills(onet_source, 'onet'),
            "knowledge": extract_knowledge(onet_source, 'onet'),
            "abilities": extract_abilities(onet_source),
            "work_activities": onet_source.get('summary', {}).get('work_activities', []) if isinstance(onet_source.get('summary'), dict) else [],
            "raw": onet_source
        }
        
        with open(onet_full_path, 'w', encoding='utf-8') as f:
            json.dump(onet_structured, f, ensure_ascii=False, indent=2)
        
        result["onet_file"] = onet_file_path
        result["onet_code"] = onet_source.get('code', '')
        
        # 合并关键信息（如果 ESCO 没有提供）
        if not result["key_skills"]:
            result["key_skills"].extend([s.get('name', s) if isinstance(s, dict) else s for s in onet_structured["skills"][:8]])
        if not result["key_tasks"]:
            result["key_tasks"].extend([t.get('description', t) if isinstance(t, dict) else t for t in onet_structured["tasks"][:5]])
        result["key_knowledge"].extend([k.get('name', k) if isinstance(k, dict) else k for k in onet_structured["knowledge"][:5]])
    
    return result


def extract_skills(source_data: Dict, source_type: str) -> List[Dict]:
    """从源数据中提取技能"""
    if not source_data:
        return []
    
    if source_type == 'esco':
        raw_skills = source_data.get('skills', source_data.get('essential_skills', []))
        return [{"skill_name": s.get('name', s) if isinstance(s, dict) else s, "importance": s.get('importance', 'essential') if isinstance(s, dict) else 'essential'} for s in raw_skills[:15]]
    
    if source_type == 'onet':
        raw_skills = source_data.get('skills', [])
        if isinstance(source_data.get('summary'), dict):
            raw_skills = source_data['summary'].get('skills', raw_skills)
        return [{"skill_name": s.get('name', s) if isinstance(s, dict) else s, "importance": s.get('importance', '') if isinstance(s, dict) else ''} for s in raw_skills[:15]]
    
    return []


def extract_tasks(source_data: Dict, source_type: str) -> List[Dict]:
    """从源数据中提取任务"""
    if not source_data:
        return []
    
    if source_type == 'esco':
        raw_tasks = source_data.get('tasks', [])
        return [{"task_description": t.get('description', t) if isinstance(t, dict) else t} for t in raw_tasks[:10]]
    
    if source_type == 'onet':
        raw_tasks = source_data.get('tasks', [])
        if isinstance(source_data.get('summary'), dict):
            raw_tasks = source_data['summary'].get('tasks', raw_tasks)
        return [{"task_description": t.get('description', t.get('task', t)) if isinstance(t, dict) else t, "importance": t.get('importance', '') if isinstance(t, dict) else ''} for t in raw_tasks[:10]]
    
    return []


def extract_knowledge(source_data: Dict, source_type: str) -> List[Dict]:
    """从源数据中提取知识要求"""
    if not source_data:
        return []
    
    if source_type == 'esco':
        raw_knowledge = source_data.get('knowledge', [])
        return [{"knowledge_area": k.get('name', k) if isinstance(k, dict) else k} for k in raw_knowledge[:10]]
    
    if source_type == 'onet':
        raw_knowledge = source_data.get('knowledge', [])
        if isinstance(source_data.get('summary'), dict):
            raw_knowledge = source_data['summary'].get('knowledge', raw_knowledge)
        return [{"knowledge_area": k.get('name', k) if isinstance(k, dict) else k} for k in raw_knowledge[:10]]
    
    return []


def extract_abilities(source_data: Dict) -> List[Dict]:
    """从 O*NET 数据中提取能力"""
    if not source_data:
        return []
    
    raw_abilities = source_data.get('abilities', [])
    if isinstance(source_data.get('summary'), dict):
        raw_abilities = source_data['summary'].get('abilities', raw_abilities)
    
    return [{"ability_name": a.get('name', a) if isinstance(a, dict) else a} for a in raw_abilities[:10]]

def analyze_typical_tasks(tasks: List[Dict]) -> List[Dict]:
    """
    分析并提炼典型工作任务
    
    基于工作任务列表，分析归类形成典型工作任务
    """
    if not tasks:
        return []
    
    typical_tasks = []
    task_groups = {}
    
    for task in tasks:
        # 防御性编程：确保task字典有'task'键
        task_text = task.get('task', '')
        if not task_text:
            continue
        
        # 简单的关键词匹配分组
        keywords = ['维护', '维修', '诊断', '检测', '销售', '服务', '管理']
        for keyword in keywords:
            if keyword in task_text:
                if keyword not in task_groups:
                    task_groups[keyword] = []
                task_groups[keyword].append(task)
                break
    
    for keyword, group_tasks in task_groups.items():
        typical_tasks.append({
            "name": f"{keyword}相关工作",
            "count": len(group_tasks),
            "tasks": group_tasks[:5]  # 只保留前5个示例
        })
    
    return typical_tasks

def integrate_data(
    china_path: Optional[str],
    esco_path: Optional[str],
    onet_path: Optional[str],
    output_path: str,
    occupation_code: Optional[str] = None,
    occupation_name: Optional[str] = None
) -> Dict:
    """
    整合三个数据源的职业信息
    
    Args:
        china_path: 中国职业大典数据路径
        esco_path: ESCO数据路径
        onet_path: O*NET数据路径
        output_path: 输出文件路径
        occupation_code: 中国职业代码（用于保存国际数据）
        occupation_name: 中国职业名称（用于保存国际数据）
    
    Returns:
        整合后的数据
    """
    # 确定项目根目录（修正路径计算）
    script_dir = Path(__file__).parent
    project_root = script_dir.parent  # scripts/ -> occupation-analysis/
    
    # 加载数据
    china_data: Dict = {}
    esco_data: Dict = {}
    onet_data: Dict = {}
    
    if china_path:
        china_full_path = project_root / china_path
        china_data = load_json(china_full_path)
    
    if esco_path:
        esco_full_path = project_root / esco_path
        esco_data = load_json(esco_full_path)
    
    if onet_path:
        onet_full_path = project_root / onet_path
        onet_data = load_json(onet_full_path)
    
    # 整合数据
    integrated = {
        "china_data": china_data,
        "international_data": {
            "esco": esco_data,
            "onet": onet_data
        },
        "merged": {
            "tasks": merge_tasks(china_data, esco_data, onet_data),
            "skills": merge_skills(esco_data, onet_data),
            "knowledge": merge_knowledge(esco_data, onet_data),
            "work_context": merge_work_context(esco_data, onet_data)
        }
    }
    
    # 分析典型工作任务
    integrated["analysis"] = {
        "typical_tasks": analyze_typical_tasks(integrated["merged"]["tasks"])
    }
    
    # 保存国际数据到独立临时文件，供后续分析任务使用
    international_details = None
    if occupation_code and occupation_name:
        international_details = save_international_data(
            occupation_code=occupation_code,
            occupation_name=occupation_name,
            esco_data=esco_data,
            onet_data=onet_data,
            project_root=project_root
        )
        integrated["international_details"] = international_details
        print(f"[OK] 国际数据已保存到: {INTERNATIONAL_DATA_DIR}/occupations/{occupation_code}_*.json")
    
    # 保存输出（带错误处理）
    save_success = False
    try:
        output_full_path = project_root / output_path
        output_full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_full_path, 'w', encoding='utf-8') as f:
            json.dump(integrated, f, ensure_ascii=False, indent=2)
        print(f"[OK] 整合数据已保存到: {output_full_path}")
        save_success = True
    except IOError as e:
        error_msg = f"保存文件失败: {e}"
        print(f"[ERROR] {error_msg}")
        integrated['save_error'] = error_msg
    
    integrated['save_success'] = save_success
    return integrated

def main():
    parser = argparse.ArgumentParser(
        description='整合职业数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例（推荐格式）:
    # 使用SKILL.md描述的参数格式
    python scripts/integrate_data.py \
        --major temp/major_info.json \
        --occupation temp/occupation_info.json \
        --mapping temp/occupation_mapping_info.json \
        --international temp/international_data.json \
        --output temp/base_data.json

示例（旧格式，兼容）:
    python scripts/integrate_data.py \
        --china temp/occupation_info.json \
        --esco temp/esco_data.json \
        --onet temp/onet_data.json \
        --output temp/integrated_data.json
        """
    )
    
    # 新参数（SKILL.md描述的格式）
    parser.add_argument('--major', '-M', help='专业教学标准数据路径 (major_info.json)')
    parser.add_argument('--occupation', '-O', help='职业信息数据路径 (occupation_info.json)')
    parser.add_argument('--mapping', help='ESCO/O*NET映射信息路径 (occupation_mapping_info.json)')
    parser.add_argument('--international', '-I', help='国际数据路径 (international_data.json)')
    
    # 旧参数（兼容）
    parser.add_argument('--china', '-c', help='[旧参数] 中国职业大典数据路径')
    parser.add_argument('--esco', '-e', help='[旧参数] ESCO数据路径')
    parser.add_argument('--onet', '-o', help='[旧参数] O*NET数据路径')
    
    parser.add_argument('--output', '-out', default='temp/base_data.json', help='输出文件路径')
    parser.add_argument('--occupation-code', help='中国职业代码（用于保存国际数据到独立文件）')
    parser.add_argument('--occupation-name', help='中国职业名称（用于保存国际数据到独立文件）')
    
    args = parser.parse_args()
    
    # 确定项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # 新参数格式：整合所有基础数据
    if args.major or args.occupation or args.mapping or args.international:
        base_data = {
            "major_info": {},
            "occupation_info": {},
            "occupation_mapping_info": {},
            "international_data": {},
            "generated_at": datetime.now().isoformat()
        }
        
        if args.major:
            major_path = project_root / args.major if not Path(args.major).is_absolute() else Path(args.major)
            base_data["major_info"] = load_json(major_path)
            print(f"[OK] 加载专业教学标准: {major_path}")
        
        if args.occupation:
            occ_path = project_root / args.occupation if not Path(args.occupation).is_absolute() else Path(args.occupation)
            base_data["occupation_info"] = load_json(occ_path)
            print(f"[OK] 加载职业信息: {occ_path}")
        
        if args.mapping:
            map_path = project_root / args.mapping if not Path(args.mapping).is_absolute() else Path(args.mapping)
            base_data["occupation_mapping_info"] = load_json(map_path)
            print(f"[OK] 加载映射信息: {map_path}")
        
        if args.international:
            int_path = project_root / args.international if not Path(args.international).is_absolute() else Path(args.international)
            base_data["international_data"] = load_json(int_path)
            print(f"[OK] 加载国际数据: {int_path}")
        
        # 保存输出
        output_path = project_root / args.output if not Path(args.output).is_absolute() else Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(base_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n[OK] 基础数据已整合到: {output_path}")
        print(f"     - 专业信息: {len(base_data['major_info'].get('results', []))} 条")
        print(f"     - 职业信息: {len(base_data['occupation_info'].get('occupations', []))} 个职业")
        print(f"     - 映射信息: {len(base_data['occupation_mapping_info'].get('mapping_results', []))} 条")
        print(f"     - 国际数据: {len(base_data['international_data'].get('occupations', []))} 个职业")
        return
    
    # 旧参数格式：兼容处理
    result = integrate_data(
        china_path=args.china,
        esco_path=args.esco,
        onet_path=args.onet,
        output_path=args.output,
        occupation_code=args.occupation_code,
        occupation_name=args.occupation_name
    )
    
    print(f"\n数据整合完成")
    print(f"- 工作任务: {len(result['merged']['tasks'])} 条")
    print(f"- 典型工作任务: {len(result['analysis']['typical_tasks'])} 个")
    if result.get('international_details'):
        print(f"- 国际数据文件: 已保存")

if __name__ == '__main__':
    main()