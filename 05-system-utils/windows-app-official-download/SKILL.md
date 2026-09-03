---
name: windows-app-official-download
agent_created: true
summary: 帮用户在 Windows 上取得指定软件的官方正版安装包（含地区限制绕过），并做来源与安全校验。只下载、不代装、不改系统设置。
description: >
  查找并下载 Windows 软件的**官方正版安装包**，并验证签名与无木马。
  触发词：下载 XX 的 Windows/电脑/PC 版、地区问题下不了、微软商店显示不可用、区域限制、
  官方正版无毒包、第三方下载站不放心、有没有原生 Win 版、离线安装包、直链。
  核心能力：①判定某软件到底有没有原生 Windows 版 ②从官方动态接口取最新直链（不信硬编码常量）
  ③Authenticode 签名 + Defender 双重校验 ④版本三对照防下到旧包。
  不适用于：破解/激活/去广告（不做）；Linux/macOS 软件（流程不同）。
---

# Windows 软件官方包获取与校验

## 硬约束（红线，任何情况不越）

0. **要 A 就给 A，不准擅自换成 B。** 用户点名要某个软件，就算它不存在、就算 B 是"合理替代品"，
   也**不许把 B 当主交付**。先说「A 没有 Windows 原生包，这个我做不到」，**等用户点头**再找替代。
   ⚠️ 真实翻车：用户要「不背单词 win 版」，我擅自交付「腾讯应用宝电脑版」
   （不背单词的安卓载体），用户直接发火。技术判断再对，交付错东西＝做错事。
1. **只下载，不代运行。** 装不装由用户决定，绝不替用户双击安装器、不静默安装。
2. **不改任何系统设置**：不动区域/语言、代理、环境变量、注册表、组策略、UAC、虚拟化开关。
3. **不碰第三方下载站**（pcsoft / dddooo / itmop 等），其"XX 电脑版含模拟器"＝重打包，木马重灾区。
4. 交付前**必须**给出签名校验结果；签名无法核实就明说风险，不粉饰。

## 流程（六步，顺序敏感）

### 1. 判定有没有原生 Windows 版
官网首页 grep `windows|win|\.exe|\.msi|\.apk|\.dmg`；只有 iOS/Android 入口 → 无原生版。
`winget search "<名>" --accept-source-agreements`（只读）作旁证，搜不到不代表没有。
**判定无原生版 → 立刻如实告知用户，别自己找替代。**

### 2. 查 Microsoft Store 判定分发形态
```bash
curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0" \
  "https://apps.microsoft.com/detail/<slug>?hl=zh-CN&gl=CN" -o store.html
```
HTML 内 grep `installer|catalogSource|packageFamilyNames|skuId`。
**不要用 WebFetch**（JS 渲染，只能拿到 `<title>`）。判读见 `references/store-forensics.md`。

| `installer.type` | 含义 | 独立包 |
|---|---|---|
| `packageFamilyNames` 非空 | 原生 MSIX/APPX | ✅ |
| `TencentAndroid` / 空数组 | 安卓兼容层 | ❌ |

### 3. 取直链 —— 优先动态接口，别信硬编码常量
抓 `/_next/static/chunks/*.js`，grep `deliver|downloadUrl|fetch(|\.exe|installer`。
**优先级与直觉相反**：
- **动态接口**（`fetch(<API端点>)`）→ **首选**。多为 POST JSON，返回
  `{code,data:{download_url,version,md5}}`。参数靠报错反推（class-validator 会明说缺哪个字段、
  要什么类型），2-3 轮必出。实例见 `references/cases.md`。
- **硬编码常量** → **多半是 fallback 旧包**。⚠️ 实测：应用宝 chunk 里硬编码的链接是
  **2023-08 老包**，而动态接口给的是 3.0.3.11。**拿到先 `curl -sI | grep -i last-modified`**。

### 4. 下载
```bash
curl -sL -A "Mozilla/5.0 ... Chrome/120.0" -e "<官网下载页URL>" "<直链>" -o "<名>_官方安装包.exe"
```
带 `-e` 防防盗链。下载后算 MD5/SHA256 并核对 `MZ` 头。

### 5. 校验（三保险）
见 `references/verify-playbook.md`：
- `Get-AuthenticodeSignature` → **Status 必须 Valid**，核对签名者主体是真厂商。
- Defender → **必须用 `Get-MpThreatDetection` 复核**，别信 ExitCode。
- **版本三对照**（防下到旧包）：接口 `version`+`md5` ↔ 文件 MD5 ↔ PE `FileVersion`，三者一致。

### 6. 交付
`present_files`；正文写清版本/大小/哈希/签名者/是否在线安装器/安装步骤；清理临时文件。

## 三个致命坑

1. **Defender ExitCode 2 ≠ 检出病毒。** 非管理员下 `MpCmdRun -Scan -ScanType 3` 返回
   `hr = 0x80004005`、退出码 2，是**权限失败**。用 `Get-MpThreatDetection` 判定。别去提权。
2. **PowerShell 工具在本机不返回 stdout。** 必须 `| Out-File <path> -Encoding utf8` 再 Read。
3. **`curl -o /tmp/x.json` 在 Git Bash 下会静默失败。** 一律用工作区绝对路径。

## 参考文件（按需 Read，勿一次全读）

- `references/cases.md` — 腾讯应用宝 deliver 接口完整调用、fallback 陷阱、不背单词判例
- `references/store-forensics.md` — Store 页抓取、字段判读、区域限制成因
- `references/verify-playbook.md` — 签名校验、Defender 误判对照表
