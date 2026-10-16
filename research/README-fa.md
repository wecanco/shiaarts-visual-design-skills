# بستهٔ پژوهش کانون هنر شیعی

این پوشه خروجی یک ممیزی عمومی، قابل‌ادامه و شواهد-محور از `https://shiaarts.ir/` است. دامنهٔ انتخاب‌شده همهٔ شاخه‌های آثار تصویری و بخش `جبهه هنرمندان` است؛ آثار تکراری با شناسهٔ node/URL ادغام می‌شوند، نه با عنوان.

## وضعیت فعلی

وضعیت قطعی را فقط از `coverage.json` بخوانید:

- `inventory_closed=false` تا وقتی همهٔ فهرست‌های کشف‌شده با موفقیت تمام نشوند.
- `fully_reviewed=false` تا وقتی تصویر هر اثر باز و با مشاهدهٔ جزئیات ثبت نشود.
- دریافت تصویر، اندازه‌گیری پیکسل، OCR یا وجود نام در taxonomy به‌تنهایی «بررسی بصری» نیست.
- `visual-review-queue.jsonl` صف کار دانه‌به‌دانه است و عمداً مشاهدات خالی و `pending` دارد.
- فایل‌های اصلی/آرشیوی `/file/.../download` درخواست نشده‌اند؛ تنها تصاویر نمایشی عمومی در مرحلهٔ `assets` قابل دریافت‌اند.

## فایل‌ها

- `catalog.jsonl`: یک رکورد برای هر اثر کشف‌شده؛ متادیتای صفحه، انتساب صریح، مناسبت صریح/نامشخص، حقوق و تصاویر.
- `artists.json`: فهرست taxonomy هنرمندان؛ عضویت در فهرست، اثبات طراحی یک اثر نیست.
- `visual-review-queue.jsonl`: صف بررسی تصویر با وضعیت و مسیر محلی asset.
- `assets-manifest.jsonl`: اندازه و فرمت واقعی فقط برای assetهای دریافت‌شده.
- `taxonomy.json`, `listing-pages.json`, `coverage.json`: دفتر کشف، خطاها و پوشش.

## ادامهٔ اجرا

از ریشهٔ workspace اجرا کنید؛ SQLite و cache مرحله‌ای هستند و اجرای مجدد از نقطهٔ فعلی ادامه می‌دهد:

```powershell
python work/site_audit.py inventory --mode metadata --scope all --retry-errors --max-requests 500
python work/site_audit.py crawl --mode metadata --scope all --max-requests 500
python work/site_audit.py crawl --mode assets --scope all --max-requests 500
python work/site_audit.py review-export
python work/build_artist_skills.py
powershell -ExecutionPolicy Bypass -File work/refresh_shiaarts_skills.ps1
```

خزنده به `robots.txt` و حداقل فاصلهٔ ۱۰ثانیه‌ای بین درخواست‌های شبکه احترام می‌گذارد و این قفل بین اجرای موازی مشترک است: `work/crawl-clock.lock`.

## حقوق و انتساب

اخطار اختصاصی هر اثر از فوتر سخت‌گیرانه‌تر است: استفادهٔ اقتصادی، بازتولید و بازنشر بدون ذکر منبع و اجازهٔ صاحب حق مجاز فرض نمی‌شود. مهارت‌ها برای خلق اثر اصیل بر پایهٔ اصول مشاهده‌شده‌اند، نه کپی، بازتولید layout، حذف امضا یا ادعای تأیید هنرمند.
