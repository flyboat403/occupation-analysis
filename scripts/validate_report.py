#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
职业分析报告验证脚本

用于验证生成的报告是否符合质量要求：
1. 表格编号连续（表1→表11）
2. 表1岗位与表2对应岗位一致
3. 表4覆盖表2所有典型任务
4. 表7与表8能力编号一致

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


def validate_blank_cells(md_content: str) -> Tuple[bool, List[str]]:
    """验证表格空白单元格（除表7外，其他表格不允许空白）
    
    统一规则：扫描所有表格，检测空白单元格，跳过表7
    """
    errors = []
    warnings = []
    
    EXCLUDED_TABLES = ["表7", "表7-"]
    
    lines = md_content.split('\n')
    current_table_id = ""
    in_table = False
    blank_cells = []
    
    for i, line in enumerate(lines, 1):
        if line.startswith("### 表"):
            current_table_id = line.split(" ")[2] if len(line.split(" ")) > 2 else ""
            in_table = True
        elif line.startswith("|") and in_table:
            if line.startswith("|---|"):
                continue
            
            cells = [cell.strip() for cell in line.split("|")[1:-1]]
            for j, cell in enumerate(cells):
                if cell == "" or cell == "待补充":
                    if not any(excluded in current_table_id for excluded in EXCLUDED_TABLES):
                        blank_cells.append(f"{current_table_id} 第{i}行 第{j+1}列")
        elif not line.startswith("|") and in_table and current_table_id:
            in_table = False
    
    if blank_cells:
        for cell_loc in blank_cells[:10]:
            errors.append(f"空白单元格: {cell_loc}")
        if len(blank_cells) > 10:
            errors.append(f"... 共 {len(blank_cells)} 个空白单元格")
        return False, errors
    
    return True, ["✅ 所有表格单元格已填充（已跳过表7）"]


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


def validate_learning_domains_count(data: Dict) -> Tuple[bool, List[str]]:
    """验证学习领域数量（SKILL.md要求：一般为10个左右）"""
    warnings = []
    
    learning_domains = data.get('learning_domains', [])
    count = len(learning_domains)
    
    if count < 8:
        warnings.append(f"学习领域数量偏少（当前{count}个，建议≥8个接近10个）")
        return False, warnings
    
    if count > 15:
        warnings.append(f"学习领域数量偏多（当前{count}个，建议10个左右）")
        return True, warnings
    
    return True, [f"✅ 学习领域数量合理（{count}个）"]


def validate_total_hours(data: Dict) -> Tuple[bool, List[str]]:
    """验证总学时（SKILL.md要求：中职≥1200学时，高职/本科≥1600学时）"""
    errors = []
    warnings = []
    
    metadata = data.get('metadata', {})
    major_info = data.get('major_info', {})
    education_level = metadata.get('education_level', major_info.get('education_level', ''))
    
    learning_domains = data.get('learning_domains', [])
    total_hours = sum(domain.get('reference_hours', 0) for domain in learning_domains)
    
    is_zhongzhi = '中职' in education_level or '中等职业' in education_level
    is_gaozhi = '高职' in education_level or '高等职业' in education_level or '专科' in education_level
    is_benke = '本科' in education_level or '职业教育本科' in education_level
    
    min_hours = 1200 if is_zhongzhi else 1600
    
    if total_hours < min_hours:
        errors.append(f"总学时不足（当前{total_hours}学时，{education_level}要求≥{min_hours}学时）")
        return False, errors
    
    if total_hours < min_hours * 1.1:
        warnings.append(f"总学时略低于建议值（当前{total_hours}学时，建议{(int)(min_hours * 1.2)}学时左右）")
        return True, warnings
    
    return True, [f"✅ 总学时符合要求（{total_hours}学时）"]


def validate_domain_hours_range(data: Dict) -> Tuple[bool, List[str]]:
    """验证每领域学时范围（SKILL.md要求：48-128学时）"""
    warnings = []
    
    learning_domains = data.get('learning_domains', [])
    
    out_of_range = []
    for domain in learning_domains:
        name = domain.get('name', '')
        hours = domain.get('reference_hours', 0)
        if hours < 48:
            out_of_range.append(f"{name}: {hours}学时（低于48学时）")
        elif hours > 128:
            out_of_range.append(f"{name}: {hours}学时（高于128学时）")
    
    if out_of_range:
        warnings.append(f"部分学习领域学时超出范围（建议48-128学时）:")
        for item in out_of_range:
            warnings.append(f"  - {item}")
        return True, warnings
    
    return True, [f"✅ 所有学习领域学时在合理范围（48-128学时）"]


def validate_learning_situations_count(data: Dict) -> Tuple[bool, List[str]]:
    """验证学习情境数量（SKILL.md要求：每领域3-6个）"""
    errors = []
    
    learning_domains = data.get('learning_domains', [])
    learning_situations = data.get('learning_situations', [])
    
    domain_situation_count = {}
    for situation in learning_situations:
        domain_id = situation.get('domain_id', '')
        if domain_id:
            domain_situation_count[domain_id] = domain_situation_count.get(domain_id, 0) + 1
    
    out_of_range = []
    for domain in learning_domains:
        domain_id = domain.get('id', '')
        domain_name = domain.get('name', '')
        count = domain_situation_count.get(domain_id, 0)
        if count < 3:
            out_of_range.append(f"{domain_name}: {count}个情境（少于3个）")
        elif count > 6:
            out_of_range.append(f"{domain_name}: {count}个情境（多于6个）")
    
    if out_of_range:
        errors.append(f"部分学习领域情境数量超出范围（建议3-6个）:")
        for item in out_of_range:
            errors.append(f"  - {item}")
        return False, errors
    
    total_situations = len(learning_situations)
    return True, [f"✅ 学习情境数量合理（总计{total_situations}个，每领域3-6个）"]


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
        ("表格空白单元格", validate_blank_cells(md_content)),
        ("典型任务覆盖性", validate_task_coverage(data)),
        ("能力编号一致性", validate_ability_consistency(data)),
        ("学习领域数量", validate_learning_domains_count(data)),
        ("总学时合理性", validate_total_hours(data)),
        ("领域学时范围", validate_domain_hours_range(data)),
        ("学习情境数量", validate_learning_situations_count(data)),
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
