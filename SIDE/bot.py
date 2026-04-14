import sqlite3
import logging
import os
import sys
from html import escape
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler, ConversationHandler


def _load_token() -> str:
    """TELEGRAM_BOT_TOKEN muhit o'zgaruvchisi yoki bot.py yonidagi telegram_token.txt (bir qator)."""
    t = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if t:
        return t
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_token.txt")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    except OSError:
        pass
    return ""


def _parse_chat_id(s):
    s = str(s).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _load_admin_chat_ids():
    """TELEGRAM_ADMIN_IDS (vergul bilan), TELEGRAM_ADMIN_ID yoki telegram_admin_ids.txt"""
    ids = []
    raw = os.environ.get("TELEGRAM_ADMIN_IDS", "").strip()
    if raw:
        for x in raw.split(","):
            cid = _parse_chat_id(x)
            if cid is not None:
                ids.append(cid)
    one = _parse_chat_id(os.environ.get("TELEGRAM_ADMIN_ID", ""))
    if one is not None:
        ids.append(one)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_admin_ids.txt")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                for part in line.replace(",", " ").split():
                    cid = _parse_chat_id(part)
                    if cid is not None:
                        ids.append(cid)
    except OSError:
        pass
    out, seen = [], set()
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


# ================= KONFIGURATSIYA =================
# Tokenni kodga yozmang: $env:TELEGRAM_BOT_TOKEN yoki telegram_token.txt
TOKEN = _load_token()
ADMIN_CHAT_IDS = _load_admin_chat_ids()
GROUP_LINK = "https://t.me/ecotimeuz"  # Valentiorlik guruhi linki

# Papkalar yaratish
if not os.path.exists("photos"):
    os.makedirs("photos")
if not os.path.exists("videos"):
    os.makedirs("videos")
if not os.path.exists("announcements"):
    os.makedirs("announcements")

# ================= LOGGING =================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def _admin_caption_header(title: str, user) -> str:
    parts = [
        f"<b>{escape(title)}</b>",
        f"🆔 <code>{user.id}</code>",
        f"👤 {escape(user.full_name or '—')}",
    ]
    if user.username:
        parts.append(f"@{escape(user.username)}")
    return "\n".join(parts)


async def _notify_admins(
    bot,
    user,
    title: str,
    text_block: str,
    *,
    photo_path=None,
    video_path=None,
    photo_file_id=None,
    video_file_id=None,
):
    if not ADMIN_CHAT_IDS:
        return
    cap = _admin_caption_header(title, user) + "\n\n" + text_block
    if len(cap) > 1024:
        cap = cap[:1021] + "..."
    for chat_id in ADMIN_CHAT_IDS:
        try:
            if photo_file_id:
                await bot.send_photo(
                    chat_id,
                    photo_file_id,
                    caption=cap,
                    parse_mode="HTML",
                )
            elif video_file_id:
                await bot.send_video(
                    chat_id,
                    video_file_id,
                    caption=cap,
                    parse_mode="HTML",
                )
            elif photo_path and os.path.isfile(photo_path):
                with open(photo_path, "rb") as f:
                    await bot.send_photo(
                        chat_id,
                        photo=f,
                        filename=os.path.basename(photo_path),
                        caption=cap,
                        parse_mode="HTML",
                    )
            elif video_path and os.path.isfile(video_path):
                with open(video_path, "rb") as f:
                    await bot.send_video(
                        chat_id,
                        video=f,
                        filename=os.path.basename(video_path),
                        caption=cap,
                        parse_mode="HTML",
                    )
            else:
                await bot.send_message(chat_id, cap, parse_mode="HTML")
        except Exception as e:
            logger.warning("Admin bildirishnomasi yuborilmadi (%s): %s", chat_id, e)


# ================= DATABASE =================
conn = sqlite3.connect('ekobot.db', check_same_thread=False)
c = conn.cursor()

# Foydalanuvchilar jadvali
c.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE,
    first_name TEXT,
    last_name TEXT,
    phone TEXT,
    address TEXT,
    registered_date TEXT
)''')

# Rasmlar jadvali
c.execute('''CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    photo_path TEXT,
    description TEXT,
    upload_date TEXT
)''')

# Videolar jadvali
c.execute('''CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    video_path TEXT,
    description TEXT,
    upload_date TEXT
)''')

# E'lonlar jadvali
c.execute('''CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    content_type TEXT,
    file_path TEXT,
    description TEXT,
    upload_date TEXT
)''')

conn.commit()

# ================= HOLATLAR =================
NAME, LASTNAME, PHONE, ADDRESS = range(4)
VALENTIOR_MEDIA, VALENTIOR_DESC = 10, 11
ANNOUNCE_MEDIA_FIRST, ANNOUNCE_DESC, ANNOUNCE_TEXT_ONLY = 20, 21, 22

# ================= START / REGISTRATION =================
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    c.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    user = c.fetchone()
    
    if user:
        await main_menu(update, context)
    else:
        await update.message.reply_text(
            "🌿 *Ekologiya botiga xush kelibsiz!*\n\n"
            "Iltimos, quyidagi ma'lumotlarni to'ldiring:\n\n"
            "✏️ *Ismingizni kiriting:*",
            parse_mode='Markdown'
        )
        return NAME

async def get_name(update: Update, context: CallbackContext):
    context.user_data['first_name'] = update.message.text
    await update.message.reply_text("✏️ *Familiyangizni kiriting:*", parse_mode='Markdown')
    return LASTNAME

async def get_lastname(update: Update, context: CallbackContext):
    context.user_data['last_name'] = update.message.text
    
    contact_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await update.message.reply_text(
        "📞 *Telefon raqamingizni yuboring:*\n"
        "Pastdagi tugma orqali yuborishingiz mumkin.",
        parse_mode='Markdown',
        reply_markup=contact_keyboard
    )
    return PHONE

async def get_phone(update: Update, context: CallbackContext):
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text
    
    context.user_data['phone'] = phone
    
    await update.message.reply_text(
        "📍 *Yashash joyingizni kiriting:*\n"
        "Masalan: Toshkent shahar, Chilonzor tumani",
        parse_mode='Markdown'
    )
    return ADDRESS

async def get_address(update: Update, context: CallbackContext):
    address = update.message.text
    user_id = update.effective_user.id
    data = context.user_data
    
    c.execute("""INSERT INTO users 
                 (telegram_id, first_name, last_name, phone, address, registered_date) 
                 VALUES (?,?,?,?,?,?)""",
              (user_id, data['first_name'], data['last_name'], data['phone'], address, 
               datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    
    # Tugmalarni olib tashlash
    reply_keyboard = ReplyKeyboardMarkup(
        [["/start"]],
        resize_keyboard=True
    )
    
    await update.message.reply_text(
        "✅ *Ro'yxatdan muvaffaqiyatli o'tdingiz!*\n\n"
        "Endi botning barcha imkoniyatlaridan foydalanishingiz mumkin.\n"
        "/start yoki /menu bilan asosiy tugmalarni oching.",
        parse_mode='Markdown',
        reply_markup=reply_keyboard
    )
    
    return ConversationHandler.END

# ================= ASOSIY TUGMALAR (menyu sarlavhasiz) =================
async def main_menu(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("♻️ Valentiorlikka qo'shilish (rasm/video)", callback_data='join_valentior')],
        [InlineKeyboardButton("📢 E'lon berish", callback_data='make_announce')],
        [InlineKeyboardButton("ℹ️ Mening ma'lumotlarim", callback_data='my_info')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.edit_text(
            "Kerakli amalni tanlang:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        await update.callback_query.answer()
    else:
        await update.message.reply_text(
            "Kerakli amalni tanlang:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

# ================= VALENTIORLIK + RASM YOKI VIDEO =================
async def join_valentior_entry(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("👥 Guruhga qo'shilish", url=GROUP_LINK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(
        "♻️ *Valentiorlik - ekologik tashabbus!*\n\n"
        "Guruhda:\n"
        "✅ Ekologik yangiliklar\n"
        "✅ Obod qilish aksiyalari\n"
        "✅ Chiqindilarni qayta ishlash bo'yicha maslahatlar\n\n"
        "Avval quyidagi tugma orqali guruhga qo'shiling.\n\n"
        "Keyin *rasm yoki video* yuboring (o'zingiz xohlaganini) — ekologik faoliyatingizdan.\n"
        "So'ng qisqa tavsif yozasiz.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return VALENTIOR_MEDIA


async def valentior_need_media(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "❌ Avval *rasm yoki video* yuboring (qaysi biri bo'lsa ham).",
        parse_mode='Markdown',
    )
    return VALENTIOR_MEDIA


async def handle_valentior_media(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        file_name = f"photos/user_{uid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        await photo_file.download_to_drive(file_name)
        context.user_data['valentior_path'] = file_name
        context.user_data['valentior_kind'] = 'photo'
    elif update.message.video:
        video_file = await update.message.video.get_file()
        file_name = f"videos/user_{uid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        await video_file.download_to_drive(file_name)
        context.user_data['valentior_path'] = file_name
        context.user_data['valentior_kind'] = 'video'
    else:
        await update.message.reply_text("❌ Iltimos, rasm yoki video yuboring.")
        return VALENTIOR_MEDIA
    await update.message.reply_text(
        "✏️ *Tavsif yozing:*\nMasalan: obod qilish yoki daraxt ekish.",
        parse_mode='Markdown'
    )
    return VALENTIOR_DESC


async def save_valentior_description(update: Update, context: CallbackContext):
    description = update.message.text
    user_id = update.effective_user.id
    path = context.user_data.get('valentior_path')
    kind = context.user_data.get('valentior_kind')
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if kind == 'photo' and path:
        c.execute(
            "INSERT INTO photos (user_id, photo_path, description, upload_date) VALUES (?,?,?,?)",
            (user_id, path, description, ts),
        )
    elif kind == 'video' and path:
        c.execute(
            "INSERT INTO videos (user_id, video_path, description, upload_date) VALUES (?,?,?,?)",
            (user_id, path, description, ts),
        )
    else:
        await update.message.reply_text("❌ Yuklash xatosi. Qaytadan /start bosing.")
        context.user_data.pop('valentior_path', None)
        context.user_data.pop('valentior_kind', None)
        return ConversationHandler.END
    conn.commit()
    context.user_data.pop('valentior_path', None)
    context.user_data.pop('valentior_kind', None)
    await update.message.reply_text(
        f"✅ *Saqlandi!*\n\nTavsif: {description}\n\nRahmat!",
        parse_mode='Markdown'
    )
    u = update.effective_user
    tb = f"📝 <b>Tavsif:</b> {escape(description)}"
    if kind == 'photo':
        await _notify_admins(
            context.bot,
            u,
            "♻️ Valentiorlik — yangi rasm",
            tb,
            photo_path=path,
        )
    elif kind == 'video':
        await _notify_admins(
            context.bot,
            u,
            "♻️ Valentiorlik — yangi video",
            tb,
            video_path=path,
        )
    await main_menu(update, context)
    return ConversationHandler.END

# ================= E'LON BERISH (avval media, keyin matn) =================
async def make_announce(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    for k in ('announce_file', 'announce_ct', 'announce_photo_id', 'announce_video_id'):
        context.user_data.pop(k, None)
    await query.message.reply_text(
        "📢 *E'lon berish*\n\n"
        "1) Avval *rasm yoki video* yuboring.\n"
        "2) Keyin e'lon matnini (tavsif) yozasiz.\n\n"
        "Faqat matn bo'lsa — /skip bosing.",
        parse_mode='Markdown'
    )
    return ANNOUNCE_MEDIA_FIRST


async def announce_need_media_first(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "❌ Avval *rasm* yoki *video* yuboring. Faqat matn uchun /skip.",
        parse_mode='Markdown',
    )
    return ANNOUNCE_MEDIA_FIRST


async def announce_receive_media(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        file_path = f"announcements/photo_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        await photo_file.download_to_drive(file_path)
        context.user_data['announce_file'] = file_path
        context.user_data['announce_ct'] = 'photo'
        context.user_data['announce_photo_id'] = update.message.photo[-1].file_id
        context.user_data.pop('announce_video_id', None)
    elif update.message.video:
        video_file = await update.message.video.get_file()
        file_path = f"announcements/video_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        await video_file.download_to_drive(file_path)
        context.user_data['announce_file'] = file_path
        context.user_data['announce_ct'] = 'video'
        context.user_data['announce_video_id'] = update.message.video.file_id
        context.user_data.pop('announce_photo_id', None)
    else:
        await update.message.reply_text("❌ Iltimos, rasm yoki video yuboring yoki /skip.")
        return ANNOUNCE_MEDIA_FIRST
    await update.message.reply_text(
        "✏️ *E'lon matnini kiriting:*",
        parse_mode='Markdown'
    )
    return ANNOUNCE_DESC


async def announce_receive_text_after_media(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    announce_text = update.message.text
    file_path = context.user_data.get('announce_file')
    content_type = context.user_data.get('announce_ct')
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if content_type == 'photo' and context.user_data.get('announce_photo_id'):
        await update.message.reply_photo(
            context.user_data['announce_photo_id'],
            caption=f"📢 *E'LON*\n\n{announce_text}",
            parse_mode='Markdown'
        )
    elif content_type == 'video' and context.user_data.get('announce_video_id'):
        await update.message.reply_video(
            context.user_data['announce_video_id'],
            caption=f"📢 *E'LON*\n\n{announce_text}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(f"📢 *E'LON*\n\n{announce_text}", parse_mode='Markdown')
        content_type = content_type or 'text'

    c.execute(
        """INSERT INTO announcements
           (user_id, content_type, file_path, description, upload_date)
           VALUES (?,?,?,?,?)""",
        (user_id, content_type, file_path, announce_text, ts),
    )
    conn.commit()
    pid = context.user_data.get('announce_photo_id')
    vid = context.user_data.get('announce_video_id')
    for k in ('announce_file', 'announce_ct', 'announce_photo_id', 'announce_video_id'):
        context.user_data.pop(k, None)
    await update.message.reply_text(
        "✅ *E'lon joylandi!*",
        parse_mode='Markdown'
    )
    u = update.effective_user
    tb = f"📢 <b>Matn:</b>\n{escape(announce_text)}"
    if content_type == 'photo' and pid:
        await _notify_admins(
            context.bot,
            u,
            "📢 Yangi e'lon (rasm)",
            tb,
            photo_file_id=pid,
        )
    elif content_type == 'video' and vid:
        await _notify_admins(
            context.bot,
            u,
            "📢 Yangi e'lon (video)",
            tb,
            video_file_id=vid,
        )
    else:
        await _notify_admins(context.bot, u, "📢 Yangi e'lon", tb)
    await main_menu(update, context)
    return ConversationHandler.END


async def announce_skip_media_first(update: Update, context: CallbackContext):
    context.user_data.pop('announce_file', None)
    context.user_data.pop('announce_ct', None)
    context.user_data.pop('announce_photo_id', None)
    context.user_data.pop('announce_video_id', None)
    await update.message.reply_text(
        "📢 *Faqat matnli e'lon*\n\nE'lon matnini kiriting:",
        parse_mode='Markdown'
    )
    return ANNOUNCE_TEXT_ONLY


async def announce_text_only_save(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    announce_text = update.message.text
    await update.message.reply_text(f"📢 *E'LON*\n\n{announce_text}", parse_mode='Markdown')
    c.execute(
        """INSERT INTO announcements
           (user_id, content_type, file_path, description, upload_date)
           VALUES (?,?,?,?,?)""",
        (user_id, 'text', None, announce_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    await update.message.reply_text("✅ *Matnli e'lon joylandi!*", parse_mode='Markdown')
    u = update.effective_user
    await _notify_admins(
        context.bot,
        u,
        "📢 Yangi e'lon (faqat matn)",
        f"📢 <b>Matn:</b>\n{escape(announce_text)}",
    )
    await main_menu(update, context)
    return ConversationHandler.END

# ================= FOYDALANUVCHI MA'LUMOTLARI =================
async def my_info(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    c.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    user = c.fetchone()
    
    if user:
        c.execute("SELECT COUNT(*) FROM photos WHERE user_id=?", (user_id,))
        photo_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM videos WHERE user_id=?", (user_id,))
        video_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM announcements WHERE user_id=?", (user_id,))
        announce_count = c.fetchone()[0]
        
        info_text = (
            f"👤 *Sizning ma'lumotlaringiz*\n\n"
            f"📛 Ism: {user[2]}\n"
            f"📛 Familiya: {user[3]}\n"
            f"📞 Telefon: {user[4]}\n"
            f"📍 Manzil: {user[5]}\n"
            f"📅 Ro'yxatdan o'tgan: {user[6]}\n\n"
            f"📸 Yuklangan rasmlar: {photo_count}\n"
            f"🎥 Yuklangan videolar: {video_count}\n"
            f"📢 E'lonlar: {announce_count}"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(info_text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await query.message.edit_text("❌ Ma'lumot topilmadi. Iltimos, /start buyrug'ini bosing.")

# ================= BACK TO MENU =================
async def back_to_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    await main_menu(update, context)

# ================= CANCEL =================
async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "❌ *Amal bekor qilindi!*\n\n"
        "Asosiy tugmalar uchun /start yoki /menu bosing.",
        parse_mode='Markdown'
    )
    context.user_data.clear()
    return ConversationHandler.END

# ================= /MENU BUYRUG'I =================
async def menu_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    c.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    user = c.fetchone()
    
    if user:
        await main_menu(update, context)
    else:
        await update.message.reply_text(
            "❌ Iltimos, avval /start buyrug'i bilan ro'yxatdan o'ting!",
            parse_mode='Markdown'
        )

# ================= ASOSIY FUNKSIYA =================
def _telegram_token_looks_valid(token: str) -> bool:
    """Telegram token: <raqam>:<maxfiy_qator> — to'liq nusxa, '...' bo'lmasin."""
    if ":" not in token:
        return False
    left, right = token.split(":", 1)
    if "..." in token or not left.isdigit() or len(right) < 30:
        return False
    low = token.lower()
    for bogus in ("your_token", "paste_your", "example", "changeme", "replace_me", "botfather"):
        if bogus in low:
            return False
    return True


def main():
    if not TOKEN:
        print(
            "Token topilmadi. Ikkalasidan birini qiling:\n"
            "1) PowerShell (shu oyna): avval tokenni $env:TELEGRAM_BOT_TOKEN ga bering, keyin python bot.py\n"
            "2) Yoki bot.py bilan bir papkada telegram_token.txt yarating — ichiga bir qator token.\n"
            "Eslatma: os.environ.get('TOKEN_BU_YERDA') yozmaydi; o'zgaruvchi nomi TELEGRAM_BOT_TOKEN bo'lishi kerak.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if not _telegram_token_looks_valid(TOKEN):
        print(
            "TELEGRAM_BOT_TOKEN yaroqsiz: @BotFather dan tokenning BUTUN qatorini nusxalang.\n"
            "Qator odatda raqamlar, ':' va undan keyin uzun maxfiy qismdan iborat (~45+ belgi).\n"
            "Qo'lda '...' yozmang va qisqartirmang. PowerShell (shu oyna, avval tokenni qo'ying):\n"
            "  $env:TELEGRAM_BOT_TOKEN = 'BU_YERGA_TO_LIQ_TOKEN'\n"
            "  python bot.py\n"
            "Yangi terminalda $env qayta berilishi kerak.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

    # Bot yaratish
    application = Application.builder().token(TOKEN).build()
    
    # Registratsiya conversation handler
    reg_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            LASTNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_lastname)],
            PHONE: [MessageHandler(filters.CONTACT | filters.TEXT, get_phone)],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_address)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    valentior_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(join_valentior_entry, pattern='^join_valentior$')],
        states={
            VALENTIOR_MEDIA: [
                MessageHandler(filters.PHOTO | filters.VIDEO, handle_valentior_media),
                MessageHandler(filters.TEXT & ~filters.COMMAND, valentior_need_media),
            ],
            VALENTIOR_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_valentior_description),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    announce_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(make_announce, pattern='^make_announce$')],
        states={
            ANNOUNCE_MEDIA_FIRST: [
                MessageHandler(filters.PHOTO | filters.VIDEO, announce_receive_media),
                CommandHandler('skip', announce_skip_media_first),
                MessageHandler(filters.TEXT & ~filters.COMMAND, announce_need_media_first),
            ],
            ANNOUNCE_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, announce_receive_text_after_media),
            ],
            ANNOUNCE_TEXT_ONLY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, announce_text_only_save),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(reg_conv_handler)
    application.add_handler(valentior_conv_handler)
    application.add_handler(announce_conv_handler)

    application.add_handler(CallbackQueryHandler(my_info, pattern='^my_info$'))
    application.add_handler(CallbackQueryHandler(back_to_menu, pattern='^back_to_menu$'))
    
    # Command handlerlar
    application.add_handler(CommandHandler('menu', menu_command))
    application.add_handler(CommandHandler('cancel', cancel))
    
    # Start bot
    print("🤖 Bot ishga tushdi...")
    print("✅ Token TELEGRAM_BOT_TOKEN orqali yuklandi")
    print("📱 Botni Telegramda @BotFather dan olingan token bilan ishga tushirdingiz")
    if ADMIN_CHAT_IDS:
        print(f"👮 Admin bildirishnomalari: {len(ADMIN_CHAT_IDS)} ta chat ID")
    else:
        print(
            "ℹ️ Admin bildirishnomalari o'chirilgan. Qo'shish: TELEGRAM_ADMIN_ID yoki "
            "TELEGRAM_ADMIN_IDS yoki telegram_admin_ids.txt (bot.py yonida)"
        )
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()