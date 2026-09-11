---
name: svg-to-animated-gif
description: 把矢量插画做成无缝循环的 GIF 动图。触发词：做成 GIF、生成动图、让插画动起来、animate this SVG、make a GIF、循环动画、动图帧。适用：单文件 SVG 插画/图标/场景要做成动画 GIF，且机器上没有 cairosvg/ImageMagick/playwright。核心：用无头 Edge 一次性截图「N 帧网格」再切帧合成，配合整数周期法保证无缝循环。不适合：视频（用 VideoGen）、纯 CSS 动画。
agent_created: true
---

# SVG 插画 → 无缝循环 GIF

## 何时用
矢量插画要变成会动的 GIF，而本机**没有** cairosvg（缺 cairo DLL）、ImageMagick、playwright 时。
Windows 上几乎一定有 Edge，无头 Edge 渲染 SVG 的保真度和抗锯齿都最好，**优先走这条路，不要装依赖**。

## 核心思路（三个非显然的点）

**1. 一次截图出 N 帧，而不是启动 N 次浏览器。**
启动一次 Edge ≈ 1.5s，24 帧就是 36s 且易失败。正确做法：把 N 帧当成一个 `COLS × ROWS` 的网格拼进**一个 HTML**，每个单元格是绝对定位的独立 `<svg>`，一次截图整张，再用 Pillow 切。

**2. 用 2 倍超采样换抗锯齿。**
单元格按 2× 渲染（如 680×460 → 1360×920），切完后用 `LANCZOS` 降采样回目标尺寸。GIF 只有 256 色，降采样能让边缘在量化后依然干净。

**3. 无缝循环 = 每个周期运动在一个循环内完成「整数个周期」。**
这是最容易翻车的地方，详见 `references/loop_math.md`。

## 流程

```bash
# 1. 写帧生成器：frame(t) 返回 SVG 内容字符串，t = i/N
#    拼成网格 HTML（见 scripts/grid_to_gif.py 的 build_page）
# 2. 无头 Edge 一次截图
"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
  --headless --disable-gpu --no-sandbox --hide-scrollbars \
  --force-device-scale-factor=1 \
  --screenshot=grid.png --window-size=8160,3680 \
  "file:///C:/path/grid.html"
# 3. 切帧 + 合成
python scripts/grid_to_gif.py     # 改顶部 CONFIG 即可复用
```

页面 CSS 必须 `html,body{margin:0;padding:0;overflow:hidden}`，否则滚动条会把整张图顶偏。
`--force-device-scale-factor=1` 必须加，否则高分屏下截图尺寸翻倍、切片全错位。

## 合成 GIF 的三个参数（决定成败）

- **共享调色板**：把所有帧竖着贴成一张长图，对它 `quantize` 得到**一个**调色板，再逐帧 `quantize(palette=pal)`。逐帧各自量化会导致帧间闪烁。
- `dither=0`：扁平色块插画不要抖动，抖动会毁掉压缩率并让纯色区起噪点。
- `disposal=2` + 每帧都是**不透明全幅**：避免残影。GIF 必须有背景色，透明背景的 SVG 要补一个 `rect`。

## 常见坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 切片全部错位/尺寸对不上 | 没加 `--force-device-scale-factor=1` | 补上，或把窗口尺寸按实际缩放系数乘 |
| 整张图偏移、右侧被裁 | 页面出现滚动条 | `overflow:hidden` + `--hide-scrollbars` |
| 循环处明显跳一下 | 某运动周期数不是整数 | 见 `references/loop_math.md`，把周期对齐 |
| 帧数对但图不动 | `t` 没参与坐标计算，只改了无关属性 | 检查每一帧的几何是否真的随 `t` 变 |
| GIF 体积过大 | 帧数过多或抖动 | 降到 24 帧左右、`dither=0`、`colors=192` |

## 已验证的成品参数
680×460 / 24 帧 / 50ms / 无限循环 / 192 色 → **约 680KB**，视觉流畅。
再大的尺寸建议改用 APNG 或视频，GIF 不划算。
