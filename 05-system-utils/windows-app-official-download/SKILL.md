---
name: windows-app-official-download
agent_created: true
summary: 帮用户在 Windows 上取得软件的官方正版安装包（尤其遇到地区限制时），并做来源与安全校验。只下载、不代装、不改系统设置。
description: >
  查找并下载 Windows 软件的**官方正版安装包**，并验证签名与无木马。
  触发词：下载 XX 的 Windows/电脑/PC 版、地区问题下不了、微软商店显示不可用、区域限制、
  官方正版无毒包、第三方下载站不放心、有没有原生 Win 版、离线安装包、直链。
  核心能力：①判定某软件到底有没有原生 Windows 版 ②从官方 CDN 取直链（含 JS 渲染页面）
  ③Authenticode 签名 + Defender 双重校验 ④绕开 Store 区域限制的正确姿势。
  不适用于：破解/激活/去广告（不做）；Linux/macOS 软件（流程不同）。
---

# Windows 软件官方包获取与校验

## 硬约束（红线，任何情况不越）

1. **只下载，不代运行。** 装不装由用户决定，绝不替用户双击安装器、不静默安装。
2. **不改任何系统设置**：不动区域/语言、代理、环境变量、注册表、组策略、UAC、虚拟化开关。
   需要用户改的，只给操作步骤让他自己改。
3. **不碰第三方下载站**（pcsoft / dddooo / itmop / 下载之家 等）。
   它们的"XX 电脑版 vX.X 含模拟器"＝ APK + 模拟器重打包，是捆绑广告与木马重灾区。
4. 交付前**必须**给出签名校验结果；签名无效或无法核实时，明确告知风险，不粉饰。

## 流程（六步，顺序敏感）

### 1. 先判定有没有原生 Windows 版
- 官网首页：抓回来 grep `windows|win|\.exe|\.msi|\.apk|\.dmg`。只有 iOS/Android 入口 → 无原生版。
- `winget search "<软件名>" --accept-source-agreements`（只读，不改系统）。搜不到不代表没有，
  只作旁证。

### 2. 查 Microsoft Store 判定分发形态
```bash
curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0" \
  "https://apps.microsoft.com/detail/<slug>?hl=zh-CN&gl=CN" -o store.html
```
在 HTML 内 grep `installer|catalogSource|packageFamilyNames|skuId`，**不要**用 WebFetch
（页面是 JS 渲染，WebFetch 只能拿到 `<title>`）。判读见 `references/store-forensics.md`。

| `installer.type` | 含义 | 能不能拿到独立包 |
|---|---|---|
| 有 `packageFamilyNames` 非空 | 原生 MSIX/APPX | ✅ 可取离线包 |
| `TencentAndroid` / 空数组 | 安卓兼容层（如应用宝） | ❌ 只能走商店或对应渠道客户端 |

### 3. 取官方直链
官网是 Next.js / SPA 渲染时，HTML 里没有直链。抓前端 chunk 再 grep：
```bash
# 从页面 HTML 提取所有 /_next/static/chunks/*.js，逐个下载后 grep：
#   \.exe   installer   down\..*\.qq\.com   downloadUrl
```
**官网常把下载直链硬编码在 `_app-*.js` 这类 chunk 里**（实测有效）。
优先取"无渠道号"的通用路径，其次才用渠道包。

### 4. 下载
```bash
curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0" \
  -e "<官网下载页URL>" "<直链>" -o "<软件名>_官方安装包.exe"
```
带 `-e` 带上 referer，避免 CDN 防盗链。下载后立刻算 MD5/SHA1/SHA256 并核对 `MZ` 头。

### 5. 校验（双保险）
见 `references/verify-playbook.md`。要点：
- `Get-AuthenticodeSignature` → **Status 必须 Valid**，核对签名者主体是不是真厂商。
- Defender 交叉验证 → **必须用 `Get-MpThreatDetection` 复核**。

### 6. 交付
`present_files` 给安装包；正文写清：版本/大小/哈希/签名者/有效期/
是否在线安装器（需联网拉组件）/安装步骤。临时文件清理干净。

## 三个致命坑

1. **Defender ExitCode 2 ≠ 检出病毒。** `MpCmdRun -Scan -ScanType 3` 非管理员下返回
   `hr = 0x80004005`（E_FAIL），退出码 2，是**权限失败**。必须用 `Get-MpThreatDetection`
   查威胁记录来判定。看到 ExitCode 2 别慌着报毒，也别去提权（会弹窗打扰用户）。
2. **PowerShell 工具在本机不返回 stdout。** 命令正常执行但输出为空，必须
   `| Out-File <path> -Encoding utf8` 再用 Read 读文件。
3. **`curl -o /tmp/x.json` 在 Git Bash 下可能静默失败**（文件不存在）。
   一律用工作区绝对路径，别用 `/tmp`。

## 判例（已验证，可直接引用）

- **不背单词**：无原生 Win 版。Store 页 `catalogSource=TencentAppStore`、
  `installer.type=TencentAndroid`、`PackageId=cn.com.langeasy.LangEasyLexis`、
  `packageFamilyNames=[]` → 无独立包。绕法＝装**腾讯应用宝电脑版**再内置市场搜。
  应用宝官方直链硬编码在 `_app-*.js`：`https://down.pc.yyb.qq.com/channel/55/115/10000/pcyyb__installer.exe`
  （6.31MB 在线引导器，ProductName `Androws`，需联网拉组件）。

## 参考文件（按需 Read，勿一次全读）

- `references/store-forensics.md` — Store 页抓取、字段判读、区域限制成因与绕法
- `references/verify-playbook.md` — 签名校验、Defender 扫描、常见误判对照表
