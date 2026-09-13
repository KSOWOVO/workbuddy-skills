---
name: phone-audio-to-pc
description: 把安卓手机的系统声音转发到 Windows 电脑（从电脑耳机/音箱出），纯音频、不投屏；也覆盖蓝牙/系统自带等备选。触发词：手机声音到电脑、手机音频转发、手机外放转到电脑、听不到手机声音、手机声音进耳机、手机声音进电脑、音频转发、scrcpy 音频、电脑当手机音箱、音频流转、手机不出声。适用小米/澎湃 OS + Windows 11。
agent_created: true
---

# 手机声音 → 电脑（纯音频）

## 0. 先判方向（最容易翻车的一步）

这个需求几乎永远是「**手机播放的声音 → 电脑输出设备**」。
市面上大量"手机当音箱"工具其实是**反方向**，先排除再动手：

| 工具 | 实际方向 | 能用吗 |
|---|---|---|
| AudioRelay | PC → 手机；手机**麦克风** → PC | ❌ 传不了手机系统音频 |
| SoundWire / Sonicast / AirMusic | PC → 手机 | ❌ |
| KDE Connect | 没有音频转发功能 | ❌ |
| sndcpy | 手机 → PC | ⚠️ 已停止维护，官方让用 scrcpy |
| Windows「手机连接」 | 手机 → PC | ⚠️ 能用但延迟大、机型受限 |
| **scrcpy `--no-video`** | 手机 → PC | ✅ 首选 |

## 1. 首选：scrcpy 纯音频模式

### 为什么不是投屏
scrcpy 通常被当成投屏软件，但 `--no-video` = **Disable video forwarding**（不采集、不传输视频），
电脑上**没有任何画面**，只把手机音频流经 ADB 抽到电脑播放。

⚠️ `--no-window` 只隐含 `--no-video-playback`（**仍然采集视频**）。
要真正"纯音频、省资源"必须显式写 `--no-video`。

### 安装（Windows）
1. 官方 release 下 `scrcpy-win64-v<ver>.zip`（**自带 adb.exe，不用另装 platform-tools**）
2. 同时下 `SHA256SUMS.txt`，用 `Get-FileHash -Algorithm SHA256` 比对（官方是唯一可信来源）
3. 解压：`tar.exe -xf <zip> -C <dest> --strip-components=1`（Windows 自带 bsdtar 认 zip）

⚠️ **国内直连 GitHub releases 大文件会中途截断**（实测 10.78MB 的包只下到 6.2MB 就断）。
解决：`curl.exe -sL -C - --retry 2 --max-time 240 -o <zip> <url>` 放进循环，直到文件字节数达标，`-C -` 断点续传。

### 运行命令
```
scrcpy.exe --no-video --no-control --audio-buffer=60
```
| 参数 | 作用 |
|---|---|
| `--audio-buffer=ms` | 默认 50。小=更跟手，大=更不易爆音。USB 30~60，Wi-Fi 100+ |
| `--audio-source=output` | 默认。手机自身静音，声音只从电脑出（走 REMOTE_SUBMIX） |
| `--audio-source=playback` | 手机**同时**外放（Android 13+；部分 app 会 opt-out 抓不到） |
| `--audio-codec=raw` | 无损（USB 带宽够时用）；默认 `opus` 省 CPU |
| `--no-control` | 不要键鼠控制（纯音频场景必加，去掉对手机的干扰） |

音频走 Windows 默认输出设备，**和游戏声音自动混音**，互不冲突。

### 手机端设置（小米 / 澎湃 OS）
```
设置 → 我的设备 → 全部参数与信息 → 连点「OS 版本」7 次
→ 回「更多设置」→ 开发者选项 → 打开「USB 调试」
```
插线后手机弹「允许 USB 调试吗」→ 勾「始终允许」。
**不需要**开「USB 调试（安全设置）」——那是给键鼠控制用的，本方案 `--no-control` 用不上。
USB 用途若弹窗，选「传输文件 / MTP」。

## 2. 交付 .bat 一键脚本时的硬坑

- **编码必须 GBK(936) + CRLF**。UTF-8 写的中文 `echo` 在 cmd 下是乱码。
  转换：`[IO.File]::WriteAllText($p, ($c -replace "\`r\`n","\`n" -replace "\`n","\`r\`n"), [Text.Encoding]::GetEncoding(936))`
- `title` / `echo` 行里的 `>` 要写成 `^>`，否则被 cmd 当重定向
- 用 `%~dp0` 定位同目录的 `scrcpy.exe` / `adb.exe`
- 三个脚本骨架：① `adb.exe devices -l` 查连接 ② USB 纯音频 ③ Wi-Fi（先 `adb connect`，`--audio-buffer=100`）
- 无设备时 scrcpy 报 `ERROR: Could not find any ADB device` —— 参数合法、只是没插线，可用来判断脚本是否写对

## 3. 备选方案（按延迟排序）

| 方案 | 延迟 | 说明 |
|---|---|---|
| 蓝牙耳机**双连**（multipoint） | 最低 | 手机也连同一副蓝牙耳机，零软件。**先问耳机是不是蓝牙的**，是就优先这个 |
| 3.5mm 音频线 → 电脑 Line-in | ~0ms | 手机耳机口 → 蓝色 Line-in，「声音设置 → 输入 → 侦听此设备」。要台式机有 Line-in |
| scrcpy `--no-video` | 35~70ms | 本方案 |
| Windows「手机连接」 | 数百 ms | 齿轮 → 功能 → Apps → 「从…收听音频」选「电脑」。零安装，玩游戏不行 |
| 蓝牙 A2DP sink（电脑当蓝牙音箱） | 150~300ms | Windows 无原生接收端，需第三方 UWP |

## 4. Wi-Fi 无线（可选）

方式 A（省事）：USB 连上时跑 `adb tcpip 5555` → 拔线 → `adb connect <手机IP>:5555`
方式 B（Android 11+）：`adb pair <ip>:<配对端口>` 输 6 位配对码 → `adb connect <ip>:<连接端口>`
游戏场景建议直接用 USB：延迟更低，还顺便充电。

## 5. 坑清单

1. AudioRelay 只能 PC→手机 / 手机麦克风→PC，**别拿它做手机系统音频转发**
2. GitHub 大文件下载会截断 → `-C -` 断点续传 + 循环校验字节数
3. bat 必须 GBK + CRLF，`>` 要转义 `^>`
4. `--no-window` ≠ 不传视频，纯音频必须 `--no-video`
5. 受 DRM 保护的 app（Netflix 等）音频抓不到，属正常
6. 交付时明确告诉用户"黑窗口无画面是正常的"，否则会被误认为投屏失败
7. Windows 上很多环境（PowerShell 工具）不回显 stdout，脚本结果写临时文件再 Read
