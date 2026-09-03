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
  `packageFamilyNames=[]` → **无独立包**，字段 `exe_download_url` 也是空的。
- 应用宝内正规上架：`https://sj.qq.com/appdetail/cn.com.langeasy.LangEasyLexis`
  （`app_id=10928685`，`developer=北京艾斯酷科技有限公司`，
  `icp_number=京ICP备12032362号-6A`）。

唯一能在 Windows 上跑的路径＝安卓兼容层（应用宝电脑版 / 模拟器）。
**但那是另一个软件，按红线 0 必须先问过用户再动手。**

### 官方 APK 获取（用户同意后已成功下载）

版本 **5.11.3**，132.26 MB（138,685,306 bytes），
MD5 `e6d7b90301c085e3656053a30f81705a`（= KS3 的 ETag）。

**下载链路（含防盗链坑）**：

1. 入口 `https://langeasy.com.cn/open.action?go=6` → 302 跳转到
   `https://kscdn.beingfine.cn/apk/is_cool_lexis_<ver>_<timestamp>.apk`
2. **直接 GET 返回 403**，响应头 `Ks-Deny-Reason: referer-acl-deny`
3. **必须带 `Referer: https://langeasy.com.cn/`** 才返回 200
4. curl 对该 CDN 偶发 `HTTP=000`（连接失败），**改用 Python urllib 稳定**

**签名**：`META-INF/ISCOOLKE.RSA`，证书
`CN=iscool, OU=iscool, L=BeiJing, C=ZH`（iscool = 北京艾斯酷），
2014-07-22 至 2039-07-16，自签名（Android 标准，见 verify-playbook.md）。
APK 内包名 `cn.com.langeasy.LangEasyLexis` 与商店记录一致。

### 官网原包 vs 应用宝渠道包

| | 官网原包 | 应用宝渠道包 |
|---|---|---|
| 大小 | 138,685,306 | 138,693,498（+8192） |
| MD5 | `e6d7b9…1705a` | `D51A75…3077` |

差 8192 字节 = 应用宝注入渠道号所致。两者都是官方正版，官网原包更纯净。
