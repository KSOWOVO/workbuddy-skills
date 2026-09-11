# Microsoft Store 页面取证与判读

## 抓页面的正确姿势

WebFetch 对 `apps.microsoft.com` **无效**（JS 渲染，只能拿到 `<title>`）。必须用 curl：

```bash
curl -sL -m 30 -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36" \
  "https://apps.microsoft.com/detail/<slug>?hl=zh-CN&gl=CN" -o store.html
```

加 `gl=CN` 才拿得到中国区目录数据。页面通常 400KB+，内含完整 `__NEXT_DATA__`。

## 关键字段与含义

在 HTML 里 grep 这些键，上下文各取 200 字符就够：

| 字段 | 在哪 | 说明 |
|---|---|---|
| `productId` | `"productId":"<slug>"` | 新版商店用 slug（如 `xpdnhn2q35g07w`），不是老的 9N 开头 ID |
| `skuId` | `skus[0].skuId` | 大写 slug，如 `XPDNHN2Q35G07W`，可拼进商店伪协议 |
| `installer.type` | `installer:{...}` | **最关键**，决定有没有独立包 |
| `installer.id` / `extras.PackageId` | 同上 | 安卓包名，可拿去应用宝网页端查详情 |
| `extras.VersionCode` | 同上 | 安卓内部版本号（如 `370`） |
| `catalogSource` | 顶层 | `TencentAppStore` = 腾讯应用宝目录，非微软原生 |
| `packageFamilyNames` | 顶层数组 | **空数组 = 没有可下载的 MSIX/APPX** |
| `marketDetails` | `"market":"CN","tier":1` | 区域可用性；tier 1 = 该区正常上架 |
| `productFamilyName` | `apps` / `games` | 通常无影响 |
| `displayPrice` | `"免费下载"` | 判断是否为付费应用 |

### installer.type 判读

```
"installer":{"type":"TencentAndroid","id":"cn.com.langeasy.LangEasyLexis",
             "extras":{"PackageId":"cn.com.langeasy.LangEasyLexis",
                       "VersionName":null,"VersionCode":"370"}}
```

- `type: TencentAndroid` → 腾讯应用宝安卓兼容层。本质是把安卓 App 跑在 Windows 上，
  **没有 exe / msix 可下载**，安装只能走：① Microsoft Store 客户端 ② 腾讯应用宝电脑版。
- `packageFamilyNames: []` 与上条互为印证。
- 若 `packageFamilyNames` 非空 → 原生 MSIX，可用 store.rg-adguard.net 或 Display Catalog API
  取微软 CDN 离线包（本 skill 未覆盖该分支，遇见过招拆招）。

## 区域限制的成因

搜索结果里常出现 "Kun tilgængelig i Kina-regionen"（仅中国区域可用）——这不是页面 bug，
是 `catalogSource=TencentAppStore` 类应用的固有属性。成因两类：

1. **微软账号区域非 CN** → 商店客户端直接拒绝购买/安装。
2. **网络出口被判为境外** → 目录返回空或不可购买。

### 绕法优先级

1. **首选：走渠道客户端，绕开商店。** 装腾讯应用宝电脑版（官方）→ 内置市场搜软件名 → 安装。
   与商店里那个"Windows 版"是同一套东西，但不经过微软账号区域校验。
2. **次选：给用户商店伪协议链接**，让他自己点：
   `ms-windows-store://pdp/?productid=<skuId>&catalog=TencentAppStore`
   仍受区域限制，仅在用户区域其实没问题、只是找不到入口时才有用。
3. **不选：改系统/账号区域。** 违反硬约束 2，只给步骤让用户自己决定。

## 用包名反查应用宝详情页

拿到安卓包名后可直接验证该软件在应用宝是否正规上架：

```bash
curl -sL -A "Mozilla/5.0 Chrome/120.0" \
  "https://sj.qq.com/myapp/detail.htm?apkName=<包名>" -o app.html
```

核对 `<link rel="canonical" href="https://sj.qq.com/appdetail/<包名>">` 与
`dt-params="...appdetail_status=常规详情页"`，确认是正规上架而非下架/风险应用。

## 商店独占（无独立安装包）的取证

用户要"安装包"、但官方只发商店时，**先如实告知，别拿 CLI 或旧版冒充**（红线 0）。三步取证：

**1. `winget show` 看真实身份**

```bash
winget show --id <商店ID> --source msstore --accept-source-agreements --disable-interactivity
```

看 `PackageName` / `Publisher` / 描述。**商店 ID 会随应用合并而变化，同名不同 ID 必须分辨。**

> 实测案例（2026-09）：`9PLM9XGG6VKS` = ChatGPT（OpenAI 发布，包族名仍是
> `OpenAI.Codex_2p2nqsd0c76g0`，由原 Codex 应用升级而来，内含 Codex 模式）；
> `9NT1R1C2HH7J` = **ChatGPT Classic 旧版，不带 Codex**。要 Codex 必须装前者。

**2. 官方包清单里有没有 CDN 直链**

```bash
curl -sL --http1.1 "https://storeedgefd.dsx.mp.microsoft.com/v9.0/packageManifests/<ID>?market=US&locale=en-us&deviceFamily=Windows.Desktop"
```

返回里**没有任何包下载 URL**（只有许可条款类链接）＝确无独立包。
`displaycatalog.mp.microsoft.com/v7.0/products/lookup` 端点会返回 **400**，别浪费时间。

**3. 离线 MSIX 拿不拿得到**

`winget download --id <ID> --source msstore` 会要求 **Microsoft Entra ID 身份验证**，
且账号须是全局管理员 / 用户管理员 / 许可证管理员成员 → **个人账号无解**。

## PE 头判定：这到底是 GUI 还是命令行

体积大不等于有图形界面。取前 16KB 读 PE 头即可定性：

```bash
# GitHub release 的 Range 请求在 302 链上会丢，先 -sIL 拿最终签名 URL 再 -r
curl -s --http1.1 -r 0-16383 "<最终 CDN 签名 URL>" -o head.bin
```

```python
import struct
d = open('head.bin','rb').read()
lf = struct.unpack_from('<I', d, 0x3c)[0]          # e_lfanew
opt = lf + 24                                       # Optional header 起点
sub = struct.unpack_from('<H', d, opt + 68)[0]      # subsystem
# 2 = GUI 窗口程序   3 = CUI 控制台（命令行）
```

> 实测：Codex 的 `codex-x86_64-pc-windows-msvc.exe` 有 281MB，看着像桌面应用，
> 但 `subsystem=3` —— 是 CLI，Rust 二进制内嵌资源导致体积虚高。
