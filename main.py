# main.py
# main.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO)

# ===============================
# 🔑 CẤU HÌNH — dán token + username ở đây
# ===============================
BOT_TOKEN = "7993525432:AAEaAgxkm8VCOUaS5LVx2bLKlXcExwUrK7g"
# Tên user của bot (không có @). Ví dụ: "KyVongBot"
BOT_USERNAME = "DÁN_USERNAME_BOT_KHÔNG_DAU_MIEU"  

# Chat/channel/group mà bắt buộc tham gia (dùng @username hoặc id)
CHANNEL_USERNAME = "@capnhatkeoo"         # kênh bắt buộc
GROUP_USERNAME = "@CongDongVTV24h"        # nhóm duyệt rút

# phần thưởng mỗi lượt mời
REWARD_PER_REF = 360
# mức rút tối thiểu
MIN_WITHDRAW = 10000

DB_PATH = "data.db"

# ===============================
# 🧩 DATABASE
# ===============================
def setup_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # users: lưu user_id, username, ref_by (user_id), invited_count, balance
    c.execute(
        """CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            ref_by INTEGER,
            invited_count INTEGER DEFAULT 0,
            balance INTEGER DEFAULT 0
        )"""
    )
    # withdrawals: lưu lịch sử rút
    c.execute(
        """CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            stk TEXT,
            bank TEXT,
            amount INTEGER,
            ts DATETIME DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.commit()
    conn.close()

def db_get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, username, ref_by, invited_count, balance FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def db_ensure_user(user_id, username=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    if username:
        c.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
    conn.commit()
    conn.close()

# ===============================
# 🔎 CHECK MEMBER
# ===============================
async def is_member_of(chat_identifier: str, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Trả về True nếu user_id là thành viên của chat_identifier (username hoặc id).
    Lưu ý: bot cần quyền phù hợp để kiểm tra.
    """
    try:
        member = await context.bot.get_chat_member(chat_identifier, user_id)
        status = member.status  # 'member', 'creator', 'administrator', 'left', 'kicked', ...
        return status in ("member", "creator", "administrator")
    except Exception as e:
        # nếu lỗi (ví dụ bot không có quyền, chat private, ...) -> trả False
        logging.info(f"is_member_of error for {chat_identifier} / {user_id}: {e}")
        return False

# ===============================
# 🏁 /start — nhận ref param, show hướng dẫn tham gia kênh+nhóm
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or ""
    args = context.args  # nếu có ?start=xxx sẽ có args[0]

    # đảm bảo user có bản ghi
    db_ensure_user(user_id, username)

    # Save a potential ref temporarily: we'll only credit when user confirms "Đã Tham Gia"
    # Store ref in DB field ref_by only if not set later after confirmation.
    # Here we put the potential ref in context.user_data so when they confirm we can use it.
    if args:
        ref_raw = args[0]
        # we expect format ref<user_id>, but allow plain number too
        if ref_raw.startswith("ref"):
            try:
                ref_id = int(ref_raw.replace("ref", ""))
                # avoid self-ref
                if ref_id != user_id:
                    context.user_data["pending_ref"] = ref_id
            except:
                pass
        else:
            try:
                ref_id = int(ref_raw)
                if ref_id != user_id:
                    context.user_data["pending_ref"] = ref_id
            except:
                pass

    # message hướng dẫn tham gia kênh + nhóm
    text = (
        "🎉 <b>Chào mừng bạn đến với Bot Kỳ Vọng!</b>\n\n"
        "🎯 Để tiếp tục và nhận thưởng, bạn phải tham gia cả <b>kênh</b> và <b>nhóm</b> sau:\n\n"
        f"📢 Kênh chính: {CHANNEL_USERNAME}\n"
        f"💬 Nhóm duyệt rút: {GROUP_USERNAME}\n\n"
        "👉 Sau khi tham gia cả 2, bấm nút <b>✅ Đã Tham Gia</b> để xác nhận.\n\n"
        "💸 Mỗi lượt mời bạn bè thành công = <b>+360đ</b>\n"
        "🏦 Rút tối thiểu 10K về ngân hàng (dùng /ruttien)\n"
    )

    keyboard = [
        [InlineKeyboardButton("🔗 Mở Kênh", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton("🔗 Mở Nhóm", url=f"https://t.me/{GROUP_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton("✅ Đã Tham Gia", callback_data="confirm_join")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)

# ===============================
# ✅ Xác nhận đã tham gia — kiểm tra thực tế, credit ref, mở menu
# ===============================
async def confirm_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_id = user.id
    username = user.username or ""

    # ensure user record
    db_ensure_user(user_id, username)

    # kiểm tra membership trong cả 2 chat
    ok_channel = await is_member_of(CHANNEL_USERNAME, user_id, context)
    ok_group = await is_member_of(GROUP_USERNAME, user_id, context)

    if not ok_channel or not ok_group:
        text = "⚠️ Bạn chưa tham gia đủ kênh và nhóm yêu cầu.\n\nVui lòng tham gia cả 2 rồi bấm lại ✅ Đã Tham Gia."
        # gửi lại nút mở link + confirm
        keyboard = [
            [InlineKeyboardButton("🔗 Mở Kênh", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
            [InlineKeyboardButton("🔗 Mở Nhóm", url=f"https://t.me/{GROUP_USERNAME.lstrip('@')}")],
            [InlineKeyboardButton("✅ Đã Tham Gia", callback_data="confirm_join")],
