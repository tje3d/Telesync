Here is the complete extracted text from the provided PDF file:

---

**معرفی رابط برنامه‌نویسی ایتایار (eitaayar.ir)**

در مقاله پیش رو به معرفی رابط برنامه‌نویسی یا به اختصار API ایتایار می‌پردازیم. برای استفاده از این امکان، داشتن حداقل دانش برنامه‌نویسی در زمینه فراخوانی UI و نیز آشنایی با json الزم و ضروری است. اگر با موارد فوق آشنا نیستید، پیش از مطالعه‌ی این متن، درباره آن‌ها مطالعه کنید.

**ساخت آدرس API محرمانه و مختص پنل شما:**

همه درخواست‌ها و متدهایی که استفاده می‌کنید به صورت زیر می‌باشند:

```
https://eitaayar.ir/api/TOKEN/METHOD_NAME
```

- `TOKEN`: توکنی که از سایت دریافت کرده‌اید.
- `METHOD_NAME`: نام متدی که قصد استفاده از آن را دارید.

هیچ‌کدام از متدهای API به حروف کوچک و بزرگ حساسیت ندارند (case-insensitive) و دو نوع `POST` و `GET` را پشتیبانی می‌کنند. شما می‌توانید برای ارسال پارامترها از روش‌های زیر استفاده کنید:

- URL query string
- application/json
- application/x-www-form-urlencoded
- multipart/form-data

اگر ارسال به درستی انجام شود، یک آبجکت `json` بازگشت داده می‌شود. اولین پارامتر این آبجکت `ok` است که مقدار `true` یا `false` دارد. مقدار `true` به معنای درست انجام شدن کار و مقدار `false` به معنای خطا در انجام کار، خطا در پارامترهای ارسالی یا خطای داخلی سرور است. ابتدای هر ذخیره‌سازی همواره مقدار `ok` را چک کنید. اگر مقدار `true` بود، ذخیره‌سازی انجام شود وگرنه باید اصلاحیه جدید اعمال شده سپس ارسال انجام شود.

---

**متدها:**

- getMe
- sendMessage
- sendDocument
- sendFile

---

**1. متد getMe**

اولین و ساده‌ترین متد است که بدون ورودی کار می‌کند و با استفاده از آن، اطلاعاتی درباره API در قالب یک آبجکت برگشت داده می‌شود. خروجی به صورت زیر می‌باشد:

```json
{
  "ok": true,
  "result": {
    "id": 112233,
    "is_bot": true,
    "first_name": "jki",
    "last_name": "eitaayar",
    "username": "testAdmin"
  }
}
```

---

**2. متد sendMessage**

از این متد برای ارسال پیغام متنی استفاده می‌شود و در صورت موفقیت آمیز بودن، پیغام ارسال شده در JSON خروجی با عنوان `text` برگشت داده می‌شود.

**پارامترهای قابل تنظیم:**

- `chat_id`: شناسه منحصر به فرد کانال یا گروه است که در قسمت کانال‌ها در پنل ایتایار برای هر کانال موجود می‌باشد. البته می‌توانید به جای شناسه از username کانال بدون `@` استفاده کنید. **(اجباری)**  
  _(مثال: `chat_id=1404` و `chat_id=eitaayar`)_
- `text`: متن پیامی که می‌خواهید ارسال کنید. **(اجباری)**
- `title`: عنوان مطلب که فقط در پنل کاربرد دارد و برای جستجو و نمایش لیستی پیغام استفاده می‌شود. **(اختیاری)**
- `disable_notification`: اگر با عدد یک مقدار دهی شود، پیام را بدون notification برای کاربر ارسال می‌کند. **(اختیاری)**
- `reply_to_message_id`: اگر می خواهید متنی که ارسال می کنید در جواب یک پیام دیگر باشد، شناسه ی آن مطلب در پیام رسان ایثار را با استفاده از این پارامتر مشخص می‌کنید. **(اختیاری)**
- `date`: تاریخ و زمان ارسال پیغام که باید به صورت Unix time ارسال شود. برای محاسبه این عدد از تعداد ثانیه‌ها از اول ژانویه 1970 (ساعت هماهنگ جهانی) استفاده می‌شود. به عنوان مثال در PHP این عدد از تابع `time()` استخراج می‌شود. **(اختیاری)**
- `pin`: اگر با مقدار `1` مقدار دهی شود، پیغام بعد از ارسال، در کانال یا گروه سنجاق می‌شود. **(اختیاری)**
- `auto_delete`: وقتی که تعداد مشاهده ی پیام توسط کاربران ایثار به این عدد برسد، پیغام فوق حذف می‌شود. **(اختیاری)**

> **توجه:** اگر خطایی رخ دهد یا پارامتر اشتباهی ارسال کنید، با مقدار `ok` برابر با `false` مواجه خواهید شد.

خروجی بدون خطا به صورت زیر می‌باشد:

```json
{
  "ok": true,
  "result": {
    "message_id": 85917,
    "from": {
      "id": 112233,
      "is_bot": true,
      "first_name": "jki",
      "last_name": "eitaayar",
      "username": "testAdmin"
    },
    "chat": {
      "id": 112233,
      "type": "public",
      "username": "eitaa"
    },
    "date": 1560849434,
    "text": "متن ارسال"
  }
}
```

---

**3. متد sendFile**

این متد همانند متد `sendMessage` می‌باشد با این تفاوت که جهت ارسال فایل، صوت، فیلم و... از آن استفاده می‌شود.

پارامترهای این متد همانند پارامترهای `sendMessage` است که یک گزینه‌ی آن متفاوت است و یک گزینه هم بیشتر دارد:

**پارامترهای قابل تنظیم:**

- `file`: برای ارسال مدیا یا هر نوع فایل دیگر به پیام‌رسان از آن استفاده می‌شود. **(اجباری)**
- `caption`: در این متد باید از `caption` به جای استفاده از `text` در متد `sendMessage` استفاده شود تا متن فایل دریافت شود. **(اختیاری)**
- _(بقیه پارامترها مانند `chat_id`, `title`, `disable_notification`, `reply_to_message_id`, `date`, `pin`, `auto_delete` مشابه `sendMessage` هستند)_

> **توجه 1:** برای ارسال گیف، فایل مورد نظر را با پسوند `.gif` ارسال کنید.  
> _(مثال: `sample.mp4` به `sample.gif` تبدیل می‌شود)_
>
> **توجه 2:** برای ارسال استیکر، باید فایل مورد نظر را با پسوند `.webp` ارسال کنید.  
> _(مثال: `sample.webp` به `sample.sticker` تبدیل می‌شود)_

خروجی ارسال درست به صورت زیر می‌باشد:

```json
{
  "ok": true,
  "result": {
    "message_id": 85917,
    "from": {
      "id": 112233,
      "is_bot": true,
      "first_name": "jki",
      "last_name": "eitaayar",
      "username": "testAdmin"
    },
    "chat": {
      "id": 112233,
      "type": "public",
      "username": "eitaa"
    },
    "date": 1560849434,
    "caption": "متن ارسال"
  }
}
```

ضمنا برای تست API می‌توانید بعد از ورود به پنل از آدرس زیر استفاده کنید:  
`https://eitaayar.ir/testApi`

---
