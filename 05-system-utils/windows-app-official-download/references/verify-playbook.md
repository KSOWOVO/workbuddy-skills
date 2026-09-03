# 安装包校验手册（签名 + Defender）

## 第 1 层：Authenticode 签名（权威）

PowerShell 工具在本机**不返回 stdout**，必须写文件再 Read：

```powershell
$p = "<绝对路径 exe>"
$sig = Get-AuthenticodeSignature -FilePath $p
$v = (Get-Item $p).VersionInfo
@(
  "Status: " + $sig.Status,
  "Signer: " + $sig.SignerCertificate.Subject,
  "Issuer: " + $sig.SignerCertificate.Issuer,
  "ValidTo: " + $sig.SignerCertificate.NotAfter,
  "SigningTime: " + $sig.SigningTime,
  "FileVersion: " + $v.FileVersion,
  "ProductName: " + $v.ProductName,
  "CompanyName: " + $v.CompanyName,
  "FileDescription: " + $v.FileDescription
) | Out-File "<工作区>\sigcheck.txt" -Encoding utf8
```

### 判读

| `Status` | 含义 | 处置 |
|---|---|---|
| `Valid` | 签名有效，**文件自签名后未被篡改** | ✅ 通过 |
| `UnknownError` / `NotSigned` | 无签名或被破坏 | ❌ 不交付，找别的源 |
| `HashMismatch` | 文件被改过 | ❌ 立即丢弃 |
| `Expired` | 签名过期（未时间戳） | ⚠️ 高风险，换源 |
| `NotTrustedRoot` | 根证书不受信 | ❌ 换源 |

同时核对**签名者主体是不是真厂商**，别只看 Status：
- 腾讯应为 `Tencent Technology (Shenzhen) Company Limited`
- 带 `OID.2.5.4.15=Private Organization` = EV 证书，可信度更高
- 签发者应为 DigiCert / GlobalSign / Sectigo 等公共 CA

### 版本号看不出来是正常的

在线引导安装器的 `FileVersion` 常是壳版本（如 `1.0.0.0`），`ProductName` 也可能是内部代号
（应用宝电脑版是 `Androws`）。以 `FileDescription` / `CompanyName` 为准判断身份。

## 第 2 层：Defender 交叉验证（踩坑重灾区）

```powershell
& "C:\Program Files\Windows Defender\MpCmdRun.exe" -Scan -ScanType 3 -File "<exe>" -DisableRemediation
$LASTEXITCODE   # ⚠️ 参考价值有限，见下表
```

### ExitCode 对照表（血泪版）

| ExitCode | 真实含义 | 是不是病毒 |
|---|---|---|
| `0` | 扫描完成，无威胁 | 否 |
| `2` + `hr = 0x80004005` | **E_FAIL：权限不足，扫描根本没跑起来** | **不是！** |
| `2`（无 hr 提示） | 可能真检出，必须复核 | 待定 |

**结论：非提权环境下 ExitCode 2 几乎必然是权限失败。** 自定义扫描需要管理员令牌，
而我们不提权（会弹 UAC 打扰用户，也违反硬约束 2）。

### 正确的复核方式

```powershell
$th = Get-MpThreatDetection -ErrorAction SilentlyContinue |
      Sort-Object InitialDetectionTime -Descending | Select-Object -First 5
if ($th) { $th | Format-List ThreatName,Resources,InitialDetectionTime | Out-File "<path>" -Encoding utf8 }
else { "no threat records" | Out-File "<path>" -Encoding utf8 }
```

- 输出 `no threat records` → **没有任何检出记录**，这才是干净信号。
- 有记录 → 看 `Resources` 是否命中我们那个 exe 路径。

**不要**为了拿到 ExitCode 0 去提权、去加排除项、去关实时防护——统统违反硬约束 2。

## 第 3 层：基础指纹（顺手做）

```python
import hashlib
b = open(path,'rb').read()
print('size:', len(b), '| MZ:', b[:2])
print('MD5   :', hashlib.md5(b).hexdigest())
print('SHA1  :', hashlib.sha1(b).hexdigest())
print('SHA256:', hashlib.sha256(b).hexdigest())
```

- `b[:2] != b'MZ'` → 不是有效 PE，多半是 HTML 错误页（直链失效/防盗链），重下。
- 大小异常小（几 KB）→ 同样可疑。

哈希写进交付说明，方便用户自己拿到 VirusTotal 之类平台复核。

## 交付文案必备项

版本 / 大小 / SHA256 / 签名状态 / 签名者 / 证书有效期 / 是否在线安装器（要不要联网）/
安装步骤 / 明确说"我没有替你运行安装器"。

---

# APK 专项（当用户接受 Android 包时）

## ⚠️ 头号误判：自签名证书 → `Verify()` 返回 False 是**正常**

```powershell
$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2
$cert.Import("<解出的 .RSA>")
$cert.Subject; $cert.Issuer; $cert.NotBefore; $cert.NotAfter; $cert.Verify()
```

**Android 的 APK 签名证书一律是自签名的**（Issuer == Subject），不挂 CA 链。
所以 `X509Certificate2.Verify()` **必然返回 False**。这不是风险信号，
真正该看的是：

| 看什么 | 期望 |
|---|---|
| `Subject` 的 CN/OU | 与厂商吻合（不背单词是 `CN=iscool, OU=iscool, L=BeiJing`） |
| `Issuer == Subject` | 必然相等，正常 |
| 有效期跨度 | Android 签名证书常 20-30 年（Google 要求覆盖到 2033 年后） |
| 签名文件名 | 如 `META-INF/ISCOOLKE.RSA`，keystore 别名常含厂商名 |

## 提取签名证书

```python
import zipfile
z = zipfile.ZipFile(apk)
rsa = [n for n in z.namelist() if n.upper().endswith((".RSA", ".DSA", ".EC"))]
open("cert_" + rsa[0].split("/")[-1], "wb").write(z.read(rsa[0]))
```

## 从 APK 内解析真实版本（别只信文件名）

`AndroidManifest.xml` 是二进制 AXML，字符串池是 **UTF-16-LE**：

```python
m = z.read("AndroidManifest.xml")
txt = m.decode("utf-16-le", errors="ignore")
import re
print(set(re.findall(r"\d+\.\d+\.\d+", txt)))   # 版本名
print([s for s in re.findall(r"[\x20-\x7e\u4e00-\u9fff]{3,}", txt)
       if "langeasy" in s.lower()][:3])          # 包名核对
```

## 云厂商 ETag 可直接当 MD5 用

金山云 **KS3**、以及多数 S3 兼容存储，对非分片上传的对象 **ETag 就是文件 MD5**。
所以：下载后算 MD5，与响应头 `ETag` 一致 → 传输无损。
比再找一个官方公布的校验值更快。
