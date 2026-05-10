# Zavod Monitoring Bot — O'rnatish

## 1. Token olish
1. Telegramda @BotFather ga yozing
2. /newbot buyrug'ini yuboring
3. Bot nomi va username kiriting
4. Berilgan TOKEN ni saqlang

## 2. Tokenni sozlash
bot.py faylida:
  BOT_TOKEN = "SHUNGA_TOKENINGIZNI_YOZING"

## 3. Railway.app da ishga tushirish (bepul, 24/7)
1. https://railway.app — GitHub bilan kiring
2. New Project → Deploy from GitHub repo
3. bot.py va requirements.txt ni yuklang
4. Variables bo'limida: BOT_TOKEN = tokeningiz
5. Deploy!

## 4. Guruhga qo'shish
1. Botni guruhga qo'shing
2. /sozla buyrug'ini yuboring — 08:00 da avtomatik hisobot yoqiladi

## Guruhga yozish namunalari

  1-smena yondi 08:05
  1-smena o'chdi 20:00
  2-smena yondi 20:10
  2-smena to'xtalish — elektr uzildi 23:30
  2-smena tuzatildi 00:15
  2-smena o'chdi 08:00

## Buyruqlar
  /hisobot  — kechagi sutka hisoboti (1-smena + 2-smena)
  /oy       — joriy oy statistikasi
  /oy 2025-05 — ma'lum oy statistikasi
  /sozla    — har kuni 08:00 da avtomatik hisobot yoqish
  /yordam   — batafsil yordam
