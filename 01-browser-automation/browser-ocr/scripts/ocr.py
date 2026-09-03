from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, ImageFilter
from rapidocr_onnxruntime import RapidOCR


def preprocess(img: Image.Image, scale: float = 3.0) -> Image.Image:
    """放大 + 灰度 + 自动对比度 + 锐化，提升小字识别率。

    - 灰度：RapidOCR 内部本会处理，先转灰可去掉彩噪
    - autocontrast：拉伸对比度，浅色 UI 截图上的灰字更清晰
    - LANCZOS 放大 3x：小字号数字（成绩/学号）明显少漏
    - SHARPEN：锐化边缘
    """
    g = img.convert("L")
    g = ImageOps.autocontrast(g)
    g = g.resize((int(g.width * scale), int(g.height * scale)), Image.LANCZOS)
    g = g.filter(ImageFilter.SHARPEN)
    return g


def _to_score(s) -> float:
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def run(image: Path, scale: float = 3.0, min_score: float = 0.3) -> list[dict]:
    engine = RapidOCR()
    items = []

    # 主识别：增强后大图
    pil = Image.open(image).convert("RGB")
    result, _ = engine(np.array(preprocess(pil, scale)))
    seen = set()
    for box, text, score in result or []:
        sc = _to_score(score)
        if sc < min_score or text in seen:
            continue
        seen.add(text)
        xs = [p[0] / scale for p in box]
        ys = [p[1] / scale for p in box]
        items.append(
            {
                "text": text,
                "confidence": round(sc, 4),
                "x0": round(min(xs)),
                "y0": round(min(ys)),
                "x1": round(max(xs)),
                "y1": round(max(ys)),
            }
        )

    # 若主识别空/极少，回退原尺寸再试一次（防过度放大失真）
    if len(items) <= 2:
        result2, _ = engine(np.array(pil))
        for box, text, score in result2 or []:
            sc = _to_score(score)
            if sc < min_score or text in seen:
                continue
            seen.add(text)
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            items.append(
                {
                    "text": text,
                    "confidence": round(sc, 4),
                    "x0": round(min(xs)),
                    "y0": round(min(ys)),
                    "x1": round(max(xs)),
                    "y1": round(max(ys)),
                }
            )

    # 按从上到下、从左到右排序（文档阅读顺序）
    items.sort(key=lambda d: (d["y0"] // 18, d["x0"]))
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="RapidOCR 图片文字识别（自动预处理增强）")
    parser.add_argument("image", help="图片路径，支持 png / jpg / webp")
    parser.add_argument("--json", action="store_true", help="输出 JSON（含坐标与置信度）")
    parser.add_argument("--min-score", type=float, default=0.3, help="置信度下限，默认 0.3")
    parser.add_argument("--scale", type=float, default=3.0, help="放大倍率，默认 3.0（越大越吃内存）")
    args = parser.parse_args()

    image = Path(args.image)
    if not image.is_file():
        print(f"找不到图片: {image}", file=sys.stderr)
        return 1

    items = [i for i in run(image, args.scale, args.min_score) if i["confidence"] >= args.min_score]

    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        for item in items:
            print(item["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
