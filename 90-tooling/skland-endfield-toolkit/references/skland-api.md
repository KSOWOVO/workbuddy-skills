# 森空岛官方 API 全链路（终末地）

> 来源：FrostN0v0/nonebot-plugin-skland 源码逆向 + 实测。全部为鹰角官方域名，无第三方中转。
> 参考实现：`C:\Users\13662\.workbuddy\skland_tools\skland_endfield.py`（纯 stdlib）

## 0. 域名

| 用途 | 域名 |
|---|---|
| OAuth 授权 | `https://as.hypergryph.com` |
| 森空岛主 API（需签名） | `https://zonai.skland.com/api/v1` |
| 终末地 webview 接口（抽卡记录，query token 鉴权） | `https://ef-webview.hypergryph.com` |
| 角色 role_token | `https://binding-api-account-prod.hypergryph.com` |

UA 固定：`Skland/1.32.1 (com.hypergryph.skland; build:103201004; Android 33; ) Okhttp/4.11.0`

## 1. 登录链：token → cred

```
POST https://as.hypergryph.com/user/oauth2/v2/grant
{"appCode": "4ca99fa6b56cc2ba", "token": <hg_token>, "type": 0}
→ data.code

POST https://zonai.skland.com/api/v1/user/auth/generate_cred_by_code
{"code": <code>, "kind": 1}
→ data.cred, data.token
```
- hg_token 获取：用户登录 skland.com 网页版 → GET `https://web-api.skland.com/account/info/hg` → `data.content`
- 响应风格不统一：grant 用 `status`，generate_cred 用 `code` —— 两种都要兼容
- token 过期报错样例："登录已过期，请重新登录"

## 2. 签名算法（每个带 cred 的请求）

```
ts = int(time.time()) - 1
header_ca = {"platform": "", "timestamp": str(ts), "dId": "", "vName": ""}   # 键序不可变！
header_str = json.dumps(header_ca, separators=(",", ":"))
params = json.dumps(body, separators=(",",":")) if method==post and body else urlparse(url).query
secret = f"{urlparse(url).path}{params}{ts}{header_str}"
sign = md5( hmac_sha256(key=cred_token, msg=secret).hexdigest() ).hexdigest()
请求头 = {cred, UA, sign, **header_ca}
```
- 键序错 → `{"code":10000,"message":"请求异常"}`（10000=鉴权/签名拒绝）
- 业务失败 = code 10001；登录失效 = 10002

## 3. 主要端点

| 功能 | 方法/路径 | 备注 |
|---|---|---|
| 绑定列表 | GET `/api/v1/game/player/binding` | `data.list[]` 按 appCode 分组；终末地 `appCode:"endfield"`；`bindingList[0].uid`=游戏UID，`defaultRole.roleId`=**角色ID(≠游戏UID)**，`channelMasterId`=服务器ID |
| 森空岛 userId | GET `/api/v1/user/teenager` | `data.teenager.userId` —— 卡片接口的 userId 参数用这个 |
| 终末地角色卡片 | GET `/web/v1/game/endfield/card/detail?roleId={roleId}&serverId={serverId}&userId={skUid}` | 返回 base(等级/世界等级/主线)/chars(干员+userSkills+weapon)/dailyMission/weeklyMission/**dungeon(体力 curStamina,maxStamina)**/spaceShip/domain/bpSystem 等 |
| 终末地签到 | POST `/web/v1/game/endfield/attendance`（空body） | 额外头 `sk-game-role: 3_{roleId}_{serverId}`；重复签到 code 10001 |
| token 刷新 | GET `/api/v1/auth/refresh`（cred 头） | 返回新 token |
| 抽卡记录 | GET `https://ef-webview.hypergryph.com/api/record/char|weapon?token={role_token}&server_id&lang=zh-cn` | role_token 来自 `binding-api-account-prod.hypergryph.com/account/binding/v1/u8_token_by_uid`（POST {uid, token: grant_code}）|

## 4. 角色卡片数据结构要点

```
detail.chars[] = {charData:{name,rarity{value},profession{value},property{value},skills[]},
                  level, userSkills:{skillId:{level,maxLevel}}, weapon:{weaponData:{name,...},level},
                  evolvePhase, potentialLevel, ...}
detail.dungeon = {curStamina, maxStamina}   ← 体力在这
detail.dailyMission = {dailyActivation, maxDailyActivation}
detail.weeklyMission = {score, total}
```

## 5. 请求示例（stdlib 强制直连）

```python
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 免受环境代理干扰
```
用户系统代理开/关都不影响——鹰角域名国内直连。
