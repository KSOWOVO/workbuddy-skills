# 解读页 HTML 设计规格

目标：**单文件、离线可看、零 CDN 依赖**（用户会直接发给别人看，不能依赖网络）。
风格参考 Apple/三星官网：大留白、克制动效、层级靠字号与色彩而非边框。

## 硬性约束

- 不引任何外部 JS/CSS（Chart.js、Tailwind 都不行），图表一律手写 SVG / CSS
- IDE 为 dark 主题时默认深色；文字必须浅色可读（不要反过来）
- `viewBox` 的 SVG 知识地图用 `width:100%;height:auto` 自适应
- 中文文件名路径在 HTML 里只作展示，不做资源引用

## 配色（深色）

```
--bg:#080b11  --card:#141b27  --line:rgba(255,255,255,.08)
--tx:#e9eef7  --tx2:#97a4b8  --tx3:#5f6d80
--ielts:#5ad1e6(青)  --invest:#ffb454(琥珀)  --track:#7ee787(绿)
--hub:#a78bfa(紫)    --warn:#ff7b72(红)      --ok:#3fb950
```

每个板块一个主色，贯穿卡片顶条 / 图标底 / 数字 / 进度条。这样一眼能分清内容线。
背景用 3 个 `radial-gradient` 做大面积氛围光，比纯黑高级。

## 动效（克制，全部 CSS/原生 JS）

| 效果 | 实现 | 参数 |
|---|---|---|
| 滚动进度条 | 顶部 3px 渐变条 | `scrollTop/(scrollHeight-clientHeight)` |
| 吸顶导航 | `translateY(-100%)→0` | 滚动 >420px 触发 |
| 区块淡入 | IntersectionObserver + `.reveal/.in` | `translateY(22px)` + opacity，`threshold:.12` |
| 数字滚动 | requestAnimationFrame + easeOutCubic | 1400ms |
| 条形图展开 | `width:0 → data-w%` | 1.1s cubic-bezier(.2,.8,.2,1) |
| 进度环 | `stroke-dashoffset` | `C=2πr` |

## 知识地图 SVG 画法

- viewBox `0 0 1200 780`，中心节点放正中，四条主干用**三次贝塞尔**向外发散
- **连线粗细 ∝ 该分支字数**（主分支 12–13px，次级 4–6px），视觉上直接表达「哪里投入最多」
- 板块用 `circle`，具体条目用 `rect rx=11`（圆角矩形比圆形能放更多字）
- 空置目录用 `stroke-dasharray="5 4"` 虚线 + 红色，一眼看出是缺口
- 发光：`feGaussianBlur stdDeviation=9` + `feMerge`，只给核心节点用（滥用会糊）
- 文字用 class 而非内联 fill，方便统一换色

## 排版

- 标题 `clamp(34px,5.6vw,62px)`，`letter-spacing:-1.5px`，关键短语用渐变文字
- Hero 下必须有 **「一句话翻译给外行」** 类比块——这是"让别人通俗易懂"的关键
- 数字用 `font-variant-numeric:tabular-nums` 防跳动
- 卡片 hover `translateY(-4px)`，不要用 box-shadow 堆

## 内容组织原则

1. 先给结论和类比，再给细节（外行看前 20 秒就懂）
2. 表格数据转成「卡片 + 极值」而不是原样贴表
3. 每个板块配一句 **外行也能懂的翻译**（例：指数基金 = "规定好只能买前 300 家公司，基金经理不许自由发挥"）
4. 体检报告必须写缺点，且缺点要给可执行的下一步（按 ROI 排序 + 标注预计耗时）

## 交付前

- 跑标签闭合校验（见 SKILL.md）
- `present_files` 传 HTML 绝对路径（会自动开预览面板）
