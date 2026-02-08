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
REWARD_PER_REF = 3.600
# mức rút tối thiểu
MIN_WITHDRAW =36.000

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
        [InlineKeyboardButton("🔙 Quay Lại Menu", callback_data="menu")],
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
           [
        [InlineKeyboardButton("🔗 Mở Kênh", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton("🔗 Mở Nhóm", url=f"https://t.me/{GROUP_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton("✅ Đã Tham Gia", callback_data="confirm_join")],
        [InlineKeyboardButton("🔙 Quay Lại Menu", callback_data="menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(text, reply_markup=reply_markup)
        except:
            await query.message.reply_text(text, reply_markup=reply_markup)
        return

    # nếu ok cả 2 -> xử lý ref (nếu có pending_ref trong user_data)
    pending_ref = context.user_data.get("pending_ref")
    if pending_ref and pending_ref != user_id:
        # kiểm tra ref có tồn tại trong DB và chưa được set ref_by cho user này
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT ref_by FROM users WHERE user_id = ?", (user_id,))
        res = c.fetchone()
        already_has_ref = False
        if res and res[0]:
            already_has_ref = True

        if not already_has_ref:
            # set ref_by cho user mới
            c.execute("UPDATE users SET ref_by = ? WHERE user_id = ? AND (ref_by IS NULL OR ref_by = '')", (pending_ref, user_id))
            # tăng invited_count của referrer
            c.execute("UPDATE users SET invited_count = invited_count + 1 WHERE user_id = ?", (pending_ref,))
            # cộng tiền thưởng cho referrer
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REWARD_PER_REF, pending_ref))
            # get invited_count to possibly notify
            c.execute("SELECT invited_count, balance FROM users WHERE user_id = ?", (pending_ref,))
            row = c.fetchone()
            conn.commit()
            conn.close()
            # notify referrer
            try:
                invited_count, new_balance = row
                await context.bot.send_message(pending_ref, f"🎉 Bạn vừa được cộng +{REWARD_PER_REF}đ vì có 1 người mới tham gia! Tổng lượt mời: {invited_count}. Số dư hiện tại: {new_balance}đ")
            except Exception as e:
                logging.info(f"Không thể gửi message cho referrer {pending_ref}: {e}")
        else:
            conn.close()

    # xóa pending_ref để không sử dụng lại
    context.user_data.pop("pending_ref", None)

    # Sau khi xác nhận thành công -> mở menu chính
    text_ok = "✅ Bạn đã xác nhận tham gia kênh & nhóm. Bây giờ bạn có thể lấy link mời và bắt đầu kiếm tiền!"
    keyboard = [
        [InlineKeyboardButton("💸 Lấy Link Mời", callback_data="get_link")],
        [InlineKeyboardButton("📊 Số Dư", callback_data="get_balance")],
        [InlineKeyboardButton("💵 Rút Tiền", callback_data="withdraw")],
        [InlineKeyboardButton("🔙 Menu Chính", callback_data="menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(text_ok, reply_markup=reply_markup)
    except:
        await query.message.reply_text(text_ok, reply_markup=reply_markup)

# ===============================
# 🔗 Tạo link mời của user
# ===============================
async def send_personal_link(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    # link mời sử dụng format ?start=ref<user_id>
    return f"https://t.me/{BOT_USERNAME}?start=ref{user_id}"

async def handle_get_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # user request link qua callback hoặc lệnh
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        uid = query.from_user.id
        link = await send_personal_link(uid, context)
        await query.edit_message_text(f"🔗 Link mời của bạn:\n{link}\n\nChia sẻ link để nhận +{REWARD_PER_REF}đ cho mỗi người tham gia.")
    else:
        user = update.effective_user
        link = await send_personal_link(user.id, context)
        await update.message.reply_text(f"🔗 Link mời của bạn:\n{link}\n\nChia sẻ link để nhận +{REWARD_PER_REF}đ cho mỗi người tham gia.")

# ===============================
# 💰 /balance — xem số dư
# ===============================
async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    row = db_get_user(user_id)
    if not row:
        await update.message.reply_text("Bạn chưa có tài khoản trong hệ thống. Hãy dùng /start để đăng ký.")
        return
    _, username, ref_by, invited_count, balance = row
    await update.message.reply_text(f"👤 ID: {user_id}\n💰 Số dư: {balance}đ\n🔁 Lượt mời: {invited_count}")

# ===============================
# 💸 /ruttien — rút tiền (giả lập)
# ===============================
async def ruttien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Vui lòng nhập đúng cú pháp:\n\n/ruttien <STK> <Ngân hàng>\n\nVí dụ: /ruttien 28273737 MB")
        return

    stk = context.args[0]
    bank = context.args[1]

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone()
    if not res:
        conn.close()
        await update.message.reply_text("❌ Bạn chưa có tài khoản trong hệ thống. Hãy dùng /start trước.")
        return

    balance = res[0]
    if balance < MIN_WITHDRAW:
        conn.close()
        await update.message.reply_text(f"⚠️ Số dư của bạn chưa đủ {MIN_WITHDRAW}đ để rút tiền.")
        return

    # trừ MIN_WITHDRAW
    new_balance = balance - MIN_WITHDRAW
    c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
    c.execute("INSERT INTO withdrawals (user_id, stk, bank, amount) VALUES (?, ?, ?, ?)", (user_id, stk, bank, MIN_WITHDRAW))
    conn.commit()
    conn.close()

    text = (
        "✅ <b>Đơn rút tiền của bạn đã được duyệt thành công!</b>\n\n"
        f"💳 <b>Số tài khoản:</b> {stk} – {bank}\n"
        f"💰 <b>Số tiền:</b> {MIN_WITHDRAW}đ\n"
        "⏱️ <b>Trạng thái:</b> Đã duyệt\n\n"
        "Cảm ơn bạn đã sử dụng hệ thống ❤️"
    )
    await update.message.reply_text(text, parse_mode="HTML")

# ===============================
# 🎛️ Callback handler chung (nút menu)
# ===============================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "confirm_join":
        return await confirm_join_callback(update, context)
    elif data == "get_link":
        return await handle_get_link(update, context)
    elif data == "get_balance":
        # show balance
        user_id = query.from_user.id
        row = db_get_user(user_id)
        if not row:
            await query.edit_message_text("Bạn chưa có tài khoản. Hãy dùng /start để đăng ký.")
            return
        _, _, _, invited_count, balance = row
        await query.edit_message_text(f"💰 Số dư: {balance}đ\n🔁 Lượt mời: {invited_count}")
    elif data == "withdraw":
        # hướng dẫn rút tiền
        await query.edit_message_text("Để rút tiền, dùng lệnh:\n/ruttien <SỐ_TÀI_KHOẢN> <NGÂN_HÀNG>\n\nVí dụ: /ruttien 28273737 MB")
    elif data == "menu":
        # đưa user về menu chính
        text = "🏠 Menu chính:\n\nChọn một chức năng:"
        keyboard = [
            [InlineKeyboardButton("💸 Lấy Link Mời", callback_data="get_link")],
            [InlineKeyboardButton("📊 Số Dư", callback_data="get_balance")],
            [InlineKeyboardButton("💵 Rút Tiền", callback_data="withdraw")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.edit_message_text("Hành động không hợp lệ.")

# ===============================
# ✳️ Helper: Khi user gửi /link hoặc /menu qua text
# ===============================
async def link_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_get_link(update, context)

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🏠 Menu chính:\n\nChọn một chức năng:"
    keyboard = [
        [InlineKeyboardButton("💸 Lấy Link Mời", callback_data="get_link")],
        [InlineKeyboardButton("📊 Số Dư", callback_data="get_balance")],
        [InlineKeyboardButton("💵 Rút Tiền", callback_data="withdraw")],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ===============================
# 🚀 KHỞI CHẠY BOT
# ===============================
def main():
    setup_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("link", link_cmd))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("ruttien", ruttien))

    # callback (buttons)
    app.add_handler(CallbackQueryHandler(callback_handler))

    # optional: handle text that contains "/start ref..." when user clicks link in mobile
    # (bot framework already passes start param to /start via context.args)

    print("🤖 Bot Kỳ Vọng đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
