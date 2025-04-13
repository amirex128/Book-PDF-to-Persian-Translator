## کتاب‌های ترجمه شده

در حال حاضر کتاب‌های زیر به فارسی ترجمه شده‌اند و از طریق GitHub Pages قابل دسترسی هستند:

### طراحی برنامه‌های داده‌محور
- عنوان انگلیسی: Designing Data-Intensive Applications
- نویسنده: Martin Kleppmann
- [نسخه دو زبانه آنلاین](https://amir-shirdel-books.netlify.app/Designing_Data-Intensive_Applications/Designing_Data-Intensive_Applications_Dual_View.html/)
- [نسخه آنلاین](https://amir-shirdel-books.netlify.app/Designing_Data-Intensive_Applications/Designing_Data-Intensive_Applications_Farsi.html/)
- [نسخه PDF](https://amirex128.github.io/Book-PDF-to-Persian-Translator/translated/Designing_Data-Intensive_Applications.pdf)

### ساخت میکروسرویس‌ها
- عنوان انگلیسی: Building Microservices
- نویسنده: Sam Newman
- [نسخه دو زبانه آنلاین](https://amir-shirdel-books.netlify.app/Building_Microservice/Building_Microservice_Dual_View.html/)
- [نسخه آنلاین](https://amir-shirdel-books.netlify.app/Building_Microservice/Building_Microservice_Farsi.html/)
- [نسخه PDF](https://amirex128.github.io/Book-PDF-to-Persian-Translator/translated/Building_Microservice.pdf)

### الگوهای میکروسرویس با مثال‌های جاوا
- عنوان انگلیسی: Microservices Patterns With examples in Java
- نویسنده: Chris Richardson
- [نسخه دو زبانه آنلاین](https://amir-shirdel-books.netlify.app/Microservices_Patterns_With_examples_in_Java/Microservices_Patterns_With_examples_in_Java_Dual_View.html/)
- [نسخه آنلاین](https://amir-shirdel-books.netlify.app/Microservices_Patterns_With_examples_in_Java/Microservices_Patterns_With_examples_in_Java_Farsi.html/)
- [نسخه PDF](https://amirex128.github.io/Book-PDF-to-Persian-Translator/translated/Microservices_Patterns_With_examples_in_Java.pdf)

### معماری برنامه‌های وب
- عنوان انگلیسی: Web Application Architecture
- نویسنده: Leon Shklar, Rich Rosen
- [نسخه دو زبانه آنلاین](https://amir-shirdel-books.netlify.app/web-application-architecture/web-application-architecture_Dual_View.html/)
- [نسخه آنلاین](https://amir-shirdel-books.netlify.app/web-application-architecture/web-application-architecture_Farsi.html/)
- [نسخه PDF](https://amirex128.github.io/Book-PDF-to-Persian-Translator/translated/web-application-architecture.pdf)

### طراحی سیستم‌های توزیع‌شده
- عنوان انگلیسی: Designing Distributed Systems
- نویسنده: Brendan Burns
- [نسخه دو زبانه آنلاین](https://amirex128.github.io/Book-PDF-to-Persian-Translatoroutput/Designing_distributed_systems_patterns/Designing_distributed_systems_patterns_Dual_View.html/)
- [نسخه آنلاین](https://amirex128.github.io/Book-PDF-to-Persian-Translatoroutput/Designing_distributed_systems_patterns/Designing_distributed_systems_patterns_Farsi.html/)
- [نسخه PDF](https://amirex128.github.io/Book-PDF-to-Persian-Translator/translated/Designing_distributed_systems_patterns.pdf)

### میکروسرویس‌های آماده تولید
- عنوان انگلیسی: Production-Ready Microservices
- نویسنده: Susan J. Fowler
- [نسخه دو زبانه آنلاین](https://amir-shirdel-books.netlify.app/Production_Ready_Microservices/Production_Ready_Microservices_Dual_View.html/)
- [نسخه آنلاین](https://amir-shirdel-books.netlify.app/Production_Ready_Microservices/Production_Ready_Microservices_Farsi.html/)
- [نسخه PDF](https://amirex128.github.io/Book-PDF-to-Persian-Translator/translated/Production_Ready_Microservices.pdf)

و به زودی کتاب های بیشتر

# مترجم PDF به فارسی

این برنامه یک ابزار قدرتمند برای ترجمه خودکار فایل‌های PDF به زبان فارسی است. این برنامه از API ترجمه استفاده می‌کند و قابلیت‌های پیشرفته‌ای مانند مدیریت محدودیت نرخ درخواست و چرخش کلیدهای API را ارائه می‌دهد.

## ویژگی‌های اصلی

- ترجمه خودکار متن PDF به فارسی
- استخراج و حفظ تصاویر از فایل PDF
- تولید خروجی HTML با قالب‌بندی مناسب
- پشتیبانی از نمایش دو صفحه‌ای (متن اصلی و ترجمه)
- مدیریت هوشمند محدودیت نرخ درخواست API
- پشتیبانی از چندین کلید API برای افزایش سرعت ترجمه
- امکان ترجمه مجدد صفحات خاص

## پیش‌نیازها

- Python 3.7 یا بالاتر
- کتابخانه‌های مورد نیاز (در فایل `requirements.txt` موجود است)

## نصب

1. مخزن را کلون کنید:
```bash
git clone [آدرس مخزن]
cd [نام پوشه پروژه]
```

2. محیط مجازی Python ایجاد کنید و آن را فعال کنید:
```bash
python -m venv venv
source venv/bin/activate  # برای لینوکس/مک
venv\Scripts\activate     # برای ویندوز
```

3. کتابخانه‌های مورد نیاز را نصب کنید:
```bash
pip install -r requirements.txt
```

4. فایل `.env` را ایجاد کنید و کلیدهای API خود را اضافه کنید:
```
PRIMARY_API_KEY=کلید_اصلی_شما
ADDITIONAL_API_KEYS=کلید1,کلید2,کلید3
```

## استفاده

### ترجمه تمام فایل‌های PDF در یک پوشه

```bash
python src/main.py --books_dir پوشه_کتاب‌ها
```

### گزینه‌های خط فرمان

- `--books_dir`: پوشه حاوی فایل‌های PDF (پیش‌فرض: `books`)
- `--output_dir`: پوشه خروجی (پیش‌فرض: `output`)
- `--limit`: محدود کردن تعداد صفحات برای ترجمه
- `--skip_pages`: صفحاتی که باید از ترجمه صرف‌نظر شوند (با کاما جدا شوند)
- `--retranslate_pages`: صفحاتی که باید مجدداً ترجمه شوند (با کاما جدا شوند)
- `--force`: اجبار به بازنویسی ترجمه‌های موجود
- `--output_format`: فرمت خروجی (`html`، `dual_page` یا `both`)
- `--check_existing`: بررسی ترجمه‌های موجود (پیش‌فرض: `True`)

### مثال‌های استفاده

1. ترجمه تمام فایل‌های PDF در پوشه `books`:
```bash
python src/main.py
```

2. ترجمه فقط 10 صفحه اول:
```bash
python src/main.py --limit 10
```

3. ترجمه مجدد صفحات خاص:
```bash
python src/main.py --retranslate_pages 1,3,5
```

4. ترجمه با نمایش دو صفحه‌ای:
```bash
python src/main.py --output_format dual_page
```

## خروجی

برنامه فایل‌های زیر را تولید می‌کند:

1. فایل‌های HTML برای هر صفحه ترجمه شده
2. فایل HTML کامل برای کل کتاب به زبان فارسی
3. فایل HTML با نمایش دو صفحه‌ای (متن اصلی و ترجمه)
4. تصاویر استخراج شده از PDF


## نکات مهم

- اطمینان حاصل کنید که کلیدهای API معتبر و دارای سقف درخواست کافی هستند
- برای فایل‌های PDF بزرگ، استفاده از چندین کلید API توصیه می‌شود
- در صورت بروز خطای محدودیت نرخ درخواست، برنامه به طور خودکار از کلید API بعدی استفاده می‌کند

## مشارکت

مشارکت‌ها به صورت Pull Request پذیرفته می‌شوند. لطفاً قبل از ارسال تغییرات، مطمئن شوید که:

1. کد شما از استانداردهای PEP 8 پیروی می‌کند
2. تست‌های جدید برای قابلیت‌های جدید نوشته شده‌اند
3. مستندات به‌روز شده‌اند

## مجوز

این پروژه تحت مجوز MIT منتشر شده است.
