# Image Cutout + Sheet Composer（原型）

[English](README.md) | [简体中文](README.zh-CN.md)

这是一个面向动画素材生产流程的小工具链，主要能力是：

- 自动抠图/拆分（连通域切分）
- 按 ID 重排拼图
- 导出 PNG/WEBP 图表，并支持调边与严格网格输出

## 文档入口

- [工具说明](docs/tool-overview.md)
- [流程图说明](docs/workflow.md)
- [CLI 参数手册](docs/cli-reference.md)
- [公开样例说明](samples/demo_work/README.md)

## 流程概览

```mermaid
flowchart LR
    A[input/source.png] --> B[new_job.py]
    B --> C[extract_sprites.py]
    C --> D[extract/contact_sheet.png]
    D --> E[edit layout.json]
    E --> F[compose_layout.py]
    E --> G[compose_reference_grid.py]
    F --> H[output/final.png + final.webp]
    G --> I[output/final3.png + final3.webp]
```

项目治理文件：

- 贡献指南：`CONTRIBUTING.md`
- 安全策略：`SECURITY.md`
- 支持说明：`SUPPORT.md`
- 行为准则：`CODE_OF_CONDUCT.md`
- 素材授权：`ASSETS_LICENSE.md`
- 更新日志：`CHANGELOG.md`

## 核心脚本

- `scripts/new_job.py`：初始化任务目录
- `scripts/extract_sprites.py`：自动拆分并生成联系表
- `scripts/compose_layout.py`：按行拼图（`strip` / `compact`）
- `scripts/compose_reference_grid.py`：严格网格切帧 + 边缘处理

## 目录结构

```text
image-cutout-composer/
  scripts/
  docs/
  samples/
    demo_work/
  requirements.txt
```

说明：

- `old/` 可作为你的本地归档目录，但默认不会上传到 GitHub。
- `jobs/` 是脚本运行产生的本地中间产物工作区（`input/`、`extract/`、`output/`、`layout.json`），已全部加入 git 忽略，不会上传。

## 环境安装

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 快速开始

1. 新建任务：

```bash
JOB_NAME=my_job
.venv/bin/python scripts/new_job.py \
  --job "$JOB_NAME" \
  --source /path/to/source.png \
  --reference /path/to/reference.webp
```

2. 设置任务目录（`new_job.py` 默认会创建该路径）：

```bash
JOB_DIR="jobs/$JOB_NAME"
```

3. 自动拆图：

```bash
.venv/bin/python scripts/extract_sprites.py --job-dir "$JOB_DIR"
```

4. 打开 `"$JOB_DIR/extract/contact_sheet.png"`，编辑 `"$JOB_DIR/layout.json"`。

5. 合成输出：

```bash
.venv/bin/python scripts/compose_layout.py --job-dir "$JOB_DIR" --style compact
```

6. 可选：严格网格切帧 + 调边：

```bash
.venv/bin/python scripts/compose_reference_grid.py \
  --job-dir "$JOB_DIR" \
  --frame-width 256 \
  --frame-height 256 \
  --defringe-white \
  --outline-size 1 \
  --blacken-fringe
```

## 贡献者

- [@Sariel2018](https://github.com/Sariel2018)

## 致谢（AI）

- OpenAI Codex（ChatGPT）：提供实现、重构与文档整理支持。
- 所有 AI 协助产出均由仓库维护者审核后合并。

## 许可证

代码使用 MIT（见 `LICENSE`）。

## 素材权利

图片/角色素材与代码许可证分离，详见 `ASSETS_LICENSE.md`。
