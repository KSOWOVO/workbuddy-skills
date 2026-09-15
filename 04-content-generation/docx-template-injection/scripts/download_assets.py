# -*- coding: utf-8 -*-
"""
下载案例真实图片素材（官方素材，用于课程作业的图文并茂）
来源1：哔哩哔哩 官方PV封面（游戏科学官方账号发布，即官方宣传海报）
来源2：Steam 商店页 官方游戏截图 / 主视觉（开发商自行上传的官方素材）
输出：assets/*.png
"""
import os, sys, json, ssl, time, io, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
ssl._create_default_https_context = ssl._create_unverified_context
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AD = os.path.join(BASE, "assets")
os.makedirs(AD, exist_ok=True)

OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
OP.addheaders = [
    ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    ("Referer", "https://www.bilibili.com/"),
]


def fetch(url, retry=3):
    for i in range(retry):
        try:
            return OP.open(url, timeout=40).read()
        except Exception as e:
            if i == retry - 1:
                print("   [失败]", url[:70], e)
                return None
            time.sleep(1.5)


def save_png(data, name, min_w=600):
    """保存为 PNG；过小的图跳过"""
    try:
        im = Image.open(io.BytesIO(data))
        im = im.convert("RGB")
        if im.width < min_w:
            print("   [跳过] %s 尺寸过小 %dx%d" % (name, im.width, im.height))
            return False
        p = os.path.join(AD, name + ".png")
        im.save(p, "PNG", optimize=True)
        print("   ✔ %-26s %dx%d  %.0f KB" % (name + ".png", im.width, im.height,
                                             os.path.getsize(p) / 1024))
        return True
    except Exception as e:
        print("   [失败]", name, e)
        return False


print("=" * 70)
print("【来源1】哔哩哔哩 官方PV封面（官方宣传海报）")
print("=" * 70)
PVS = [
    ("wukong_13min", "BV1x54y1e7zf", "《黑神话：悟空》13分钟实机演示"),
    ("wukong_ue5",   "BV1y64y1q757", "《黑神话：悟空》UE5实机测试集锦"),
    ("wukong_final", "BV1oH4y1c7Kk", "《黑神话：悟空》最终预告"),
    ("wukong_story", "BV1tN4y1F79k", "《黑神话：悟空》6分钟实机剧情片段"),
    ("zhongkui_teaser", "BV1sHePzWEbG", "《黑神话：钟馗》先导预告"),
    ("zhongkui_15min",  "BV1kS8H6VERt", "《黑神话：钟馗》15分钟实机演示"),
]
posters = {}
for name, bvid, title in PVS:
    try:
        r = json.loads(OP.open(
            "https://api.bilibili.com/x/web-interface/view?bvid=" + bvid, timeout=25
        ).read().decode("utf-8"))
        if r.get("code") != 0:
            print("   [无数据]", bvid); continue
        pic = r["data"]["pic"].replace("http://", "https://")
        data = fetch(pic)
        if data and save_png(data, name):
            posters[name] = {"file": name + ".png", "title": title,
                             "author": r["data"]["owner"]["name"],
                             "src": pic, "bvid": bvid}
    except Exception as e:
        print("   [异常]", bvid, e)
    time.sleep(0.7)

print()
print("=" * 70)
print("【来源2】Steam 商店页 官方素材（开发商上传）")
print("=" * 70)
steam_ok = []
try:
    s = json.loads(OP.open(
        "https://store.steampowered.com/api/appdetails?appids=2358720&l=schinese",
        timeout=30).read().decode("utf-8"))
    d = s["2358720"]["data"]
    # 主视觉
    hdr = d.get("header_image")
    if hdr:
        dt = fetch(hdr)
        if dt and save_png(dt, "steam_header"):
            steam_ok.append(("steam_header.png", "《黑神话：悟空》官方主视觉"))
    # 游戏截图
    for i, sc in enumerate(d.get("screenshots", [])[:6], 1):
        dt = fetch(sc["path_full"])
        if dt and save_png(dt, "steam_shot%d" % i):
            steam_ok.append(("steam_shot%d.png" % i, "游戏实机画面（官方截图 %d）" % i))
        time.sleep(0.6)
except Exception as e:
    print("   Steam 获取失败:", e)

# 写入素材清单
manifest = {"posters": posters, "steam": steam_ok}
with open(os.path.join(AD, "assets_manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

print()
print("=" * 70)
print("素材清单已写入 assets/assets_manifest.json")
print("共下载：海报 %d 张 + Steam 素材 %d 张" % (len(posters), len(steam_ok)))
for f in sorted(os.listdir(AD)):
    if f.endswith(".png"):
        print("   ", f, "%.0f KB" % (os.path.getsize(os.path.join(AD, f)) / 1024))
