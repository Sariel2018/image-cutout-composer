# CLI Parameter Reference (CN)

这份文档用于说明每个脚本参数的作用、默认值和常见用法。

## 1) `scripts/new_job.py`

用途：初始化一个新的任务目录（`jobs/<job_name>/`）并生成 `layout.json` 模板。

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--job` | 必填 | 任务名，例如 `my_job`。 |
| `--source` | `""` | 可选，复制到 `input/source.png`。 |
| `--reference` | `""` | 可选，复制到 `input/reference.webp`。 |
| `--canvas` | `2400x1500` | 生成 `layout.json` 时的画布尺寸（`WIDTHxHEIGHT`）。 |

示例：

```bash
.venv/bin/python scripts/new_job.py \
  --job my_job \
  --source /path/to/source.png \
  --reference /path/to/reference.webp \
  --canvas 2400x1500
```

## 2) `scripts/extract_sprites.py`

用途：对输入图做连通域拆分，产出 `crops/`、`objects.json`、`contact_sheet.png`、`bbox_preview.png`。

### 输入/输出

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--job-dir` | `jobs/demo_work` | 任务目录模式。通常与 `--input/--out-dir` 二选一。 |
| `--input` | `""` | 显式输入 PNG 路径。 |
| `--out-dir` | `""` | 显式输出目录。 |

### 分割与过滤

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--segmentation-mode` | `auto` | 前景分割模式：`auto` / `alpha` / `checker`。 |
| `--alpha-threshold` | `8` | alpha 大于该阈值视为前景。 |
| `--bg-gray-low` | `185` | `checker` 模式下灰度下界。 |
| `--bg-gray-high` | `252` | `checker` 模式下灰度上界。 |
| `--bg-chroma-tol` | `12` | `checker` 模式下允许的 RGB 通道差。 |
| `--min-area` | `20` | 忽略小于该面积的连通域。 |
| `--padding` | `2` | 每个裁片额外外扩像素。 |

### 预览与小符号合并

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--columns` | `0` | 联系表列数，`0` 为自动。 |
| `--merge-floating-symbols` | 开启 | 合并分离的小符号（`?`、`z` 等）到邻近主体。 |
| `--no-merge-floating-symbols` | 关闭 | 禁用上面的合并策略。 |

示例：

```bash
.venv/bin/python scripts/extract_sprites.py --job-dir jobs/my_job
```

## 3) `scripts/compose_layout.py`

用途：按 `layout.json` 中的 ID 顺序拼图，输出 `final.png/final.webp` 与 `composition.json`。

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--job-dir` | `jobs/demo_work` | 任务目录模式。 |
| `--objects` | `""` | 显式指定 `objects.json`。 |
| `--layout` | `""` | 显式指定 `layout.json`。 |
| `--crops-dir` | `""` | 显式指定裁片目录。 |
| `--reference` | `""` | 参考图路径（`compact` 风格会用到）。 |
| `--output` | `""` | 输出 PNG 路径。 |
| `--output-webp` | `""` | 输出 WEBP 路径。 |
| `--report` | `""` | 输出布局报告 JSON 路径。 |
| `--style` | `strip` | 拼图风格：`strip`（旧版底条）/ `compact`（更紧凑透明底）。 |

示例：

```bash
.venv/bin/python scripts/compose_layout.py \
  --job-dir jobs/my_job \
  --style compact
```

说明：
- 不传 `--reference` 时，脚本会优先尝试自动发现 `jobs/<job>/input/reference.webp`（或 `reference.png`）。
- 如果参考图布局与当前内容不匹配，脚本会自动回退到普通 `compact` 排版，避免角色过小或被裁切。

## 4) `scripts/compose_reference_grid.py`

用途：按固定帧宽高强制拼成规则网格，用于前端稳定切帧；同时支持边缘处理。

### 基础输入输出

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--job-dir` | 必填 | 任务目录。 |
| `--objects` | `""` | 显式 `objects.json`。 |
| `--layout` | `""` | 显式 `layout.json`。 |
| `--crops-dir` | `""` | 显式 `crops/` 目录。 |
| `--reference` | `""` | 显式参考图路径。 |
| `--frame-width` | 必填 | 每帧宽度。 |
| `--frame-height` | 必填 | 每帧高度。 |
| `--output` | `""` | 输出 PNG。 |
| `--output-webp` | `""` | 输出 WEBP。 |
| `--report` | `""` | 输出报告 JSON。 |
| `--fill-mode` | `cycle` | 帧不足时填充策略：`cycle` / `hold-last`。 |
| `--alpha-threshold` | `20` | 参考图分析时的 alpha 阈值。 |

### 边缘调节参数

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--defringe-white` | 关闭 | 尝试消除半透明白边。 |
| `--outline-size` | `0` | 黑色描边像素宽度（`0` 关闭）。 |
| `--outline-alpha` | `230` | 描边透明度。 |
| `--outline-threshold` | `24` | 判定主体 alpha 阈值。 |
| `--sharpen` | 关闭 | 轻微锐化。 |
| `--blacken-fringe` | 关闭 | 将亮色半透明外缘压黑。 |
| `--fringe-alpha-max` | `220` | 外缘压黑候选 alpha 上限。 |
| `--fringe-luma-min` | `130` | 外缘压黑候选亮度下限。 |
| `--fringe-chroma-max` | `70` | 外缘压黑候选色差上限。 |
| `--fringe-iterations` | `1` | 外缘压黑迭代次数。 |
| `--force-black-edge-width` | `0` | 强制把外层 N 像素 alpha 边带刷黑。 |
| `--force-black-edge-alpha-floor` | `0` | 若 >0，将边带 alpha 至少抬到该值。 |

示例（常用“调边 + 规则帧”）：

```bash
.venv/bin/python scripts/compose_reference_grid.py \
  --job-dir jobs/my_job \
  --frame-width 256 \
  --frame-height 256 \
  --fill-mode hold-last \
  --defringe-white \
  --outline-size 1 \
  --blacken-fringe \
  --force-black-edge-width 1
```

说明：
- 不传 `--reference` 时，脚本也会优先尝试自动发现 `jobs/<job>/input/reference.webp`（或 `reference.png`）。

## 推荐上手流程

```bash
# 1) 创建任务
.venv/bin/python scripts/new_job.py --job my_job --source /path/to/source.png

# 2) 自动拆图
.venv/bin/python scripts/extract_sprites.py --job-dir jobs/my_job

# 3) 人工编辑 layout.json（选 ID + 排顺序）

# 4) 普通合成
.venv/bin/python scripts/compose_layout.py --job-dir jobs/my_job --style compact

# 5) 前端切帧版（可选）
.venv/bin/python scripts/compose_reference_grid.py --job-dir jobs/my_job --frame-width 256 --frame-height 256
```
