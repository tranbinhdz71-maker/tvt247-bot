from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
import sqlite3

BOT_TOKEN = "7993525432:AAEaAgxkm8VCOUaS5LVx2bLKlXcExwUrK7g"

# ===============================
# ⚙️ DATABASE
# ===============================
def setup_db():
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, ref_by INTEGER, invited_count INTEGER DEFAULT 0, balance INTEGER DEFAULT 0)')
    conn.commit()
    conn.close()

# ===============================
# 🏠 MENU CHÍNH
# ===============================
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💰 Nhận thưởng", callback_data="referral")],
        [InlineKeyboardButton("🔗 Lấy link mời", callback_data="get_link")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎯 Chọn tính năng bạn muốn:", reply_markup=reply_markup)

# ===============================
# 📩 LỆNH START (nhận ref)
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))

    if args:
        referrer = int(args[0].replace('ref', ''))
        if referrer != user_id:
            c.execute('UPDATE users SET ref_by = ? WHERE user_id = ? AND ref_by IS NULL', (referrer, user_id))
            c.execute('UPDATE users SET invited_count = invited_count + 1 WHERE user_id = ?', (referrer,))
            c.execute('SELECT invited_count FROM users WHERE user_id = ?', (referrer,))
            count = c.fetchone()[0]
            if count % 5 == 0:
                c.execute('UPDATE users SET balance = balance + 3000 WHERE user_id = ?', (referrer,))
                await context.bot.send_message(referrer, f'🎉 Bạn đã mời đủ {count} người và nhận được 3k!')
    conn.commit()
    conn.close()

    await menu(update, context)

# ===============================
# 🔗 TẠO LINK MỜI
# ===============================
async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    invite_link = f"https://t.me/{context.bot.username}?start=ref{user_id}"
    await update.message.reply_text(f"🔗 Link mời của bạn:\n{invite_link}")

# ===============================
# 🎛️ XỬ LÝ NÚT BẤM MENU
# ===============================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "referral":
        await query.edit_message_text(
            "💸 Mời bạn bè để nhận thưởng!\nDùng lệnh /link để lấy link mời.\n\n🏠 Gõ /menu để quay lại."
        )
    elif query.data == "get_link":
        user_id = update.effective_user.id
        invite_link = f"https://t.me/{context.bot.username}?start=ref{user_id}"
        await query.edit_message_text(f"🔗 Link mời của bạn:\n{invite_link}\n\n🏠 Gõ /menu để quay lại.")
    else:
        await query.edit_message_text("🏠 Quay lại menu chính.")

# ===============================
# 🚀 CHẠY BOT
# ===============================
setup_db()
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", menu))
app.add_handler(CommandHandler("link", link))
app.add_handler(CallbackQueryHandler(button_callback))

app.run_polling()
