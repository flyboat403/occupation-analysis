#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
职业分析报告生成脚本

将分析数据 JSON 转换为 Markdown 报告，然后可通过 pandoc 转换为 Word 文档

用法:
    python scripts/generate_report.py --data temp/analysis_data.json --output temp/report.md
    
转换为 Word:
    pandoc temp/report.md --reference-doc=references/reference.docx -o output/report.docx
"""

import json
import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


# ==================== 常量定义 ====================

# 能力编号前缀
ABILITY_CODE_PREFIX = {
    'professional': 'Z',
    'methodological': 'F',
    'social': 'S'
}

# 能力类型名称
ABILITY_TYPE_NAMES = {
    'professional': '专业能力',
    'methodological': '方法能力',
    'social': '社会能力'
}

# 教育层次禁止动词
EDUCATION_LEVEL_FORBIDDEN_VERBS = {
    '中职': ['设计', '优化', '创新', '管理', '分析', '诊断'],
    '高职': ['研发', '创新', '管理'],
    '职教本科': []
}

# 教育层次允许动词
EDUCATION_LEVEL_ALLOWED_VERBS = {
    '中职': ['操作', '执行', '完成', '使用', '识别', '检测'],
    '高职': ['检测', '诊断', '分析', '维护', '维修', '优化'],
    '职教本科': ['设计', '优化', '管理', '创新']
}


def normalize_task_fields(task: Dict) -> Dict:
    """标准化任务字段名（支持 name 和 task_name 两种字段名）"""
    if 'task_name' in task and 'name' not in task:
        task['name'] = task['task_name']
    return task


def check_ability_verb_compliance(text: str, education_level: str) -> List[str]:
    """检查能力描述是否符合教育层次要求
    
    Args:
        text: 能力描述文本
        education_level: 教育层次（中职/高职/职教本科）
    
    Returns:
        发现的禁止动词列表
    """
    violations = []
    level_key = None
    
    if '中职' in education_level or '中等职业教育' in education_level:
        level_key = '中职'
    elif '高职' in education_level or '高等职业教育' in education_level:
        level_key = '高职'
    elif '职教本科' in education_level or '职业教育本科' in education_level:
        level_key = '职教本科'
    
    if level_key:
        forbidden = EDUCATION_LEVEL_FORBIDDEN_VERBS.get(level_key, [])
        for verb in forbidden:
            if verb in text:
                violations.append(verb)
    
    return violations


def load_analysis_data(data_path: Path) -> Dict:
    """加载分析数据"""
    if not data_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {data_path}")
    
    with open(data_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_data_structure(data: Dict) -> None:
    """校验数据结构是否符合预期
    
    检查必需字段是否存在，结构是否正确
    参考: references/analysis_data_template.json
    """
    errors = []
    warnings = []
    
    # 检查 major_info
    if 'major_info' not in data:
        errors.append("缺少 major_info 字段")
    else:
        required = ['major_name', 'major_code', 'education_level']
        for field in required:
            if field not in data['major_info']:
                warnings.append(f"major_info 缺少 {field} 字段")
    
    # 检查 typical_tasks
    if 'typical_tasks' not in data:
        warnings.append("缺少 typical_tasks 字段，表2-3将为空")
    else:
        for i, task in enumerate(data['typical_tasks']):
            normalize_task_fields(task)
            if 'name' not in task:
                warnings.append(f"typical_tasks[{i}] 缺少 name 字段")
    
    # 检查 action_domains 结构
    if 'action_domains' in data:
        for i, domain in enumerate(data['action_domains']):
            if 'name' not in domain:
                errors.append(f"action_domains[{i}] 缺少 name 字段")
            if 'tasks' not in domain:
                errors.append(f"action_domains[{i}] 缺少 tasks 字段（必需）")
            
            abilities = domain.get('abilities', {})
            if not abilities:
                errors.append(f"action_domains[{i}] 缺少 abilities 字段（必需，影响表6-8）")
    
    # 检查 learning_domains 结构
    if 'learning_domains' in data:
        for i, course in enumerate(data['learning_domains']):
            if 'name' not in course:
                errors.append(f"learning_domains[{i}] 缺少 name 字段")
            if 'methods' not in course:
                errors.append(f"learning_domains[{i}] 缺少 methods 字段（必需，影响表10）")
            if 'assessment' not in course:
                errors.append(f"learning_domains[{i}] 缺少 assessment 字段（必需，影响表10）")
    
    # 输出校验结果
    if errors:
        print("\n[ERROR] 数据结构校验失败:")
        for err in errors:
            print(f"  [ERROR] {err}")
        raise ValueError("数据结构不符合预期，请检查 analysis_data.json\n参考格式: references/analysis_data_template.json")
    
    if warnings:
        print("\n[WARNING] 数据结构校验警告:")
        for warn in warnings:
            print(f"  [WARN] {warn}")
        print("[HINT] 部分表格内容可能为空，建议补充缺失字段\n")


def extract_ability_names(ability_list: List) -> List[str]:
    """从能力列表中提取名称（支持字符串和字典格式）
    
    Args:
        ability_list: 能力列表，元素可以是字符串或字典
    
    Returns:
        能力名称列表
    """
    names = []
    if not ability_list:
        return names
    
    for item in ability_list:
        if isinstance(item, dict):
            name = item.get('name', item.get('description', ''))
            if name:
                names.append(name)
        elif isinstance(item, str):
            names.append(item)
    
    return names


def generate_markdown_table(headers: List[str], rows: List[List[str]]) -> str:
    """生成 Markdown 表格（横向表格）"""
    header_line = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    data_lines = []
    for row in rows:
        while len(row) < len(headers):
            row.append("")
        row_str = "| " + " | ".join(str(cell) for cell in row[:len(headers)]) + " |"
        data_lines.append(row_str)
    return "\n".join([header_line, separator] + data_lines)


def generate_vertical_table(data: Dict[str, str]) -> str:
    """生成纵向表格（属性作为行标题）
    
    Pandoc 要求表格必须有：
    1. 表头行
    2. 分隔行（|---|---|）
    3. 数据行
    """
    lines = []
    # 表头行
    lines.append("| 属性 | 内容 |")
    # 分隔行
    lines.append("|------|------|")
    # 数据行
    for key, value in data.items():
        lines.append(f"| **{key}** | {value} |")
    return "\n".join(lines)


def validate_action_domains_coverage(typical_tasks: List[Dict], action_domains: List[Dict]) -> None:
    """验证行动领域覆盖所有典型工作任务
    
    约束：action_domains 中的 tasks 必须对应 typical_tasks 中的任务ID
    """
    if not typical_tasks or not action_domains:
        return
    
    # 收集所有典型任务ID
    task_ids = set()
    for task in typical_tasks:
        task_id = task.get('id', '')
        if task_id:
            task_ids.add(task_id)
    
    # 收集行动领域中的所有任务ID
    domain_task_ids = set()
    for domain in action_domains:
        for task in domain.get('tasks', []):
            domain_task_ids.add(task)
    
    # 检查未覆盖的任务
    missing = task_ids - domain_task_ids
    if missing:
        print(f"[WARNING] 以下典型任务ID未被行动领域覆盖: {missing}")
        print(f"[HINT] 请在 analysis_data.json 的 action_domains.tasks 中添加这些任务ID")


def generate_report(data: Dict) -> str:
    """生成完整的 Markdown 报告"""
    
    metadata = data.get('metadata', {})
    major_info = data.get('major_info', {})
    
    major_name = major_info.get('major_name', '{专业名称}')
    major_code = major_info.get('major_code', '{专业代码}')
    education_level = major_info.get('education_level', '{教育层次}')
    date = datetime.now().strftime('%Y年%m月%d日')
    
    sections = []
    
    # 标题
    sections.append(f"# {major_name}专业职业分析报告\n")
    sections.append(f"**教育层次**：{education_level}\n")
    sections.append(f"**专业代码**：{major_code}\n")
    sections.append(f"**编制日期**：{date}\n")
    sections.append("---\n")
    
    # 目录
    sections.append("## 目录\n")
    sections.append("- 一、工作任务分析")
    sections.append("- 二、确定典型工作任务")
    sections.append("- 三、典型工作任务分析")
    sections.append("- 四、归类、划分行动领域")
    sections.append("- 五、行动领域描述与职业能力分析")
    sections.append("- 六、学习领域分析")
    sections.append("- 七、学习情境设计\n")
    sections.append("---\n")
    
    # ==================== 一、工作任务分析 ====================
    # 修改：每个工作任务单独一个表格，内容完整
    # 修复：一个职业可能对应多个工种，需要展开为独立岗位
    sections.append("## 一、工作任务分析\n")
    
    occupations = data.get('occupations', [])
    task_counter = 1
    
    # 构建岗位-任务映射：从典型任务中提取岗位信息
    typical_tasks = data.get('typical_tasks', [])
    job_task_mapping = {}  # {岗位名: [任务名列表]}
    for task in typical_tasks:
        job = task.get('related_job', '')
        task_name = task.get('name', task.get('task_name', ''))
        if job and task_name:
            if job not in job_task_mapping:
                job_task_mapping[job] = []
            job_task_mapping[job].append(task_name)
    
    # 如果没有从典型任务中提取到岗位，则使用occupations数据
    if not job_task_mapping and occupations:
        for occ in occupations:
            occ_name = occ.get('职业名称', occ.get('name', '岗位'))
            tasks = occ.get('主要工作任务', occ.get('tasks', []))
            job_task_mapping[occ_name] = [t if isinstance(t, str) else t.get('name', '') for t in tasks]
    
    # 获取工作任务详细信息
    task_details = data.get('work_task_details', {})
    
    # 为每个岗位生成工作任务分析表
    for job_name, task_list in job_task_mapping.items():
        for task_name in task_list:
            if not task_name:
                continue
                
            sections.append(f"### 表1-{task_counter} {task_name}工作任务分析\n")
            sections.append(f"**所属岗位**：{job_name}\n")
            
            # 获取详细分析数据
            detail = task_details.get(task_name, {})
            
            # 根据教育层次调整能力描述深度
            edu_level = metadata.get('education_level', major_info.get('education_level', ''))
            ability_desc = detail.get('ability', f"能独立完成{task_name}相关任务，具备相应的专业技能和操作能力")
            if '中职' in edu_level:
                # 中职侧重操作技能
                ability_desc = ability_desc.replace('分析', '识别').replace('诊断', '检测')
            
            # 动态生成默认值（基于岗位和任务名称），避免硬编码模板内容
            default_condition = f"{job_name}工作场所，配备必要的专业设备和工具"
            default_certificate = f"{job_name}相关职业资格证书"
            
            # 根据任务类型智能推断工作条件
            task_lower = task_name.lower()
            if any(kw in task_lower for kw in ['设计', '视觉', '界面', '平面', 'ui', '交互']):
                default_condition = "设计工作室，配备设计工作站和专业设计软件"
                default_certificate = "设计师相关职业资格证书"
            elif any(kw in task_lower for kw in ['视频', '剪辑', '影视', '后期', '拍摄', '短视频']):
                default_condition = "视频制作工作室，配备拍摄设备和剪辑工作站"
                default_certificate = "视频剪辑师相关证书"
            elif any(kw in task_lower for kw in ['三维', '动画', '建模', '渲染', '特效']):
                default_condition = "三维动画工作室，配备高性能工作站和专业软件"
                default_certificate = "数字创意建模相关证书"
            elif any(kw in task_lower for kw in ['运营', '新媒体', '内容', '媒体', '策划']):
                default_condition = "新媒体运营工作室，配备内容制作工具和数据分析平台"
                default_certificate = "全媒体运营师证书"
            elif any(kw in task_lower for kw in ['维修', '检修', '维护', '故障', '检测', '诊断']):
                default_condition = "维修车间，配备必要的检测设备和维修工具"
                default_certificate = "维修工职业资格证书"
            elif any(kw in task_lower for kw in ['护理', '照护', '康复', '医疗', '保健']):
                default_condition = "医疗机构或康复中心，配备必要的护理设备"
                default_certificate = "护理员或康复师职业资格证书"
            
            # 使用纵向表格
            table_data = {
                "工作任务": task_name,
                "工作内容": detail.get('content', f"根据工作要求，完成{task_name}相关工作任务"),
                "职业能力": ability_desc,
                "工作条件": detail.get('condition', default_condition),
                "工作经验要求": detail.get('experience', "经过专业培训，掌握基本操作技能"),
                "工作成果": detail.get('result', f"完成{task_name}任务并达到质量标准"),
                "职业类证书": detail.get('certificate', default_certificate)
            }
            sections.append(generate_vertical_table(table_data))
            sections.append("\n")
            task_counter += 1
    
    # ==================== 二、确定典型工作任务 ====================
    sections.append("## 二、确定典型工作任务\n")
    sections.append(f"### 表2-1 {major_name}典型工作任务汇总表\n")
    
    typical_tasks = data.get('typical_tasks', [])
    if typical_tasks:
        headers = ["序号", "对应岗位", "典型工作任务", "工作对象", "工作难度"]
        rows = []
        for i, task in enumerate(typical_tasks, 1):
            rows.append([
                str(i),
                task.get('related_job', ''),
                task.get('name', task.get('task_name', '')),
                task.get('work_object', task.get('object', '')),
                task.get('difficulty_level', task.get('difficulty', ''))
            ])
        sections.append(generate_markdown_table(headers, rows))
    sections.append("\n")
    
    # ==================== 三、典型工作任务分析 ====================
    sections.append("## 三、典型工作任务分析\n")
    
    for i, task in enumerate(typical_tasks, 1):
        task_name = task.get('name', task.get('task_name', f'任务{i}'))
        sections.append(f"### 表3-{i} {task_name}\n")
        
        # 支持新字段名和旧字段名
        table_data = {
            "工作对象": task.get('work_object', task.get('object', '')),
            "工具/材料/设备": task.get('tools_materials', task.get('tools', '')),
            "工作方法": task.get('work_method', task.get('method', '')),
            "劳动组织方式": task.get('labor_organization', task.get('organization', '')),
            "工作要求": task.get('work_requirements', task.get('requirement', ''))
        }
        sections.append(generate_vertical_table(table_data))
        sections.append("\n")
    
    # ==================== 四、归类、划分行动领域 ====================
    action_domains = data.get('action_domains', [])
    
    # 构建任务ID到任务名称的映射
    task_id_to_name = {}
    for task in typical_tasks:
        task_id = task.get('id', '')
        task_name = task.get('name', '')
        if task_id and task_name:
            task_id_to_name[task_id] = task_name
    
    # 验证数据一致性：行动领域必须覆盖所有典型任务
    validate_action_domains_coverage(typical_tasks, action_domains)
    
    sections.append("## 四、归类、划分行动领域\n")
    sections.append(f"### 表4-1 {major_name}行动领域表\n")
    if action_domains:
        headers = ["序号", "行动领域", "典型工作任务", "聚类原则"]
        rows = []
        for i, domain in enumerate(action_domains, 1):
            # 将任务ID转换为任务名称
            task_ids = domain.get('tasks', [])
            task_names = [task_id_to_name.get(tid, tid) for tid in task_ids]
            tasks_str = "、".join(task_names)
            rows.append([
                str(i),
                domain.get('name', ''),
                tasks_str,
                domain.get('clustering_principle', domain.get('principle', ''))
            ])
        sections.append(generate_markdown_table(headers, rows))
    sections.append("\n")
    
    # ==================== 五、行动领域描述与职业能力分析 ====================
    sections.append("## 五、行动领域描述与职业能力分析\n")
    
    # 表5-x: 行动领域分析表
    for i, domain in enumerate(action_domains, 1):
        domain_name = domain.get('name', f'行动领域{i}')
        sections.append(f"### 表5-{i} {domain_name}行动领域分析\n")
        
        skill_level = domain.get('skill_level', domain.get('level', '中级工'))
        
        task_ids = domain.get('tasks', [])
        task_names = [task_id_to_name.get(tid, tid) for tid in task_ids]
        task_desc = "、".join(task_names)
        
        abilities = domain.get('abilities', {})
        prof_abilities = abilities.get('professional', [])
        meth_abilities = abilities.get('methodological', abilities.get('method', []))
        soc_abilities = abilities.get('social', [])
        
        def extract_ability_names(ability_list):
            names = []
            for a in ability_list:
                if isinstance(a, dict):
                    names.append(a.get('name', ''))
                elif isinstance(a, str):
                    names.append(a)
            return "、".join(names) if names else ""
        
        ability_desc = extract_ability_names(prof_abilities)
        if meth_abilities:
            meth_desc = extract_ability_names(meth_abilities)
            if meth_desc:
                ability_desc = f"{ability_desc}；{meth_desc}" if ability_desc else meth_desc
        if soc_abilities:
            soc_desc = extract_ability_names(soc_abilities)
            if soc_desc:
                ability_desc = f"{ability_desc}；{soc_desc}" if ability_desc else soc_desc
        
        table_data = {
            "行动领域名称": domain_name,
            "典型工作任务描述": task_desc,
            "工作过程": "按照工作任务流程，完成相关工作内容",
            "工作与学习条件": "实训基地，配备必要的专业设备和工具",
            "能力描述": ability_desc,
            "能力等级": skill_level,
            "获得途径": "校内实训、企业实习"
        }
        sections.append(generate_vertical_table(table_data))
        sections.append("\n")
    
    # 表6: 行动领域职业能力分析汇总表
    sections.append("### 表6 行动领域职业能力分析汇总表\n")
    
    def format_abilities(ability_list):
        if not ability_list:
            return ""
        if isinstance(ability_list, str):
            return ability_list
        names = []
        for a in ability_list:
            if isinstance(a, dict):
                names.append(a.get('name', ''))
            elif isinstance(a, str):
                names.append(a)
        return "、".join(names)
    
    if action_domains:
        headers = ["行动领域", "专业能力", "方法能力", "社会能力", "行动成果"]
        rows = []
        for domain in action_domains:
            abilities = domain.get('abilities', {})
            rows.append([
                domain.get('name', ''),
                format_abilities(abilities.get('professional', [])),
                format_abilities(abilities.get('methodological', abilities.get('method', []))),
                format_abilities(abilities.get('social', [])),
                "完成相关工作任务，达到质量标准"
            ])
        sections.append(generate_markdown_table(headers, rows))
    sections.append("\n")
    
    # 表7: 职业能力一览表
    sections.append("### 表7 职业能力一览表\n")
    
    # 收集所有能力并保存编号映射，供表8使用
    ability_mapping = {"Z": [], "F": [], "S": []}
    
    if action_domains:
        # 收集所有能力
        all_professional = []
        all_method = []
        all_social = []
        for domain in action_domains:
            abilities = domain.get('abilities', {})
            prof = abilities.get('professional', [])
            meth = abilities.get('methodological', abilities.get('method', []))
            soc = abilities.get('social', [])
            
            # 支持字符串格式（旧格式）和数组格式（新标准）
            if isinstance(prof, str) and prof:
                all_professional.extend([p.strip() for p in prof.split('、') if p.strip()])
            elif isinstance(prof, list):
                for p in prof:
                    if isinstance(p, dict):
                        all_professional.append(p.get('name', p.get('description', '')))
                    elif isinstance(p, str):
                        all_professional.append(p)
            
            if isinstance(meth, str) and meth:
                all_method.extend([m.strip() for m in meth.split('、') if m.strip()])
            elif isinstance(meth, list):
                for m in meth:
                    if isinstance(m, dict):
                        all_method.append(m.get('name', m.get('description', '')))
                    elif isinstance(m, str):
                        all_method.append(m)
            
            if isinstance(soc, str) and soc:
                all_social.extend([s.strip() for s in soc.split('、') if s.strip()])
            elif isinstance(soc, list):
                for s in soc:
                    if isinstance(s, dict):
                        all_social.append(s.get('name', s.get('description', '')))
                    elif isinstance(s, str):
                        all_social.append(s)
        
        # 去重
        all_professional = list(dict.fromkeys(all_professional))
        all_method = list(dict.fromkeys(all_method))
        all_social = list(dict.fromkeys(all_social))
        
        # 保存能力编号映射（供表8使用）
        for i, ability in enumerate(all_professional, 1):
            ability_mapping["Z"].append({"code": f"Z{i:03d}", "name": ability})
        for i, ability in enumerate(all_method, 1):
            ability_mapping["F"].append({"code": f"F{i:03d}", "name": ability})
        for i, ability in enumerate(all_social, 1):
            ability_mapping["S"].append({"code": f"S{i:03d}", "name": ability})
        
        # 生成带序号的三列表格
        max_len = max(len(all_professional), len(all_method), len(all_social))
        headers = ["序号", "Z 专业能力", "F 方法能力", "S 社会能力"]
        rows = []
        for i in range(max_len):
            prof = all_professional[i] if i < len(all_professional) else ''
            meth = all_method[i] if i < len(all_method) else ''
            soc = all_social[i] if i < len(all_social) else ''
            prof_display = f"Z{i+1:03d} {prof}" if prof else ''
            meth_display = f"F{i+1:03d} {meth}" if meth else ''
            soc_display = f"S{i+1:03d} {soc}" if soc else ''
            rows.append([str(i + 1), prof_display, meth_display, soc_display])
        sections.append(generate_markdown_table(headers, rows))
    sections.append("\n")
    
    sections.append("### 表8 职业能力解构表\n")
    
    all_abilities = (
        ability_mapping["Z"] + 
        ability_mapping["F"] + 
        ability_mapping["S"]
    )
    
    if all_abilities:
        headers = ["能力编号和名称", "知识", "技术技能", "职业素养", "主要评价指标"]
        rows = []
        
        for item in all_abilities:
            code = item["code"]
            name = item["name"]
            
            if code.startswith("Z"):
                quality = "规范意识、质量意识、创新意识"
            elif code.startswith("F"):
                quality = "逻辑思维、方法论意识、持续改进意识"
            else:
                quality = "团队协作、沟通能力、责任意识"
            
            rows.append([
                f"{code} {name}",
                f"{name}相关理论知识",
                f"{name}操作技能",
                quality,
                f"能独立完成{name}相关任务"
            ])
        sections.append(generate_markdown_table(headers, rows))
    sections.append("\n")
    
    # ==================== 六、学习领域分析 ====================
    sections.append("## 六、学习领域分析\n")
    sections.append("### 表9 学习领域表\n")
    
    learning_domains = data.get('learning_domains', [])
    if learning_domains:
        # 构建行动领域ID到名称的映射
        domain_id_to_name = {domain.get('id', ''): domain.get('name', '') for domain in action_domains}
        
        headers = ["序号", "学习领域", "对应的行动领域", "典型工作任务", "参考学时"]
        rows = []
        for i, course in enumerate(learning_domains, 1):
            related_domain_id = course.get('related_action_domain', course.get('action_domain', ''))
            domain_tasks = ""
            for domain in action_domains:
                if domain.get('id', '') == related_domain_id:
                    task_ids = domain.get('tasks', [])
                    domain_tasks = "、".join([task_id_to_name.get(tid, tid) for tid in task_ids])
                    break
            rows.append([
                str(i),
                course.get('name', ''),
                domain_id_to_name.get(related_domain_id, related_domain_id),
                domain_tasks,
                str(course.get('reference_hours', course.get('hours', 64)))
            ])
        sections.append(generate_markdown_table(headers, rows))
    sections.append("\n")
    
    # 学习领域描述表（纵向表格）
    for i, course in enumerate(learning_domains, 1):
        course_name = course.get('name', f'课程{i}')
        sections.append(f"### 表10-{i:02d} {course_name}学习领域描述表\n")
        
        def format_list_field(value):
            if isinstance(value, list):
                return '、'.join(str(v) for v in value)
            return str(value) if value else ''
        
        table_data = {
            "学习领域编号与名称": f"C{i:02d} {course_name}",
            "参考学时": str(course.get('reference_hours', course.get('hours', 64))),
            "学期安排": f"第{i}学期",
            "学习目标（能力描述）": course.get('learning_objective', course.get('objectives', '')),
            "学习内容（内容描述）": course.get('learning_content', course.get('content', '')),
            "教学方法": format_list_field(course.get('methods', '')),
            "评价方式": format_list_field(course.get('assessment', ''))
        }
        sections.append(generate_vertical_table(table_data))
        sections.append("\n")
    
    # ==================== 七、学习情境设计 ====================
    sections.append("## 七、学习情境设计\n")
    
    learning_situations = data.get('learning_situations', [])
    
    for i, domain in enumerate(learning_domains, 1):
        domain_name = domain.get('name', f'学习领域{i}')
        domain_id = domain.get('id', f'LD{i:03d}')
        sections.append(f"### 表11-{i:02d} {domain_name}学习情境表\n")
        
        situations = [s for s in learning_situations if s.get('domain_id', '') == domain_id]
        
        if situations:
            headers = ["学习情境名称", "参考学时", "学习目标", "学习内容", "教学方式"]
            rows = []
            for sit in situations:
                rows.append([
                    sit.get('name', ''),
                    str(sit.get('hours', 16)),
                    sit.get('learning_objective', sit.get('objectives', '')),
                    sit.get('learning_content', sit.get('content', '')),
                    sit.get('teaching_method', sit.get('method', ''))
                ])
            sections.append(generate_markdown_table(headers, rows))
        else:
            sections.append("*暂无学习情境设计*\n")
        sections.append("\n")
    
    # ==================== 附录 ====================
    sections.append("## 附录\n")
    sections.append("### 职业面向\n")
    
    # 从major_info获取职业面向描述
    career_orientation = major_info.get('career_orientation', '')
    if career_orientation:
        sections.append(f"{career_orientation}\n\n")
    
    # 展示职业列表
    occupations = data.get('occupations', [])
    if occupations:
        sections.append("**职业列表**：\n")
        for occ in occupations:
            occ_name = occ.get('name', '')
            occ_code = occ.get('code', '')
            if occ_name:
                sections.append(f"- {occ_name}（{occ_code}）\n")
        sections.append("\n")
    
    # 展示国际职业代码映射
    occupation_mapping = data.get('occupation_mapping', [])
    if occupation_mapping:
        sections.append("\n**国际职业代码映射**：\n\n")
        headers = ["中国职业代码", "职业名称", "ISCO代码", "O*NET代码"]
        rows = []
        for mapping in occupation_mapping:
            rows.append([
                mapping.get('china_code', ''),
                mapping.get('china_name', ''),
                mapping.get('isco_code', ''),
                mapping.get('onet_code', '')
            ])
        sections.append(generate_markdown_table(headers, rows))
    
    # 新增：国际职业数据详情
    international_details = data.get('international_details', {})
    if international_details and international_details.get('occupations'):
        sections.append("\n### 国际职业数据参考\n")
        sections.append("*以下数据来源于 ESCO 和 O*NET，供工作任务分析和能力分析参考*\n")
        
        for occ in international_details['occupations']:
            china_name = occ.get('china_name', '')
            onet_code = occ.get('onet_code', '')
            isco_code = occ.get('isco_code', '')
            
            sections.append(f"\n#### {china_name}\n")
            sections.append(f"- **ISCO代码**: {isco_code}")
            sections.append(f"- **O*NET代码**: {onet_code}\n")
            
            # 关键技能
            key_skills = occ.get('key_skills', [])
            if key_skills:
                sections.append("**关键技能参考**：")
                sections.append("、".join(key_skills[:8]) + "\n")
            
            # 关键任务
            key_tasks = occ.get('key_tasks', [])
            if key_tasks:
                sections.append("**主要任务参考**：")
                for task in key_tasks[:5]:
                    sections.append(f"  - {task}")
                sections.append("")
            
            # 知识领域
            key_knowledge = occ.get('key_knowledge', [])
            if key_knowledge:
                sections.append("**知识领域参考**：" + "、".join(key_knowledge) + "\n")
        
        sections.append(f"\n*详细数据文件：{international_details.get('data_files', {}).get('mapping', '')}*\n")
    
    sections.append("\n### 数据来源\n")
    sections.append("- 专业教学标准：教育部职业教育专业教学标准")
    sections.append("- 职业大典：中国职业分类大典（2022版）")
    sections.append("- 国际数据：ESCO、O*NET\n")
    
    sections.append("---\n")
    sections.append("*本报告由职业分析 Skill 自动生成*\n")
    
    return "\n".join(sections)


def main():
    parser = argparse.ArgumentParser(description='生成职业分析 Markdown 报告')
    parser.add_argument('--data', '-d', required=True, help='分析数据 JSON 文件路径')
    parser.add_argument('--template', '-t', help='Markdown 模板文件路径（可选）')
    parser.add_argument('--output', '-o', required=True, help='输出 Markdown 文件路径')
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    data_path = project_root / args.data if not Path(args.data).is_absolute() else Path(args.data)
    output_path = project_root / args.output if not Path(args.output).is_absolute() else Path(args.output)
    
    print(f"[INFO] 加载数据: {data_path}")
    
    data = load_analysis_data(data_path)
    
    # 校验数据结构
    validate_data_structure(data)
    
    print(f"[INFO] 生成 Markdown 报告...")
    markdown_content = generate_report(data)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    print(f"[OK] 报告已保存到: {output_path}")
    print(f"\n转换为 Word 文档命令:")
    print(f"  pandoc {args.output} --reference-doc=references/reference.docx -o output/report.docx")


if __name__ == '__main__':
    main()