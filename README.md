# AI 预打分系统（AI_scoring_2）使用说明

基于**分割图几何特征（逐笔颜色比对）+ 多档位锚点刻度插值（3/5/9 可调）**的手写汉字六维预打分系统。为评分老师提供可修改的初稿，降低人工评分工作量。

版本：v5（锚点档位 3/5/9 + `--anchor-count` 切换，对应方案文档 `AI预打分方案_v6.docx`）｜更新记录见 [CHANGELOG.md](CHANGELOG.md)

---

## 一、评分原理（30 秒版）

1. 每个样本有分割图（**无背景、每笔一色、颜色顺序固定**）→ 颜色分离出逐笔画 → 逐笔骨架分析
2. 提取六维特征（笔画/结构/位置/占格/衔接/留白）→ 与锚点图池（`1.png`~`9.png`，1=最佳 / 9=最差）做偏差比较
3. 按档位取锚点子集做分段线性插值 → 六维分（0~15/20/15/10/10/10）→ 写入 Excel，总分由公式自动求和

**锚点档位**：`3/5/9` 三档可选，共用同一套 `1.png`~`9.png` 图池；跑分时用 `--anchor-count` 指定用哪一档，档位与 ratio 可在 `config.json → anchor_defaults` 中调整。

| 档位 | 使用的图 | 默认 ratio（score_levels） |
|---|---|---|
| 3 档 | 1 / 5 / 9 | 1.0 / 0.425 / 0.125 |
| 5 档 | 1 / 3 / 5 / 7 / 9 | 1.0 / 0.78 / 0.55 / 0.32 / 0.1 |
| 9 档 | 1 ~ 9 全用 | 1.0 / 0.85 / 0.7 / 0.55 / 0.425 / 0.3 / 0.2 / 0.125 / 0.05 |

---

## 二、环境与依赖

| 项目 | 说明 |
|---|---|
| Python | `D:\app_wqgao\anaconda3\envs\poc_env\python.exe` |
| 依赖 | openpyxl、Pillow、numpy、scipy、opencv-python、scikit-image、python-docx（均已装） |
| 运行目录 | 所有命令在 `D:\wqgao\code\AI_scoring_2\src` 下执行 |

---

## 三、目录结构

```
AI_scoring_2\
├── CHANGELOG.md             # 版本更新记录
├── README.md                # 本说明
├── AI预打分方案_v*.docx     # 方案文档（设计/原理）
├── write_*.py               # 各 docx 的生成脚本（保留可复跑）
├── src\                     # 全部代码
│   ├── main.py              # CLI 统一入口（所有命令从这里进）
│   ├── config.py            # 配置加载（读 config.json）
│   ├── config.json          # 全局配置（路径/input_suffix/维度上限/校准/锚点档位）
│   ├── init_anchor.py       # 生成锚点目录模板
│   ├── apply_scores.py      # 从 scores json 单独写回 Excel
│   ├── common\              # ★ 可复用公共库（业务模块只 import 不复制）
│   │   ├── io_utils.py      #   路径/JSON 读写/源工作簿路径拼接/字符清单/进度条
│   │   ├── image_utils.py   #   图像加载/颜色量化/笔画分离/骨架化/端点交叉点
│   │   ├── excel_utils.py   #   openpyxl 封装（提图/写分/公式保留/校验）
│   │   ├── anchor_utils.py  #   锚点模板/分档配置解析/目录校验
│   │   └── logging_utils.py #   日志初始化
│   ├── features\            # 特征层
│   │   ├── stroke_separate.py  # 颜色量化+逐笔分离+笔画数校验
│   │   ├── skeleton.py         # 逐笔骨架分析（方向/长度/宽度/曲率/端点）
│   │   ├── features.py         # 六维特征提取 + 每维偏差距离
│   │   ├── stroke_check.py     # CLI: 笔画分离质量验证
│   │   └── feature_check.py    # CLI: 特征提取验证（CSV）
│   ├── scoring\
│   │   └── score_mapper.py  # 多档位锚点分段插值 + 分布校准
│   └── pipeline\
│       ├── single_char.py   # 单字流水线（评分 + 写回 + 特征 sheet）
│       └── run_all.py       # 批量/单字入口（CLI: run-all）
├── data\
│   ├── anchors\{字}\        # 锚点（1~9.png 图池 + anchor3/5/9.json，需人工提供）
│   ├── features\*.csv       # 特征验证表（中间产物）
│   ├── scores\{字}_scores.json   # 六维分结果（每字一份）
│   └── output\
│       ├── {字}_all_data_new_已评分.xlsx  # 成品（含评分+可选特征 sheet）
│       └── summary.csv      # 批量汇总
└── logs\                    # 运行日志
```

---

## 四、每个 py 文件的作用

| 文件 | 职责 | 关键函数 | CLI 入口 |
|---|---|---|---|
| `src/main.py` | CLI 统一入口，分发 5 个子命令 | `get_args()` / `main()` | ✅ |
| `src/config.py` | 读取 config.json、解析绝对路径 | `load_config()` / `resolve_path()` | — |
| `src/init_anchor.py` | 生成锚点目录模板（anchor{count}.json） | `run()` | ✅ `init-anchor` |
| `src/apply_scores.py` | 从已有 scores json 写回 Excel（独立入口） | `write_back()` | ✅ `apply-scores` |
| `src/common/io_utils.py` | 目录创建、JSON 安全读写、字符清单、源工作簿扫描 | `ensure_dir/load_json_safe/save_json/resolve_char_list` | — |
| `src/common/image_utils.py` | 图像加载、颜色 KMeans 量化、逐笔分离、骨架化、端点/交叉点提取 | `quantize_colors/separate_by_color/skeleton_of/endpoints_of` | — |
| `src/common/excel_utils.py` | 工作簿加载、嵌入图提取、D:I 写入、公式快照与校验 | `extract_images_by_row/write_scores/verify_workbook` | — |
| `src/common/anchor_utils.py` | 锚点模板创建、anchor{count}.json 分档解析、目录校验 | `create_anchor_template/load_anchor_config/validate_anchor_dir` | — |
| `src/common/logging_utils.py` | 控制台+文件日志初始化 | `setup_logger()` | — |
| `src/features/stroke_separate.py` | 颜色量化→逐笔掩膜→笔画数校验（业务层） | `separate_strokes/check_stroke_count` | — |
| `src/features/skeleton.py` | 单笔骨架几何：方向直方图/长度/宽度/曲率/端点 | `analyze_stroke/stroke_vector` | — |
| `src/features/features.py` | 六维特征提取（layout+逐笔）与每维偏差距离 | `extract_features/feature_distance/stroke_topology` | — |
| `src/features/stroke_check.py` | 笔画分离质量验证（颜色数 vs 实际笔画数） | `run()` | ✅ `stroke-check` |
| `src/features/feature_check.py` | 特征提取验证，输出特征表 CSV + 分布统计 | `run()` | ✅ `feature-check` |
| `src/scoring/score_mapper.py` | N 档锚点分段插值 → 六维分；批量映射+分布校准 | `map_dimension/map_scores_batch` | — |
| `src/pipeline/single_char.py` | 单字流水线：特征→评分→scores json→写回（可选特征 sheet） | `run_char/add_feature_sheet` | — |
| `src/pipeline/run_all.py` | 字符清单遍历、逐字跑、汇总 summary.csv | `run()` | ✅ `run-all` |

---

## 五、命令手册

所有命令统一格式：`python main.py <子命令> [参数]`（在 `src` 目录下执行）。

### 1. 生成锚点模板 `init-anchor`

```bash
python main.py init-anchor --char 刀           # 3 档（默认，取 config.anchor_defaults.anchor_count）
python main.py init-anchor --char 刀 --count 5 # 5 档
python main.py init-anchor --char 刀 --count 9 # 9 档
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--char` | 刀 | 字名（目录名） |
| `--count` | 取 config | 锚点档位数 3/5/9 |
| `--anchor-dir` | 取 config | 锚点根目录 |

产出 `data\anchors\{字}\anchor{count}.json`（N 条锚点，`file` = 对应图序号）。**图池规范**：`1.png`=最佳(perfect)、`9.png`=最差(worst)、`5.png`=中等(fair)；3/5/9 档三份 json 可并存，跑分时用 `--anchor-count` 选档。`score_ratio` 与 `label` 已自动填好，可改。

### 2. 笔画分离验证 `stroke-check`

```bash
python main.py stroke-check --char 刀 --expected-strokes 2
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--char` | 刀 | 验证的字 |
| `--expected-strokes` | 2 | 该字预期笔画数 |
| `--limit` | 0 | 抽样数，0=全部 |
| `--n-colors` | 8 | 颜色量化聚类数 |
| `--source-dir` | 取 config | 源工作簿目录 |

输出：笔画数分布与一致性百分比。

### 3. 特征提取验证 `feature-check`

```bash
python main.py feature-check --char 刀
```

产出 `data\features\{字}_features.csv`（16 列）+ 分布统计，用于检查特征是否有区分度。

### 4. 预打分 `run-all`（核心命令）

```bash
# 单字（推荐先验证）；指定锚点档位 9 档
python main.py run-all --char 上 --save-features --anchor-count 9

# 全量（扫描源目录全部 {字}{input_suffix}.xlsx），默认档位取 config.anchor_defaults.anchor_count
python main.py run-all

# 指定清单文件 + 5 档
python main.py run-all --chars-file data\chars.txt --anchor-count 5
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--char` | None | 只处理单字 |
| `--chars-file` | None | 字符清单文件 |
| `--n-colors` | 8 | 颜色量化聚类数 |
| `--save-features` | False | 在成品 xlsx 新增"ai特征值"sheet |
| `--source-dir` / `--anchors-dir` | 取 config | 源/锚点目录 |
| `--anchor-count` | 取 config | 锚点档位数 3/5/9（选 anchor{count}.json） |

产出：`data\scores\{字}_scores.json`、`data\output\{字}{input_suffix}{output_suffix}.xlsx`、`summary.csv`。缺锚点（该档 json 或对应图缺失）的字跳过不阻塞。

**换数据源**：修改 `config.json` 的 `source_dir`（目录）和 `paths.input_suffix`（文件后缀，如 `_all_data_new` 或 `-打分表-1`），源文件名即 `{字}{input_suffix}.xlsx`，代码不用改。

运行时输出：每字打印 `[处理] 字=X | 锚点=N档 | 待打分样本量=N | 打分表保存: ...`；样本量 >50 时特征提取阶段显示终端进度条。

### 5. 单独写回 `apply-scores`

```bash
python main.py apply-scores --char 上
```

从已有 scores json 写回 Excel（评分已算好但写回失败/老师改分后重写时用）。

---

## 六、数据流

```
源 xlsx（{字}{input_suffix}.xlsx，C 列分割图）
  → extract_features（六维特征，内存）
  → map_scores_batch（按档位锚点子集做偏差插值 + 分布校准 → 六维分）
  → data/scores/{字}_scores.json
  → 写回 data/output/{字}{input_suffix}{output_suffix}.xlsx
      ├── 评分汇总 sheet（D:I 六维分 + J/K/M 公式，L 留空给老师）
      └──（--save-features 时）ai特征值 sheet
```

**ai特征值 sheet（28 列，中文）**：`char_id | 笔画数 | 中心偏移 | 边距不对称 | 占格面积比 | 宽高比偏差 | 密度熵 | 字内空白比 | 四宫格×4 | 笔画长度均值 | 笔画宽度均值 | 笔画曲率均值 | 偏差×6 | 六维分 | 总分`

---

## 七、新字评分完整流程

```bash
# 1. 生成锚点模板（默认 3 档；也可 --count 5/9；可对多档分别生成）
python main.py init-anchor --char 新字 --count 9

# 2. 放置图池 1.png ~ 9.png（1 最好 → 9 最差，由好到差）；同一套图可支撑 3/5/9 三档 json
#    （仅生成 9 档模板时，默认 json 引用 1~9 全部；如需 3/5 档并存，再分别 init-anchor --count 3/5）
# 3. 验证笔画分离
python main.py stroke-check --char 新字 --expected-strokes N

# 4. 预打分（指定 9 档 + 特征 sheet）
python main.py run-all --char 新字 --save-features --anchor-count 9

# 5. 检查 data/output/ 成品 + summary.csv；对比不同档位效果时改 --anchor-count 重跑即可
```

老师收到成品后：打开 xlsx → 复核"评分汇总"sheet 的六维分 → 修改 D:I（或接受）→ L 列填最终等级。

---

## 八、常见问题

| 问题 | 处理 |
|---|---|
| 写回报 `PermissionError` | 输出 xlsx 正被 Excel/WPS 打开，关闭后重跑或 `apply-scores` 补写回 |
| 换数据源（文件名不同） | 改 `config.json`：`source_dir`（目录）+ `paths.input_suffix`（后缀，如 `-打分表-1`），源文件名 = `{字}{input_suffix}.xlsx` |
| 分数分布整体偏低/偏高 | 检查 `config.json` 的 `calibration.enabled`（默认 true）；换更合理的锚点图 |
| 某字被跳过 | 缺锚点：`data\anchors\{字}\` 缺少所选档位 `anchor{count}.json` 或其引用的 `{n}.png`；补齐后 `run-all --char 字 --anchor-count N` 单字重跑 |
| 想换一档锚点重跑 | `run-all` 加 `--anchor-count 3/5/9`，无需改图与代码；对应档 json 不存在则该字跳过 |
| 报告"笔画数异常" | 分割图缺笔/粘连，该样本标记复核，不参与评分 |
| 需要关闭分布校准 | `config.json` → `calibration.enabled` 改 `false` |
| 想回退代码版本 | 见 CHANGELOG 提交历史；本地 `git checkout <commit>`（需按约定确认后操作） |

---

## 九、代码约束（开发约定）

- 公共函数收敛 `src/common/`，业务模块只 import 不复制粘贴
- 依赖单向：pipeline → scoring/features → common
- 路径/参数集中 `config.json`，代码不硬编码
- CLI 一律 `get_args()` 且每个参数带 default
- **git 提交/推送须用户确认后执行**（见 ~/.workbuddy/MEMORY.md 约定）
