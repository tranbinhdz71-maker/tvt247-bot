# main.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)

# ===============================
# 🔑 CẤU HÌNH BOT
# ===============================
BOT_TOKEN = "7993525432:AAEaAgxkm8VCOUaS5LVx2bLKlXcExwUrK7g"
BOT_USERNAME = "Casino36_bot"

CHANNEL_USERNAME = "@capnhatkeoo"
GROUP_USERNAME = "@CongDongVTV24h"

REWARD_PER_REF = 3600
MIN_WITHDRAW = 36000
DB_PATH = "data.db"

ADMIN_ID = 7509928631  # 👈 ID của bạn (Kỳ Vọng)

# ===============================
# 🧩 DATABASE
# ===============================
def setup_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            ref_by INTEGER,
            invited_count INTEGER DEFAULT 0,
            balance INTEGER DEFAULT 0
        )"""
    )
    conn.commit()
    conn.close()

def db_get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def db_ensure_user(user_id, username=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    if username:
        c.execute("UPDATE users SET username=? WHERE user_id=?", (username, user_id))
    conn.commit()
    conn.close()

# ===============================
# 🏁 /start
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id, username = user.id, user.username or ""
    db_ensure_user(user_id, username)

    args = context.args
    if args:
        ref = args[0].replace("ref", "")
        try:
            ref_id = int(ref)
            if ref_id != user_id:
                context.user_data["pending_ref"] = ref_id
        except:
            pass

    text = (
        "🔔 <b>Sân chơi kiếm tiền uy tín xanh chín</b>\n"
        f"🎁 Mời bạn bè nhận <b>{REWARD_PER_REF:,}đ</b> / bạn\n"
        f"💵 Rút thưởng từ <b>{MIN_WITHDRAW:,}đ</b> / duyệt 24/7\n"
        "👉 Gõ <b>/start</b> để khởi động nào!\n\n"
        "🎯 Để tiếp tục và nhận thưởng, hãy tham gia đầy đủ:\n"
        f"📢 Kênh: {CHANNEL_USERNAME}\n"
        f"💬 Nhóm: {GROUP_USERNAME}\n\n"
        "Sau khi tham gia, bấm <b>✅ Đã tham gia</b> để xác nhận.\n"
    )

    keyboard = [
        [InlineKeyboardButton("📢 Vào Kênh", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton("💬 Vào Nhóm", url=f"https://t.me/{GROUP_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton("✅ Đã Tham Gia", callback_data="confirm_join")],
        [InlineKeyboardButton("🔙 Quay Lại Menu", callback_data="menu")]
    ]
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# ===============================
# ✅ Xác nhận đã tham gia
# ===============================
async def confirm_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Đang xác minh...")
    user_id = query.from_user.id
    username = query.from_user.username or ""
    db_ensure_user(user_id, username)

    ref = context.user_data.get("pending_ref")
    if ref:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT ref_by FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if not row or not row[0]:
            c.execute("UPDATE users SET ref_by=? WHERE user_id=?", (ref, user_id))
            c.execute(
                "UPDATE users SET invited_count = invited_count + 1, balance = balance + ? WHERE user_id=?",
                (REWARD_PER_REF, ref),
            )
            conn.commit()
        conn.close()
        context.user_data.pop("pending_ref", None)

    text = "✅ Bạn đã xác minh thành công! Hãy chọn menu bên dưới 👇"
    keyboard = [
        [InlineKeyboardButton("💸 Lấy Link Mời", callback_data="get_link")],
        [InlineKeyboardButton("📊 Số Dư", callback_data="balance")],
        [InlineKeyboardButton("💵 Rút Tiền", callback_data="withdraw")],
        [InlineKeyboardButton("🔙 Quay Lại Menu", callback_data="menu")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ===============================
# 📊 Số dư
# ===============================
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    row = db_get_user(user_id)
    balance = row[4] if row else 0
    invited = row[3] if row else 0

    text = f"💰 Số dư: {balance:,}đ\n👥 Lượt mời: {invited}"
    keyboard = [[InlineKeyboardButton("🔙 Quay Lại Menu", callback_data="menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ===============================
# 💸 Lấy link mời
# ===============================
async def get_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    link = f"https://t.me/{BOT_USERNAME}?start=ref{user_id}"
    text = f"🔗 Link mời của bạn:\n{link}\n\nChia sẻ link này để nhận +{REWARD_PER_REF:,}đ cho mỗi người tham gia!"
    keyboard = [[InlineKeyboardButton("🔙 Quay Lại Menu", callback_data="menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ===============================
# 💵 Rút tiền
# ===============================
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text = "💳 Gửi lệnh rút theo cú pháp:\n\n/ruttien <STK> <Ngân hàng>\n\nVí dụ: /ruttien 28273737 MB"
    keyboard = [[InlineKeyboardButton("🔙 Quay Lại Menu", callback_data="menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ===============================
# /ruttien
# ===============================
async def ruttien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Dùng đúng cú pháp:\n/ruttien <STK> <Ngân hàng>")
        return

    stk, bank = context.args
    text = (
        f"✅ Đơn rút tiền của bạn đã được duyệt!\n\n"
        f"💳 STK: {stk}\n🏦 Ngân hàng: {bank}\n"
        f"💰 Số tiền: {MIN_WITHDRAW:,}đ\nTrạng thái: Đã duyệt ✅"
    )
    await update.message.reply_text(text)

# ===============================
# 🔙 Menu chính
# ===============================
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text = "🏠 Menu chính, chọn chức năng:"
    keyboard = [
        [InlineKeyboardButton("💸 Lấy Link Mời", callback_data="get_link")],
        [InlineKeyboardButton("📊 Số Dư", callback_data="balance")],
        [InlineKeyboardButton("💵 Rút Tiền", callback_data="withdraw")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ===============================
# 📢 LỆNH /thongbao — chỉ admin
# ===============================
async def thongbao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Bạn không có quyền dùng lệnh này.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Dùng đúng cú pháp:\n/thongbao <nội dung>")
        return

    message = " ".join(context.args)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    user_ids = [row[0] for row in c.fetchall()]
    conn.close()

    sent = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(uid, f"📢 <b>THÔNG BÁO MỚI</b>\n\n{message}", parse_mode="HTML")
            sent += 1
        except Exception as e:
            logging.info(f"Lỗi gửi tới {uid}: {e}")

    await update.message.reply_text(f"✅ Đã gửi thông báo tới {sent} người dùng.")

# ===============================
# Handler
# ===============================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data == "confirm_join":
        return await confirm_join(update, context)
    elif data == "get_link":
        return await get_link(update, context)
    elif data == "balance":
        return await balance(update, context)
    elif data == "withdraw":
        return await withdraw(update, context)
    elif data == "menu":
        return await menu(update, context)

# ===============================
# 🚀 MAIN
# ===============================
def main():
    setup_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ruttien", ruttien))
    app.add_handler(CommandHandler("thongbao", thongbao))
    app.add_handler(CallbackQueryHandler(callback))

    print("🤖 Bot Casino36 đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
