# -*- coding: utf-8 -*-
"""
段落小标题生成 —— 从转录内容里提取主题，给长段落加导航。

★ 设计红线（延续 polisher 的原则）：
   小标题必须**从该段原文里提取**，不能凭空生成。
   因为一旦是我「想」出来的，就脱离了原意，回到不可复现的幻觉。

做法（纯规则，不做语义推断）：
  1. 按时间间隔切「话题块」——间隔 > 阈值说明讲者在换话题/停顿
  2. 对每个块，用 TF 词频找出最能代表它的词
  3. 标题格式：▎<关键词1> · <关键词2>（最多 2 个）
  4. 块太短（< 阈值字数）不单独起标题，避免标题比正文还密

这样生成的标题有个天然优点：**它们全是你视频里真讲过的词**，
扫一眼标题就知道这段在讲什么，还能当搜索索引。
"""
import re
from collections import Counter

CJK = r"\u4e00-\u9fff"

# 中文停用词（只收高频无实义的）
STOP = set("""
的 了 是 我 你 他 她 它 们 这 那 这个 那个 一个 什么 怎么 就是 还是 但是 因为 所以
然后 而且 如果 可以 需要 应该 大家 我们 你们 他们 咱们 自己 的时候 这些东西 什么样
其实 真的 非常 特别 一定 可能 已经 现在 这样 那样 有些 很多 的话 对吧 好吧
ok OK 对 好 嗯 啊 哦 呃 就是 不是 有没有 是不是 知道 明白 觉得 认为
一般 情况 时候 地方 东西 事情 意思 部分 上面 下面 里面 前面 后面 一般情况
""".split())

# 虚词：以这些字开头或结尾的 n-gram 一律丢弃（避免「的使」这类碎片）
# ⚠️ 必须含「们 咱」——否则会产出「们的中文」这种碎片标题
FUNC_CHARS = set("的了着过和与及或而但就都也还很太更最把被让使给对于在从向到"
                 "这那哪什么怎样吗呢吧啊哦嗯呃呀哇噢们咱又再只才没别请您")

# 英文停用词
STOP_EN = set("""
the a an and or but if then of to in on at for with is are was were be been
you your we our they their it this that these those do does did what how
so very can could would should may might will just not no yes ok
""".split())


def _bad_gram(g: str) -> bool:
    """判断一个 n-gram 是不是无意义的碎片。"""
    if g in STOP:
        return True
    if g[0] in FUNC_CHARS or g[-1] in FUNC_CHARS:
        return True
    # 全是虚词
    if all(c in FUNC_CHARS for c in g):
        return True
    return False


def _tokens(text: str) -> list[str]:
    """
    粗分词：中文 2-6 字词组 + 英文单词。不依赖分词库。

    ⚠️ 窗口必须开到 6 字：语法类术语普遍是 4-5 字
    （形容词从句 / 主语从句 / 宾语补语从句 / 同位语从句）。
    旧版只开 2-3 字，直接导致「形容 · 容词」「语从句 · 句子」这种碎片标题。
    """
    toks: list[str] = []
    # 英文
    for w in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text):
        wl = w.lower()
        if wl not in STOP_EN:
            toks.append(wl)
    # 中文：滑窗 2-6 字，交给 _pick_title 的「长词压制短词」去筛
    zh = re.sub(rf"[^{CJK}]", " ", text)
    for seg in zh.split():
        for n in range(2, 7):
            for i in range(len(seg) - n + 1):
                g = seg[i:i + n]
                if not _bad_gram(g):
                    toks.append(g)
    return toks


def _pick_title(block: list[dict], topn: int = 2) -> str:
    """
    从一个话题块里挑最代表性的词。

    ★ 关键规则：**长词压制短词**。
    短词是长词的子串时，出现次数天然 ≥ 长词，纯按频次选必然选中碎片
    （「语从句」压过「主语从句」、「形容」压过「形容词」）。
    所以：若存在更长的词 h 包含当前词 w，且 cnt[h] >= 0.6 * cnt[w]，
    就丢弃 w —— 说明这个字串的“完整形态”才是真正反复出现的单位。
    """
    txt = " ".join(s["text"] for s in block)
    toks = _tokens(txt)
    if not toks:
        return ""
    cnt = Counter(toks)

    cand = [(w, c) for w, c in cnt.items() if c >= 2]
    if not cand:
        cand = cnt.most_common(4)
    # 频次优先；同频次时长的优先
    cand.sort(key=lambda x: (-x[1], -len(x[0])))

    # 按长度建索引，便于快速找「更长的包含词」
    by_len: dict[int, list[str]] = {}
    for k in cnt:
        by_len.setdefault(len(k), []).append(k)

    def suppressed(w: str, c: int) -> bool:
        for L in range(len(w) + 1, min(len(w) + 3, 9)):
            for h in by_len.get(L, ()):
                if w in h and cnt[h] >= 0.6 * c:
                    return True
        return False

    kept: list[str] = []
    for w, c in cand:
        if any(w in p or p in w for p in kept):
            continue
        if suppressed(w, c):
            continue
        kept.append(w)
        if len(kept) >= topn:
            break

    # 兜底：全被压制就取频次最高的那个（总比没有标题好）
    if not kept and cand:
        kept = [cand[0][0]]

    # 中文词之间用「 · 」连接，更清爽
    return " · ".join(kept) if kept else ""


def segment_topics(segments: list[dict], gap_threshold: float = 4.0,
                   min_block_chars: int = 120,
                   max_block_chars: int = 900,
                   target_blocks: int | None = None) -> list[dict]:
    """
    把转录段切成「话题块」，每块给一个小标题。

    切分依据（两条，任一满足即切）：
      1. 时间间隔 >= gap_threshold —— 讲者停顿较久，通常在换话题
      2. 块内字数超过 max_block_chars —— 强制切开，避免一整页没导航

    合并依据：块内字数 < min_block_chars 就并进上一块，
              避免出现「标题比正文还长」的碎片块。

    返回 [{ts, title, start_idx, end_idx, text_len}]
    """
    if not segments:
        return []

    # 1. 先按时间间隔切初稿
    blocks: list[list[dict]] = [[segments[0]]]
    for seg in segments[1:]:
        gap = seg["start"] - blocks[-1][-1]["end"]
        if gap >= gap_threshold:
            blocks.append([seg])
        else:
            blocks[-1].append(seg)

    # 2. 合并过小的块
    merged: list[list[dict]] = []
    for b in blocks:
        n = sum(len(s["text"]) for s in b)
        if merged and n < min_block_chars:
            merged[-1].extend(b)
        else:
            merged.append(b)

    # 3. 切分过大的块（按累计字数均分，保证每块都有导航）
    split: list[list[dict]] = []
    for b in merged:
        total = sum(len(s["text"]) for s in b)
        if total <= max_block_chars or len(b) < 4:
            split.append(b)
            continue
        n_parts = max(2, round(total / max_block_chars))
        per = total / n_parts
        cur: list[dict] = []
        acc = 0
        for s in b:
            cur.append(s)
            acc += len(s["text"])
            # 达到均分阈值且后面还有内容 -> 收一块
            if acc >= per and len(split) < len(merged) + n_parts:
                split.append(cur)
                cur = []
                acc = 0
        if cur:
            # 尾块太短就并回上一块
            if split and sum(len(x["text"]) for x in cur) < min_block_chars:
                split[-1].extend(cur)
            else:
                split.append(cur)

    # 4. 生成标题
    out = []
    for b in split:
        title = _pick_title(b)
        out.append({
            "ts": b[0]["start"],
            "title": title,
            "start_idx": segments.index(b[0]),
            "end_idx": segments.index(b[-1]),
            "text_len": sum(len(s["text"]) for s in b),
        })
    return out


if __name__ == "__main__":
    demo = [
        {"start": 0, "end": 4, "text": "OK 大家好，我是卡萨。本期视频我们正式开始讲雅思大作文写作。"},
        {"start": 4, "end": 9, "text": "雅思作文本质上是填空题。我可以给大家讲每种题型对应模板，与其说模板不如说是结构。"},
        {"start": 9, "end": 14, "text": "很多人谈模板就觉得用了模板会被判抄袭，但事实上不是这样的。"},
        {"start": 20, "end": 26, "text": "我先讲语法的重要性。语法真的非常重要，作文 6.5 不需要很高的语法水平。"},
        {"start": 26, "end": 32, "text": "但一定要懂基本语法体系，比如简单句的五种基本句型、连词的用法、定语从句。"},
        {"start": 32, "end": 38, "text": "定语从句和状语从句的使用、介词的使用、不定式的使用都要熟练。"},
        {"start": 45, "end": 52, "text": "接下来看雅思考试的抓大放小。大作文分值三分之二，小作文三分之一。"},
        {"start": 52, "end": 58, "text": "所以大作文是主要矛盾，你要把三分之二的分数拿到手，小作文随便写六分也是 6.5。"},
    ]
    print("生成的小标题：\n")
    for t in segment_topics(demo):
        print(f"  [{t['ts']:>3.0f}s]  ▎{t['title']}")
