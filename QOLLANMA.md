# 📘 TDIU Iqtisodiyot Fakulteti Davomat va Jadval Boti — To'liq Qo'llanma

Mazkur qo'llanma botni o'rnatish, sozlash, Docker orqali serverda ishga tushirish hamda **Admin** va **Tyutorlar** tomonidan botdan to'liq foydalanish bo'yicha batafsil yo'riqnomadir.

---

## 📑 Mundarija
1. [Loyiha Haqida](#1-loyiha-haqida)
2. [O'rnatish va Sozlash](#2-ornatish-va-sozlash)
   - [Lokal muhitda ishga tushirish](#21-lokal-muhitda-ishga-tushirish)
   - [🐳 Docker / Serverda 24/7 ishga tushirish](#22--docker--serverda-247-ishga-tushirish)
3. [Admin Bo'limi Qo'llanmasi](#3-admin-bolimi-qollanmasi)
   - [Dars jadvalini Google Sheets ga yuklash](#31-dars-jadvalini-google-sheets-ga-yuklash)
   - [Tyutorlarni boshqarish va guruh biriktirish](#32-tyutorlarni-boshqarish-va-guruh-biriktirish)
   - [Excel orqali Import / Export (Barcha bo'limlar)](#33-excel-orqali-import--export)
     - [Yangi talabalarni qo'shish (Smart)](#331-yangi-talabalarni-qoshish-smart)
     - [Guruh bo'yicha talabalarni alohida yangilash](#332-guruh-boyicha-talabalarni-alohida-yangilash)
     - [Butun Fakultet talabalarini to'liq almashtirish](#333-butun-fakultet-talabalarini-toliq-almashtirish)
     - [EduPage Guruhlari xaritasini boshqarish (ID | Guruh | Kurs)](#334-edupage-guruhlari-xaritasini-boshqarish)
     - [Fanlar va Kafedralar xaritasini boshqarish](#335-fanlar-va-kafedralar-xaritasini-boshqarish)
     - [Tyutorlarni yuklash va eksport qilish](#336-tyutorlarni-yuklash-va-eksport-qilish)
     - [Namunaviy shablonlarni yuklab olish](#337-namunaviy-shablonlarni-yuklab-olish)
   - [Yoqlamani tahrirlash](#34-yoqlamani-tahrirlash)
   - [Yoqlamalar tarixini Excel qilib olish](#35-yoqlamalar-tarixini-excel-qilib-olish)
4. [Tyutorlar Uchun Qo'llanma](#4-tyutorlar-uchun-qollanma)
   - [Yoqlama kiritish tartibi](#41-yoqlama-kiritish-tartibi)
   - [100% to'liq qatnashishni belgilash](#42-100-toliq-qatnashishni-belgilash)
5. [Avtomatlashtirish (Scheduler)](#5-avtomatlashtirish-scheduler)

---

## 1. Loyiha Haqida

Ushbu bot **Toshkent Davlat Iqtisodiyot Universiteti (TDIU)** Iqtisodiyot fakultetida o'quv jarayonini avtomatlashtirish uchun mo'ljallangan:
* **EduPage platformasi**dan dars jadvallarini avtomatik yig'adi va Google Sheets ga chiroyli ranglar, formulalar bilan joylaydi.
* **Tyutorlar** har bir parada o'z guruhlari bo'yicha talabalar davomatini inline tugmalar orqali soniyalar ichida kiritadi.
* Kiritilgan davomat bir vaqtning o'zida **PostgreSQL** ma'lumotlar bazasida saqlanadi va **Google Sheets** dagi jadvalda avtomatik yangilanadi.

---

## 2. O'rnatish va Sozlash

### 2.1. Lokal muhitda ishga tushirish

1. `.env` faylini to'ldiring:
```env
BOT_TOKEN=TELEGRAM_BOT_TOKEN
ADMINS=TELEGRAM_ADMIN_ID
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST/DATABASE?ssl=require
SPREADSHEET_ID=GOOGLE_SHEETS_ID
SPREADSHEET_NAME=Dars jadvali 2025
GOOGLE_CREDENTIALS=credentials.json
```

2. Ishga tushirish:
```bash
.\.venv\Scripts\python main.py
```

---

### 2.2. 🐳 Docker / Serverda 24/7 ishga tushirish

Loyihada Linux server uchun Headless Chromium va aynan shu paketga mos ChromeDriver bir image ichida o'rnatiladi. Google service-account JSON fayli image ichiga yozilmaydi; `.env` dagi `GOOGLE_CREDENTIALS` yo'li orqali konteynerga faqat o'qish rejimida ulanadi.

Google Sheets faylini service-account JSON ichidagi `client_email` manziliga **Editor** qilib ulashing. `.env` ichidagi `GOOGLE_CREDENTIALS` serverdagi JSON fayl nomiga mos bo'lishi kerak, masalan `credentials.json`.

#### Serverda ishga tushirish buyruqlari:

1. **Konfiguratsiyani tekshirish va image yig'ish:**
```bash
docker compose config
docker compose build --pull
```

2. **Neon, Telegram, Google Sheets yozish va EduPage/Chromium to'liq testini bajarish:**
```bash
docker compose run --rm bot python deployment_check.py --google-write
```
Tekshiruv Google Sheets ichida vaqtinchalik varaq yaratadi, formula ishlashini tekshiradi va varaqni darhol o'chiradi.

3. **Botni fonda ishga tushirish:**
```bash
docker compose up -d
```

4. **Bot loglarini jonli kuzatish:**
```bash
docker compose logs -f
```

5. **Konteyner holatini tekshirish:**
```bash
docker compose ps
```

6. **Botni to'xtatish:**
```bash
docker compose down
```

7. **Botni qayta ishga tushirish:**
```bash
docker compose restart
```

---

## 3. Admin Bo'limi Qo'llanmasi

Admin Telegramda `/start` buyrug'ini yuborganida quyidagi asosiy menyu ochiladi:

```
[ 📅 Jadval yuklash ]   [ 📋 Yoqlama qilish ]
[ 👥 Tyutorlar ]       [ ➕ Tyutor qo'shish ]
[ 📊 Yoqlamalar tarixi ][ ✏️ Yoqlamani tahrirlash ]
[ 📥 Import / Export (Excel) ]
```

---

### 3.1. Dars jadvalini Google Sheets ga yuklash
1. **«📅 Jadval yuklash»** tugmasini bosing.
2. Bot taqvimdan haftaning kunlarini chiqaradi. Kerakli sanani tanlang.
3. Kursni tanlang (masalan: `1-kurs` yoki `2-kurs`).
4. Bot avtomatik ravishda EduPage tizimidan jadvalni yig'adi va Google Sheets ga maxsus tartibda (kafedra, o'qituvchi, xona, para, formulalar bilan) joylaydi.

---

### 3.2. Tyutorlarni boshqarish va guruh biriktirish
* **Yangi tyutor qo'shish:**
  1. **«➕ Tyutor qo'shish»** tugmasini bosing.
  2. Tyutorning to'liq ism-familiyasini kiriting (masalan: *Safarova Sevara*).
  3. Tyutorning Telegram ID raqamini kiriting.
* **Guruh biriktirish yoki o'chirish:**
  1. **«👥 Tyutorlar»** tugmasini bosing.
  2. Kerakli tyutor nomini tanlang.
  3. **«📎 Guruhlarni biriktirish / o'chirish»** tugmasini bosing.
  4. Guruhlar ro'yxatidan kerakli guruhlarni bosing:
     - `⬜` — biriktirilmagan
     - `☑️` — yangi tanlangan
     - `✅` — biriktirilgan
  5. **«💾 Saqlash»** tugmasini bosing.

---

### 3.3. Excel orqali Import / Export

Bu bo'lim orqali barcha ma'lumotlarni Excel fayllari orqali soniyalar ichida boshqarishingiz mumkin:

#### 3.3.1. Yangi talabalarni qo'shish (Smart)
* **«📥 Yangi Talabalarni qo'shish»** — Mavjud talabalarga tegilmaydi, faqat yangi talabalar bazaga qo'shiladi.

#### 3.3.2. Guruh bo'yicha talabalarni alohida yangilash
* **«🔄 Guruh bo'yicha Talabalarni yangilash»** — Faqat bitta guruhning talabalari o'zgarganda, o'sha guruhni tanlab yangilash.

#### 3.3.3. Butun Fakultet talabalarini to'liq almashtirish
* **«⚠️ Butun Fakultet Talabalarini To'liq Almashtirish»** — Yangi o'quv yili boshida butun fakultet talabalarini yangi ro'yxatga 100% almashtirish.

#### 3.3.4. EduPage Guruhlari xaritasini boshqarish (ID | Guruh | Kurs)
* **«🏫 EduPage Guruhlarini Import qilish»** — EduPage dagi guruh ID lari va kurslarini Excel orqali kiritish.
* **«📤 EduPage Guruhlarini Export qilish»** — Mavjud ro'yxatni Excel formatda yuklab olish.

#### 3.3.5. Fanlar va Kafedralar xaritasini boshqarish
* **«📚 Fanlar & Kafedralarni Import qilish»** — Fan va kafedralar xaritasini Excel orqali yuklash.
* **«📤 Fanlar & Kafedralarni Export qilish»** — Mavjud ro'yxatni yuklab olish.

#### 3.3.6. Tyutorlarni yuklash va eksport qilish
* **«📥 Tyutorlarni Import qilish»** / **«📤 Tyutorlarni Export qilish»**.

#### 3.3.7. Namunaviy shablonlarni yuklab olish
* **«📄 Namunaviy Shablonlarni yuklab olish»** orqali barcha bo'limlar uchun 5 xil tayyor shablonlarni yuklab olishingiz mumkin.

---

### 3.4. Yoqlamani tahrirlash
Agar avval kiritilgan yoqlamada xatolik ketgan bo'lsa yoki o'zgartirish kerak bo'lsa:
1. **«✏️ Yoqlamani tahrirlash»** tugmasini bosing.
2. Sanani kiriting (masalan: `25.03.2026`).
3. Kerakli parani va guruhni tanlang.
4. Talabalar ro'yxatidan kerakli talabani belgilang/o'zgartiring va **«💾 Saqlash»** tugmasini bosing.

---

### 3.5. Yoqlamalar tarixini Excel qilib olish
1. **«📊 Yoqlamalar tarixi»** tugmasini bosing.
2. Kerakli sanani tanlang.
3. Hisobotga kiritmoqchi bo'lgan paralarni belgilang (yoki «Barchasi»ni bosing) va **«➡️ Davom etish»**ni bosing.
4. Guruhlarni tanlang va **«📥 Excel hisobotni yuklash»** tugmasini bosing.
5. Bot bir necha soniyada rangli, foizlari va qatnashmagan talabalar ro'yxati keltirilgan tayyor `.xlsx` hisobot faylini yuboradi.

---

## 4. Tyutorlar Uchun Qo'llanma

### 4.1. Yoqlama kiritish tartibi
1. Botga kirib `/start` buyrug'ini yuboring.
2. **«📋 Yoqlama qilish»** tugmasini bosing.
3. O'zingizga biriktirilgan guruhlar ro'yxatidan kerakli guruhni tanlang.
4. Dars juftligini (masalan: `1-para`) tanlang.
5. Guruh talabalari ro'yxati chiqadi:
   - Darsda **yo'q (kelmagan)** talabalarning ustiga bir marta bosing (ular oldida `❌` belgisi paydo bo'ladi).
   - Agar guruhda talabalar ko'p bo'lsa, pastdagi `▶️` tugmasi orqali keyingi sahifaga o'ting.
6. Barcha kelmaganlar belgilangach, pastdagi **«💾 Saqlash»** tugmasini bosing.

### 4.2. 100% to'liq qatnashishni belgilash
Agar guruhdagi barcha talabalar darsda to'liq qatnashayotgan bo'lsa:
* Hech kimni belgilamasdan to'g'ridan-to'g'ri **«💯 Hammasi kelgan»** tugmasini bosing.

---

## 5. Avtomatlashtirish (Scheduler)

Botda o'rnatilgan foniy scheduler (APScheduler) mavjud:
* **Har kuni ertalab soat 07:00 da (Toshkent vaqti bilan)** bot avtomatik tarzda bugungi kun uchun EduPage dan dars jadvallarini yuklab oladi va Google Sheets ga joylaydi.
* Muvaffaqiyatli yuklanganligi haqida barcha adminlarga avtomatik xabar yuboriladi.
* Yakshanba kunlari dars bo'lmaganligi sababli scheduler avtomatik dam oladi.

---

🎉 **Tizim foydalanishga to'liq tayyor!**
