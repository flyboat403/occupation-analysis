# 第三方数据与许可范围

本仓库的代码、脚本、文档，以及维护者原创的整理、拆分和格式转换成果，采用 [MIT 许可证](LICENSE)。

**MIT 许可证不适用于下列第三方来源的原文内容**，这些内容的著作权和使用条件归原权利人所有：

## 中国职业分类大典（2022 年版）

- **文件**：`assets/occupation_dictionary_split/`
- **收录范围**：第 1–6 大类（`class_1`–`class_6`）的职业定义与主要工作任务文本。
- **来源**：人力资源社会保障部、市场监管总局、统计局颁布（人社部发〔2022〕68 号），中国劳动社会保障出版社出版。
- **官方通知**：https://www.mohrss.gov.cn/SYrlzyhshbzb/rencairenshi/zcwj/RCDWJSzonghe/202211/t20221103_489285.html
- **MIT 范围**：维护者对该文本所做的按大类拆分、字段整理和 Markdown 格式转换可按 MIT 使用；其中来自《大典》的**职业定义、主要工作任务等描述性原文不适用 MIT**。复用时应按字段区分，不能把整个目录下的文件视为 MIT。
- **使用建议**：公开转载、展示或再分发定义/任务原文前，请向人力资源社会保障部（职业能力建设司）或中国劳动社会保障出版社确认；如仅使用职业编码/名称，也请注明来源。

## 教育部职业教育材料

- **文件**：`assets/moe_pdfs_final.json`、`assets/moe_jianjie_final_github.json`、`assets/moe_pdfs_md/`、`assets/职业教育专业目录.xlsx`、`assets/专业-职业对照表.xlsx`
- **说明**：来自教育部公开材料。使用时应遵循原发布方条款并注明来源；MIT 不覆盖这些材料的原文。

## ESCO 与 O*NET

- **文件**：`assets/esco_final.json`、`assets/onet_final.json`、`assets/esco_details_md/`、`assets/onet_details_md/`
- **ESCO**：European Commission，依据 Commission Decision 2011/833/EU 复用，需署名。
- **O*NET 31.0**：U.S. Department of Labor, Employment and Training Administration，CC BY 4.0，需署名并标注修改。
- 详细来源与署名要求见镜像仓库 `vocational-education-standard-system` 的 `SOURCES.md`。

## 署名格式（MIT 部分）

复用本仓库代码或维护者原创整理成果时，建议保留：

```text
occupation-analysis (https://github.com/flyboat403/occupation-analysis), MIT License
```

## 后续版本

本说明针对当前仓库快照。MIT 部分对后续版本继续适用（除非某个文件另作声明）；第三方原文的许可需按来源和版本分别确认，本说明不构成对未声明内容的授权。

如对上述范围有疑问，请通过仓库 Issue 联系维护者。
