#!/usr/bin/env python3
"""查询天天基金 QDII / 跨境基金的当日申购状态与单日申购上限。

用法:
  python quota.py 007721,050025,017641 --need=20
  python quota.py 018738 096001 --need=10

--need=N  按"每天投 N 元"标注该份额是否装得下（OK / X）
输出: 代码 | 简称 | 状态 | 单日上限 | 判定
"""
import sys
import json
import re
import urllib.request

API = ("https://fundmobapi.eastmoney.com/FundMApi/FundBaseTypeInformation.ashx"
       "?FCODE={code}&deviceid=Wap&plat=Wap&product=EFund&version=2.0.0&appType=ttjj")


def fetch(code):
    req = urllib.request.Request(
        API.format(code=code),
        headers={
            "User-Agent": "EMProjJijin/6.4.0",
            "Referer": "https://fund.eastmoney.com/",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        d = json.load(resp).get("Datas") or {}
    sgzt = d.get("SGZT") or ""
    m = re.search(r"上限\s*([\d,]+)\s*元", sgzt)
    limit = float(m.group(1).replace(",", "")) if m else None
    return {
        "code": code,
        "name": d.get("SHORTNAME") or "-",
        "status": (sgzt.split("(")[0] or sgzt or "-"),
        "limit": limit,
        "min_buy": d.get("MINSG") or "-",
        "redeem": d.get("SHZT") or "-",
    }


def main():
    need = 0.0
    codes = []
    for a in sys.argv[1:]:
        if a.startswith("--need="):
            need = float(a.split("=", 1)[1])
        else:
            codes += [c.strip() for c in a.split(",") if c.strip()]
    if not codes:
        print(__doc__)
        return

    rows = [fetch(c) for c in codes]
    width = max(len(r["name"]) for r in rows)
    for r in rows:
        lim = r["limit"]
        lim_s = str(int(lim)) if lim is not None else "-"
        if not need:
            flag = ""
        elif lim is None:
            flag = "?"
        else:
            flag = "OK" if lim >= need else "X"
        print("{code}  {name:<{w}}  {status:<6}  上限={lim:>6} 起投={min_buy:>3}  {flag}".format(
            code=r["code"], name=r["name"], w=width, status=r["status"],
            lim=lim_s, min_buy=r["min_buy"], flag=flag))


if __name__ == "__main__":
    main()
