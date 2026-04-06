# 职业分析报告生成工具

> 职业教育专业建设辅助工具 - 按工作过程系统化方法自动生成职业分析报告

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 📖 项目简介

本工具用于职业教育专业建设中的职业分析环节，按照**工作过程系统化课程开发方法**，自动生成规范的职业分析报告。支持三个教育层次：

- 🎓 **中等职业教育**（中职）
- 🎓 **高等职业教育**（高职/专科）
- 🎓 **职业教育本科**（职教本科）

### 核心功能

- ✅ 自动检索专业教学标准
- ✅ 智能提取职业大典信息
- ✅ ESCO/O*NET 国际职业映射
- ✅ 典型工作任务分析
- ✅ 行动领域划分
- ✅ 学习领域转换
- ✅ 学习情境设计
- ✅ 生成七部分结构报告（Markdown/Word）

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Pandoc（用于 Word 文档转换）

### 安装依赖

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Pandoc（Ubuntu/Debian）
sudo apt-get update && sudo apt-get install -y pandoc

# 安装 Pandoc（macOS）
brew install pandoc
```

### 基本使用

```bash
# 1. 检索专业教学标准
python scripts/search_major.py --major "服装设计与工艺" --level "中等职业教育" --output temp/major_info.json

# 2. 查询本地国际职业文档
python scripts/fetch_local.py --mapping temp/occupation_mapping_info.json --output temp/international_data.json

# 3. 生成分析报告
python scripts/generate_report.py --data temp/analysis_data.json --output temp/report.md

# 4. 转换为 Word 文档
pandoc temp/report.md --reference-doc=references/reference.docx -o output/report.docx

# 5. 验证报告质量
python scripts/validate_report.py --report temp/report.md --data temp/analysis_data.json
```

## 📁 项目结构

```
occupation-analysis/
├── SKILL.md                    # 技能定义（完整工作流程）
├── AGENTS.md                   # Agent 快速指南
├── requirements.txt            # Python 依赖
│
├── scripts/                    # 核心脚本
│   ├── search_major.py        # 专业教学标准检索
│   ├── fetch_local.py         # 本地文档查询
│   ├── generate_report.py     # 报告生成
│   ├── validate_report.py     # 报告验证
│   ├── occupation_dict_loader.py  # 职业大典分块加载
│   ├── integrate_data.py      # 数据整合
│   ├── pdf_parser.py          # PDF 解析
│   └── ...
│
├── references/                 # 参考文档和模板
│   ├── work_process_method.md     # 工作过程系统化方法
│   ├── analysis_data_template.json # 分析数据模板
│   ├── report_template.md     # 报告模板
│   ├── troubleshooting.md     # 故障排除指南
│   └── ...
│
├── assets/                     # 数据文件（2,830个）
│   ├── moe_pdfs_final.json    # 专业教学标准索引
│   ├── moe_pdfs_md/           # 专业教学标准 MD 文件
│   ├── occupation_dictionary_split/  # 中国职业大典（按大类拆分）
│   ├── esco_details_md/       # ESCO 职业文档（~3,000个）
│   └── onet_details_md/       # O*NET 职业文档（894个）
│
├── temp/                       # 临时输出（运行时生成）
└── output/                     # 最终报告（运行时生成）
```

## 📊 数据源说明

| 数据源 | 文件位置 | 说明 |
|--------|----------|------|
| **专业教学标准** | `assets/moe_pdfs_final.json` | 教育部发布的官方标准（172KB） |
| **中国职业大典** | `assets/occupation_dictionary_split/` | 2022版，按7个大类拆分 |
| **ESCO** | `assets/esco_details_md/` | 欧洲技能/能力/资格框架（~3,000个文件） |
| **O*NET** | `assets/onet_details_md/` | 美国职业信息网络（894个文件） |

## 📝 报告结构（七部分）

生成的职业分析报告包含以下七个部分：

| 部分 | 内容 | 对应表格 |
|------|------|----------|
| 一 | 职业面向分析 | 表1：工作任务分析表 |
| 二 | 典型工作任务确定 | 表2-3：典型工作任务汇总表 |
| 三 | 典型工作任务描述 | 表4-5：任务详细描述表 |
| 四 | 行动领域划分 | 表6：行动领域表 |
| 五 | 职业能力分析 | 表7-8：能力一览表和解构表 |
| 六 | 学习领域转换 | 表9-10：学习领域表 |
| 七 | 学习情境设计 | 表11：学习情境表 |

## 🔧 核心脚本说明

### search_major.py - 专业教学标准检索

```bash
python scripts/search_major.py --major "专业名称或代码" --level "教育层次" --output temp/major_info.json

# 参数说明
--major      专业名称或6位代码（如 "680402"）
--level      教育层次（中等职业教育/高等职业教育/职业教育本科）
--output     输出文件路径
--no-pdf     跳过PDF解析（仅返回基本信息）
```

### fetch_local.py - 本地文档查询

```bash
python scripts/fetch_local.py --mapping temp/occupation_mapping_info.json --output temp/international_data.json

# 根据 ESCO/O*NET 映射查询本地文档
```

### generate_report.py - 报告生成

```bash
python scripts/generate_report.py --data temp/analysis_data.json --output temp/report.md

# 将 analysis_data.json 转换为 Markdown 报告
```

### validate_report.py - 报告验证

```bash
python scripts/validate_report.py --report temp/report.md --data temp/analysis_data.json

# 验证项：
# - 必需字段完整性
# - 表格编号连续性
# - 能力动词层次匹配
# - 典型任务覆盖性
# - 能力编号一致性
```

## 🎯 教育层次适配

不同教育层次对应不同的能力动词要求：

| 层次 | 允许动词 | 禁止动词 |
|------|----------|----------|
| **中职** | 操作、执行、完成、使用、识别、检测 | 设计、优化、创新、管理、分析 |
| **高职** | 检测、诊断、分析、维护、维修、优化 | 研发、创新、管理 |
| **职教本科** | 设计、优化、管理、创新 | - |

## ⚙️ 工作流程

完整的工作流程包含以下步骤：

```
阶段一：数据获取
├─ 步骤1: 检索专业教学标准
├─ 步骤2: 获取职业信息（大模型处理）
├─ 步骤3: 用户确认职业信息
├─ 步骤4: ESCO/O*NET 映射推断
├─ 步骤5: 本地文档查询
└─ 步骤6: 整合基础数据

阶段二：语义分析
├─ 步骤7-9: 工作任务分析
├─ 步骤10: 行动领域划分
├─ 步骤11: 职业能力分析
├─ 步骤12: 学习领域转换
├─ 步骤13: 学习情境设计
└─ 步骤14: 输出结构化数据

阶段三：报告生成
└─ 步骤15: 生成 Markdown 报告

阶段四：质量校验
├─ 步骤16: 质量校验
└─ 步骤17: 问题修复
```

## 🔑 能力编号规则

- **Z** = 专业能力（ZhuanYe），编号 Z001, Z002...
- **F** = 方法能力（FangFa），编号 F001, F002...
- **S** = 社会能力（SheHui），编号 S001, S002...

> ⚠️ 表7（能力一览表）与表8（能力解构表）的能力编号必须完全一致

## 📚 参考文档

| 文档 | 用途 |
|------|------|
| `references/work_process_method.md` | 工作过程系统化方法理论基础 |
| `references/analysis_data_template.json` | 分析数据 JSON 格式模板 |
| `references/report_template.md` | 报告 Markdown 模板 |
| `references/troubleshooting.md` | 故障排除指南 |

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 📮 联系方式

如有问题或建议，请提交 [GitHub Issue](https://github.com/flyboat403/occupation-analysis/issues)

---

**⭐ 如果这个项目对您有帮助，请给一个 Star！**