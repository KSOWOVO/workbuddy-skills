---
name: skland-endfield-toolkit
description: 终末地(MaaEnd)每日任务自动化 + 森空岛官方API数据工具箱。触发词：MaaEnd、终末地自动化、每日任务、森空岛签到、协议空间、基质刷取、账号面板、skland token、preaction。含 MaaEnd 配置安全修改五步流程、森空岛API全链路(token→cred→签名→角色卡片→签到)、已知坑与诊断方法。
agent_created: true
---

# skland-endfield-toolkit

终末地日常自动化（MaaEnd）+ 森空岛官方数据 API，两合一套装。**生产环境已部署，勿重建，只维护。**

## 生产环境位置

| 项 | 路径 |
|---|---|
| MaaEnd 本体 | `D:\Hypergryph Launcher\maaend`（GUI=MFAAvalonia，v2.27+）|
| 用户配置 | `maaend\config\mxu-MaaEnd.json`（instances[].tasks[].optionValues）|
| 永久工具目录 | `C:\Users\13662\.workbuddy\skland_tools\`（签到脚本/token/面板/修复，**看它自带 README.md**）|

## 流程 1：安全修改 MaaEnd 配置（五步，勿省）

1. 确认 `MaaEnd.exe` 已退出——GUI 运行中会覆写配置文件（日志可见每次焦点变化都触发保存）
2. 备份 config/mxu-MaaEnd.json（带时间戳，放 skland_tools）
3. 只改 `instances[].tasks[]` 与 `preActions`；**绝不碰 tasks/ 目录**（更新会整体替换）
4. 改完双重校验：JSON 语法 + 任务名/选项值对照 `tasks/**/*.json` schema 全量比对（注意 JSONC 注释与 pretasks 公共选项，见坑 3/4）
5. 更新持久性已验证：任务名/选项名是持久化键（官方刻意保留，PR #5513）；前置动作丢失 → 双击 `repair_preaction.bat`

## 流程 2：森空岛官方 API（复刻小黑盒数据通道）

已部署为 `skland_tools\skland_endfield.py`，命令：
`python skland_endfield.py --token-file skland_token.txt --sign --lenient`
- `--sign` 顺手签到；`--lenient` 任何失败退出 0（前置动作场景必加，不阻塞日常）
- token 获取：用户登录 skland.com 网页版 → 开 `https://web-api.skland.com/account/info/hg` → 复制 `content` 值（首尾空格 strip 安全）
- 完整端点链与签名算法 → `references/skland-api.md`（按需读）

## 流程 3：诊断

- **前置动作失败是静默的**（lenient 退出 0）——脚本自带 trace 写 `skland_tools\preaction_run.log`，读它定因
- GUI 日志：`maaend\debug\YYYY-MM-DD-N.log`（加载/提交/停止）；框架识别细节：`maafw.log`（约 5 分钟轮转 .bak）
- 任务识别失败但无报错 → 先查游戏分辨率是否 16:9、语言是否简中（官方资源简中最佳）

## 关键坑（踩过，勿再踩）

0. **MaaEnd 前置动作 useCmd=false 时参数会被吞**——`program=python.exe args=...` 启动了 python 但 argv 为空（静默无操作）。正解：`program=<某.cmd> args="" useCmd=true`，参数全部硬编码在 .cmd 内；.cmd 用探针日志（echo >> probe.log）+ 脚本自带 trace 双重验证是否真的执行
1. 响应风格混用：`status` 与 `code` 两种都要兼容，否则把成功当失败
2. 签名串 JSON **键序必须** `platform,timestamp,dId,vName`——顺序错 → 10000 请求异常
3. MaaEnd 任务 JSON 是 JSONC：整行注释 + 行尾注释（`"enabled": false //xx`）都要剥，且要跳过字符串内的 `//`
4. AutoFight* 等公共选项定义在 `tasks/pretasks/GameSetting.json`，不在任务文件本体
5. `tasklist` 输出 GBK：`decode("gbk", errors="ignore")`
6. 工具链（bash/命令层）会把反斜杠归一化成正斜杠——写 .cmd/配置路径后必须显式校验并 `replace("/", chr(92))` 还原
7. 上游已知问题：启动自动更新弹窗阻断无人值守（#5343）；协议空间勿配应急理智加强剂（#4999）；Agent start failed "status 0" 多为瞬态，重试即好
