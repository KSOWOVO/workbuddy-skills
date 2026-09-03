from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, ImageFilter


# ============ 多引擎 OCR（PaddleOCR 优先，RapidOCR 兜底）============
# 引擎优先级：
#   1. PaddleOCR（PP-OCRv6，识别率最高，~98%）
#   2. RapidOCR（ONNX 轻量，~95%，paddle 装不上/崩溃时自动回退）
# 首次运行任一引擎会自动下载模型，之后走本地缓存。

def _preprocess(img: Image.Image, scale: float = 3.0) -> Image.Image:
    """放大 + 灰度 + 自动对比度 + 锐化，提升小字识别率。"""
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


def _rows_from_boxes(items: list[dict], scale: float) -> list[dict]:
    for d in items:
        d["x0"] = round(d["x0"] / scale)
        d["y0"] = round(d["y0"] / scale)
        d["x1"] = round(d["x1"] / scale)
        d["y1"] = round(d["y1"] / scale)
    items.sort(key=lambda d: (d["y0"] // 18, d["x0"]))
    return items


def _engine_paddle():
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        lang="ch",
    )
    def recv(pil: Image.Image):
        tmp = Path(pil.filename) if hasattr(pil, "filename") else None
        if tmp and tmp.is_file():
            res = ocr.predict(str(tmp))
        else:
            res = ocr.predict(np.array(pil))
        lines = []
        for r in res:
            texts = r.get("rec_texts") or r.get("texts") or []
            for t in texts:
                lines.append(t)
        return lines
    return recv


def _engine_rapid():
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()
    def recv(pil: Image.Image, scale: float = 1.0, min_score: float = 0.3):
        result, _ = engine(np.array(pil))
        items, seen = [], set()
        for box, text, score in result or []:
            sc = _to_score(score)
            if sc < min_score or text in seen:
                continue
            seen.add(text)
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            items.append({
                "text": text, "confidence": round(sc, 4),
                "x0": round(min(xs)), "y0": round(min(ys)),
                "x1": round(max(xs)), "y1": round(max(ys)),
            })
        return items
    return recv


def run(image: Path, scale: float = 3.0, min_score: float = 0.3,
        prefer: str = "auto", verbose: bool = False) -> tuple[list[dict], str]:
    """识别图片，返回 (结果列表, 实际使用的引擎名)。

    prefer: auto（Paddle→Rapid 兜底）| paddle | rapid
    """
    pil_orig = Image.open(image).convert("RGB")
    used = ""
    items = []

    def try_engine(name):
        nonlocal used, items
        if used:
            return
        try:
            if name == "paddle":
                recv = _engine_paddle()
                # PaddleOCR 自带检测，传原图即可；内部对清晰图效果最好
                res = recv(pil_orig)
                seen = set()
                out = []
                for text in res:
                    if text in seen:
                        continue
                    seen.add(text)
                    out.append({"text": text, "confidence": 1.0,
                                "x0": 0, "y0": 0, "x1": 0, "y1": 0})
                items = out
            else:
                recv = _engine_rapid()
                big = _preprocess(pil_orig, scale)
                items = recv(big, scale, min_score)
                items = _rows_from_boxes(items, scale)
            used = name
        except Exception as e:
            if verbose:
                print(f"[ocr] 引擎 {name} 失败: {e}", file=sys.stderr)
            items = []

    if prefer in ("paddle", "rapid"):
        try_engine(prefer)
        if not used:
            try_engine("rapid" if prefer == "paddle" else "paddle")
    else:
        try_engine("paddle")
        if not used:
            try_engine("rapid")

    return items, used


def main() -> int:
    ap = argparse.ArgumentParser(description="多引擎 OCR：PaddleOCR 优先，RapidOCR 兜底")
    ap.add_argument("image", help="图片路径 png/jpg/webp")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--min-score", type=float, default=0.3)
    ap.add_argument("--scale", type=float, default=3.0, help="RapidOCR 放大倍率")
    ap.add_argument("--engine", default="auto", choices=["auto", "paddle", "rapid"],
                    help="引擎选择：auto 自动（默认）")
    ap.add_argument("-v", "--verbose", action="store_true", help="打印引擎切换信息")
    args = ap.parse_args()

    image = Path(args.image)
    if not image.is_file():
        print(f"找不到图片: {image}", file=sys.stderr)
        return 1

    items, used = run(image, args.scale, args.min_score, args.engine, args.verbose)
    if not items:
        print(f"[ocr] 所有引擎均未识别到文字", file=sys.stderr)
        return 2

    if args.json:
        payload = {"engine": used, "items": items}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if args.verbose:
            print(f"[ocr] 引擎: {used}", file=sys.stderr)
        for it in items:
            print(it["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
