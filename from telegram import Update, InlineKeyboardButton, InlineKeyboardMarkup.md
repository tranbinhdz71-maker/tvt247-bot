from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup  
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes  
import sqlite3  
  
# 🔑 Token bot của bạn  
BOT_TOKEN = "7993525432:AAEaAgxkm8VCOUaS5LVx2bLKlXcExwUrK7g"  
  
# 🔗 Thông tin nhóm  
GROUP_ID = -1003668413482  # ⚠️ Thay bằng ID nhóm thật của bạn  
GROUP_LINK = "https://t.me/CongDongVTV24h"  
  
# ==============================  
# Tạo database để lưu điểm  
def init_db():  
    conn = sqlite3.connect("users.db")  
    cur = conn.cursor()  
    cur.execute("""  
        CREATE TABLE IF NOT EXISTS users (  
            user_id INTEGER PRIMARY KEY,  
            username TEXT,  
            points INTEGER DEFAULT 0  
        )  
    """)  
    conn.commit()  
    conn.close()  
  
def add_points(user_id, username, amount=1000):  
    conn = sqlite3.connect("users.db")  
    cur = conn.cursor()  
    cur.execute("""  
        INSERT INTO users (user_id, username, points)  
        VALUES (?, ?, ?)  
        ON CONFLICT(user_id) DO UPDATE SET points = points + ?  
    """, (user_id, username, amount, amount))  
    conn.commit()  
    conn.close()  
  
def get_points(user_id):  
    conn = sqlite3.connect("users.db")  
    cur = conn.cursor()  
    cur.execute("SELECT points FROM users WHERE user_id=?", (user_id,))  
    row = cur.fetchone()  
    conn.close()  
    return row[0] if row else 0  
  
# ==============================  
# Giao diện /start  
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):  
    keyboard = [  
        [InlineKeyboardButton("🔗 Vào nhóm", url=GROUP_LINK)],  
        [InlineKeyboardButton("✅ Tôi đã vào nhóm", callback_data="xacnhan")],  
        [  
            InlineKeyboardButton("💰 Xem số dư", callback_data="sodu"),  
            InlineKeyboardButton("📋 Hướng dẫn", callback_data="huongdan")  
        ]  
    ]  
    await update.message.reply_text(  
        "🎯 Chào bạn! Hãy vào nhóm rồi nhấn **Tôi đã vào nhóm** để nhận 1000 điểm thưởng 💎",  
        reply_markup=InlineKeyboardMarkup(keyboard)  
    )  
  
# ==============================  
# Xử lý các nút  
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):  
    query = update.callback_query  
    await query.answer()  
    user = query.from_user  
    user_id = user.id  
    username = user.username or user.first_name  
  
    if query.data == "xacnhan":  
        try:  
            member = await context.bot.get_chat_member(GROUP_ID, user_id)  
            if member.status in ["member", "administrator", "creator"]:  
                add_points(user_id, username)  
                points = get_points(user_id)  
                await query.edit_message_text(f"✅ Xác nhận thành công!\nBạn được cộng +1000 điểm.\n💰 Tổng điểm: {points}")  
            else:  
                await query.edit_message_text("⚠️ Bạn chưa vào nhóm! Hãy vào nhóm trước khi xác nhận.")  
        except Exception as e:  
            await query.edit_message_text("⚠️ Bot chưa được thêm vào nhóm hoặc ID nhóm sai.")  
  
    elif query.data == "sodu":  
        points = get_points(user_id)  
        await query.edit_message_text(f"💰 Số dư hiện tại của bạn: {points} điểm.")  
  
    elif query.data == "huongdan":  
        await query.edit_message_text("📋 Hướng dẫn:\n1️⃣ Vào nhóm Telegram.\n2️⃣ Nhấn 'Tôi đã vào nhóm'.\n3️⃣ Bot tự cộng điểm thưởng 💎.")  
  
# ==============================  
# Chạy bot  
if __name__ == "__main__":  
    init_db()  
    app = ApplicationBuilder().token(BOT_TOKEN).build()  
    app.add_handler(CommandHandler("start", start))  
    app.add_handler(CallbackQueryHandler(handle_buttons))  
    print("✅ Bot đang chạy...")  
    app.run_polling()  
