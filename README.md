# Namanganliklar.uz — Admin bilan aloqa boti

Kanal a'zolaridan murojaat va sotiladigan videolarni qabul qilib,
to'g'ridan-to'g'ri **botning o'zi orqali** adminga yetkazuvchi Telegram bot
(alohida guruh kerak emas). Python + [aiogram 3](https://docs.aiogram.dev/)
da yozilgan, ma'lumotlar SQLite'da saqlanadi.

## Bot nima qiladi

1. **✉️ Oddiy murojaat** — foydalanuvchi matn/rasm/video/ovozli xabar yuboradi,
   bot uni to'g'ridan-to'g'ri adminning (sizning) botga shaxsiy
   yozishmangizga yetkazadi. O'sha xabarga **reply** qilib javob yozsangiz,
   javob avtomatik foydalanuvchiga yetadi (foydalanuvchi botning
   username'ini yoki ID'sini bilishi shart emas, hammasi bot ichida bo'ladi).
   - Sizga kelgan har bir **rasm/video/hujjat/audio/ovozli xabar** ostida
     kimdan kelgani (ism, username, ID, agar bo'lsa telefon raqami va
     ticket raqami) avtomatik yozib qo'yiladi — bir nechta kishi bir vaqtda
     yozayotganda ham adashib qolmaysiz.
   - Agar kimdir **video** yuborsa-yu, bizda uning telefon raqami hali
     bo'lmasa (masalan "Oddiy murojaat" orqali to'g'ridan-to'g'ri video
     yuborsa), bot videoni qabul qilishdan oldin **avval telefon raqamini
     so'raydi** — video shu payt yuborilmaydi, raqam ulashilgach qayta
     yuborish kerak bo'ladi.
2. **🎥 Video sotaman** — tugma bosilishi bilan bot avval foydalanuvchiga
   qoidalarni eslatadi (video tiniq/sifatli va ma'lumotlar aniq bo'lishi
   shart, to'lov video kanalga chiqqandan keyin amalga oshadi, yolg'on
   ma'lumot uchun javobgarlik o'zida, shaxsi sir saqlanishi kafolatlanadi),
   so'ng telefon raqamini (Telegram profilidan, "Share contact" orqali)
   so'raydi va video(lar)ni qabul qiladi. Sizga (adminga) foydalanuvchi
   ismi, username, ID, telefon raqami va **✅ Sotib olindi / 🤝 Muzokara /
   ❌ Rad etish** tugmalari bilan xabar keladi.
   - **✅ Sotib olindi** bosilganda bot sizdan **necha so'mga sotib
     olganingizni so'raydi** (masalan `25000` deb yozasiz) — shundan keyin
     ticket "sotib olindi" deb belgilanadi, narx saqlanadi, summasi
     foydalanuvchining **balansiga qo'shiladi** va unga tabrik xabari ketadi.
   - **🤝 Muzokara** / **❌ Rad etish** — narx so'ralmaydi, holat darrov
     yangilanadi va foydalanuvchiga tegishli xabar ketadi.
3. **💰 Balans va pulni yechib olish** — har bir foydalanuvchining bot
   ichida shaxsiy "balansi" bor:
   - Videosi sotib olinganda summasi avtomatik balansiga qo'shiladi (bir
     nechta video sotsa, hammasi qo'shilib boradi). Foydalanuvchi asosiy
     menyudagi **"💰 Balansim"** tugmasi orqali istalgan payt balansini
     ko'rishi mumkin.
   - Foydalanuvchi **"💳 Hoziroq yechib olish"** tugmasini bossa, sizga
     (adminga) so'rov keladi — ism, telefon raqami va summasi bilan.
   - Siz to'lovni qo'lda amalga oshirgach (karta/naqd), **"✅ To'ladim"**
     tugmasini bosasiz — shunda foydalanuvchiga "pul tushdimi?" deb so'rov
     ketadi.
   - Foydalanuvchi **"✅ Ha, pul tushdi"** deb tasdiqlasa, uning balansi
     shu summaga kamayadi (odatda 0 ga tushadi) va unga "kelajakda yana
     sizdan video kutib qolamiz" degan yakuniy xabar ketadi.
4. **Majburiy obuna tekshiruvi** (ixtiyoriy, `.env`da o'chirish mumkin) —
   kanalga a'zo bo'lmagan foydalanuvchi botdan foydalana olmaydi.
5. **Statistika** — botga (admin sifatida) yozsangiz:
   - `/stats` — umumiy statistika: foydalanuvchilar, murojaatlar, necha
     video sotib olingan/rad etilgan/ko'rib chiqilmoqda, **jami qancha
     summa sarflangani** va foydalanuvchilarda **hali yechilmagan balans**.
   - `/bought` — sotib olingan videolarning ro'yxati (kim, qachon, necha
     so'mga) — oxirgi 20 tasi.

> ⚠️ **Muhim:** botning sizga yuborgan xabariga (yoki o'sha zanjirdagi
> istalgan xabarga) **reply** qilingan HAR QANDAY xabaringiz avtomatik
> foydalanuvchiga yuboriladi. Shunchaki reply qilmasdan yozgan xabarlaringiz
> (masalan o'z eslatmalaringiz) foydalanuvchiga yuborilmaydi.

Har bir murojaat/video-taklif alohida "ticket" sifatida bazada saqlanadi,
shuning uchun bir nechta murojaat parallel kelsa ham chalkashlik bo'lmaydi —
qaysi xabarga reply qilsangiz, javob aynan o'sha foydalanuvchiga boradi.

**Bir nechta admin kerak bo'lsa** — `ADMIN_IDS` ga IDlarni vergul bilan
qo'shsangiz, murojaat/video HAMMA adminlarga birdek keladi va istalgan admin
o'z chatidan reply qilib javob bera oladi (kim birinchi javob yozsa, o'shani
foydalanuvchi ko'radi; ikkinchi admin yana javob yozsa, u ham alohida
xabar sifatida boradi — shuning uchun bir nechta admin bo'lsa, kim kimga
javob berayotganini o'zaro Telegram'da kelishib olishingiz tavsiya etiladi,
chunki adminlar bir-birining chatini ko'rmaydi).

## 1-qadam: Bot yaratish (BotFather)

1. Telegram'da [@BotFather](https://t.me/BotFather) ga yozing → `/newbot`.
2. Nom va username bering (username `bot` bilan tugashi kerak, masalan
   `namanganliklar_admin_bot`).
3. Sizga beriladigan **tokenni** saqlab qo'ying — bu `BOT_TOKEN`.

## 2-qadam: O'zingizning Telegram ID'ingizni bilib olish

1. Telegram'da [@userinfobot](https://t.me/userinfobot) ga yozing — u sizga
   ID'ingizni (masalan `123456789`) yozadi.
2. Bir nechta admin bo'lsa, har biri shu botga yozib o'z ID'sini bilib oladi.
3. Shu raqam(lar) — `ADMIN_IDS` (bir nechta bo'lsa vergul bilan:
   `123456789,987654321`).
4. **Muhim:** botni ishga tushirgach, har bir admin albatta **o'zi shu
   botga birinchi bo'lib `/start` bosishi shart** — aks holda Telegram
   qoidasiga ko'ra bot unga xabar yubora olmaydi (bot birinchi bo'lib
   yozolmaydi).

## 3-qadam: Kanal bilan bog'lash (obuna tekshiruvi uchun, ixtiyoriy)

Agar `REQUIRE_SUBSCRIPTION=true` bo'lsa, bot foydalanuvchi kanalga a'zo
ekanini tekshiradi. Buning uchun **bot Namanganliklar.uz kanaliga admin
sifatida qo'shilgan bo'lishi kerak** (oddiy a'zo sifatida emas — aks holda
Telegram API boshqa foydalanuvchilarning a'zolik holatini ko'rsatmaydi).
`CHANNEL_USERNAME` ga kanal username'ini yozing (`@` belgisisiz).

Agar bu funksiya kerak bo'lmasa, `.env` da `REQUIRE_SUBSCRIPTION=false`
qiling — shunda kanalga admin qilib qo'shish shart emas.

## 4-qadam: GitHub'ga joylashtirish

```bash
cd namanganliklar_bot
git init
git add .
git commit -m "Namanganliklar admin bot"
git branch -M main
git remote add origin https://github.com/<username>/<repo-nomi>.git
git push -u origin main
```

`.env` fayli `.gitignore`da bor — tokeningiz GitHub'ga tasodifan yuklanib
ketmaydi. `.env.example`ni namuna sifatida qoldiring.

## 5-qadam: Railway'da deploy qilish

1. [railway.app](https://railway.app) ga GitHub akkountingiz bilan kiring.
2. **New Project → Deploy from GitHub repo** → shu repozitoriyni tanlang.
3. Railway `requirements.txt` va `Procfile`ni avtomatik aniqlaydi (worker
   sifatida `python bot.py` ishga tushadi).
4. **Variables** bo'limiga quyidagilarni qo'shing (`.env.example` asosida):
   - `BOT_TOKEN`
   - `ADMIN_IDS`
   - `CHANNEL_USERNAME`
   - `REQUIRE_SUBSCRIPTION`
   - `MIN_VIDEO_PRICE`, `MAX_VIDEO_PRICE`
   - `DB_PATH` (masalan `bot.db`)
5. **Deploy** tugmasini bosing. Loglar bo'limida
   `Bot ishga tushdi (polling)...` yozuvini ko'rsangiz — tayyor.
6. Deploy tugagach, o'zingiz botga Telegram'da `/start` yozishni unutmang
   (2-qadamdagi eslatma) — aks holda bot sizga murojaatlarni yuborolmaydi.

> **Eslatma (ma'lumotlar bazasi haqida):** Railway'ning oddiy fayl tizimi
> har safar qayta deploy qilinganda tozalanadi. Agar murojaatlar tarixi
> uzoq muddat saqlanishi muhim bo'lsa, Railway'da **Volume** qo'shib
> `DB_PATH`ni shu volume ichidagi faylga ko'rsating (Railway → Settings →
> Volumes), aks holda har deploy'da statistika/tarix nolanishi mumkin
> (joriy murojaatlarga bu ta'sir qilmaydi, chunki ular tezkor javob
> beriladi).

## Lokal test qilish

```bash
cd namanganliklar_bot
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # so'ng .env faylini to'ldiring
python bot.py
```

## Loyihaviy tuzilma

```
namanganliklar_bot/
├── bot.py              # kirish nuqtasi (polling ishga tushiradi)
├── config.py            # .env o'zgaruvchilarini o'qiydi
├── database.py           # SQLite: users, tickets, ticket_messages
├── keyboards.py          # tugmalar
├── utils.py              # admin xabar matnlari
├── handlers/
│   ├── user.py           # foydalanuvchi bilan suhbat
│   └── admin.py          # adminning shaxsiy chatidagi javob/holat mantig'i
├── requirements.txt
├── Procfile               # Railway/Heroku uchun
├── runtime.txt
└── .env.example
```

## Qo'shimcha takliflar (rivojlantirish uchun)

Siz so'ragan asosiy funksiyalardan tashqari, quyidagilarni ham qo'shish
mumkin — hozircha kodga kiritilmagan, lekin mavjud tuzilma ustiga qo'shish
oson:

- **Anonim murojaat rejimi** — foydalanuvchi ismini adminlardan yashirish
  imkoniyati (murojaat matnida sezgir mavzular bo'lsa foydali).
- **Bir nechta admin bir video ustida ishlamasligi uchun "band qilindi"**
  belgisi — kimdir "Men bilan gaplashyapman" tugmasini bossa, boshqalarga
  ko'rinadi (hozir bir nechta admin bo'lsa, kim kimga javob berayotganini
  o'zaro kelishib olish kerak, chunki adminlar bir-birining chatini
  ko'rmaydi).
- **Spam/flood himoyasi** — bir daqiqada bir nechta xabar yuborishni
  cheklash, muammoli foydalanuvchilarni bloklash (`is_blocked` ustuni
  bazada allaqachon tayyor turibdi).
- **Video uchun avtomatik kanalga post qilish tugmasi** — admin "Sotib
  olindi" bossa, bitta tugma bilan videoni to'g'ridan kanalga ulash.
- **Tez-tez so'raladigan savollar (FAQ) bo'limi** — asosiy menyuga
  qo'shimcha tugma sifatida.
- **Ma'lumotlar bazasi zaxira nusxasi (backup)** — `bot.db` faylini har
  kuni avtomatik Telegram'ga yoki bulutga yuborib turish.
- **Excel/CSV eksport** — `/bought` ro'yxatini oylik hisobot sifatida fayl
  qilib olish.

Qaysi birini keyingi navbatda qo'shishni xohlasangiz, ayting — shu tuzilma
ustiga qo'shib beraman.
