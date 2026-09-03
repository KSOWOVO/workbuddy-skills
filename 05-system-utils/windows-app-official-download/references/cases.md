# 判例与已知直链

## 腾讯应用宝电脑版（官方）

- **最新版本**：`3.0.3.11`（7.44 MB，在线引导器，ProductName `Androws`，需联网拉组件）
- **签名**：`Status: Valid`，签名者 `Tencent Technology (Shenzhen) Company Limited`
  （DigiCert Trusted G4 Code Signing RSA4096 SHA384 2021 CA1，EV 证书）
- `FileDescription: 腾讯应用宝移动应用引擎`，`CompanyName: Tencent`

### 动态接口（唯一可靠来源）

```
POST https://yybadaccess.3g.qq.com/pc_yyb/deliver
Content-Type: application/json
Ual-Access-Businessid: 2100200129
Version: v2
businessid: pcyyb
Origin: https://sj.qq.com
Referer: https://sj.qq.com/

body: {"pkg_name":"com.tencent.android.qqdownloader","supply_id":115}
```

返回：

```json
{"code":0,"message":"成功",
 "data":{"supply_id":2100200003,
         "download_url":"https://down.pc.yyb.qq.com/pcyyb/packing/<hash>/com.tencent.android.qqdownloader_yybinstaller_<hash>.exe",
         "version":"3.0.3.11",
         "md5":"fe745833071ffbcb2b23b55116b70c13"}}
```

注意：`download_url` 含 hash，有实效性，拿到立刻下载。
带 `client_type` 时返回 `conf.syzs.qq.com` 域名，不带则返回 `down.pc.yyb.qq.com`（主 CDN，优先）。

### ⚠️ 硬编码 fallback 陷阱

`sj.qq.com/download` 的 chunk `_app-*.js` 里有常量：

```
f = "https://down.pc.yyb.qq.com/channel/55/115/10000/pcyyb__installer.exe"
```

**`Last-Modified: Tue, 22 Aug 2023` —— 是 2023 年的老包，不是当前版本。**
它是 fallback 常量。拿到任何硬编码链接，先 `curl -sI | grep -i last-modified` 验年龄。

### 参数反推过程（可复用套路）

1. 先发 `{"pkg_name":...}`
2. 报错 `supply_id must be a number conforming to the specified constraints`
   → 知道缺 `supply_id` 且要是**数字**（不是字符串）
3. 补上 `{"pkg_name":..., "supply_id":115}` → `code:0` 成功

NestJS / class-validator 的报错信息会精确告诉你字段名和类型，2-3 轮必出。

## 不背单词（cn.com.langeasy.LangEasyLexis）

**结论：没有 Windows 原生安装包。给不了可直接安装的 exe —— 这件事做不到。**

- 官网 `bbdc.cn`（langeasy）只有 App Store（`id698570469`）和
  Android（`langeasy.com.cn/open.action?go=6`）两个入口。
- Microsoft Store 详情页 slug `xpdnhn2q35g07w` / skuId `XPDNHN2Q35G07W`：
  `catalogSource=TencentAppStore`、`installer.type=TencentAndroid`、
  `extras.PackageId=cn.com.langeasy.LangEasyLexis`、`VersionCode=370`、
  `packageFamilyNames=[]` → **无独立包**。
- 应用宝内已正规上架：`https://sj.qq.com/appdetail/cn.com.langeasy.LangEasyLexis`
  （canonical 正常，`appdetail_status=常规详情页`）。

唯一能在 Windows 上跑的路径＝安卓兼容层（应用宝电脑版 / 模拟器）。
**但那是另一个软件，按红线 0 必须先问过用户再动手。**
