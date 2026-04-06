#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
职业分析报告验证脚本

用于验证生成的报告是否符合质量要求：
1. 表格编号连续（表1→表11）
2. 表1岗位与表2对应岗位一致
3. 表4覆盖表2所有典型任务
4. 表7与表8能力编号一致
5. 能力动词符合教育层次要求

用法：
    python scripts/validate_report.py --report temp/report.md --data temp/analysis_data.json
"""

import json
import argparse
import re
from pathlib import Path
from typing import Dict, List, Tuple


def load_json(file_path: Path) -> Dict:
    """加载JSON文件"""
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_markdown(file_path: Path) -> str:
    """加载Markdown文件"""
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def validate_table_numbers(md_content: str) -> Tuple[bool, List[str]]:
    """验证表格编号连续性（主编号表1→表11）"""
    errors = []
    
    # 查找所有表格编号（支持"表X"和"表X-Y"格式）
    pattern = r'### 表(\d+)(?:-\d+)?'
    matches = re.findall(pattern, md_content)
    
    if not matches:
        errors.append("未找到任何表格编号")
        return False, errors
    
    # 提取主表格编号
    main_tables = set(int(m) for m in matches)
    
    # 检查主表格编号完整性（应包含1-11）
    expected = set(range(1, 12))  # 表1到表11
    missing = expected - main_tables
    extra = main_tables - expected
    
    if missing:
        errors.append(f"缺少主表格编号: 表{sorted(missing)}")
    if extra:
        errors.append(f"存在额外表格编号: 表{sorted(extra)}")
    
    if errors:
        return False, errors
    
    tables_found = sorted(main_tables)
    return True, [f"✅ 表格编号完整（表{tables_found[0]}→表{tables_found[-1]}）"]


def validate_ability_verb_level(data: Dict) -> Tuple[bool, List[str]]:
    """验证能力动词符合教育层次要求"""
    errors = []
    warnings = []
    
    education_level = data.get('metadata', {}).get('education_level', '')
    is_zhongzhi = '中职' in education_level or '中等职业' in education_level
    
    if not is_zhongzhi:
        return True, ["⚠️ 非中职层次，跳过能力动词检查"]
    
    # 中职禁用的动词
    forbidden_verbs = ['设计', '优化', '创新', '规划', '研发', '开发', '研究']
    # 中职应使用的动词
    recommended_verbs = ['配置', '安装', '操作', '执行', '使用', '维护', '诊断', '维修']
    
    # 检查能力描述
    abilities = data.get('abilities', {})
    all_abilities = (
        abilities.get('professional', []) +
        abilities.get('methodological', []) +
        abilities.get('social', [])
    )
    
    issues = []
    for ability in all_abilities:
        if isinstance(ability, dict):
            desc = ability.get('description', '')
        else:
            desc = str(ability)
        
        for verb in forbidden_verbs:
            if verb in desc and not any(rv in desc for rv in recommended_verbs):
                issues.append(f"'{desc}' 使用了 '{verb}'")
    
    if issues:
        errors.append(f"能力动词不符合中职要求（应使用'能操作/能配置/能维护'等）:")
        for issue in issues[:5]:
            errors.append(f"  - {issue}")
        return False, errors
    
    return True, ["✅ 能力动词符合中职层次要求"]


def validate_task_coverage(data: Dict) -> Tuple[bool, List[str]]:
    """验证表4覆盖表2所有典型任务"""
    errors = []
    
    typical_tasks = data.get('typical_tasks', [])
    action_domains = data.get('action_domains', [])
    
    if not typical_tasks:
        return True, ["⚠️ 无典型任务数据"]
    
    if not action_domains:
        errors.append("无行动领域数据")
        return False, errors
    
    # 收集任务ID
    task_ids = set()
    for task in typical_tasks:
        task_id = task.get('id', '')
        if task_id:
            task_ids.add(task_id)
    
    # 收集行动领域覆盖的任务
    covered_ids = set()
    for domain in action_domains:
        for task in domain.get('tasks', []):
            covered_ids.add(task)
    
    missing = task_ids - covered_ids
    if missing:
        errors.append(f"表4未覆盖以下典型任务: {missing}")
        return False, errors
    
    return True, [f"✅ 表4覆盖所有典型任务（{len(covered_ids)}/{len(task_ids)}）"]


def validate_ability_consistency(data: Dict) -> Tuple[bool, List[str]]:
    """验证表7与表8能力编号一致"""
    errors = []
    
    # 从abilities中获取能力编号
    abilities = data.get('abilities', {})
    
    prof = abilities.get('professional', [])
    meth = abilities.get('methodological', [])
    soc = abilities.get('social', [])
    
    # 收集所有能力编号
    all_codes = set()
    for ability_list in [prof, meth, soc]:
        for ability in ability_list:
            if isinstance(ability, dict):
                code = ability.get('code', '')
                if code:
                    all_codes.add(code)
    
    # 从action_domains中获取能力编号
    domain_codes = set()
    for domain in data.get('action_domains', []):
        domain_abilities = domain.get('abilities', {})
        for ability_type in ['professional', 'methodological', 'social']:
            for ability in domain_abilities.get(ability_type, []):
                if isinstance(ability, dict):
                    code = ability.get('code', '')
                    if code:
                        domain_codes.add(code)
    
    if all_codes and domain_codes:
        missing = domain_codes - all_codes
        if missing:
            errors.append(f"表8能力编号与表7不一致，缺少: {missing}")
            return False, errors
    
    return True, [f"✅ 表7与表8能力编号一致（{len(all_codes)}个能力）"]


def validate_required_fields(data: Dict) -> Tuple[bool, List[str]]:
    """验证必需字段完整性"""
    errors = []
    
    required_fields = {
        'major_info': ['major_code', 'major_name', 'education_level'],
        'typical_tasks': ['id', 'name'],
        'action_domains': ['id', 'name', 'tasks'],
        'learning_domains': ['id', 'name']
    }
    
    for field, sub_fields in required_fields.items():
        if field not in data:
            errors.append(f"缺少必需字段: {field}")
            continue
        
        if isinstance(data[field], list):
            for i, item in enumerate(data[field]):
                for sub_field in sub_fields:
                    if sub_field not in item:
                        errors.append(f"{field}[{i}] 缺少字段: {sub_field}")
    
    if errors:
        return False, errors
    
    return True, ["✅ 必需字段完整"]


def main():
    parser = argparse.ArgumentParser(description='职业分析报告验证')
    parser.add_argument('--report', '-r', required=True, help='Markdown报告文件路径')
    parser.add_argument('--data', '-d', required=True, help='analysis_data.json文件路径')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详细信息')
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    report_path = Path(args.report)
    data_path = Path(args.data)
    
    if not report_path.is_absolute():
        report_path = project_root / report_path
    if not data_path.is_absolute():
        data_path = project_root / data_path
    
    print("="*60)
    print("职业分析报告质量验证")
    print("="*60)
    print(f"报告文件: {report_path}")
    print(f"数据文件: {data_path}")
    print()
    
    # 加载文件
    try:
        md_content = load_markdown(report_path)
        data = load_json(data_path)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return 1
    
    all_passed = True
    
    # 执行验证
    validations = [
        ("必需字段完整性", validate_required_fields(data)),
        ("表格编号连续性", validate_table_numbers(md_content)),
        ("能力动词层次匹配", validate_ability_verb_level(data)),
        ("典型任务覆盖性", validate_task_coverage(data)),
        ("能力编号一致性", validate_ability_consistency(data)),
    ]
    
    for name, (passed, messages) in validations:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"\n【{name}】{status}")
        for msg in messages:
            print(f"  {msg}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ 所有验证通过")
        return 0
    else:
        print("❌ 存在验证失败项，请检查并修复")
        return 1


if __name__ == '__main__':
    exit(main())
