# -*- coding: utf-8 -*-
"""
CStream 整理层 —— 转录稿 → 通顺文本（通顺不删减、纠错不改意）

对齐 Kelsen 既定铁律：「通顺不删减、纠错不改意」

★ 设计原则（重要）：
   本模块**只做机械、可审计、无歧义的整理**，绝不猜测词义。
   任何「这个词应该是那个词」的推测都属于改写，会引入幻觉且不可复现——
   那类修正留给 Nova 在对话里人工判断，不由脚本自动做。

只做这五件事：
  1. 合并被 VAD 切碎的短句
  2. 清理语气词与口吃重复（嗯嗯嗯 / 那个那个）
  3. 中英文之间补空格
  4. 中文语境下的英文标点转中文标点
  5. 空白与重复标点规整
"""
import re

CJK = r"\u4e00-\u9fff"

# 语气词与口吃：只删「确定无信息量」的
FILLER_PATTERNS = [
    (re.compile(r"[嗯呃啊哦]{2,}[，,、]?\s*"), ""),        # 连续 2+ 个语气词
    (re.compile(r"(\S{1,4})\1{2,}"), r"\1"),              # 同一词重复 3+ 次
    (re.compile(r"[，,]{2,}"), "，"),
    (re.compile(r"\s+"), " "),
]

# 安全替换：只有「写法统一」性质的，语义完全不变
SAFE_FIX = [
    ("Ok", "OK"),
    ("ok", "OK"),
]


def _space_cjk_latin(s: str) -> str:
    """中英文之间补空格，让混排更易读。"""
    s = re.sub(rf"([{CJK}])([A-Za-z0-9])", r"\1 \2", s)
    s = re.sub(rf"([A-Za-z0-9])([{CJK}])", r"\1 \2", s)
    return s


def _dedup_join(a: str, b: str, max_overlap: int = 12) -> str:
    """
    合并两段文本时去掉接缝处的重复。

    Whisper 分段常见问题：前段结尾与后段开头重复同几个字。
      例：「...我们正式开始讲雅思」+「雅思作文写作」
      期望：「...我们正式开始讲雅思作文写作」
    从长到短找重叠片段，找到就删掉后段的重复部分。
    """
    a = a.rstrip()
    b = b.lstrip()
    if not a or not b:
        return a + b
    limit = min(max_overlap, len(a), len(b))
    for n in range(limit, 1, -1):        # 至少 2 字重叠才处理，避免误删
        if a.endswith(b[:n]):
            return a + b[n:]
    return a + b


def merge_short_segments(segments: list[dict], max_gap: float = 1.5,
                         min_chars: int = 30) -> list[dict]:
    """
    合并被切碎的短段。
    Whisper + VAD 会把一句话切成好几段，读起来一顿一顿的。
    规则：前段字数不足 min_chars 且与后段间隔 < max_gap -> 合并。
    合并时用 _dedup_join 去掉接缝重复。
    """
    if not segments:
        return []
    out = [dict(segments[0])]
    for seg in segments[1:]:
        prev = out[-1]
        gap = seg["start"] - prev["end"]
        if gap <= max_gap and len(prev["text"]) < min_chars:
            prev["text"] = _dedup_join(prev["text"], seg["text"])
            prev["end"] = seg["end"]
        else:
            out.append(dict(seg))
    return out


def clean_text(t: str) -> str:
    """清洗单段文本。语义零改动，只做机械整理。"""
    s = t.strip()

    # 1. 语气词 / 口吃 / 重复标点
    for pat, rep in FILLER_PATTERNS:
        s = pat.sub(rep, s)

    # 2. 写法统一（语义不变）
    for k, v in SAFE_FIX:
        s = s.replace(k, v)

    # 3. 中英空格
    s = _space_cjk_latin(s)

    # 4. 中文语境下，英文标点转中文
    if re.search(rf"[{CJK}]", s):
        s = s.replace(",", "，").replace(";", "；")
        s = s.replace("?", "？").replace("!", "！")
        # 句号只改「中文后紧跟英文句点」的情况，避免破坏数字小数点
        s = re.sub(rf"([{CJK}])\.(\s|$)", r"\1。", s)

    # 5. 收尾规整
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^[，。、；！？]+", "", s)
    s = re.sub(r"([，。！？])\1+", r"\1", s)
    return s


def polish(segments: list[dict], do_merge: bool = True) -> list[dict]:
    """整理全部段落。"""
    segs = merge_short_segments(segments) if do_merge else [dict(s) for s in segments]
    out = []
    for s in segs:
        t = clean_text(s["text"])
        if not t:
            continue
        out.append({"start": s["start"], "end": s["end"], "text": t})
    return out


if __name__ == "__main__":
    demo = [
        {"start": 0.0, "end": 2.5, "text": "OK大家好，我是卡萨。"},
        {"start": 2.7, "end": 4.0, "text": "本期视频我们正式开始讲雅思"},
        {"start": 4.1, "end": 6.0, "text": "雅思作文写作"},
        {"start": 6.5, "end": 9.0, "text": "嗯嗯，如你所见，这期视频标题非常"},
        {"start": 9.1, "end": 12.0, "text": "非常的的的简单粗暴懂了吗?"},
    ]
    print("原始：")
    for s in demo:
        print("   ", s["text"])
    print("\n整理后（通顺不删减、语义零改动）：")
    for s in polish(demo):
        print("   ", f"[{s['start']:>5.1f}]", s["text"])
