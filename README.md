# AI 预打分系统（AI_scoring_2）使用说明

基于**分割图几何特征（逐笔颜色比对）+ 三锚点刻度插值**的手写汉字六维预打分系统。为评分老师提供可修改的初稿，降低人工评分工作量。

版本：v3（commit `6282a72`）｜更新记录见 [CHANGELOG.md](CHANGELOG.md)

---

## 一、评分原理（30 秒版）

1. 每个样本有分割图（**无背景、每笔一色、颜色顺序固定**）→ 颜色分离出逐笔画 → 逐笔骨架分析
2. 提取六维特征（笔画/结构/位置/占格/衔接/留白）→ 与**三张锚点图**（满分/较差/最差）的特征做偏差比较
3. 三锚点刻度插值映射出六维分（0~15/20/15/10/10/10）→ 写入 Excel，总分由公式自动求和

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
│   ├── config.json          # 全局配置（路径/维度上限/校准参数）
│   ├── init_anchor.py       # 生成锚点目录模板
│   ├── apply_scores.py      # 从 scores json 单独写回 Excel
│   ├── common\              # ★ 可复用公共库（业务模块只 import 不复制）
│   │   ├── io_utils.py      #   路径/JSON 读写/字符清单/源目录扫描
│   │   ├── image_utils.py   #   图像加载/颜色量化/笔画分离/骨架化/端点交叉点
│   │   ├── excel_utils.py   #   openpyxl 封装（提图/写分/公式保留/校验）
│   │   ├── anchor_utils.py  #   锚点模板/配置解析/目录校验
│   │   └── logging_utils.py #   日志初始化
│   ├── features\            # 特征层
│   │   ├── stroke_separate.py  # 颜色量化+逐笔分离+笔画数校验
│   │   ├── skeleton.py         # 逐笔骨架分析（方向/长度/宽度/曲率/端点）
│   │   ├── features.py         # 六维特征提取 + 每维偏差距离
│   │   ├── stroke_check.py     # CLI: 笔画分离质量验证
│   │   └── feature_check.py    # CLI: 特征提取验证（CSV）
│   ├── scoring\
│   │   └── score_mapper.py  # 三锚点刻度插值映射 + 分布校准
│   └── pipeline\
│       ├── single_char.py   # 单字流水线（评分 + 写回 + 特征 sheet）
│       └── run_all.py       # 批量/单字入口（CLI: run-all）
├── data\
│   ├── anchors\{字}\        # 锚点（每字三张图 + anchor.json，需人工提供）
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
| `src/init_anchor.py` | 生成锚点目录模板（三张占位+anchor.json） | `run()` | ✅ `init-anchor` |
| `src/apply_scores.py` | 从已有 scores json 写回 Excel（独立入口） | `write_back()` | ✅ `apply-scores` |
| `src/common/io_utils.py` | 目录创建、JSON 安全读写、字符清单、源工作簿扫描 | `ensure_dir/load_json_safe/save_json/resolve_char_list` | — |
| `src/common/image_utils.py` | 图像加载、颜色 KMeans 量化、逐笔分离、骨架化、端点/交叉点提取 | `quantize_colors/separate_by_color/skeleton_of/endpoints_of` | — |
| `src/common/excel_utils.py` | 工作簿加载、嵌入图提取、D:I 写入、公式快照与校验 | `extract_images_by_row/write_scores/verify_workbook` | — |
| `src/common/anchor_utils.py` | 锚点模板创建、anchor.json 解析、锚点目录校验 | `create_anchor_template/validate_anchor_dir` | — |
| `src/common/logging_utils.py` | 控制台+文件日志初始化 | `setup_logger()` | — |
| `src/features/stroke_separate.py` | 颜色量化→逐笔掩膜→笔画数校验（业务层） | `separate_strokes/check_stroke_count` | — |
| `src/features/skeleton.py` | 单笔骨架几何：方向直方图/长度/宽度/曲率/端点 | `analyze_stroke/stroke_vector` | — |
| `src/features/features.py` | 六维特征提取（layout+逐笔）与每维偏差距离 | `extract_features/feature_distance/stroke_topology` | — |
| `src/features/stroke_check.py` | 笔画分离质量验证（颜色数 vs 实际笔画数） | `run()` | ✅ `stroke-check` |
| `src/features/feature_check.py` | 特征提取验证，输出特征表 CSV + 分布统计 | `run()` | ✅ `feature-check` |
| `src/scoring/score_mapper.py` | 三锚点刻度插值 → 六维分；批量映射+分布校准 | `map_dimension/map_scores/map_scores_batch` | — |
| `src/pipeline/single_char.py` | 单字流水线：特征→评分→scores json→写回（可选特征 sheet） | `run_char/add_feature_sheet` | — |
| `src/pipeline/run_all.py` | 字符清单遍历、逐字跑、汇总 summary.csv | `run()` | ✅ `run-all` |

---

## 五、命令手册

所有命令统一格式：`python main.py <子命令> [参数]`（在 `src` 目录下执行）。

### 1. 生成锚点模板 `init-anchor`

```bash
python main.py init-anchor --char 刀
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--char` | 刀 | 字名（目录名） |
| `--anchor-dir` | 取 config | 锚点根目录 |

产出 `data\anchors\{字}\`：三张占位说明 + `anchor.json`。放置三张分割图后删除占位文件。

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
# 单字（推荐先验证）
python main.py run-all --char 上 --save-features

# 全量（扫描源目录全部 *_all_data_new.xlsx）
python main.py run-all

# 指定清单文件
python main.py run-all --chars-file data\chars.txt
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--char` | None | 只处理单字 |
| `--chars-file` | None | 字符清单文件 |
| `--n-colors` | 8 | 颜色量化聚类数 |
| `--save-features` | False | 在成品 xlsx 新增"ai特征值"sheet |
| `--source-dir` / `--anchors-dir` | 取 config | 源/锚点目录 |

产出：`data\scores\{字}_scores.json`、`data\output\{字}_all_data_new_已评分.xlsx`、`summary.csv`。缺锚点的字跳过不阻塞。

### 5. 单独写回 `apply-scores`

```bash
python main.py apply-scores --char 上
```

从已有 scores json 写回 Excel（评分已算好但写回失败/老师改分后重写时用）。

---

## 六、数据流

```
源 xlsx（C 列分割图）
  → extract_features（六维特征，内存）
  → map_scores_batch（锚点偏差 + 分布校准 → 六维分）
  → data/scores/{字}_scores.json
  → 写回 data/output/{字}_all_data_new_已评分.xlsx
      ├── 评分汇总 sheet（D:I 六维分 + J/K/M 公式，L 留空给老师）
      └──（--save-features 时）ai特征值 sheet
```

**ai特征值 sheet（28 列，中文）**：`char_id | 笔画数 | 中心偏移 | 边距不对称 | 占格面积比 | 宽高比偏差 | 密度熵 | 字内空白比 | 四宫格×4 | 笔画长度均值 | 笔画宽度均值 | 笔画曲率均值 | 偏差×6 | 六维分 | 总分`

---

## 七、新字评分完整流程

```bash
# 1. 生成锚点模板
python main.py init-anchor --char 新字

# 2. 放入三张分割图（perfect/fair/worst.png），删占位文件，按需改 anchor.json
# 3. 验证笔画分离
python main.py stroke-check --char 新字 --expected-strokes N

# 4. 预打分（带特征 sheet）
python main.py run-all --char 新字 --save-features

# 5. 检查 data/output/ 成品 + summary.csv
```

老师收到成品后：打开 xlsx → 复核"评分汇总"sheet 的六维分 → 修改 D:I（或接受）→ L 列填最终等级。

---

## 八、常见问题

| 问题 | 处理 |
|---|---|
| 写回报 `PermissionError` | 输出 xlsx 正被 Excel/WPS 打开，关闭后重跑或 `apply-scores` 补写回 |
| 分数分布整体偏低/偏高 | 检查 `config.json` 的 `calibration.enabled`（默认 true）；换更合理的锚点图 |
| 某字被跳过 | 缺锚点：`data\anchors\{字}\` 未放三张图；补齐后 `run-all --char 字` 单字重跑 |
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
