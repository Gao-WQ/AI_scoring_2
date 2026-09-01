# 版本更新记录（CHANGELOG）

本项目为手写汉字六维预打分系统（AI_scoring_2），基于分割图几何特征（逐笔颜色比对）+ 三锚点刻度插值。

版本提交约定：**所有 git 提交/推送需经确认后执行**，本文件随版本更新同步维护。

---

## v3（commit `6282a72`）— 评分中间值写入 xlsx"ai特征值"sheet

- 日期：2026-09-01
- 类型：功能增强（评分过程可视化）

### 改动内容

| 模块 | 改动 |
|---|---|
| `src/scoring/score_mapper.py` | `map_scores_batch` 新增 `return_details`：返回每样本偏差 d/分数/完整特征，以及锚点原始刻度与校准后刻度；修复第二遍映射时 `d_sample` 误传字典的 bug |
| `src/pipeline/single_char.py` | 新增 `add_feature_sheet`：`--save-features` 时在输出 xlsx 新增"ai特征值"sheet（中文列名、第一列 char_id、无图片、28 列含总分），替代原 `score_details.json` 输出 |
| `src/pipeline/run_all.py` / `src/main.py` | `run-all` 子命令新增 `--save-features` 参数 |
| `src/common/io_utils.py` | 清理无调用方的 `json_safe` |

### ai特征值 sheet 结构（28 列，中文表头）

`char_id | 笔画数 | 中心偏移 | 边距不对称 | 占格面积比 | 宽高比偏差 | 密度熵 | 字内空白比 | 四宫格-左上/右上/左下/右下 | 笔画长度均值 | 笔画宽度均值 | 笔画曲率均值 | 偏差-笔画/结构/位置/占格/衔接/留白 | 笔画规范分 | 结构规范分 | 位置规范分 | 占格大小分 | 笔画衔接分 | 留白空间分 | 总分`

### 验证结果（上字，727 样本）

- ai特征值 sheet：727 行 × 28 列，总分 = 六维和校验通过
- 主表写回校验通过：727 行、1454 图、L 列空、J/K/M 公式保留
- 用法：`python main.py run-all --char 上 --save-features`（不加开关则行为与 v2 一致）

---

## v2（commit `41b9746`）— 评分改进：H 拓扑量 + 分布校准

- 日期：2026-09-01
- 类型：评分准确性与分布优化

### 改动内容

| 模块 | 改动 |
|---|---|
| `src/features/features.py` | H 维度（笔画衔接位置）弃用 `cross_color_gap`（异色笔画最近端点距，对"上"字刻度反转），改用 `stroke_topology` 拓扑量：端点数 + 交叉点数 + 悬空率（`dangling_ratio = 端点/(端点+2×交叉点)`），距离 = 0.5×端点差归一化 + 0.5×悬空率差 |
| `src/scoring/score_mapper.py` | 新增 `map_scores_batch`：两遍计算（先收集样本偏差分布 → 校准刻度 → 再映射）；新增 `calibration` 分布校准兜底 |
| `src/config.json` | 新增 `calibration` 配置块：`{enabled: true, fair_percentile: 0.5, worst_percentile: 0.9}`（可关闭） |
| `src/pipeline/single_char.py` | 改用批量映射接口 |

### 分布校准逻辑

- fair 刻度 = max(锚点偏差值, 样本偏差 50 分位)
- worst 刻度 = max(锚点偏差值, 样本偏差 90 分位)
- 目的：锚点刻度过严时防止分数分布被压死；锚点仍决定"满分锚点 = 维度满分"

### 验证结果（上字，727 样本）

| 指标 | v1 | v2 |
|---|---|---|
| 总分均值 | 32.63 | **40.17** |
| F 位置规范均值 | 4.86/15 | **7.30** |
| H 衔接位置均值 | 4.88/10 | **6.38** |
| I 留白空间均值 | 4.11/10 | **5.59** |
| E 结构规范均值 | 7.34/20 | **9.05** |
| 等级分布 | B- 275 / C+ 213 / C 147（左偏压死） | B 216 / B- 308 / C+ 92 / A- 13（钟形） |

写回校验通过：727 行、1454 图、L 列空、J/K/M 公式保留。

---

## v1（commit `92d05ae`）— 基线：Phase 0-3 全链路跑通

- 日期：2026-09-01
- 类型：项目初始化 + 全链路验证

### 内容

- **目录结构**：src 四层（common 公共库 / features 特征层 / scoring 评分层 / pipeline 管道层）+ data（anchors/features/scores/output）+ logs
- **公共库**：`common/`（io_utils / image_utils / excel_utils / anchor_utils / logging_utils），只写一次、业务模块 import 复用
- **CLI**：`src/main.py` 统一入口（init-anchor / stroke-check / feature-check / run-all / apply-scores），全部 get_args() + default 传参
- **锚点规范**：每字 `data/anchors/{字}/` 三张分割图（perfect/fair/worst.png）+ anchor.json（刻度比例 1.0 / 0.425 / 0.125）
- **评分链路**：分割图 → 颜色量化逐笔分离 → 逐笔骨架分析 → 六维特征（逐笔比对 + 画布参考）→ 三锚点刻度插值 → scores json → 写回 Excel（D:I + J 自动求和 + L 留空 + 公式保留）

### 验证结果

- 刀字 689 张：笔画分离 100% 一致（2 画）
- 上字 727 样本：全链路跑通（特征 → 评分 → 写回验证通过）

### 已知问题（v2 已解决）

- H 维度 `cross_color_gap` 度量不稳定（fair 锚点偏差 47.7 远大于 worst 0.25，刻度反转）
- 无分布校准，锚点刻度过严时分数分布左偏压死

---

## 提交历史

| commit | 说明 |
|---|---|
| `92d05ae` | v1 基线：Phase 0-3 全链路跑通 |
| `41b9746` | v2 评分改进：H 拓扑量 + 分布校准 |
| `6282a72` | v3 评分中间值写入 xlsx"ai特征值"sheet |
