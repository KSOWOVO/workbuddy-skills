# -*- coding: utf-8 -*-
"""
proofread_batch.py —— 批量校对 Whisper 中文同音误识别

核心洞察（2026-09-22 实测）：
  Whisper 对中文的同音误识别是**跨文件高度重复**的。
  同一个「从句」，在 19 个文件里会被用同样的几种方式听错。
  所以**一个统一的纠正词典可以一次修完所有文件**，
  比逐个文件人工读要快一个数量级；之后再逐文件抽查补特例即可。

原则（Kelsen 铁律）：「只改听错的词，绝不改意思」。
  拿不准的一律不动，只记录到报告里交人判断。
"""
import argparse
import glob
import json
import os
import re
import sys

# ---------------- 纠正词典 ----------------
# 顺序很重要：**长短语必须排在通用词前面**，否则会被通用规则先吃掉。

PHRASES = [
    # —— 副词从句的四类错形（先处理完整短语）——
    ("复制重句", "副词从句"), ("复制从具", "副词从句"), ("复制从句", "副词从句"),
    ("复次从句", "副词从句"), ("复次从举", "副词从句"),
    ("复次冲击", "副词从句"), ("复次从具", "副词从句"), ("复次从剧", "副词从句"),
    ("条件复词重聚", "条件副词从句"), ("条件复词从句", "条件副词从句"),
    ("方式复词重聚", "方式副词从句"), ("方式复词从句", "方式副词从句"),
    ("方式复次从句", "方式副词从句"),
    ("地点复词冲剧", "地点副词从句"), ("地点复词从句", "地点副词从句"),
    ("比较壮与从剧", "比较状语从句"),
    ("时间复次从举", "时间副词从句"), ("时间状与冲剧", "时间状语从句"),
    ("原音副词从句", "原因副词从句"), ("原音状语从句", "原因状语从句"),
    # —— 专有名词 ——
    ("英语 tool 我", "英语兔我"), ("英语突围", "英语兔"),
    ("英语托", "英语兔"), ("英语图", "英语兔"),
    # —— 句子成分术语 ——
    ("同位于从句", "同位语从句"), ("同文语从句", "同位语从句"),
    ("同文语", "同位语"), ("同语从句", "同位语从句"), ("同谓语", "同位语"),
    ("主语冲句", "主语从句"), ("主语冲剧", "主语从句"), ("主语重句", "主语从句"),
    ("宾语重句", "宾语从句"), ("逐语从句", "主语从句"),
    ("标语从句", "表语从句"), ("表语冲剧", "表语从句"),
    ("定语冲句", "定语从句"), ("方式状语冲剧", "方式状语从句"),
    ("形容词冲剧", "形容词从句"),
    ("毕动词", "be 动词"),
    ("位于动词", "谓语动词"), ("位语动词", "谓语动词"), ("尾语动词", "谓语动词"),
    ("不吉误动词", "不及物动词"), ("单吉误动词", "单及物动词"),
    ("双吉误动词", "双及物动词"), ("复杂吉误动词", "复杂及物动词"),
    ("复杂集误动词", "复杂及物动词"),
    ("连细动词", "联系动词"), ("细动词", "系动词"),
    ("形式主义没有实际意义", "形式主语没有实际意义"),
    ("只带物体的代词", "指代物体的代词"),
    ("一问代词", "疑问代词"), ("一问副词", "疑问副词"),
    ("借词参与", "介词参与"),
    # —— 其他高频错词 ——
    ("形态助词", "情态动词"),
    ("将来事态", "将来时态"), ("实态视频", "时态视频"), ("在实态上", "在时态上"),
    ("竹子翻译", "逐字翻译"), ("好像迟太远", "好像扯太远"),
    ("打在公平上", "打在公屏上"), ("逗好隔开", "逗号隔开"),
    ("修是 reason", "修饰 reason"), ("修是 day", "修饰 day"),
    ("后制的", "后置的"), ("拆剧", "拆句"), ("旁杂", "庞杂"),
    ("toOK", "took"), ("loOK", "look"), ("pop a rabbit", "Papa Rabbit"),
    # —— 英文粘连（补空格）——
    ("carrotwhich", "carrot which"), ("carrotas ", "carrot as "),
    ("carrotat ", "carrot at "), ("videoyou ", "video you "),
    ("reasonfor ", "reason for "), ("hungryso ", "hungry so "),
    ("videoso ", "video so "), ("carrotthat ", "carrot that "),
    ("sinceSince", "since / Since"), ("asbecause", "as / because"),
    ("whereverywhereanywhere", "wherever / where / anywhere"),
    ("thougheven thoughbut", "though / even though / but"),
    # —— 2026-09-22 跨 18 文件扫描出的高频道错词（按频次）——
    # 借词 53 处 -> 介词（全部上下文均为「借词短语/时间借词」）
    ("借词短语", "介词短语"), ("时间借词", "时间介词"),
    ("借词", "介词"),
    # 贯词 41 处 -> 冠词
    ("不定贯词", "不定冠词"), ("定贯词", "定冠词"), ("零贯词", "零冠词"),
    ("贯词", "冠词"),
    # 道中 14 处 -> 倒装
    ("道中句", "倒装句"), ("道装", "倒装"), ("道中", "倒装"),
    # 主位一致 -> 主谓一致
    ("主位一致", "主谓一致"), ("主位", "主谓"),
    # 英语法 -> 英语语法
    ("英语法上", "英语语法上"), ("英语法", "英语语法"),
    # 原音 14 处 -> 元音
    ("原音字母", "元音字母"), ("原音", "元音"),
    ("音速", "音素"),
    # —— 冠词 / 音系类（第 1 个视频实测）——
    ("你也学会想", "你也许会想"),
    ("a，n，the", "a，an，the"), ("a, n, the", "a, an, the"),
    # —— 限定词篇（小A 校对实测发现，2026-09-24）——
    ("古名思义", "顾名思义"), ("听图一席话", "听兔一席话"),
    ("名词所有个", "名词所有格"), ("语文代词", "疑问代词"),
    ("固定代词", "不定代词"), ("计数词", "基数词"), ("积数词", "基数词"),
    ("叙述词", "序数词"), ("限定特质", "限定特指"),
    ("前卫限定词", "前位限定词"), ("中卫限定词", "中位限定词"),
    ("后卫限定词", "后位限定词"), ("具意", "句意"),
    # —— 通用兜底（放最后）——
    ("重聚", "从句"), ("从具", "从句"), ("从剧", "从句"), ("从举", "从句"),
    ("冲剧", "从句"), ("冲句", "从句"), ("重句", "从句"),
    ("复词", "副词"), ("复次", "副词"),
    ("编语", "宾语"), ("兵语", "宾语"), ("谱语", "补语"), ("主剧", "主句"),
]

# 「从去」单独处理，避免误伤「从去年」
SPECIAL = [("后面的从去", "后面的从句"), ("时间点从去引导词", "时间点从句引导词")]

# 需整行拆开的粘连英文（值里用 \n\n 分行）
SPLITS = {
    "I bought the carrotThe rabbit ate a carrot":
        "I bought the carrot\n\nThe rabbit ate a carrot",
    "I saw the teacher yesterdayThe teacher's favorite food is carrot":
        "I saw the teacher yesterday\n\nThe teacher's favorite food is carrot",
    "a teacher who is a rabbita teacher whom I saw yesterday":
        "a teacher who is a rabbit\n\na teacher whom I saw yesterday",
    "I saw who ate the carrotI saw what the rabbit ate":
        "I saw who ate the carrot\n\nI saw what the rabbit ate",
    "He is as smart as meThis carrot is as big as that one":
        "He is as smart as me\n\nThis carrot is as big as that one",
    "Because you like meYou have given all my videos":
        "Because you like me\n\nYou have given all my videos",
}


def fix(text):
    n = 0
    for a, b in SPLITS.items():
        if a in text:
            n += text.count(a)
            text = text.replace(a, b)
    for a, b in PHRASES + SPECIAL:
        c = text.count(a)
        if c:
            n += c
            text = text.replace(a, b)
    # 压掉连续空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="目录或文件")
    ap.add_argument("--apply", action="store_true", help="实际写入（默认只预演）")
    ap.add_argument("--report", default=None, help="写出统计 json")
    a = ap.parse_args()

    if os.path.isdir(a.target):
        files = sorted(glob.glob(os.path.join(a.target, "*.md")))
    else:
        files = [a.target]

    stat = []
    for p in files:
        s = open(p, encoding="utf-8").read()
        s2, n = fix(s)
        stat.append({"file": os.path.basename(p), "chars": len(s),
                     "fixes": n, "changed": n > 0})
        if a.apply and n:
            open(p, "w", encoding="utf-8").write(s2)

    tot = sum(x["fixes"] for x in stat)
    print("%s：%d 个文件，共修 %d 处"
          % ("已写入" if a.apply else "预演", len(files), tot))
    for x in stat:
        flag = "★" if x["fixes"] else " "
        print("  %s %-62s %5d 处  %6d 字"
              % (flag, x["file"][:60], x["fixes"], x["chars"]))
    if a.report:
        json.dump(stat, open(a.report, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
