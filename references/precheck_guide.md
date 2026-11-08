# 预检验证指南

> 本文件为 SKILL.md 步骤0 的详细参考文档，按需加载。

---

## 一、环境检查清单

在开始任何工作流程之前，必须验证以下条件：

| 检查项 | 命令/方法 | 预期结果 |
|--------|----------|----------|
| Python 环境 | `python --version` | Python 3.8+ |
| 依赖安装 | `pip install -r requirements.txt` | 无错误 |
| 数据文件存在 | 检查 `assets/moe_pdfs_final.json` | 文件存在 |
| 职业大典存在 | 检查 `assets/occupation_dictionary_split/` | 大类文件与 `split_info.json` 记录一致 |
| 输出目录 | 检查/创建 `output/` 和 `temp/` | 目录存在 |
| IMA 凭证 | 检查环境变量 `IMA_OPENAPI_CLIENTID` | 已设置 |

---

## 二、预检脚本

### 2.1 快速检查命令

```bash
# 一行检查核心文件
python -c "from pathlib import Path; print('[OK]' if Path('assets/moe_pdfs_final.json').exists() else '[X]', 'moe_pdfs_final.json')"
```

### 2.2 完整预检脚本

```python
#!/usr/bin/env python3
"""预检验证脚本"""

import json
import os
from pathlib import Path

def check_environment():
    """检查环境配置"""
    checks = []
    
    # Python 版本
    import sys
    checks.append(("Python 版本", sys.version_info >= (3, 8), f"{sys.version_info.major}.{sys.version_info.minor}"))
    
    # 必需文件
    required_files = [
        "assets/moe_pdfs_final.json",
        "assets/moe_jianjie_final_github.json",
        "assets/moe_pdfs_md",
        "assets/esco_final.json",
        "assets/onet_final.json",
    ]
    for f in required_files:
        path = Path(f)
        checks.append((f, path.exists(), "存在" if path.exists() else "缺失"))

    # 国际文档目录（文件数需与索引一致）
    for index_file, directory in (
        ("assets/esco_final.json", "assets/esco_details_md"),
        ("assets/onet_final.json", "assets/onet_details_md"),
    ):
        path = Path(directory)
        count = len(list(path.glob("*.md"))) if path.exists() else 0
        index_path = Path(index_file)
        try:
            expected = len(json.loads(index_path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            checks.append((directory, False, f"索引读取失败: {index_file} ({e})"))
            continue
        checks.append((directory, count == expected, f"{count} 个文件（索引 {expected}）"))
    
    # 职业大典分块目录
    occ_dir = Path("assets/occupation_dictionary_split")
    split_info_path = occ_dir / "split_info.json"
    if not occ_dir.exists():
        checks.append(("职业大典分块", False, "目录不存在"))
    elif not split_info_path.exists():
        checks.append(("职业大典分块", False, "缺少 split_info.json"))
    else:
        try:
            sections = json.loads(split_info_path.read_text(encoding="utf-8")).get("sections", [])
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            sections = None
            checks.append(("职业大典分块", False, f"split_info.json 读取失败: {e}"))
        if sections is not None:
            if not sections:
                checks.append(("职业大典分块", False, "split_info.json 未记录大类"))
            else:
                expected_names = {s.get("filename") for s in sections if s.get("filename")}
                actual_names = {p.name for p in occ_dir.glob("*.md")}
                missing = expected_names - actual_names
                if missing:
                    checks.append(("职业大典分块", False, f"缺少大类文件: {sorted(missing)}"))
                else:
                    checks.append(("职业大典分块", True,
                                   f"{len(actual_names)} 个大类文件（与 split_info 一致）"))
    
    # 输出目录
    for d in ["output", "temp"]:
        path = Path(d)
        if not path.exists():
            path.mkdir(parents=True)
        checks.append((f"{d}/ 目录", path.exists(), "已创建" if path.exists() else "创建失败"))
    
    # IMA 凭证
    ima_clientid = os.environ.get("IMA_OPENAPI_CLIENTID", "")
    ima_apikey = os.environ.get("IMA_OPENAPI_APIKEY", "")
    checks.append(("IMA Client ID", bool(ima_clientid), "已配置" if ima_clientid else "未配置"))
    checks.append(("IMA API Key", bool(ima_apikey), "已配置" if ima_apikey else "未配置"))
    
    # 打印结果
    print("\n=== 预检验证结果 ===\n")
    all_passed = True
    for name, passed, detail in checks:
        status = "[OK]" if passed else "[X]"
        print(f"  {status} {name}: {detail}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("[OK] 所有检查通过")
    else:
        print("[WARNING] 部分检查未通过，请检查配置")
    
    return all_passed

if __name__ == "__main__":
    check_environment()
```

### 2.3 使用 occupation_dict_loader 内置检查

```bash
python scripts/occupation_dict_loader.py
```

运行时会自动验证文件。

### 2.4 校验 ESCO/O*NET 索引

```bash
python scripts/build_intl_index.py --check
```

校验索引条数、代码唯一性、`md_url` 前缀，以及与本地文档的双向一致性。

---

## 三、数据源优先级

| 优先级 | 数据源 | 用途 | 备注 |
|--------|--------|------|------|
| 1 | `assets/moe_pdfs_final.json` | 专业教学标准 | 主数据源（PDF链接指向GitHub镜像） |
| 2 | `assets/moe_jianjie_final_github.json` | 专业简介索引 | 兜底数据源（md_url指向GitHub镜像） |
| 3 | `assets/moe_pdfs_md/` | 专业简介（类级MD） | 离线兜底 |
| 4 | `assets/esco_final.json` | ESCO索引 | 3036条，`md_url`指向GitHub镜像 |
| 5 | `assets/onet_final.json` | O*NET索引 | 896条，`md_url`指向GitHub镜像 |
| 6 | `assets/esco_details_md/` | ESCO职业文档 | 本地离线兜底 |
| 7 | `assets/onet_details_md/` | O*NET职业文档 | 本地离线兜底 |

---

## 四、常见预检问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| Python 版本过低 | 系统安装的是 Python 2 或旧版 3.x | 安装 Python 3.8+ |
| 数据文件缺失 | 未下载或路径错误 | 检查 assets/ 目录 |
| IMA 凭证未配置 | .env 文件不存在或未加载 | 创建 .env 文件并配置环境变量 |
| 依赖安装失败 | 网络问题或版本冲突 | 使用国内镜像或更新 pip |

---

## 五、快速启动检查清单

```bash
# 1. 检查 Python
python --version

# 2. 安装依赖
pip install -r requirements.txt

# 3. 检查数据文件
ls assets/moe_pdfs_final.json
ls assets/occupation_dictionary_split/

# 4. 配置环境变量（创建 .env）
echo "IMA_OPENAPI_CLIENTID=your_client_id" > .env
echo "IMA_OPENAPI_APIKEY=your_api_key" >> .env

# 5. 运行测试
python scripts/search_major.py --major "汽车运用与维修" --level "中等职业教育"
```