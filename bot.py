import os
import json
import re
from datetime import datetime, time, timedelta
from collections import defaultdict

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8739407292:AAH-KoH_ZakxmwM6IkvFNGGigBDwtfyNdKQ")
DATA_FILE = "zavod_data.json"

# =====================
# MA'LUMOTLAR
# =====================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_today():
    return datetime.now().strftime("%Y-%m-%d")

def get_month():
    return datetime.now().strftime("%Y-%m")

def uzbek_date(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        oylar = ["","Yanvar","Fevral","Mart","Aprel","May","Iyun",
                 "Iyul","Avgust","Sentabr","Oktabr","Noyabr","Dekabr"]
        return f"{dt.day}-{oylar[dt.month]}, {dt.year}"
    except:
        return date_str

def uzbek_month(month_str):
    try:
        dt = datetime.strptime(month_str + "-01", "%Y-%m-%d")
        oylar = ["","Yanvar","Fevral","Mart","Aprel","May","Iyun",
                 "Iyul","Avgust","Sentabr","Oktabr","Noyabr","Dekabr"]
        return f"{oylar[dt.month]} {dt.year}"
    except:
        return month_str

def init_kun(data, date):
    if date not in data:
        data[date] = {
            "1-smena": {
                "vaqt": "08:00 - 20:00",
                "yonildi": None, "ochildi": None,
                "toxtalishlar": [], "faol_toxtalish": None
            },
            "2-smena": {
                "vaqt": "20:00 - 08:00",
                "yonildi": None, "ochildi": None,
                "toxtalishlar": [], "faol_toxtalish": None
            }
        }
    return data

def qaysi_smena(vaqt_str=None):
    if vaqt_str:
        try:
            h = int(vaqt_str.split(":")[0])
            return "1-smena" if 8 <= h < 20 else "2-smena"
        except:
            pass
    h = datetime.now().hour
    return "1-smena" if 8 <= h < 20 else "2-smena"

def joriy_smena():
    return qaysi_smena()

# =====================
# VAQT
# =====================
def parse_time(text):
    m = re.search(r'(\d{1,2})[:\.](\d{2})', text)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            return f"{h:02d}:{mn:02d}"
    return None

def time_diff(t1, t2):
    try:
        d1 = datetime.strptime(t1, "%H:%M")
        d2 = datetime.strptime(t2, "%H:%M")
        diff = (d2 - d1).total_seconds() / 3600
        if diff < 0:
            diff += 24
        return round(diff, 2)
    except:
        return 0.0

# =====================
# XABAR TAHLILI
# =====================
def analyze_message(text):
    t = text.lower()
    result = {"type": None, "time": parse_time(text), "reason": None, "smena": None}

    if "1-smena" in t or "birinchi smena" in t:
        result["smena"] = "1-smena"
    elif "2-smena" in t or "ikkinchi smena" in t:
        result["smena"] = "2-smena"

    if any(w in t for w in ["yondi","ishga tushdi","boshlandi","yoqildi","start"]):
        result["type"] = "yondi"
        if not result["smena"]:
            result["smena"] = qaysi_smena(result["time"])
        return result

    if any(w in t for w in ["o'chdi","ochdi","to'xtadi","toxtadi","tugadi","yopildi","stop"]):
        result["type"] = "ochdi"
        if not result["smena"]:
            result["smena"] = qaysi_smena(result["time"])
        return result

    if any(w in t for w in ["to'xtalish","toxtalish","nosozlik","buzildi",
                             "elektr uzildi","elektr o'chdi","xom ashyo",
                             "ta'mirlash","remont","ishlamayapti"]):
        result["type"] = "toxtalish_boshlandi"
        if not result["smena"]:
            result["smena"] = qaysi_smena(result["time"])
        sabab_map = {
            "elektr": "Elektr uzilishi",
            "nosozlik": "Texnik nosozlik",
            "buzildi": "Texnik nosozlik",
            "xom ashyo": "Xom ashyo yo'qligi",
            "ta'mirlash": "Texnik xizmat",
            "remont": "Texnik xizmat",
            "ob-havo": "Ob-havo",
        }
        for key, val in sabab_map.items():
            if key in t:
                result["reason"] = val
                break
        result["reason"] = result["reason"] or "Boshqa sabab"
        return result

    if any(w in t for w in ["tuzatildi","davom etdi","qayta yondi",
                             "toxtalish tugadi","to'xtalish tugadi"]):
        result["type"] = "toxtalish_tugadi"
        if not result["smena"]:
            result["smena"] = qaysi_smena(result["time"])
        return result

    return result

# =====================
# ESLATMA TEKSHIRUVI
# =====================
def smena_holati(data, date, smena_nomi):
    """Smena uchun qaysi ma'lumotlar yetishmayotganini qaytaradi"""
    yetishmaydi = []
    if date not in data or smena_nomi not in data[date]:
        yetishmaydi.append("yonildi vaqti")
        yetishmaydi.append("o'chdi vaqti")
        return yetishmaydi

    smena = data[date][smena_nomi]

    if not smena.get("yonildi"):
        yetishmaydi.append("zavod qachon yongani")
    if not smena.get("ochildi"):
        # Faqat smena tugash vaqti o'tgan bo'lsa
        now = datetime.now()
        if smena_nomi == "1-smena" and now.hour >= 20:
            yetishmaydi.append("zavod qachon o'chgani")
        elif smena_nomi == "2-smena" and now.hour < 8:
            yetishmaydi.append("zavod qachon o'chgani")

    # To'xtalish sababi yozilmagan
    for tx in smena.get("toxtalishlar", []):
        if tx.get("boshlandi") and not tx.get("tugadi"):
            yetishmaydi.append(f"to'xtalish ({tx['boshlandi']}) tugash vaqti")
        if tx.get("sabab") == "Boshqa sabab":
            yetishmaydi.append(f"to'xtalish ({tx.get('boshlandi','?')}) sababi")

    return yetishmaydi

async def har_ikki_soat_eslatma(context: ContextTypes.DEFAULT_TYPE):
    """Har 2 soatda ishlaydigan eslatma"""
    chat_id = context.job.chat_id
    data = load_data()
    today = get_today()
    now_h = datetime.now().hour
    smena_nomi = joriy_smena()

    # Faqat ish vaqtida tekshir (07:00-23:00)
    if now_h < 7 or now_h >= 23:
        return

    yetishmaydi = smena_holati(data, today, smena_nomi)

    if yetishmaydi:
        emoji = "🌅" if smena_nomi == "1-smena" else "🌙"
        xabar = (
            f"⚠️ *Eslatma — {smena_nomi}* {emoji}\n\n"
            f"Quyidagi ma'lumotlar hali kiritilmagan:\n"
        )
        for yetm in yetishmaydi:
            xabar += f"  ❌ {yetm}\n"
        xabar += f"\n_Iltimos, ma'lumotni guruhga yozing!_"
        await context.bot.send_message(chat_id=chat_id, text=xabar, parse_mode="Markdown")

async def smena_tugash_eslatma(context: ContextTypes.DEFAULT_TYPE):
    """Smena tugashidan 30 daqiqa oldin (19:30 va 07:30 da) eslatma"""
    chat_id = context.job.chat_id
    data = load_data()
    today = get_today()
    now_h = datetime.now().hour
    smena_nomi = "1-smena" if now_h == 19 else "2-smena"

    yetishmaydi = []
    if today in data and smena_nomi in data[today]:
        smena = data[today][smena_nomi]
        if not smena.get("yonildi"):
            yetishmaydi.append("zavod qachon yongani")
        if not smena.get("ochildi"):
            yetishmaydi.append("zavod qachon o'chgani")
        for tx in smena.get("toxtalishlar", []):
            if not tx.get("tugadi"):
                yetishmaydi.append(f"to'xtalish ({tx.get('boshlandi','?')}) tugash vaqti va sababi")
    else:
        yetishmaydi = ["smena boshlanish vaqti", "smena tugash vaqti"]

    if yetishmaydi:
        emoji = "🌅" if smena_nomi == "1-smena" else "🌙"
        tugash = "20:00" if smena_nomi == "1-smena" else "08:00"
        xabar = (
            f"🔔 *{smena_nomi} yakunlanmoqda!* {emoji}\n"
            f"_{tugash} ga 30 daqiqa qoldi_\n\n"
            f"Hali kiritilmagan ma'lumotlar:\n"
        )
        for yetm in yetishmaydi:
            xabar += f"  ❌ {yetm}\n"
        xabar += f"\n_Iltimos, smena tugashidan oldin ma'lumotlarni kiriting!_"
        await context.bot.send_message(chat_id=chat_id, text=xabar, parse_mode="Markdown")

# =====================
# HISOBOT
# =====================
def smena_blok(smena_nomi, smena):
    emoji = "🌅" if smena_nomi == "1-smena" else "🌙"
    vaqt_oraliq = smena.get("vaqt", "")
    yonildi = smena.get("yonildi") or "—"
    ochildi = smena.get("ochildi") or "—"
    toxtalishlar = smena.get("toxtalishlar", [])

    jami_ish = 0.0
    if smena.get("yonildi") and smena.get("ochildi"):
        jami_ish = time_diff(smena["yonildi"], smena["ochildi"])

    jami_tox = 0.0
    for tx in toxtalishlar:
        if tx.get("boshlandi") and tx.get("tugadi"):
            jami_tox += time_diff(tx["boshlandi"], tx["tugadi"])
    jami_tox = round(jami_tox, 2)

    lines = [f"{emoji} *{smena_nomi.upper()}* ({vaqt_oraliq})"]
    lines.append(f"  ▶️ Yondi: *{yonildi}*  |  ⏹ O'chdi: *{ochildi}*")

    if jami_ish:
        sof = round(jami_ish - jami_tox, 2)
        lines.append(f"  ⏱ Ish vaqti: *{jami_ish}h*  |  ✅ Sof: *{sof}h*")

    if toxtalishlar:
        lines.append(f"  ⚠️ To'xtalishlar: *{len(toxtalishlar)} ta* ({jami_tox}h)")
        for i, tx in enumerate(toxtalishlar, 1):
            b = tx.get("boshlandi", "?")
            tu = tx.get("tugadi") or "davom etmoqda"
            s = tx.get("sabab", "—")
            if tx.get("boshlandi") and tx.get("tugadi"):
                d = time_diff(tx["boshlandi"], tx["tugadi"])
                lines.append(f"    {i}. {b} → {tu} ({d}h) — {s}")
            else:
                lines.append(f"    {i}. {b} → ... — {s} *(tugallanmagan)*")
    else:
        lines.append("  ✅ To'xtalishlar: yo'q")

    return "\n".join(lines), jami_ish, jami_tox

def sutka_hisobot_matn(data, hisobot_date):
    kecha = (datetime.strptime(hisobot_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

    lines = [
        "📊 *SUTKALIK HISOBOT*",
        f"📅 *{uzbek_date(kecha)}*",
        "━━━━━━━━━━━━━━━━━━",
    ]

    jami_ish = 0.0
    jami_tox = 0.0
    jami_tox_soni = 0

    for smena_nomi in ["1-smena", "2-smena"]:
        if kecha in data and smena_nomi in data[kecha]:
            blok, ish, tox = smena_blok(smena_nomi, data[kecha][smena_nomi])
            jami_ish += ish
            jami_tox += tox
            jami_tox_soni += len(data[kecha][smena_nomi].get("toxtalishlar", []))
        else:
            emoji = "🌅" if smena_nomi == "1-smena" else "🌙"
            vaqt = "08:00-20:00" if smena_nomi == "1-smena" else "20:00-08:00"
            blok = f"{emoji} *{smena_nomi.upper()}* ({vaqt})\n  ℹ️ Ma'lumot kiritilmagan"
        lines.append(blok)
        lines.append("─────────────────")

    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("📌 *JAMI SUTKA:*")
    lines.append(f"  ⏱ Ish vaqti: *{round(jami_ish,2)}h*  |  ✅ Sof: *{round(jami_ish-jami_tox,2)}h*")
    if jami_tox_soni:
        lines.append(f"  ⚠️ To'xtalish: *{jami_tox_soni} ta* ({round(jami_tox,2)}h)")
    else:
        lines.append("  ✅ To'xtalishsiz ishlandi")
    lines.append("━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)

def oylik_hisobot_matn(data, month):
    month_keys = sorted(k for k in data if k.startswith(month))
    if not month_keys:
        return f"📭 {uzbek_month(month)} uchun ma'lumot topilmadi."

    jami_ish = 0.0
    jami_tox = 0.0
    jami_tox_soni = 0
    ish_kunlar = 0
    sabab_counter = defaultdict(float)

    for date in month_keys:
        kun_ish = 0.0
        for smena_nomi in ["1-smena", "2-smena"]:
            smena = data[date].get(smena_nomi, {})
            if smena.get("yonildi") and smena.get("ochildi"):
                d = time_diff(smena["yonildi"], smena["ochildi"])
                kun_ish += d
                jami_ish += d
            for tx in smena.get("toxtalishlar", []):
                if tx.get("boshlandi") and tx.get("tugadi"):
                    d = time_diff(tx["boshlandi"], tx["tugadi"])
                    jami_tox += d
                    sabab_counter[tx.get("sabab","Boshqa")] += d
                jami_tox_soni += 1
        if kun_ish > 0:
            ish_kunlar += 1

    sof = round(jami_ish - jami_tox, 2)
    lines = [
        f"📈 *OYLIK STATISTIKA — {uzbek_month(month)}*",
        "━━━━━━━━━━━━━━━━━━",
        f"📅 Ish kunlari: *{ish_kunlar} kun*",
        f"⏱ Jami ish vaqti: *{round(jami_ish,2)} soat*",
        f"✅ Sof ish vaqti: *{sof} soat*",
        "━━━━━━━━━━━━━━━━━━",
        f"⚠️ Jami to'xtalish: *{jami_tox_soni} ta* ({round(jami_tox,2)}h)",
    ]
    if sabab_counter:
        lines.append("\n📋 *Sabablari:*")
        for sabab, soat in sorted(sabab_counter.items(), key=lambda x: -x[1]):
            lines.append(f"  • {sabab}: {round(soat,2)}h")
    lines.append("━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)

# =====================
# BOT HANDLERS
# =====================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Zavod Monitoring Botiga xush kelibsiz!*\n\n"
        "🌅 *1-smena:* 08:00 – 20:00\n"
        "🌙 *2-smena:* 20:00 – 08:00\n\n"
        "*Guruhga qanday yozasiz:*\n"
        "`1-smena yondi 08:00`\n"
        "`1-smena o'chdi 20:00`\n"
        "`2-smena yondi 20:10`\n"
        "`2-smena to'xtalish — elektr uzildi 23:30`\n"
        "`2-smena tuzatildi 00:10`\n"
        "`2-smena o'chdi 08:00`\n\n"
        "*Buyruqlar:*\n"
        "/hisobot — kechagi sutka hisoboti\n"
        "/oy — joriy oy statistikasi\n"
        "/sozla — avtomatik hisobotni yoqish\n"
        "/yordam — batafsil yordam",
        parse_mode="Markdown"
    )

async def yordam_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *YORDAM*\n\n"
        "*Smena boshlash:*\n"
        "`1-smena yondi 08:05`\n"
        "`2-smena yondi 20:10`\n\n"
        "*Smena tugash:*\n"
        "`1-smena o'chdi 19:55`\n"
        "`2-smena tugadi 08:00`\n\n"
        "*To'xtalish:*\n"
        "`1-smena to'xtalish — nosozlik 11:30`\n"
        "`2-smena elektr uzildi 22:00`\n\n"
        "*To'xtalish tugashi:*\n"
        "`1-smena tuzatildi 12:15`\n"
        "`2-smena davom etdi 22:45`\n\n"
        "*Buyruqlar:*\n"
        "/hisobot — kechagi sutka\n"
        "/oy — joriy oy\n"
        "/oy 2025-04 — boshqa oy\n"
        "/sozla — avtomatik hisobotlarni yoqish",
        parse_mode="Markdown"
    )

async def hisobot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    today = get_today()
    text = sutka_hisobot_matn(data, today)
    await update.message.reply_text(text, parse_mode="Markdown")

async def oy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    month = context.args[0] if context.args else get_month()
    await update.message.reply_text(oylik_hisobot_matn(data, month), parse_mode="Markdown")

async def sozla_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    jq = context.job_queue

    # Eski joblarni o'chirish
    for job_name in [f"sutka_{chat_id}", f"eslatma_{chat_id}",
                     f"smena1_tugash_{chat_id}", f"smena2_tugash_{chat_id}"]:
        for job in jq.get_jobs_by_name(job_name):
            job.schedule_removal()

    # 1. Har kuni 08:00 da sutkalik hisobot
    jq.run_daily(
        avtomatik_hisobot,
        time=time(hour=8, minute=0),
        chat_id=chat_id,
        name=f"sutka_{chat_id}"
    )

    # 2. Har 2 soatda eslatma (08:00, 10:00, 12:00, 14:00, 16:00, 18:00, 20:00, 22:00)
    for soat in [8, 10, 12, 14, 16, 18, 20, 22]:
        jq.run_daily(
            har_ikki_soat_eslatma,
            time=time(hour=soat, minute=0),
            chat_id=chat_id,
            name=f"eslatma_{chat_id}_{soat}"
        )

    # 3. Smena tugashidan 30 daqiqa oldin (19:30 va 07:30)
    jq.run_daily(
        smena_tugash_eslatma,
        time=time(hour=19, minute=30),
        chat_id=chat_id,
        name=f"smena1_tugash_{chat_id}"
    )
    jq.run_daily(
        smena_tugash_eslatma,
        time=time(hour=7, minute=30),
        chat_id=chat_id,
        name=f"smena2_tugash_{chat_id}"
    )

    await update.message.reply_text(
        "✅ *Barcha avtomatik bildirishnomalar yoqildi!*\n\n"
        "🕗 *08:00* — Sutkalik hisobot\n"
        "🔔 *Har 2 soatda* — Ma'lumot kiritilmagan bo'lsa eslatma\n"
        "⏰ *19:30* — 1-smena tugashidan oldin eslatma\n"
        "⏰ *07:30* — 2-smena tugashidan oldin eslatma",
        parse_mode="Markdown"
    )

async def avtomatik_hisobot(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    data = load_data()
    today = get_today()
    text = sutka_hisobot_matn(data, today)
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    result = analyze_message(text)
    if not result["type"]:
        return

    data = load_data()
    today = get_today()
    data = init_kun(data, today)
    smena = result["smena"] or qaysi_smena()
    vaqt = result["time"] or datetime.now().strftime("%H:%M")
    smena_data = data[today][smena]

    if result["type"] == "yondi":
        smena_data["yonildi"] = vaqt
        save_data(data)
        await update.message.reply_text(
            f"✅ *{smena}* — *{vaqt}* da yondi 🟢",
            parse_mode="Markdown"
        )

    elif result["type"] == "ochdi":
        smena_data["ochildi"] = vaqt
        save_data(data)
        extra = ""
        if smena_data.get("yonildi"):
            d = time_diff(smena_data["yonildi"], vaqt)
            extra = f"\n⏱ Smena ish vaqti: *{d} soat*"

        # To'xtalishlar sababi yozilganmi tekshir
        yozilmagan = [tx for tx in smena_data.get("toxtalishlar", [])
                      if tx.get("sabab") == "Boshqa sabab" or not tx.get("tugadi")]
        sabab_eslatma = ""
        if yozilmagan:
            sabab_eslatma = (
                f"\n\n⚠️ *Diqqat!* {len(yozilmagan)} ta to'xtalish uchun "
                f"sabab yoki tugash vaqti kiritilmagan.\n"
                f"_Iltimos, to'xtalish sababini yozing!_"
            )

        await update.message.reply_text(
            f"✅ *{smena}* — *{vaqt}* da o'chdi 🔴{extra}{sabab_eslatma}",
            parse_mode="Markdown"
        )

    elif result["type"] == "toxtalish_boshlandi":
        tx = {"boshlandi": vaqt, "tugadi": None, "sabab": result["reason"]}
        smena_data["toxtalishlar"].append(tx)
        smena_data["faol_toxtalish"] = len(smena_data["toxtalishlar"]) - 1
        save_data(data)

        # Agar sabab "Boshqa sabab" bo'lsa aniqroq yozishni so'ra
        sabab_sorov = ""
        if result["reason"] == "Boshqa sabab":
            sabab_sorov = (
                f"\n\n❓ *To'xtalish sababi aniqlanmadi.*\n"
                f"Iltimos, sababni yozing, masalan:\n"
                f"`{smena} to'xtalish sababi — [sabab]`"
            )

        await update.message.reply_text(
            f"⚠️ *{smena}* — to'xtalish qayd etildi!\n"
            f"🕐 Boshlandi: *{vaqt}*\n"
            f"📋 Sabab: *{result['reason']}*{sabab_sorov}\n\n"
            f"_Tugagach: `{smena} tuzatildi HH:MM` deb yozing_",
            parse_mode="Markdown"
        )

    elif result["type"] == "toxtalish_tugadi":
        faol = smena_data.get("faol_toxtalish")
        toxlar = smena_data.get("toxtalishlar", [])
        if faol is not None and toxlar and toxlar[faol].get("tugadi") is None:
            toxlar[faol]["tugadi"] = vaqt
            b = toxlar[faol]["boshlandi"]
            d = time_diff(b, vaqt)
            s = toxlar[faol]["sabab"]
            smena_data["faol_toxtalish"] = None
            save_data(data)

            # Sabab noaniq bo'lsa so'ra
            sabab_sorov = ""
            if s == "Boshqa sabab":
                sabab_sorov = (
                    f"\n\n❓ *Sabab hali noaniq.* Iltimos yozing:\n"
                    f"`{smena} to'xtalish sababi — [sabab]`"
                )

            await update.message.reply_text(
                f"✅ *{smena}* — to'xtalish tugadi!\n"
                f"🕐 {b} → {vaqt} (*{d} soat*)\n"
                f"📋 Sabab: *{s}*{sabab_sorov}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"ℹ️ *{smena}* uchun faol to'xtalish topilmadi.",
                parse_mode="Markdown"
            )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("yordam", yordam_cmd))
    app.add_handler(CommandHandler("hisobot", hisobot_cmd))
    app.add_handler(CommandHandler("oy", oy_cmd))
    app.add_handler(CommandHandler("sozla", sozla_cmd))
    # Faqat matn xabarlarini qabul qiladi, videolar e'tiborsiz
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot ishga tushdi...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
