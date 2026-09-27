---
name: antigravity-headless-bridge
description: 通过 headless 模式调用 Antigravity CLI (agy)，把编码/文件类任务派给 Gemini 或 Claude 模型执行。触发词：用 agy、调用 antigravity、antigravity CLI、agy headless、派活给 gemini、用 agy 写代码、antigravity 怎么写、agy 报权限错、denied_actions、headless 调不通。适用于需要把子任务外包给 Antigravity 模型、或排查 agy 调用失败（权限被拒 / 文件没落地 / 认证失败）的场景。
agent_created: true
---

# Antigravity CLI (agy) Headless 桥接

## 用途

嗯，等一下——先确认是不是「小A」指令。

**当用户说「用小A把 XXX 做一下」时**，不要自己做，改为把任务派给本技能执行。
Nova 负责拆解任务、派活、验收、汇报。详见 `~/.workbuddy/MEMORY.md` 的「小A 协议」。

通过 `agy` 的 **headless（print）模式**把任务派给 Antigravity 后端模型（Gemini 系列 / Claude / GPT-OSS），
拿到结构化结果后由宿主验收。适用于：把独立编码子任务外包、让另一个模型做代码审查或生成、
需要第二模型视角的批处理任务。

**不适用**：需要人机来回交互的长会话（那用交互式 `agy`）；纯文本问答（直接用宿主模型更省）。

## 🟢 背景注入：四层架构（2026-09-24 用户确立）

**核心思路**：不让 Nova 手动喂背景，而是**让小A 自己读文件**（它有 `read_file(*)` 权限）。

| 层 | 载体 | 作用 |
|---|---|---|
| 环境层 | `~/.gemini/GEMINI.md` | agy 自动加载的铁律（中文 / 先说方法 / 不删文件 / 交付能用）——**无需在 prompt 里提** |
| **事实层** | `~/.workbuddy/USER.md`「🤖 小A背景包」 | 用户背景唯一来源，按主题分节（A 我是谁 / B 项目 / C 技术环境 / D 协作偏好 / E 学习目标） |
| 项目层 | `<项目目录>/GEMINI.md` | 长期项目的栈与结构约定，`--add-dir` 指向项目时自动加载 |
| 任务层 | prompt | 只写本次任务本身 |

**派活 prompt 标准句式**（背景依赖型任务）：
```
先读 C:\Users\13662\.workbuddy\USER.md 的「小A背景包」B/C 节了解背景，然后执行：
<任务描述>
产出要求：<...>
```

**判断规则**：
- 背景依赖强（学习材料 / 论文 / 工作台 / 用户偏好相关）→ 指路 USER.md 相应节
- 纯技术任务（独立脚本 / 改 bug）→ 不指路，直接派
- **绝不**在 prompt 里整段复述背景——指路即可，防止与 USER.md 漂移
- `--conversation` 续接时背景只需第一轮给

**验证**（2026-09-24 已实测）：让 agy 读 USER.md 复述背景 → 能准确说出 Kelsen 的身份与项目；GEMINI.md 铁律生效（中文回复）。

## 🔴🔴 铁律：单次任务必须压在 10 分钟以内（2026-09-24 实证）

**任务时长与成功率强相关**，这是比节点更硬的天花板：

| 单次任务时长 | 实测结果 |
|---|---|
| 3 s ~ 184 s | ✅ 成功 |
| 381 s / 672 s | ⚠️ 文件写成了，但收尾报 `stream was interrupted` |
| **超过约 900 s** | ❌ **全部失败**（`tls: bad record MAC` / 流中断） |

**实证对比**（同一个任务）：
- ❌ 一次性派大活（读 3 个文件 + 写 3000 字）：Gemini 18min、Opus 20min、Sonnet **15min24s** —— **三次全失败**
- ✅ 拆成 4 步（限制输出行数）：84s / 184s / 381s / 672s —— **4/4 全部产出**

**派活规范**：
1. **拆步**：读 1-2 个文件 + 写 ≤100 行，为一步
2. **限制输出**：prompt 里明确写「不超过 N 行」——输出越长越容易崩
3. **串行执行**：并行会互相拖慢（实测并行 7min 未完成，串行 3min 完成）
4. **超时设 ≥600s**：别设 400s，实测有步骤需要 428s，会被误杀（`Exit Code 124`）
5. **只看文件，不看 status**：⚠️ 实测有步骤返回 `status:ERROR`（stream interrupted）**但文件完整落地**。
   判定成功的唯一标准是 **`ls` 目标文件**。
   🔴 **补充（2026-09-27 实测）**：声明了多个 `--add-dir` 时，小A **可能把产出写到其中任意一个目录**
   （给它「输入目录 + 输出目录」两个，它可能写进输入目录）。所以验收要**把所有 `--add-dir` 目录都 `ls` 一遍**，
   不能只看你预期的那个输出目录；否则会误判成"文件没落地"。
   另：`_r.json` 的 `response` 字段本身通常就含完整答案（1216 字符的核对报告就在里面），
   文件没找到时先去 `response` 里取。


## 🔴 每次用完必须汇报（用户 2026-09-23 硬性要求）

派活完成后，**固定汇报这三项**：

1. **本次 token 用量明细**（从返回的 `usage` 字段取）：
   `input_tokens` / `output_tokens` / `thinking_tokens` / `cache_read_tokens` / `total_tokens`
2. **耗时**：`duration_seconds`
3. **剩余额度**：⚠️ **headless 模式拿不到**。

关于额度，务必如实说明，**绝不编造数字**：
- 官方额度只显示在**交互式 TUI 的状态栏右侧**（形如 `AI Credits: 42`）和 `/credits`、`/usage` 面板中。
- headless 模式不产出这些数据；实测直接询问 agy 自身也会回复 `NO_QUOTA_ACCESS`。
- 正确话术：「剩余额度无法从 headless 获取，可在 Antigravity 交互界面查看状态栏。」

**汇报模板**：
```
小A 已完成：<任务摘要>
模型：<model id>
耗时：<duration_seconds>s
用量：输入 X / 输出 Y / 思考 Z / 缓存读取 W / 合计 T
额度：headless 无法获取（请在 Antigravity 界面查看状态栏）
```

## 工具脚本

| 脚本 | 用途 |
|---|---|
| `scripts/agy-dispatch.sh <目录> "<任务>" [模型]` | 派活 + 自动重试 + 校验文件是否真落地 |
| `scripts/agy-ping.sh` | 只做链路体检（版本 / 出口地区 / 代理 / 凭证），**不消耗额度** |
| `scripts/agy-ping.sh report` | 体检 + 跑一次探针并输出格式化用量汇报 |

## 前置检查（每次调用前，3 秒完成）

```bash
# 1. agy 是否可用
command -v agy && agy --version

# 2. 代理环境是否已注入（应有输出；无需自己设置）
env | grep -i proxy

# 3. 凭证是否有效（能拉到模型列表即通）
agy models | head -5
```

三项都过 → 直接派活。任一项失败 → 见「故障排查」章节。

## 标准调用

```bash
agy -p "任务描述" --add-dir <目标目录> --output-format json
```

**参数要点**：

| 参数 | 用途 | 备注 |
|---|---|---|
| `-p` / `--print` | headless 模式（必需） | 不带 `-p` 会进交互模式，无法编排 |
| `--add-dir <path>` | **声明工作区（文件类任务必需）** | 可重复；不声明则文件落到 `~/.gemini/antigravity-cli/scratch/` |
| `--output-format json` | 单次 JSON 结果 | 拿 `status`/`response`/`usage`/`conversation_id` |
| `--output-format stream-json` | NDJSON 事件流 | 需要实时监控进度时才用 |
| `--model <id>` | 指定模型 | `agy models` 列可用值 |
| `--conversation <id>` | 续接指定会话 | 或 `-c` 续最近一轮 |
| `--effort low\|medium\|high` | 推理强度 | 🔴 **一律不要带这个参数**（2026-09-24 实证）。`agy models` 列出的 Gemini / GPT-OSS 模型 ID **本身就以 `-high`/`-medium`/`-low` 结尾**，档位已经选好了，再加 `--effort` 会**秒失败**：`invalid model selection (...): --model gemini-3.8-flash-high conflicts with --effort=low`（0 token）。claude-* 则完全不支持（报 `--effort is not supported`）。**要用哪个档位就选哪个模型 ID 后缀。** |
| `--json-schema <schema>` | 强制结构化输出 | 只对最终结果生效 |

**输出示例**：
```json
{"conversation_id":"...","status":"SUCCESS","response":"DONE\n",
 "duration_seconds":15.6,"num_turns":1,
 "usage":{"input_tokens":55919,"output_tokens":560}}
```

### ⚠️ 调用参数解析坑（2026-09-24 实测，极易踩）

`agy` 用 Go flag 解析，`-p` / `--print` / `--prompt` 是**带值参数**，行为反直觉：

1. **不要同时写 `-p="..."` 又单独写 `--print`**：`--print`（无 `=`）会把**紧跟的下一个 flag 整个吞掉当 prompt**。
   - 错误：`agy --print --output-format json ...` → 报 `Error: --print took "--output-format" as its prompt`。
   - 正确：只用 `-p="<任务>"`（或 `--print="<任务>"`），其余 flag 全部放后面。`-p` 与 `--print` 是同一别名，**二选一**。
2. **`--print-timeout` 必须带 Go duration 单位**：`150s` ✅，`150` ❌（报 `missing unit in duration "150"`）。
3. prompt 含空格/特殊字符务必用 `-p="..."` 的 `=` 形式；`-p "..."` 也行，但后面不能再跟会被误吞的 flag。

最简可用模板（含超时与模型，已实测通过）：
```bash
agy -p="<任务描述>" --add-dir <目标目录> \
    --model gemini-3.8-flash-high \
    --output-format json --print-timeout 150s > _r.json 2>&1
```

## 🔴 权限配置（最常见的坑）

headless 模式**无法弹窗询问权限，未配置则静默拒绝**，表现为：
```json
"response":"", "denied_actions":[{"action":"command","display_name":"RunCommand"}]
```

**必须创建** `~/.gemini/antigravity-cli/settings.json`：

```json
{
  "permissions": {
    "allow": ["write_file(*)", "read_file(*)", "read_url(*)",
              "command(*)", "command(regex:.*)"],
    "deny": ["command(rm -rf)", "command(regex:.*sudo.*)",
             "write_file(.git/)", "write_file(*/.ssh/)"]
  }
}
```

**规则语法**：`action(target)`，7 类 action：
`read_file` / `write_file` / `read_url` / `execute_url` / `command` / `unsandboxed`（仅 Windows）/ `mcp`

- `command(prefix)` 按词逐字匹配前缀；正则须加 `regex:` 前缀
- `write_file` 隐式授予同路径 `read_file`；deny `read_file` 连带 deny `write_file`
- **优先级：Deny > Ask > Allow**（写反会出安全问题）

### 🔴 `command(regex:.*)` 单独一条是不够的（2026-09-23 实证）

**只写 `"command(regex:.*)"` 时，`RunCommand` 仍会被静默拒绝。** 必须**同时**加上字面通配
`"command(*)"`。加齐后写文件/建文件才真正放行（已实测：探针建文件成功）。

**判别特征**——`status` 是 `SUCCESS` 但 `response` 为空、且有 `denied_actions`：

```json
{"status":"SUCCESS","response":"","denied_actions":[{"action":"command","display_name":"RunCommand"}],
 "usage":{"input_tokens":87218,"output_tokens":2141}}
```

⚠️ **注意这个假象**：`status:SUCCESS` 会骗人。判定成功的唯一标准是
**`response` 非空 / 目标文件真的落地**，而不是 `status`。
（另有友好提示版：「jetski: no output produced — a tool required the "command" permission
that headless mode cannot prompt for, so it was auto-denied.」）

**⚠️ 绝不使用 `--dangerously-skip-permissions`** —— 用上面的精细化授权替代。

## 关键陷阱：文件落到 scratch

`--add-dir` **未声明**的目录不算工作区。此时若任务要求写文件，agy 不报错，但文件会写进
`~/.gemini/antigravity-cli/scratch/`，目标目录为空。

**判别方法**：任务完成后必须实际检查目标目录：
```bash
ls -la <目标目录>
```
若为空但 `status: SUCCESS`，去 scratch 找：
```bash
ls -la ~/.gemini/antigravity-cli/scratch/
```

## 故障排查

| 症状 | 原因 | 处理 |
|---|---|---|
| `invalid model selection (...): --model gemini-3.8-flash-high conflicts with --effort=low`，或 `--effort is not supported for model "claude-*"`；`status:ERROR`、0 token、秒失败 | 带了 `--effort`。**Gemini / GPT-OSS 的模型 ID 已含档位后缀**，Claude 则完全不支持该参数 | **去掉 `--effort`** 重跑，档位改用模型 ID 后缀（`-high`/`-medium`/`-low`）控制（2026-09-24 实证） |
| `denied_actions` + `response` 为空 | `settings.json` 缺失或规则不全 | 按上文创建配置文件 |
| `status: SUCCESS` 但目标目录无文件 | 未 `--add-dir` 声明工作区 | 加 `--add-dir`，或去 scratch 取 |
| 认证失败 / token 错误 | 凭证过期 | 交互式跑一次 `agy` 完成 OAuth |
| `Bad Gateway` / `EOF` / 连接重置 / 大面积失败 | **代理节点质量差（首要怀疑对象）** | **先换节点**，优先 JP 等亚洲邻近节点 |
| 直连超时 | 未走代理 | 确认 Clash TUN 开启 + 规则模式 |

### 🔴 失败时先怀疑节点，不要怀疑配置（2026-09-23 实证）

该链路对**代理节点质量高度敏感**。同一套配置、同一台机器，节点不行就是连不上。

**实测对比**：
- 2026-09-19：某节点，10 连测仅成功 1 次
- 2026-09-23：换 **JP 节点**（Tokyo）后，20 连测 **20/20 全成功**

**排查顺序**：连续失败 → ① **先换节点**（JP 优先）→ ② 再看 TUN/规则模式 → ③ 最后才怀疑配置。

**节点切换职责（用户 2026-09-23 明确）**：
- **能自己换就自己换**，优先 JP 等亚洲邻近节点。
- **换不了就明确告诉用户**、请其手动操作，不要卡住也不要绕。
- 用 `scripts/agy-ping.sh` 一键体检（含节点评价与换节点建议）。
- 核实出口：`curl -s https://ipinfo.io/json`。**出口在国内（CN）必定失败。**

**不要因为一个节点的失败就推翻整条技术路线。** 也不要归因到"沙箱不可解"这类无法验证的结论上。

**注意端口漂移**：代理端口会变（曾见 `5576` / `1638` / `7897` / `1426` / `7441`），**不要硬编码**，用
`env | grep -i proxy` 现查。agy 是 Go 写的，原生识别 `HTTPS_PROXY`/`HTTP_PROXY`，
宿主会话通常已注入，**一般无需手动设置**。

### 🔴🔴 例外：`User location is not supported` —— 换节点无效，别白折腾（2026-09-24 实证）

**症状**：
```json
{"status":"ERROR","response":"",
 "error":"FAILED_PRECONDITION (code 400): User location is not supported for the API use.",
 "error_code":400,"retryable":false}
```

**这不是节点问题。** 换节点完全无效——实测两个不同的 JP 节点（SoftBank 家宽 / Akari 机房）**报同样的错**。

**一次性定性测试**（关键：**不加 API key**）：
```bash
curl -s --max-time 12 "https://generativelanguage.googleapis.com/v1beta/models"
```
| 返回 | 含义 |
|---|---|
| `403 PERMISSION_DENIED` + "Method doesn't allow unregistered callers" | ✅ **网络层地区正常**（这是缺 key 的标准响应）→ 问题在**账号层** |
| `400 FAILED_PRECONDITION` + "User location is not supported" | ❌ 网络层真的没出去（这才是节点/代理问题） |

**结论（2026-09-24 实测）**：curl 无 key 访问返回 **403**（正常），但 agy 报 **400 地区不支持**。
→ **根因是 agy 的认证身份（OAuth 登录的 Google 账号）被 Google 判了地区，与 IP 无关。**
→ 换节点、换规则、换 TUN 都没用。要解决得在 **agy 交互式界面重新登录 / 换 Google 账号**。

**✅ 首选替代：改用 Claude 家族**
- `claude-sonnet-4-6` / `claude-opus-4-6-thinking` **不受 Google 地区判定影响**，实测可用
- 且**明显更快**：小任务 3 秒返回（Gemini 同任务要 14 秒起，重任务 18 分钟）
- ⚠️ 用 Claude 时**不要带 `--effort`**（见上文参数表）

**处理原则**：
1. 先跑上面的 curl 定性测试 —— **先分清是网络层还是账号层**
2. 网络层 → 换节点；**账号层 → 换模型家族（用 Claude），不要换节点**
3. 如实告诉用户「换节点解决不了，需要重新登录 Google 账号」

### ⚙️ 自查 Clash 节点（能自己换，但先判断是否该换）

用户授权「能自己换就自己换」。Clash Verge Rev 的 External Controller 通常**无密钥开放**：

```bash
# 1. 找控制端口（进程 verge-mihomo.exe + 监听端口）
netstat -ano | grep LISTENING | grep -E ":(9090|9097)\b"
curl -s --noproxy '*' http://127.0.0.1:9097/version      # {"meta":true,"version":"v1.19.3"}

# 2. 列出策略组与当前节点
curl -s --noproxy '*' http://127.0.0.1:9097/proxies

# 3. 切换节点
curl -s -X PUT --noproxy '*' http://127.0.0.1:9097/proxies/<组名> \
  -H "Content-Type: application/json" -d '{"name":"🇯🇵JP06"}'
```

配置目录：`~/AppData/Roaming/io.github.clash-verge-rev.clash-verge-rev/`
（`config.yaml` 有 `external-controller` / `secret`；`profiles/` 是订阅）

**典型策略组结构**（会看到）：`Google` / `Ai` / `GitHub` / `Proxies` / `Final` / `自动选择`，
条目形如 `Google [Selector] → Proxies → 🇯🇵JP06`。

⚠️ **先确认「该不该换」再动手**：若报的是上面的 `User location not supported`，换节点纯属浪费。


## 🔴 小A 访问不到宿主 MCP → 用「数据包（brief）供数模式」（2026-09-24 实证）

**agy 是独立进程，拿不到宿主的 MCP 工具**（行情接口、邮箱、表格等一律不可见）。
但小A 有 `read_file(*)` 权限 —— 所以正确做法是**宿主先取数、落成文件、再派活**：

```
① 宿主用 MCP 抓真实数据（行情/表格/检索结果）
② 写成 <工作区>/brief.md —— 数据包（含表头、单位换算、逐日数据）
③ 派活时 prompt 第一句就是「先读取工作区中的 brief.md」
④ 明确禁止编造：「只能使用 brief.md 内的数据，引用外部结论须标注『外部来源，未独立核验』」
⑤ 要求逐条标注依据（如「依据：3.1 表 2026-08-25 行」）→ 便于宿主复核
⑥ 宿主验收后独立复算关键数字，纠正口径错误
```

**实践效果**（2026-09-24 投资分析任务，2 步串行）：
- 步1（黄金，读 1 个 brief）→ 81 s，产 9 KB
- 步2（美股，读 2 个 brief）→ 97 s，产 8 KB
- 两步 `status` 均为 `SUCCESS`，文件均实际落地，**零编造**，且主动区分了「十年回报压缩」与「近期崩盘」两个层次

**要点**：
- **数据包要写全**：单位换算（如「1 份 ETF = 0.01 克，净值 ×100 = 元/克」）、逐日原始数据、以及**明确的禁止清单**（哪些说法不可采信）
- **把不可信信息单独列一节**并标注「未能核验、不采信」，小A 会照做（实测它专门开了一节说明）
- **prompt 里写清「不要拍板」**（不写「应该买」），否则会越界给投资/医疗决策建议
- **限制行数**（「全文不超过 150 行」）比说「简明扼要」有效得多
- 宿主复核必须做：本次实测抓到 2 处口径问题（涨幅起点算错、引用格式不规范）

## 重试包装（推荐）

### ⚠️ 必须后台运行，否则会被 SIGTERM（2026-09-24 踩坑）

宿主 Bash 工具**前台命令有默认超时（约 2 分钟）**。直接在prompt里写 `timeout 900` **没用**——
是**工具层**先杀掉进程，表现为 `Exit Code 1 / Signal: SIGTERM`、输出为空、任务白跑。

**正确做法**：一律用 `run_in_background: true`，再用 `TaskOutput` 取结果。

```bash
# ✅ 正确
agy -p "..." --add-dir <dir> --model claude-sonnet-4-6 --output-format json > _r.json 2>&1
# 配合工具参数 run_in_background=true
```

⚠️ 另注：`agy` 的错误输出可能**跑到 stdout 之外**（如 stderr 直出 "AGY_ERROR: ..."）。
用 `> file 2>&1` 一并捕获，别只 `| tail -1`，否则会丢错误信息。

网络偶发抖动时用带重试的调用，避免单次失败就误判为「不可用」：

```bash
agy_retry() {
  local prompt="$1" dir="$2" max=3 i=1 out
  while [ $i -le $max ]; do
    out=$(timeout 180 agy -p "$prompt" --add-dir "$dir" --output-format json 2>&1 | tail -1)
    if echo "$out" | grep -q '"status":"SUCCESS"'; then
      echo "$out"; return 0
    fi
    echo "attempt $i failed" >&2; i=$((i+1))
  done
  echo "$out"; return 1
}
```

**教训**：不要跑几次就判定链路不可用，更不要归因到无法验证的结论上。
- 2026-09-19 因「10 连测成功 1 次」推翻整条路线，并归因为「沙箱 5576 不可解」。
- 2026-09-23 换 JP 节点后 **20/20 全成功**——真实根因是**当时的节点质量**。
- **下结论前至少跑 20 次压测**，并记录当时的节点/出口地区。

## 验证清单（派活后必做）

1. `status` 是否为 `SUCCESS`
2. `denied_actions` 是否存在（存在 = 权限没配好）
3. 文件类任务 → **实际 `ls` 目标目录确认文件落地**
4. 需要续接时 → 保存 `conversation_id`

## 🟢 成果呈现规范（2026-09-24 用户明确）

派活完成 ≠ 任务完成。小A 产出后必须做**完整呈现**，当成 Nova 自己的作品交付：

1. **读产出文件全文**，验收内容质量（逻辑 / 规范 / 是否满足任务要求）
2. **像 WorkBuddy 模型一样呈现**：代码贴关键部分（≤100 行贴全文）+ 讲思路 + 给运行结果；文档贴核心段落
3. **`present_files` 呈现文件**——用户能直接打开，不是给一串路径
4. **用量汇报**——模型 / 耗时 / token 明细 / 额度（headless 拿不到就注明）
5. **发现问题就打回**——有 bug、跑不通就指出并重派，不做传话筒

**找回小A 已完成任务的记录**（含用户在别处派的单）：
```
~/.gemini/antigravity-cli/brain/<conversation_id>/.system_generated/logs/transcript.jsonl
```
该文件含用户输入、模型 thinking、工具调用、运行输出，按修改时间 `ls -t` 可找到最近对话。
