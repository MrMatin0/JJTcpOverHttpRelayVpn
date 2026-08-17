<div dir="rtl">

# JJTcpOverHttpRelayVPN

این پروژه یه پروکسی محلی HTTP و SOCKS5ـه که می‌تونه ترافیکت رو از Google Apps Script رد کنه. مسیر TCP اختیاری هم با کمک Cloudflare Durable Object یه سوکت TCP واقعی رو زنده نگه می‌داره و Apps Script فقط درخواست‌های کوتاه HTTP رو بین دو طرف جابه‌جا می‌کنه.

> **مسئولانه استفاده کن.** این پروژه برای یادگیری و تحقیق شبکه‌ست. مسئولیت ترافیکی که می‌فرستی، سرویس‌هایی که deploy می‌کنی و رعایت قوانین و قوانین استفاده‌ی Google و Cloudflare با خودته.

**[راهنمای انگلیسی](README.md)**

## پروژه دقیقاً چه کار می‌کنه؟

- پروکسی HTTP روی `127.0.0.1:8080`
- حالت HTTPS MITM برای درخواست‌های HTTP داخل CONNECT، با نیاز به نصب CA محلی
- پروکسی SOCKS5 روی `127.0.0.1:1080` برای TCP واقعی
- رله‌ی HTTP با Google Apps Script
- رله‌ی TCP پایدار با Cloudflare Worker و Durable Object
- قابلیت‌های جانبی مثل cache، دانلود تکه‌ای فایل‌های بزرگ، انتخاب SNI و چند deployment

**هشدار مهم:** SOCKS5 پیش‌فرض هیچ احراز هویتی نداره. تا وقتی دقیقاً نمی‌دونی داری چی کار می‌کنی، `listen_host` رو روی `127.0.0.1` نگه دار و LAN sharing رو روشن نکن.

## معماری ساده

```text
حالت HTTP:
مرورگر -> پروکسی محلی -> TLS فرانت‌شده -> Apps Script -> سایت مقصد

حالت TCP:
کلاینت SOCKS5 -> پروکسی محلی -> Apps Script -> Worker/DO کلودفلر -> سوکت TCP مقصد
                                      ^                         |
                                      +------ اکشن‌های JSON ----+
```

در مسیر TCP چهار اکشن داریم: `open`، `send`، `poll` و `close`. سوکت واقعی داخل Durable Object نگه داشته می‌شه؛ پایتون هم داده‌های کلاینت رو upload می‌کنه و برای داده‌های برگشتی long-poll می‌زنه.

## چیزهایی که لازم داری

- Python **3.10 یا جدیدتر**
- Node.js **18 یا جدیدتر** و npm، فقط برای deploy کردن Worker
- یه حساب Google برای Apps Script
- یه حساب Cloudflare برای حالت TCP
- یه رمز مشترک طولانی و تصادفی

## ۱. گرفتن پروژه

```bash
git clone https://github.com/MrMatin0/JJTcpOverHttpRelayVpn.git
cd JJTcpOverHttpRelayVpn
```

## ۲. نصب بخش پایتون

لینوکس و مک:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

ویندوز PowerShell:

```powershell
py -3 -m venv .venv
.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## ۳. Deploy کردن TCP Worker

اگه فقط رله‌ی HTTP می‌خوای، این مرحله رو رد کن.

1. Wrangler رو نصب کن: `npm install -g wrangler`
2. وارد Cloudflare شو: `wrangler login`
3. یه رمز بساز:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

4. فایل `apps_script/wrangler_tcp.toml` رو باز کن و اسم Worker، مقدار `AUTH_KEY` و تنظیمات Durable Object رو بررسی کن. رمز واقعی رو داخل Git commit نکن.
5. deploy کن:

```bash
cd apps_script
wrangler deploy --config wrangler_tcp.toml
cd ..
```

6. آدرس Worker رو نگه دار و تستش کن:

```bash
curl https://YOUR-WORKER.YOUR-SUBDOMAIN.workers.dev
```

باید یه پاسخ سلامت مربوط به TCP Worker بگیری.

## ۴. Deploy کردن Google Apps Script

1. برو به <https://script.google.com> و یه پروژه‌ی جدید بساز.
2. کل محتوای `apps_script/Code.gs` رو داخل ادیتور بچسبون.
3. مقدار `AUTH_KEY` رو دقیقاً برابر همون رمز Worker بذار.
4. مقدار `CF_ENDPOINT` رو برابر آدرس Worker بذار؛ اسلش آخرش رو بردار.
5. از مسیر **Deploy → New deployment** نوع **Web app** رو انتخاب کن، اجرا با **Me** و دسترسی **Anyone**.
6. **Deployment ID** رو کپی کن. چیزی که لازم داری Deployment IDـه، نه Script ID پروژه.
7. اگه `Code.gs` رو تغییر دادی، deployment رو update کن یا یه نسخه‌ی جدید deploy کن.

## ۵. ساختن `config.json`

```bash
cp config.example.json config.json
```

حداقل اینا رو تنظیم کن:

```json
{
  "mode": "apps_script",
  "script_id": "YOUR_APPS_SCRIPT_DEPLOYMENT_ID",
  "auth_key": "THE_SAME_LONG_RANDOM_SECRET",
  "listen_host": "127.0.0.1",
  "listen_port": 8080,
  "socks5_enabled": true,
  "socks5_port": 1080
}
```

اگه حوصله‌ی ویرایش دستی نداری، wizard رو اجرا کن:

```bash
python setup.py
```

برای ظرفیت بیشتر Apps Script می‌تونی به‌جای `script_id` از `script_ids` استفاده کنی و چند Deployment ID بدی. همه‌شون باید زیر حساب‌هایی باشن که خودت کنترل می‌کنی و `AUTH_KEY` یکسان داشته باشن.

## ۶. اجرا و تست

```bash
python main.py
```

تست پروکسی HTTP:

```bash
curl -x http://127.0.0.1:8080 https://example.com
```

تست SOCKS5 و TCP:

```bash
curl --proxy socks5h://127.0.0.1:1080 https://example.com
```

در فایرفاکس نوع SOCKS رو روی **SOCKS v5** بذار، Host رو `127.0.0.1` و Port رو `1080` بزن و گزینه‌ی **Proxy DNS when using SOCKS v5** رو روشن کن.

دستورهای کاربردی:

```bash
python main.py --scan
python main.py --install-cert
python main.py --uninstall-cert
python main.py --disable-socks5
```

## تنظیمات مهم

| کلید | کاربرد |
| --- | --- |
| `auth_key` | رمز مشترک پایتون، Apps Script و Worker |
| `script_id` / `script_ids` | Deployment ID اپلیکیشن وب Apps Script |
| `google_ip` | IP فرانت برای اتصال TLS؛ با `--scan` می‌تونی پیشنهاد بگیری |
| `front_domain` | SNI، معمولاً `www.google.com` |
| `listen_host` | آدرس گوش دادن؛ معمولاً همون `127.0.0.1` امن‌تره |
| `lan_sharing` | باز کردن listener روی همه‌ی کارت‌های شبکه؛ با احتیاط |
| `socks5_enabled` | روشن یا خاموش کردن SOCKS5 بدون احراز هویت |
| `relay_timeout` | حداکثر زمان درخواست HTTP رله‌شده |
| `chunked_download_*` | کنترل دانلود تکه‌ای؛ برای سهمیه و RAM کمتر، کاهش بده |
| `block_hosts` / `bypass_hosts` | سیاست مسدودسازی یا bypass برای hostnameها |

## رفع خطاهای رایج

**`Config not found`**: `config.example.json` رو به `config.json` کپی کن یا `python setup.py` رو اجرا کن.

**`unauthorized`**: مقدار `auth_key` در `config.json`، مقدار `AUTH_KEY` در `Code.gs` و secret Worker رو کاراکتر‌به‌کاراکتر مقایسه کن.

**`script id not found`**: Deployment ID وب‌اپ رو استفاده کن، deployment رو Web app بساز و دسترسی لازم رو بده.

**مرورگر می‌گه connection closed**: برای حالت HTTP/HTTPS دستور `python main.py --install-cert` رو اجرا کن و مرورگر رو ببند و باز کن. حالت SOCKS5 به CA محلی نیاز نداره.

**TCP یه بار کار می‌کنه و بعد می‌ایسته**: با `wrangler tail` لاگ Worker رو ببین، سهمیه‌های Google و Cloudflare رو بررسی کن و آدرس Worker و رمز رو دوباره چک کن.

**اولین درخواست کندتره**: برنامه اتصال‌های TLS و کانتینر Apps Script رو گرم می‌کنه. درخواست‌های بعدی باید بهتر بشن.

**سهمیه تموم شده**: long-poll مصرف polling بی‌خودی رو کم می‌کنه، ولی سهمیه رو نامحدود نمی‌کنه. تعداد تونل‌ها رو کم کن، ویدیو رو از مسیر SOCKS5 رد نکن، یا از deploymentهایی که خودت داری استفاده کن.

## توسعه

برای اجرای تست‌ها:

```bash
pytest -q
```

نمونه‌های deploy داخل `apps_script/` و مستندات exit-node داخل `docs/exit-node/` هستن.

## لایسنس

[LICENSE](LICENSE) رو ببین.

</div>