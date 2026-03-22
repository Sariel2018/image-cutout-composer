# Tool Overview (CN)

这个项目是一个面向网页动画素材生产的小工具链，核心目标是把“手工抠图 + 手工拼图”流程标准化。

## 它解决什么问题

- 从一张素材图里自动拆出可复用角色/部件（抠图拆分）
- 按你给的顺序重新拼成动画表（拼图合成）
- 对边缘做可控处理，减少白边/毛边，增强黑边轮廓（边缘调节）

## 核心能力

- `extract_sprites.py`
  - 连通域拆分
  - 输出 `crops/`、`objects.json`、`contact_sheet.png`
  - 支持“浮动小符号合并”（默认开启）

- `compose_layout.py`
  - 基于 `layout.json` 按行拼图
  - 输出 `final.png/final.webp`
  - 支持 `strip` / `compact` 两种排版风格

- `compose_reference_grid.py`
  - 强制网格切帧（按 `frame-width/frame-height`）
  - 面向前端动画切帧稳定性
  - 支持边缘处理参数：
    - `--defringe-white`
    - `--outline-size`
    - `--blacken-fringe`
    - `--force-black-edge-width`

## 推荐定位（对外描述）

“一个用于网页动画素材生产的原型工具：自动抠图拆分、可控拼图合成，并支持边缘调节与严格切帧。”

