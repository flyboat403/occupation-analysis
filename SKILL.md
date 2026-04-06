---
name: occupation-analysis
version: 1.0.0
description: 职业教育专业建设辅助工具，按工作过程系统化方法生成七部分结构的职业分析报告，支持中职、高职、职教本科三个层次；当用户需要职业分析、工作任务分析、典型工作任务提取、行动领域划分、学习领域转换或课程开发时使用
dependency:
  python:
    - requests==2.31.0
    - python-dotenv==1.0.0
    - pypdf==3.17.0
    - python-docx==1.2.0
  system:
    - sudo apt-get update && sudo apt-get install -y pandoc
---

# 职业教育职业分析 Skill

## 概述

本skill用于职业教育专业建设中的职业分析环节，按照工作过程系统化课程开发方法，自动生成规范的职业分析文档。

**适用范围**：
- 中等职业教育（中职）
- 高等职业教育（高职/专科）
- 职业教育本科（职教本科）

---

## 分析前思维框架

在开始职业分析前，必须理解以下关键决策点：

### 1. 层次适配原则

**核心问题**：这个教育层次的职业面向和能力深度是什么？

| 层次 | 职业面向 | 能力要求 | 课程特征 |
|------|----------|----------|----------|
| 中职 | 操作岗位 | 技能操作为主 | 操作技能、规范执行 |
| 高职 | 技术岗位 | 技术应用能力 | 技术应用、问题诊断 |
| 职教本科 | 管理/技术岗 | 技术创新与管理 | 综合应用、系统优化 |

**判断方法**：查看专业教学标准中的"培养目标"关键词：
- "熟练操作"、"掌握...技能" → 中职深度
- "技术应用"、"故障诊断" → 高职深度
- "系统设计"、"项目管理" → 职教本科深度

### 2. 数据源选择决策树

```
需要职业数据？
├─ 职业定义和主要任务 → 必须用中国职业大典（本地文件）
├─ 技能和能力补充 → 推荐 ESCO/O*NET（本地文档）
└─ 工具和工作环境 → 可选 O*NET Tools & Technology
```

**数据源必要性判断**：

| 场景 | 中国职业大典 | ESCO | O*NET |
|------|-------------|------|-------|
| 职业定义提取 | 必须 | 补充 | 补充 |
| 工作任务分析 | 必须 | 补充 | 补充 |
| 技能要求分析 | 参考 | 推荐 | 推荐 |
| 工作情境分析 | 参考 | 参考 | 推荐 |
| 工具技术分析 | 不需要 | 不需要 | 推荐 |

### 3. Token 优化策略

**核心问题**：如何在不超出上下文限制的情况下完成任务？

```
完整职业大典 = ~136K tokens（超出大多数模型限制）

分块策略：
├─ 按职业代码第一位选择大类文件
├─ 第6大类最大（~62K tokens）- 生产制造类职业
├─ 第2大类次之（~36K tokens）- 专业技术人员
└─ 其他大类均 <30K tokens
```

**关键判断**：
- 如果目标职业代码以 `6-` 开头 → 加载第6大类
- 如果需要多个职业 → 检查是否属于同一大类，合并加载

### 4. 课程转换逻辑

**行动领域 → 学习领域 的转换依据**：

1. **工作对象相似性**：处理相同或相关对象的任务归为一类
2. **任务难度梯度**：从简单到复杂，符合学习认知规律
3. **工作逻辑顺序**：按实际工作流程排列
4. **学时合理性**：每个学习领域参考学时 48-96 学时为宜

---

## NEVER Do

### Token 和性能

- **NEVER** 一次性加载完整职业大典文件（`职业大典2022.md`，~136K tokens）
  - 原因：会耗尽上下文窗口，导致后续步骤失败
  - 正确做法：使用 `OccupationDictionaryLoader` 按需加载对应大类

- **NEVER** 在同一会话中重复加载同一大类文件
  - 原因：浪费 tokens，`OccupationDictionaryLoader` 已实现缓存
  - 正确做法：复用已加载的内容

### 数据处理

- **NEVER** 使用简单字符串匹配来对应中国职业代码与国际标准
  - 原因：不同分类体系命名差异大（如"汽车维修工" vs "Motor Vehicle Mechanic"）
  - 正确做法：由大模型进行语义理解和推断

- **NEVER** 忽略教育层次差异，为所有层次生成相同深度的内容
  - 原因：中职侧重操作，本科侧重管理，内容深度必须匹配
  - 正确做法：参考"层次适配原则"调整能力描述深度

- **NEVER** 在用户确认职业信息前就开始数据检索
  - 原因：可能检索错误的专业或层次
  - 正确做法：先展示确认面板，用户确认后再执行

- **NEVER** 接受用户提出的非职业大典中的职业
  - 原因：非职业大典职业无法获取标准定义和任务
  - 正确做法：要求用户重新提出职业大典中存在的职业

### 流程

- **NEVER** 跳过步骤0预检验证
  - 原因：数据文件缺失会导致后续所有步骤失败
  - 正确做法：每次执行前运行预检脚本

- **NEVER** 跳过用户确认环节
  - 原因：职业信息可能有误或不完整，用户可能需要修改、删除或新增职业
  - 正确做法：步骤3必须使用 `question` 工具展示确认面板，**等待用户回复**后才能继续步骤4
  - ⚠️ 即使执行"全流程测试"也必须等待用户确认

- **NEVER** 忽略本地文档缺失警告
  - 原因：缺失文档会影响分析完整性
  - 正确做法：展示缺失列表，用户确认后继续

- **NEVER** 使用非职业大典中的职业
  - 原因：无法获取标准职业定义和任务
  - 正确做法：要求用户提供职业大典中存在的职业

---

## 边缘场景处理

> **详细场景处理方法**: 详见 [references/troubleshooting.md](references/troubleshooting.md)

---

## 工作流程

### 架构概览

本Skill采用**分层架构**，明确区分Python脚本层和大模型处理层：

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        Python脚本层（数据获取与格式化）                            │
│                                                                                 │
│  职责：精确匹配、文件读写、API调用、格式转换                                       │
│  特点：不调用大模型API，执行确定性逻辑                                            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼ JSON数据
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        大模型处理层（语义分析与生成）                              │
│                                                                                 │
│  职责：语义理解、创造性生成、质量校验                                             │
│  特点：由执行本Skill的Agent（当前大模型）完成，不单独调用API                       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 完整工作流程

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ 阶段一：数据获取（Python脚本 + 大模型）                                            │
├──────────────────────────────────────────────────────────────────────────────────┤
│  步骤1: 检索专业教学标准    → search_major.py      → major_info.json             │
│                                                                                  │
│  步骤2: 获取职业信息（大模型处理）                                                 │
│         - 加载职业大典文档（class_*.md）                                          │
│         - 语义解析职业面向字段                                                     │
│         - 输出：职业代码、名称、定义、任务                                         │
│         → occupation_info.json                                                   │
│                                                                                  │
│  步骤3: 【新增】用户确认环节（⚠️ 强制性暂停点）                                    │
│         - 展示提取的职业信息（批量展示）                                           │
│         - 使用 question 工具展示确认选项                                          │
│         - ⚠️ 必须等待用户回复（确认/修改/删除）                                     │
│         - 若用户提出新职业不在职业大典 → 要求重新提出                              │
│         → 确认后的occupation_info.json                                            │
│                                                                                  │
│  步骤4: 【新增】Agent/大模型推断ESCO和O*NET映射                                   │
│         - 对每个职业单独进行映射推断                                              │
│         - 根据职业定义和任务推断英文名称和代码                                     │
│         - 输出：ESCO名称+代码、O*NET名称+代码                                     │
│         → occupation_mapping_info.json                                           │
│                                                                                  │
│  步骤5: 【修改】从本地文档获取详细内容                                             │
│         - 查询 assets/esco_detail_md/（ESCO文档）                                │
│         - 查询 assets/onet_details_md/（O*NET文档）                              │
│         - 若文档缺失 → 警告并等待用户确认后继续                                   │
│         → international_data.json                                                │
│                                                                                  │
│  步骤6: 整合基础数据        → 手动合并              → base_data.json              │
└──────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ 阶段二：语义分析与生成（大模型自身）                                                │
├──────────────────────────────────────────────────────────────────────────────────┤
│  步骤7: 职业面向语义解析                                                          │
│         - 从职业面向字段提取职业名称和岗位名称                                     │
│         - 生成分岗位的工作任务列表                                                 │
│                                                                                  │
│  步骤8: 工作任务分析                                                              │
│         - 为每个工作任务生成：工作对象、工具/材料、工作方法、劳动组织              │
│         - 根据教育层次适配能力描述深度                                             │
│                                                                                  │
│  步骤9: 典型工作任务确定                                                          │
│         - 归类相似工作任务                                                        │
│         - 确定任务难度等级                                                        │
│         - 生成典型工作任务汇总表                                                  │
│                                                                                  │
│  步骤10: 行动领域划分                                                             │
│         - 按工作对象相似性、任务难度梯度、工作逻辑顺序聚类                         │
│         - 生成行动领域表和聚类原则                                                │
│         - 设定能力等级递进（初级→中级→高级）                                      │
│                                                                                  │
│  步骤11: 职业能力分析                                                             │
│         - 推导专业能力、方法能力、社会能力                                        │
│         - 生成表6（汇总表）、表7（一览表）、表8（解构表）                          │
│         - 确保表7与表8能力编号和名称一致                                          │
│                                                                                  │
│  步骤12: 学习领域转换                                                             │
│         - 行动领域转换为学习领域                                                 │
│         - 设定参考学时（每领域48-96学时为宜）                                    │
│         - 生成学习目标和学习内容                                                 │
│                                                                                  │
│  步骤13: 学习情境设计                                                             │
│         - 为每个学习领域设计2-4个学习情境                                        │
│         - 生成学时、教学方式、评价方式                                           │
│                                                                                  │
│  步骤14: 输出结构化分析数据 → analysis_data.json                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ 阶段三：格式化输出（Python脚本）                                                   │
├──────────────────────────────────────────────────────────────────────────────────┤
│  步骤15: 生成Markdown报告   → generate_report.py    → report.md                  │
│           - 将analysis_data.json转换为Markdown格式                                │
│           - 按七部分结构组织表格                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ 阶段四：自我校正（大模型自身）                                                      │
├──────────────────────────────────────────────────────────────────────────────────┤
│  步骤16: 质量校验                                                                │
│          - 验证表1岗位与表2对应岗位一致                                           │
│          - 验证表4覆盖表2所有典型任务                                             │
│          - 验证能力动词符合教育层次要求                                           │
│          - 验证表格编号连续（表1→表11）                                           │
│          - 验证表7与表8能力编号一致                                               │
│                                                                                  │
│  步骤17: 问题修复（如有）                                                         │
│          - 修复发现的问题                                                         │
│          - 重新生成analysis_data.json                                            │
│          - 最多3次修复循环                                                        │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 职责划分速查表

| 步骤 | 执行者 | 任务类型 | 输出 |
|------|--------|----------|------|
| 1 | Python脚本 | 数据获取 | major_info.json |
| **2** | **大模型** | 文档解析、职业信息提取 | occupation_info.json |
| **3** | **大模型+用户** | 用户确认 | 确认后的occupation_info.json |
| **4** | **大模型** | ESCO/O*NET映射推断 | occupation_mapping_info.json |
| 5 | Python脚本 | 本地文档查询 | international_data.json |
| 6 | Python脚本 | 数据合并 | base_data.json |
| 7-14 | **大模型自身** | 语义分析与生成 | analysis_data.json |
| 15 | Python脚本 | 格式化输出 | report.md |
| 16-17 | **大模型自身** | 质量校验与修复 | 最终报告 |

###  重要原则

1. **Python脚本不做语义分析**：脚本只负责精确匹配和格式转换
2. **大模型不调用外部API**：所有语义分析由执行Skill的Agent完成
3. **数据驱动**：每个阶段的输出是下一阶段的输入
4. **结构化传递**：使用JSON格式传递数据，确保数据完整性
5. **用户确认必需**：步骤3和步骤5均需用户确认

### 步骤0：预检验证（必须执行）

> **MANDATORY - READ REFERENCE FILE**: 在开始工作流程前，建议阅读
> [`references/precheck_guide.md`](references/precheck_guide.md)
> 获取完整的环境检查清单和预检脚本。

**快速检查命令**：
```bash
# 检查核心数据文件
python -c "from pathlib import Path; files=['assets/moe_pdfs_final.json', 'assets/esco_details_md', 'assets/onet_details_md']; [print('[OK]' if Path(f).exists() else '[X]', f) for f in files]"
```

**核心检查项**：Python 3.8+、依赖安装、数据文件（职业大典、ESCO、O*NET本地文档）。

## 数据源配置

### 本地数据文件

所有数据文件位于 `assets/` 目录下：

| 文件 | 路径 | 说明 |
|------|------|------|
| 专业教学标准 | `assets/moe_pdfs_final.json` | 教育部发布的专业教学标准索引 |
| 专业简介 | `assets/moe_pdfs_new.json` | 备选数据源 |
| 职业大典 | `assets/occupation_dictionary_split/` | 中国职业分类大典（2022版，按大类拆分） |
| ESCO文档 | `assets/esco_detail_md/` | ESCO职业详细文档（约3000+个MD文件） |
| O*NET文档 | `assets/onet_details_md/` | O*NET职业详细文档（894个MD文件） |



### 职业大典

**方案**：将完整职业大典（~136K tokens）按6个大类拆分为小文件，按需加载

| 大类 | 文件名 | Token数 |
|------|--------|---------|
| 第1大类 | `class_1_党的机关...负责人.md` | ~5K |
| 第2大类 | `class_2_专业技术人员.md` | ~36K |
| 第3大类 | `class_3_办事人员...md` | ~3K |
| 第4大类 | `class_4_社会生产服务...md` | ~27K |
| 第5大类 | `class_5_农林牧渔...md` | ~5K |
| 第6大类 | `class_6_生产制造...md` | ~62K |
| 第7大类 | `class_7_2025年新增职业.md` | ~62K |

**使用方法**：
```python
from scripts.occupation_dict_loader import OccupationDictionaryLoader

loader = OccupationDictionaryLoader()
# 根据职业代码自动加载对应大类
content = loader.load_by_occupation_code('6-22-02')  # 只加载第6大类
```

### ESCO本地文档

**位置**：`assets/esco_details_md/`

**文件命名**：`{ISCO代码}.{序号}.md`（如 `7231.1.md`、`7231.2.md`）

**特点**：
- 一个ISCO代码可能对应多个文件（不同的具体职业）
- 例如 ISCO代码 `7231`（Motor vehicle mechanics and repairers）对应多个文件：
  - `7231.1.md` - automotive brake technician
  - `7231.2.md` - motorcycle technician
  - 等等...

**内容结构**：
```markdown
# automotive brake technician

## Basic Information
| Field | Value |
|-------|-------|
| **Title** | automotive brake technician |
| **ISCO Code** | 7231.1 |

## Description
Automotive brake technicians inspect, maintain, diagnose...

## Essential Skills
### Skills
- wear appropriate protective gear
- troubleshoot
...

## Essential Knowledge
- automotive diagnostic equipment
- mechanics of motor vehicles
...
```

**查询方式**：
1. 根据大模型推断的ISCO代码（如 `7231`）查找所有匹配文件
2. 合并所有匹配文件的内容进行分析

### O*NET本地文档

**位置**：`assets/onet_details_md/`

**文件命名**：O*NET代码.md（如 `49-3023.00.md`）

**内容结构**：
```markdown
# 49-3023.00 - Automotive Service Technicians and Mechanics

## Summary
Diagnose, adjust, repair, or overhaul automotive vehicles.

## Tasks
| Importance | Category | Task |
|------------|----------|------|
| 91 | Core | Inspect vehicles for damage... |

## Worker Requirements
### Skills
### Knowledge
### Abilities
```

**查询方式**：
1. 根据大模型推断的O*NET代码查找文件
2. 精确匹配代码（如 `49-3023.00`）

## 实施步骤

---

## 阶段一：数据获取（Python脚本执行）

> 本阶段所有步骤由Python脚本完成，Agent只需调用脚本并读取输出。

### 步骤1：检索专业教学标准

> **详细执行命令和脚本逻辑详见**：[references/workflow_details.md](references/workflow_details.md) 步骤1

**任务**：从专业教学标准数据源检索专业信息。

**执行命令**：
```bash
python scripts/search_major.py --major "专业名称" --level "教育层次" --output temp/major_info.json
```

**输出**：`major_info.json`，包含专业代码、名称、职业面向、培养目标等字段。

### 步骤2：获取职业信息（大模型处理）

> **本步骤由执行本Skill的Agent（大模型）完成，不使用脚本**
> 
> **详细流程和输出格式详见**：[references/workflow_details.md](references/workflow_details.md) 步骤2

**任务**：
1. 加载对应的职业大典大类文件（根据职业代码首位）
2. 从职业面向字段提取职业名称，在职业大典中查找匹配条目
3. 提取职业代码、定义、任务

**输出**：`occupation_info.json`，包含 `occupations` 和 `jobs` 数组。

### 步骤3：用户确认环节

> **本步骤由执行本Skill的Agent（大模型）完成**
> 
> **确认面板示例和处理方式详见**：[references/workflow_details.md](references/workflow_details.md) 步骤3

---

> ⚠️ **MANDATORY - 必须等待用户回复**
> 
> 本步骤是**强制性暂停点**。Agent必须：
> 1. 展示提取的职业信息表格
> 2. 使用 `question` 工具展示确认选项
> 3. **等待用户回复**（确认/修改/删除）
> 4. 用户明确回复后才能继续步骤4
>
> **禁止行为**：
> - ❌ 展示信息后直接继续执行步骤4
> - ❌ 以"结果显而易见"为由跳过确认
> - ❌ 以"全流程测试"为由跳过确认
>
> **正确示例**：
> ```
> 已提取职业信息：
> | 序号 | 职业大典职业 | 代码 | 匹配来源 |
> |------|-------------|------|----------|
> | 1 | 数字媒体艺术专业人员 | 2-09-06-07 | 虚拟现实产品设计师 |
> ...
> 
> 请确认以上职业信息是否正确？
> [question工具展示选项：确认继续 / 需要修改 / 删除某项]
> ```

---

**任务**：展示提取的职业信息，等待用户确认。用户可确认、修改或删除职业。

**重要约束**：若用户新增职业，该职业必须在职业大典中存在。

**输出**：确认后的 `occupation_info.json`。

### 步骤4：Agent/大模型推断ESCO和O*NET映射

> **本步骤由执行本Skill的Agent（大模型）完成**
> 
> **推断提示词模板和输出格式详见**：[references/workflow_details.md](references/workflow_details.md) 步骤4

**任务**：
1. 分析职业定义和工作任务
2. 语义匹配ESCO职业（英文名称+4位ISCO代码）
3. 语义匹配O*NET职业（英文名称+O*NET代码）
4. 评估映射置信度

**输出格式规范**：[references/occupation_mapping_template.json](references/occupation_mapping_template.json)

**输出**：`occupation_mapping_info.json`，包含 `mapping_results` 数组。

### 步骤5：从本地文档获取详细内容

> 使用Python脚本查询本地ESCO和O*NET文档。
> 
> **详细查询逻辑和文档缺失处理详见**：[references/workflow_details.md](references/workflow_details.md) 步骤5

**执行命令**：
```bash
python scripts/fetch_local.py \
  --mapping temp/occupation_mapping_info.json \
  --output temp/international_data.json
```

**脚本行为**：
- 根据ESCO代码查询 `assets/esco_details_md/` 目录
- 根据O*NET代码查询 `assets/onet_details_md/` 目录
- 若文档缺失则展示警告，等待用户确认后继续

**输出**：`international_data.json`，包含ESCO和O*NET职业详细信息。

### 步骤6：整合基础数据

将以上JSON文件合并为 `base_data.json`，供大模型分析使用。

```json
{
  "major_info": { ... },
  "occupation_info": { ... },
  "occupation_mapping_info": { ... },
  "international_data": { ... }
}
```

---

## 阶段二：语义分析与生成（大模型自身执行）

> Agent/大模型基于阶段一获取的数据，进行语义理解、分析推理、创造性生成。

### 步骤7：职业面向语义解析

**输入**：`career_orientation` 字段（如"面向数字媒体艺术专业人员等职业，摄影摄像、数字影音剪辑、界面设计等岗位。"）

**任务**：
1. 提取职业名称列表
2. 提取岗位名称列表
3. 语义匹配职业大典中的职业代码
4. 生成分岗位的工作任务列表

**输出示例**：
```json
{
  "occupations": [
    {"name": "数字媒体艺术专业人员", "code": "2-09-06-07"}
  ],
  "jobs": [
    {"name": "摄影摄像", "related_occupation": "2-09-06-07"},
    {"name": "数字影音剪辑", "related_occupation": "2-09-06-07"},
    {"name": "界面设计", "related_occupation": "2-09-06-07"}
  ]
}
```

### 步骤8：工作任务分析

**教育层次适配原则**：

| 层次 | 能力动词 | 不建议使用的动词 |
|------|----------|----------|
| 中职 | 操作、执行、完成、使用、识别、检测 | 设计、优化、创新、管理、分析、诊断 |
| 高职 | 检测、诊断、分析、维护、维修、优化、改进 | 研发、创新、管理 |
| 职教本科 | 设计、优化、管理、创新 | - |

**任务**：
为每个岗位的工作任务生成完整分析，字段包括：工作任务、工作内容、工作对象、工具/材料、工作方法、劳动组织、工作要求、职业能力、工作条件、职业类证书。

### 步骤9：典型工作任务确定

**任务**：
1. 归类相似工作任务
2. 确定任务难度等级（简单/中等/复杂）
3. 生成典型工作任务汇总表

**输出**：`typical_tasks` 数组，包含 `name`、`related_job`、`difficulty`、`description` 字段。

### 步骤10：行动领域划分

> **MANDATORY - READ REFERENCE FILE**: 开始前必须阅读
> [`references/work_process_method.md`](references/work_process_method.md) 
> 的**2.1 行动领域描述通用模板**章节。

**Do NOT load**: `troubleshooting.md`、`precheck_guide.md`（此步骤不需要）

**聚类原则**：
1. **工作对象相似性**：处理相同或相关对象的任务归为一类
2. **任务难度梯度**：从简单到复杂，符合学习认知规律
3. **工作逻辑顺序**：按实际工作流程排列

**任务**：
1. 将典型任务聚类为3-6个行动领域
2. 为每个领域设定能力等级（初级→中级→高级）
3. 使用模板格式描述每个行动领域

### 步骤11：职业能力分析

**能力分类与编号规则**：
- **Z. 专业能力** (ZhuanYe)：专业知识和技能，编号格式 Z001, Z002...
- **F. 方法能力** (FangFa)：工作方法和学习能力，编号格式 F001, F002...
- **S. 社会能力** (SheHui)：沟通协作和职业道德，编号格式 S001, S002...

**任务**：
1. 为每个行动领域推导专业能力、方法能力、社会能力
2. 生成表6（汇总表）、表7（一览表）、表8（解构表）
3. **确保表7与表8能力编号和名称完全一致**

**关键约束**：
- 表7列标题必须使用 "Z 专业能力 | F 方法能力 | S 社会能力"
- 表7每个能力单元格必须包含编号（如 "Z001 能力名称"）
- 表8能力编号必须与表7一一对应
- 编号前缀：Z=专业能力，F=方法能力，S=社会能力

### 步骤12：学习领域转换

> **MANDATORY - READ REFERENCE FILE**: 开始前必须阅读
> [`references/work_process_method.md`](references/work_process_method.md) 
> 的**2.2 学习领域描述通用模板**章节。

**Do NOT load**: `troubleshooting.md`、`precheck_guide.md`（此步骤不需要）

**转换原则**：
1. 每个行动领域对应1-2个学习领域
2. 参考学时：每领域48-96学时
3. 课程深度匹配教育层次

**任务**：
1. 行动领域转换为学习领域
2. 设定参考学时
3. 使用模板格式生成学习目标和学习内容

### 步骤13：学习情境设计

> **MANDATORY - READ REFERENCE FILE**: 开始前必须阅读
> [`references/work_process_method.md`](references/work_process_method.md) 
> 的**2.3 学习情境描述通用模板**章节。

**Do NOT load**: `troubleshooting.md`、`precheck_guide.md`（此步骤不需要）

**任务**：
为每个学习领域设计2-4个学习情境，包含：情境名称、参考学时、学习目标、学习内容、教学方式、评价方式。

### 步骤14：输出结构化分析数据

将步骤7-13的分析结果整合为完整的 `analysis_data.json`。

> **MANDATORY - READ REFERENCE FILE**: 完整格式规范详见
> [references/analysis_data_template.json](references/analysis_data_template.json)

**必需字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `major_info` | Object | 专业基本信息 |
| `occupations` | Array | 职业列表 |
| `jobs` | Array | 岗位列表 |
| `typical_tasks` | Array | 典型工作任务列表 |
| `action_domains` | Array | 行动领域列表（含能力分析） |
| `abilities` | Object | 三类能力汇总（professional/methodological/social） |
| `learning_domains` | Array | 学习领域列表 |
| `learning_situations` | Array | 学习情境列表 |
| `metadata` | Object | 元数据（教育层次、日期等） |

**⚠️ 子字段约束（必须包含，否则报告生成失败）**：

| 父字段 | 必需子字段 | 影响 |
|--------|-----------|------|
| `action_domains[i]` | `tasks` | 表4典型任务覆盖验证失败 |
| `action_domains[i]` | `abilities` | 表6-8能力分析表格为空 |
| `learning_domains[i]` | `methods` | 表10教学方法为空 |
| `learning_domains[i]` | `assessment` | 表10评价方式为空 |

> **验证机制**：`generate_report.py` 会在数据结构不完整时抛出错误并终止，要求修复 `analysis_data.json`

---

## 阶段三：格式化输出（Python脚本执行）

### 步骤15：生成Markdown报告

```bash
python scripts/generate_report.py \
  --data temp/analysis_data.json \
  --output temp/report.md
```

脚本将 `analysis_data.json` 转换为七部分结构的Markdown报告。

**转换为Word**：
```bash
pandoc temp/report.md --reference-doc=references/reference.docx -o output/report.docx
```

---

## 阶段四：自我校正

### 步骤16：质量校验

Agent读取生成的报告，检查以下项：

| 检查项 | 严重程度 | 验证方法 |
|--------|----------|----------|
| 表1岗位与表2对应岗位一致 | 高 | 不得统称为单一岗位 |
| 表4覆盖表2所有典型任务 | 高 | 无遗漏任务 |
| 表7与表8能力编号一致 | 高 | 一一对应 |
| 能力动词符合教育层次要求 | 高 | 中职禁用"设计/优化/创新" |
| 能力等级有递进 | 中 | 不得全为同一等级 |
| 表格编号连续（表1→表11） | 中 | 无跳跃 |

### 步骤17：问题修复

如发现问题：
1. 修改 `analysis_data.json` 中对应字段
2. 重新执行步骤15生成报告
3. 重复步骤16验证
4. 最多3次修复循环

**修复后输出**：最终版 `report.md` 和 `report.docx`

---

## 执行检查清单

Agent执行本Skill时，按以下清单逐项确认：

### 阶段一检查
- [ ] 步骤1（Python脚本）：`major_info.json` 已生成，包含 `career_orientation`
- [ ] 步骤2（大模型）：已加载职业大典文档，输出职业信息
- [ ] 步骤3（大模型+用户）：已展示确认面板，**用户已回复确认**，`occupation_info.json` 已更新
- [ ] 步骤4（大模型）：ESCO/O*NET映射已完成
- [ ] 步骤5（Python脚本）：`international_data.json` 已生成（如有缺失已警告）
- [ ] 步骤6：基础数据已整合

### 阶段二检查（大模型自身）
- [ ] 步骤7：职业面向已解析
- [ ] 步骤8：每个工作任务已生成完整分析
- [ ] 步骤9：典型工作任务已确定
- [ ] 步骤10：行动领域已划分，能力等级已设定
- [ ] 步骤11：能力分析完成，表7/表8一致
- [ ] 步骤12：学习领域已转换
- [ ] 步骤13：学习情境已设计
- [ ] 步骤14：`analysis_data.json` 已生成

### 阶段三检查（Python脚本）
- [ ] 步骤15：`report.md` 已生成

### 阶段四检查（大模型自身）
- [ ] 步骤16：质量校验通过
- [ ] 步骤17：如有问题已修复

---

## 脚本工具

| 脚本 | 功能 | 核心命令 |
|------|------|----------|
| `scripts/search_major.py` | 专业教学标准检索（支持PDF解析） | `python scripts/search_major.py --major "专业名称" --level "层次"` |
| `scripts/pdf_parser.py` | PDF下载与解析 | `python scripts/pdf_parser.py --url "PDF_URL" --code "专业代码"` |
| `scripts/major_catalog_mapper.py` | 专业目录映射（xlsx→大类→MD文件） | `python scripts/major_catalog_mapper.py` |
| `scripts/fetch_local.py` | 本地ESCO/O*NET文档查询 | `python scripts/fetch_local.py --mapping mapping.json --output intl.json` |
| `scripts/integrate_data.py` | 多源数据整合 | `python scripts/integrate_data.py --major major.json --occupation-code "代码" --occupation-name "名称"` |
| `scripts/generate_report.py` | Markdown 报告生成（表7/表8一致） | `python scripts/generate_report.py --data analysis.json --output report.md` |
| `scripts/validate_report.py` | 报告验证与审校 | `python scripts/validate_report.py --report report.md --data analysis.json` |
| `scripts/occupation_dict_loader.py` | 职业大典分块加载 | `get_occupation_dictionary('6-22-02')` |

**关键参数**：
- `--output`: 输出文件路径
- `--no-pdf`: 跳过PDF解析（仅返回基本信息）
- `--cache-dir`: PDF缓存目录
- `--mapping`: 映射信息JSON文件（用于本地文档查询）

## 配置要求

### Python依赖

```bash
pip install requests python-dotenv pypandoc pypdf pdfplumber
```

**系统依赖**：pandoc（Word 转换必需）

### 本地数据文件

确保以下目录和文件存在：
- `assets/moe_pdfs_final.json` - 专业教学标准
- `assets/occupation_dictionary_split/` - 职业大典（按大类拆分）
- `assets/esco_detail_md/` - ESCO职业文档
- `assets/onet_details_md/` - O*NET职业文档

## 注意事项

| 类别 | 关键点 |
|------|--------|
| 数据完整性 | 专业教学标准用最新官方版、职业大典用2022 markdown版、ESCO/O*NET用本地文档 |
| 职业匹配 | 中国代码与国际标准需大模型语义推断、不同体系名称差异大、由大模型进行语义理解 |
| 本地化 | ESCO/O*NET数据为英文需翻译、注意专业术语准确性、可保留双语版本 |
| 层次适配 | 中职→操作技能、高职→技术应用、职教本科→管理优化 |
| 用户确认 | 步骤3必须让用户确认职业信息、步骤5文档缺失需用户确认后继续 |

## 故障排除

> **CONDITIONAL - READ IF NEEDED**: 如需详细的故障排除指南，请阅读
> [`references/troubleshooting.md`](references/troubleshooting.md)
> 获取常见问题、调试方法、数据完整性检查指南。

### 常见问题速查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 找不到专业教学标准 | 名称/代码错误 | 用代码检索、检查官方名称 |
| 本地文档缺失 | 文件名不匹配 | 检查ESCO英文名/O*NET代码、支持模糊匹配 |
| 表格格式错误 | 缺少分隔行 | 检查纵向表格格式 |
| 用户提出非职业大典职业 | 无法获取标准定义 | 要求用户重新提出职业大典中存在的职业 |

## 参考资料

| 文件 | 用途 | 加载时机 |
|------|------|----------|
| `references/precheck_guide.md` | 预检验证详细指南 | 步骤0 **按需** 加载 |
| `references/workflow_details.md` | 步骤1-6详细执行命令和输出格式 | 阶段一 **按需** 参考 |
| `references/work_process_method.md` | 行动领域/学习领域/学习情境描述模板 | 步骤10/12/13 **必须** 加载对应章节 |
| `references/analysis_data_template.json` | analysis_data.json 完整格式规范 | 步骤14 **必须** 参考 |
| `references/occupation_mapping_template.json` | 映射输出格式规范 | 步骤4 参考 |
| `references/report_template.md` | Markdown 报告模板（七部分结构） | 步骤15 **必须** 加载 |
| `references/troubleshooting.md` | 故障排除详细指南 | 遇到问题时 **按需** 加载 |
| `references/reference.docx` | Word 样式模板（自定义格式） | 步骤15 **可选** |

