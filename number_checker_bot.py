
import logging
import sqlite3
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler
)

# ========== الإعدادات ==========
TOKEN = "YOUR_BOT_TOKEN_HERE"  # ضع توكن البوت هنا
DB_FILE = "numbers_db.sqlite"

# حالات المحادثة
REPORT_NUMBER, REPORT_REASON, REPORT_PROOF = range(3)

# ========== قاعدة البيانات ==========
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reported_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE NOT NULL,
            report_count INTEGER DEFAULT 1,
            first_report_date TEXT,
            last_report_date TEXT,
            report_reason TEXT,
            risk_level TEXT DEFAULT "medium"
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            reporter_id INTEGER,
            report_date TEXT,
            reason TEXT,
            proof TEXT
        )
    """)

    conn.commit()
    conn.close()

def add_report(phone_number, reporter_id, reason, proof=""):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("SELECT report_count FROM reported_numbers WHERE phone_number = ?", (phone_number,))
    result = cursor.fetchone()

    if result:
        cursor.execute("""
            UPDATE reported_numbers 
            SET report_count = report_count + 1,
                last_report_date = ?,
                risk_level = CASE 
                    WHEN report_count >= 10 THEN "high"
                    WHEN report_count >= 5 THEN "medium"
                    ELSE "low"
                END
            WHERE phone_number = ?
        """, (now, phone_number))
    else:
        cursor.execute("""
            INSERT INTO reported_numbers (phone_number, first_report_date, last_report_date, report_reason, risk_level)
            VALUES (?, ?, ?, ?, "low")
        """, (phone_number, now, now, reason))

    cursor.execute("""
        INSERT INTO reports (phone_number, reporter_id, report_date, reason, proof)
        VALUES (?, ?, ?, ?, ?)
    """, (phone_number, reporter_id, now, reason, proof))

    conn.commit()
    conn.close()

def check_number(phone_number):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT phone_number, report_count, first_report_date, last_report_date, risk_level, report_reason
        FROM reported_numbers WHERE phone_number = ?
    """, (phone_number,))

    result = cursor.fetchone()
    conn.close()
    return result

def get_stats():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM reported_numbers")
    total_numbers = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(report_count) FROM reported_numbers")
    total_reports = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM reported_numbers WHERE risk_level = 'high'")
    high_risk = cursor.fetchone()[0]

    conn.close()
    return total_numbers, total_reports, high_risk

# ========== أوامر البوت ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """
🛡️ <b>مرحباً بك في بوت كاشف الأرقام!</b>

هذا البوت يساعدك في التحقق من الأرقام المشبوهة والإبلاغ عنها.

<b>الأوامر المتاحة:</b>
🔍 /check [الرقم] - التحقق من رقم
📝 /report - الإبلاغ عن رقم مشبوه
📊 /stats - إحصائيات
💡 /tips - نصائح للحماية
❓ /help - المساعدة

<b>⚠️ تنبيه:</b> هذا البوت يعتمد على بلاغات المستخدمين ولا يقدم تحقيقاً قضائياً.
    """
    await update.message.reply_text(welcome_text, parse_mode="HTML")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
<b>📖 دليل استخدام البوت:</b>

<b>1. التحقق من رقم:</b>
أرسل: <code>/check 0501234567</code>

<b>2. الإبلاغ عن رقم:</b>
أرسل: <code>/report</code> ثم اتبع التعليمات

<b>3. الإحصائيات:</b>
أرسل: <code>/stats</code>

<b>4. النصائح:</b>
أرسل: <code>/tips</code>

<b>⚠️ ملاحظات:</b>
- يتم حذف الأرقام بعد 3 أشهر إذا لم تتكرر البلاغات
- البلاغات الكاذبة قد تؤدي إلى حظر المستخدم
- البوت لا يكشف هويات الأشخاص، فقط يُحذر من الأرقام
    """
    await update.message.reply_text(help_text, parse_mode="HTML")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ <b>الاستخدام الصحيح:</b>\n<code>/check 0501234567</code>",
            parse_mode="HTML"
        )
        return

    phone_number = context.args[0].strip()
    phone_number = phone_number.replace("+", "").replace(" ", "").replace("-", "")

    result = check_number(phone_number)

    if result:
        number, count, first_date, last_date, risk, reason = result

        if risk == "high":
            emoji = "🔴"
            risk_text = "<b>خطر عالي</b>"
        elif risk == "medium":
            emoji = "🟡"
            risk_text = "<b>خطر متوسط</b>"
        else:
            emoji = "🟢"
            risk_text = "<b>خطر منخفض</b>"

        response = f"""
{emoji} <b>نتيجة التحقق من الرقم:</b> <code>{number}</code>

📊 <b>عدد البلاغات:</b> {count}
⚠️ {risk_text}
📅 <b>أول بلاغ:</b> {first_date}
📅 <b>آخر بلاغ:</b> {last_date}
📝 <b>سبب البلاغ الأكثر شيوعاً:</b> {reason or "غير محدد"}

<b>⚠️ تحذير:</b> هذا الرقم مُبلّغ عنه من قبل مستخدمين. كن حذراً!
        """
    else:
        response = f"""
✅ <b>الرقم غير مُبلّغ عنه</b>

<code>{phone_number}</code>

هذا الرقم غير موجود في قاعدة بيانات البلاغات.
<b>لكن:</b> عدم وجود بلاغات لا يعني أن الرقم آمن بالضرورة.
استمر في الحذر!
        """

    await update.message.reply_text(response, parse_mode="HTML")

# ========== نظام الإبلاغ ==========

async def report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 <b>الإبلاغ عن رقم مشبوه</b>\n\n"
        "الخطوة 1/3: أرسل الرقم المشبوه:\n"
        "(مثال: 0501234567)",
        parse_mode="HTML"
    )
    return REPORT_NUMBER

async def report_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone_number = update.message.text.strip()
    phone_number = phone_number.replace("+", "").replace(" ", "").replace("-", "")

    if not phone_number.isdigit() or len(phone_number) < 8:
        await update.message.reply_text(
            "❌ الرقم غير صالح. أرسل رقماً صحيحاً (8 أرقام على الأقل):"
        )
        return REPORT_NUMBER

    context.user_data["report_number"] = phone_number

    keyboard = [
        [InlineKeyboardButton("💰 طلب تحويل أموال", callback_data="money_transfer")],
        [InlineKeyboardButton("💼 وظيفة وهمية", callback_data="fake_job")],
        [InlineKeyboardButton("🏆 ربح/جائزة وهمية", callback_data="fake_prize")],
        [InlineKeyboardButton("📞 مكالمات مزعجة/ابتزاز", callback_data="harassment")],
        [InlineKeyboardButton("🎣 تصيد/احتيال إلكتروني", callback_data="phishing")],
        [InlineKeyboardButton("❓ سبب آخر", callback_data="other")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📝 <b>الخطوة 2/3:</b> اختر سبب البلاغ:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    return REPORT_REASON

async def report_reason_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    reason_map = {
        "money_transfer": "طلب تحويل أموال",
        "fake_job": "وظيفة وهمية",
        "fake_prize": "ربح/جائزة وهمية",
        "harassment": "مكالمات مزعجة/ابتزاز",
        "phishing": "تصيد/احتيال إلكتروني",
        "other": "سبب آخر"
    }

    context.user_data["report_reason"] = reason_map.get(query.data, "غير محدد")

    await query.edit_message_text(
        "📝 <b>الخطوة 3/3 (اختياري):</b>\n"
        "أرسل وصفاً أو دليلاً إضافياً (لقطة شاشة، تفاصيل)...\n"
        "أو أرسل /skip للتخطي:",
        parse_mode="HTML"
    )
    return REPORT_PROOF

async def report_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    proof = update.message.text
    context.user_data["report_proof"] = proof
    return await save_report(update, context)

async def report_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["report_proof"] = ""
    return await save_report(update, context)

async def save_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = context.user_data.get("report_number")
    reason = context.user_data.get("report_reason")
    proof = context.user_data.get("report_proof", "")
    reporter_id = update.effective_user.id

    add_report(phone, reporter_id, reason, proof)

    result = check_number(phone)
    count = result[1] if result else 1

    await update.message.reply_text(
        f"✅ <b>تم إرسال البلاغ بنجاح!</b>\n\n"
        f"📱 الرقم: <code>{phone}</code>\n"
        f"📝 السبب: {reason}\n"
        f"📊 إجمالي البلاغات على هذا الرقم: {count}\n\n"
        f"شكراً لمشاركتك في حماية الآخرين! 🛡️",
        parse_mode="HTML"
    )

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ تم إلغاء الإبلاغ.")
    return ConversationHandler.END

# ========== أوامر إضافية ==========

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_numbers, total_reports, high_risk = get_stats()

    stats_text = f"""
📊 <b>إحصائيات البوت</b>

📱 إجمالي الأرقام المُبلّغ عنها: <b>{total_numbers}</b>
📝 إجمالي البلاغات: <b>{total_reports}</b>
🔴 أرقام عالية الخطورة: <b>{high_risk}</b>

<b>⚠️ تذكر:</b> هذه البيانات تعتمد على بلاغات المستخدمين.
    """
    await update.message.reply_text(stats_text, parse_mode="HTML")

async def tips_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tips_text = """
💡 <b>نصائح للحماية من الاحتيال الهاتفي:</b>

1️⃣ <b>لا تُرسل أموالاً</b> لشخص لا تعرفه.

2️⃣ <b>لا تشارك معلوماتك البنكية</b> مع أحد.

3️⃣ <b>تحقق من الهوية:</b> اتصل بالجهة مباشرة.

4️⃣ <b>كن حذراً من الوظائف الوهمية.</b>

5️⃣ <b>لا تصدق "الأرباح السريعة".</b>

6️⃣ <b>استخدم هذا البوت</b> للتحقق من الأرقام.

7️⃣ <b>أبلغ فوراً</b> إذا شعرت أنك مستهدف.

<b>🛡️ حمايتك تبدأ من وعيك!</b>
    """
    await update.message.reply_text(tips_text, parse_mode="HTML")

async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text.replace("+", "").replace(" ", "").replace("-", "").isdigit():
        context.args = [text]
        await check_command(update, context)
    else:
        await update.message.reply_text(
            "❓ لم أفهم طلبك.\n"
            "استخدم /help لعرض الأوامر المتاحة."
        )

# ========== التشغيل ==========

def main():
    init_db()

    application = Application.builder().token(TOKEN).build()

    report_conv = ConversationHandler(
        entry_points=[CommandHandler("report", report_start)],
        states={
            REPORT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_number)],
            REPORT_REASON: [CallbackQueryHandler(report_reason_callback)],
            REPORT_PROOF: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, report_proof),
                CommandHandler("skip", report_skip)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_report)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(report_conv)
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("tips", tips_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown))

    print("🤖 البوت يعمل الآن...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
