from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR


def run(image: Path) -> list[dict]:
    engine = RapidOCR()
    result, _ = engine(str(image))
    if not result:
        return []
    items = []
    for box, text, score in result:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        items.append(
            {
                "text": text,
                "confidence": round(float(score), 4),
                "x0": round(min(xs)),
                "y0": round(min(ys)),
                "x1": round(max(xs)),
                "y1": round(max(ys)),
            }
        )
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="RapidOCR 图片文字识别")
    parser.add_argument("image", help="图片路径，支持 png / jpg / webp")
    parser.add_argument("--json", action="store_true", help="输出 JSON（含坐标与置信度）")
    parser.add_argument("--min-score", type=float, default=0.5, help="置信度下限，默认 0.5")
    args = parser.parse_args()

    image = Path(args.image)
    if not image.is_file():
        print(f"找不到图片: {image}", file=sys.stderr)
        return 1

    items = [i for i in run(image) if i["confidence"] >= args.min_score]

    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        for item in items:
            print(item["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
