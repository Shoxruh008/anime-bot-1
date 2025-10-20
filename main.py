import json
import os
import logging
import telebot
from telebot import types
from telebot.util import quick_markup
import requests
from fpdf import FPDF
import datetime

# ⚙️ Sozlamalar
API_TOKEN = "8428253874:AAH1gMCyahs0c2rQnwTWAkNA20OXXXkpsqI"
MAIN_ADMIN_ID = 5371043130
JSON_FILE = "anime.json"
ADMINS_FILE = "admins.json"
CHANNELS_FILE = "channels.json"

logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(API_TOKEN)

# 📂 JSON fayllarini tayyorlash
for file in [JSON_FILE, ADMINS_FILE, CHANNELS_FILE]:
    if not os.path.exists(file):
        with open(file, "w", encoding="utf-8") as f:
            if file == CHANNELS_FILE:
                json.dump([], f, ensure_ascii=False)
            else:
                json.dump({}, f, ensure_ascii=False)

def load_data(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        if filename == CHANNELS_FILE:
            return []
        return {}

def save_data(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        if filename == CHANNELS_FILE:
            json.dump(data, f, ensure_ascii=False, indent=4)
        else:
            json.dump(data, f, ensure_ascii=False, indent=4)

# Foydalanuvchilarni tekshirish
def check_user(user_id):
    admins = load_data(ADMINS_FILE)
    return str(user_id) in admins or user_id == MAIN_ADMIN_ID

def check_subscription(user_id):
    channels = load_data(CHANNELS_FILE)
    if not channels:
        return True
        
    for channel in channels:
        try:
            chat_member = bot.get_chat_member(channel, user_id)
            if chat_member.status in ['left', 'kicked']:
                return False
        except Exception as e:
            logging.error(f"Kanal tekshirishda xato: {e}")
            continue
    return True

# Asosiy menu
def main_menu(user_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    if check_user(user_id):
        keyboard.add(
            types.InlineKeyboardButton("➕ Anime qo'shish", callback_data="add_anime"),
            types.InlineKeyboardButton("📊 Statistika", callback_data="stats"),
            types.InlineKeyboardButton("👥 Adminlar", callback_data="admin_manage"),
            types.InlineKeyboardButton("📢 Kanallar", callback_data="channel_manage")
        )
        keyboard.add(
            types.InlineKeyboardButton("📋 Barcha animelar", callback_data="all_anime_list"),
            types.InlineKeyboardButton("✏️ Anime tahrirlash", callback_data="edit_anime_menu")
        )
    
    keyboard.add(
        types.InlineKeyboardButton("❓ Yordam", callback_data="help"),
        types.InlineKeyboardButton("🏷️ Asosiy kanal", url="https://t.me/AnimeUzbekca")
    )
    return keyboard

# Matnni PDF uchun to'g'rilash
def clean_text_for_pdf(text):
    """Matndagi maxsus belgilarni oddiy belgilarga almashtirish"""
    replacements = {
        'ʻ': "'", 'ʼ': "'", '‘': "'", '’': "'", '`': "'",
        '´': "'", 'ʹ': "'", 'ʺ': '"', '«': '"', '»': '"',
        '„': '"', '“': '"', '”': '"', '–': '-', '—': '-',
        '…': '...'
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text

# PDF yaratish funksiyasi
def create_anime_pdf():
    anime_data = load_data(JSON_FILE)
    
    pdf = FPDF()
    pdf.add_page()
    
    # Sarlavha
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Anime Lar Ro\'yxati', 0, 1, 'C')
    pdf.ln(5)
    
    # Sana va vaqt
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 10, f"Yaratilgan sana: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, 1)
    pdf.ln(5)
    
    # Jami statistika
    total_anime = len(anime_data)
    total_episodes = 0
    for anime in anime_data.values():
        if "episodes" in anime:
            total_episodes += len(anime["episodes"])
        else:
            total_episodes += 1
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"Jami Anime: {total_anime}", 0, 1)
    pdf.cell(0, 10, f"Jami Qismlar: {total_episodes}", 0, 1)
    pdf.ln(10)
    
    # Har bir anime uchun ma'lumot
    for i, (code, anime) in enumerate(anime_data.items(), 1):
        clean_title = clean_text_for_pdf(anime['title'])
        
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, f"{i}. {clean_title}", 0, 1)
        
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 8, f"Kod: {code}", 0, 1)
        
        # Start link
        link = f"https://t.me/AnirenXinata_bot?start={code}"
        pdf.cell(0, 8, f"Link: {link}", 0, 1)
        
        # Anime turi va qismlar soni
        if "episodes" in anime:
            pdf.cell(0, 8, f"Turi: Serial (Jami {len(anime['episodes'])} qism)", 0, 1)
        else:
            pdf.cell(0, 8, "Turi: Bitta anime", 0, 1)
        
        pdf.ln(8)
        
        # Har 3 anime dan keyin yangi sahifa
        if i % 3 == 0 and i != len(anime_data):
            pdf.add_page()
    
    filename = f"anime_list_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(filename, 'F')
    return filename

# Sahifalangan qismlarni ko'rsatish
def show_episodes_page(chat_id, anime, anime_code, page=0, message_id=None):
    episodes = anime["episodes"]
    
    # Sahifalash parametrlari
    episodes_per_page = 20
    total_pages = (len(episodes) + episodes_per_page - 1) // episodes_per_page
    
    # Agar 21-25 qism bo'lsa, bitta sahifada ko'rsatish
    if len(episodes) <= 25 and total_pages > 1:
        episodes_per_page = len(episodes)
        total_pages = 1
        page = 0
    
    # Joriy sahifadagi qismlar
    start_idx = page * episodes_per_page
    end_idx = min(start_idx + episodes_per_page, len(episodes))
    current_episodes = episodes[start_idx:end_idx]
    
    # Keyboard yaratish (har qatorda 2 ta tugma)
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    # Qismlar tugmalari (har qatorda 2 ta)
    for i in range(0, len(current_episodes), 2):
        row_buttons = []
        # Birinchi tugma
        if i < len(current_episodes):
            episode_idx1 = start_idx + i
            button_text1 = f"🎬 {current_episodes[i]['episode']}"
            row_buttons.append(types.InlineKeyboardButton(button_text1, callback_data=f"ep_{anime_code}_{episode_idx1}"))
        
        # Ikkinchi tugma
        if i + 1 < len(current_episodes):
            episode_idx2 = start_idx + i + 1
            button_text2 = f"🎬 {current_episodes[i+1]['episode']}"
            row_buttons.append(types.InlineKeyboardButton(button_text2, callback_data=f"ep_{anime_code}_{episode_idx2}"))
        
        if row_buttons:
            keyboard.add(*row_buttons)
    
    # Navigatsiya tugmalari (faqat kerak bo'lsa)
    nav_buttons = []
    if total_pages > 1:
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton("⬅️ Oldingi", callback_data=f"page_{anime_code}_{page-1}"))
        
        # Sahifa raqami
        nav_buttons.append(types.InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="no_action"))
        
        if page < total_pages - 1:
            nav_buttons.append(types.InlineKeyboardButton("Keyingi ➡️", callback_data=f"page_{anime_code}_{page+1}"))
    
    if nav_buttons:
        keyboard.add(*nav_buttons)
    
    # Asosiy menyuga qaytish
    keyboard.add(types.InlineKeyboardButton("🏠 Asosiy menyu", callback_data="main_menu"))
    
    text = (f"<b>🎌 {anime['title']}</b>\n\n"
            f"📺 Sahifa {page + 1}/{total_pages} (Jami {len(episodes)} qism)\n"
            f"Quyidagi qismlardan birini tanlang:")
    
    if message_id:
        bot.edit_message_text(
            text,
            chat_id,
            message_id,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        bot.send_message(
            chat_id,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

# 📌 /start
@bot.message_handler(commands=["start"])
def start(msg):
    user_id = msg.from_user.id
    user_name = msg.from_user.first_name
    
    # Obunani tekshirish
    channels = load_data(CHANNELS_FILE)
    if channels and not check_subscription(user_id):
        keyboard = types.InlineKeyboardMarkup()
        for channel in channels:
            try:
                chat = bot.get_chat(channel)
                if chat.username:
                    url = f"https://t.me/{chat.username}"
                else:
                    url = f"https://t.me/c/{str(chat.id)[4:]}" if str(chat.id).startswith('-100') else f"https://t.me/c/{chat.id}"
                
                keyboard.add(types.InlineKeyboardButton(f"{chat.title}", url=url))
            except Exception as e:
                logging.error(f"Kanal ma'lumotlarini olishda xato: {e}")
                continue
        
        keyboard.add(types.InlineKeyboardButton("✅ Obuna bo'ldim", callback_data="check_subscription"))
        
        bot.send_message(
            msg.chat.id, 
            "🤖 Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo'ling:", 
            reply_markup=keyboard
        )
        return
    
    args = msg.text.split()[1] if len(msg.text.split()) > 1 else None
    if not args:
        welcome_text = (
            f"👋 Salom, {user_name} Aniren Xinata Botiga Xush Kelibsiz!\n\n"
            "📺 Bu bot orqali siz turli animelarni professional dublajda tomosha qilishingiz mumkin.\n\n"
            "🔗 Animelarni tomosha qilish uchun esa asosiy kanaldan anime tanlab keling."
        )
        bot.send_message(
            msg.chat.id,
            welcome_text,
            reply_markup=main_menu(user_id),
            parse_mode="HTML"
        )
    else:
        data = load_data(JSON_FILE)
        if args not in data:
            bot.send_message(msg.chat.id, "❌ <b>Bunday anime topilmadi.</b>", parse_mode="HTML")
            return

        anime = data[args]
        
        # File_id ni tekshirish
        try:
            if "episodes" in anime:  # Ko'p qismli anime
                # Sahifalangan ro'yxatni ko'rsatish (0-sahifa)
                show_episodes_page(msg.chat.id, anime, args, 0)
            else:  # Bitta anime
                bot.send_video(msg.chat.id, anime["file_id"], caption=f"<b>🎌 {anime['title']}</b>", parse_mode="HTML")
        except Exception as e:
            logging.error(f"Video yuborishda xato: {e}")
            bot.send_message(msg.chat.id, f"❌ <b>Xato:</b> Video yuborishda muammo yuz berdi. Iltimos, anime ni qayta yuklang.", parse_mode="HTML")

# Foydalanuvchi holatlari
user_states = {}

# Anime tahrirlash menyusi
@bot.callback_query_handler(func=lambda call: call.data == 'edit_anime_menu')
def edit_anime_menu_callback(call):
    user_id = call.from_user.id
    if not check_user(user_id):
        bot.answer_callback_query(call.id, "❌ Sizda bunday huquq yo'q!", show_alert=True)
        return
    
    anime_data = load_data(JSON_FILE)
    
    if not anime_data:
        bot.send_message(call.message.chat.id, "❌ <b>Hozircha animelar mavjud emas.</b>", parse_mode="HTML")
        return
    
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    for code, anime in anime_data.items():
        anime_type = "📺 Serial" if "episodes" in anime else "🎬 Film"
        keyboard.add(types.InlineKeyboardButton(
            f"{anime_type} | {anime['title']}", 
            callback_data=f"edit_{code}"
        ))
    
    keyboard.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu"))
    
    bot.edit_message_text(
        "✏️ <b>Anime tahrirlash</b>\n\n"
        "Qaysi anime ni tahrirlamoqchisiz?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

# Anime ni tahrirlashni boshlash
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def start_edit_anime(call):
    user_id = call.from_user.id
    if not check_user(user_id):
        bot.answer_callback_query(call.id, "❌ Sizda bunday huquq yo'q!", show_alert=True)
        return
    
    anime_code = call.data.replace('edit_', '')
    anime_data = load_data(JSON_FILE)
    
    if anime_code not in anime_data:
        bot.answer_callback_query(call.id, "❌ Anime topilmadi!", show_alert=True)
        return
    
    anime = anime_data[anime_code]
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    if "episodes" in anime:
        # Serial anime
        keyboard.add(
            types.InlineKeyboardButton("✏️ Nomi", callback_data=f"edit_title_{anime_code}"),
            types.InlineKeyboardButton("📺 Qismlar soni", callback_data=f"edit_episodes_{anime_code}")
        )
    else:
        # Bitta anime
        keyboard.add(
            types.InlineKeyboardButton("✏️ Nomi", callback_data=f"edit_title_{anime_code}"),
            types.InlineKeyboardButton("🎬 Video", callback_data=f"edit_video_{anime_code}")
        )
    
    keyboard.add(types.InlineKeyboardButton("🗑️ O'chirish", callback_data=f"delete_{anime_code}"))
    keyboard.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="edit_anime_menu"))
    
    anime_type = "Serial" if "episodes" in anime else "Film"
    episodes_info = f"\n📺 Qismlar soni: {len(anime['episodes'])}" if "episodes" in anime else ""
    
    bot.edit_message_text(
        f"✏️ <b>Anime tahrirlash</b>\n\n"
        f"🎬 <b>Nomi:</b> {anime['title']}\n"
        f"📁 <b>Turi:</b> {anime_type}\n"
        f"🆔 <b>Kod:</b> <code>{anime_code}</code>{episodes_info}\n\n"
        f"Quyidagilardan birini tanlang:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

# Anime nomini tahrirlash
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_title_'))
def edit_anime_title(call):
    user_id = call.from_user.id
    if not check_user(user_id):
        bot.answer_callback_query(call.id, "❌ Sizda bunday huquq yo'q!", show_alert=True)
        return
    
    anime_code = call.data.replace('edit_title_', '')
    
    user_states[user_id] = {
        'state': 'editing_title',
        'anime_code': anime_code
    }
    
    bot.send_message(
        call.message.chat.id,
        f"✏️ <b>Anime nomini tahrirlash</b>\n\n"
        f"Yangi nomni yuboring:",
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

# Anime nomini qabul qilish
@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id]['state'] == 'editing_title')
def get_new_title(msg):
    user_id = msg.from_user.id
    user_data = user_states[user_id]
    anime_code = user_data['anime_code']
    new_title = msg.text.strip()

    anime_data = load_data(JSON_FILE)
    
    if anime_code not in anime_data:
        bot.send_message(msg.chat.id, "❌ <b>Anime topilmadi!</b>", parse_mode="HTML")
        user_states.pop(user_id, None)
        return

    anime_data[anime_code]['title'] = new_title
    save_data(anime_data, JSON_FILE)

    bot.send_message(
        msg.chat.id,
        f"✅ <b>Anime nomi muvaffaqiyatli o‘zgartirildi!</b>\n\n"
        f"🎬 <b>Yangi nom:</b> {new_title}\n"
        f"🆔 <b>Kod:</b> <code>{anime_code}</code>\n"
        f"🔗 <b>Link:</b> <code>https://t.me/AnirenXinata_bot?start={anime_code}</code>",
        parse_mode="HTML"
    )

    user_states.pop(user_id, None)

# Serial uchun qismlar sonini tahrirlash
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_episodes_'))
def edit_episodes_count(call):
    user_id = call.from_user.id
    if not check_user(user_id):
        bot.answer_callback_query(call.id, "❌ Sizda bunday huquq yo‘q!", show_alert=True)
        return

    anime_code = call.data.replace('edit_episodes_', '')
    anime_data = load_data(JSON_FILE)

    if anime_code not in anime_data or "episodes" not in anime_data[anime_code]:
        bot.answer_callback_query(call.id, "❌ Serial topilmadi!", show_alert=True)
        return

    anime = anime_data[anime_code]
    current_episodes = len(anime["episodes"])

    user_states[user_id] = {
        'state': 'editing_episodes',
        'anime_code': anime_code,
        'current_episodes': current_episodes
    }

    bot.send_message(
        call.message.chat.id,
        f"📺 <b>Qismlar sonini tahrirlash</b>\n\n"
        f"🎬 Anime: <b>{anime['title']}</b>\n"
        f"📊 Joriy qismlar soni: <b>{current_episodes}</b>\n\n"
        f"Yangi qismlar sonini kiriting (kamida {current_episodes}):",
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

# Qismlar sonini qabul qilish
@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id]['state'] == 'editing_episodes')
def get_new_episodes_count(msg):
    user_id = msg.from_user.id
    data = user_states[user_id]
    anime_code = data['anime_code']
    current_episodes = data['current_episodes']

    if not msg.text.isdigit():
        bot.send_message(msg.chat.id, "❌ <b>Iltimos, raqam yuboring!</b>", parse_mode="HTML")
        return

    new_count = int(msg.text)
    if new_count < current_episodes:
        bot.send_message(msg.chat.id, f"❌ <b>Qismlar soni {current_episodes} dan kam bo‘lishi mumkin emas!</b>", parse_mode="HTML")
        return

    anime_data = load_data(JSON_FILE)
    if anime_code not in anime_data:
        bot.send_message(msg.chat.id, "❌ <b>Anime topilmadi!</b>", parse_mode="HTML")
        user_states.pop(user_id, None)
        return

    # Agar yangi qismlar qo‘shilishi kerak bo‘lsa
    if new_count > current_episodes:
        user_states[user_id].update({
            'state': 'adding_new_episodes',
            'episodes_to_add': new_count - current_episodes,
            'current_adding_episode': current_episodes + 1,
            'new_episodes': []
        })

        bot.send_message(
            msg.chat.id,
            f"✅ <b>{new_count - current_episodes} ta yangi qism qo‘shish boshlandi!</b>\n\n"
            f"📹 Endi <b>{current_episodes + 1}-qism</b> uchun video yuboring:",
            parse_mode="HTML"
        )
    else:
        # Qismlar soni o'zgarmadi
        bot.send_message(
            msg.chat.id,
            f"✅ <b>Qismlar soni o‘zgarmadi!</b>\n\n"
            f"Jami qismlar soni: <b>{current_episodes}</b>",
            parse_mode="HTML"
        )
        user_states.pop(user_id, None)

# Yangi qismlar uchun videolarni qabul qilish
@bot.message_handler(content_types=['video'], func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id]['state'] == 'adding_new_episodes')
def get_new_episode_video(msg):
    user_id = msg.from_user.id
    data = user_states[user_id]
    anime_code = data['anime_code']
    file_id = msg.video.file_id
    current_episode = data['current_adding_episode']

    # Qismni ro‘yxatga qo‘shamiz
    data['new_episodes'].append({
        'episode': f"{current_episode}-qism",
        'file_id': file_id
    })

    # Keyingi qismga tayyorlanamiz
    if len(data['new_episodes']) < data['episodes_to_add']:
        data['current_adding_episode'] += 1
        bot.send_message(
            msg.chat.id,
            f"✅ <b>{current_episode}-qism</b> qo‘shildi!\n\n"
            f"📹 Endi <b>{data['current_adding_episode']}-qism</b> uchun video yuboring:",
            parse_mode="HTML"
        )
    else:
        # Barcha yangi qismlar qo‘shildi
        anime_data = load_data(JSON_FILE)
        if anime_code not in anime_data:
            bot.send_message(msg.chat.id, "❌ <b>Anime topilmadi!</b>", parse_mode="HTML")
            user_states.pop(user_id, None)
            return

        anime_data[anime_code]["episodes"].extend(data['new_episodes'])
        save_data(anime_data, JSON_FILE)

        bot.send_message(
            msg.chat.id,
            f"✅ <b>Barcha yangi qismlar muvaffaqiyatli qo‘shildi!</b>\n\n"
            f"🎬 <b>{anime_data[anime_code]['title']}</b>\n"
            f"📺 Yangi jami qismlar soni: <b>{len(anime_data[anime_code]['episodes'])}</b>",
            parse_mode="HTML"
        )
        user_states.pop(user_id, None)

# Bitta anime uchun videoni tahrirlash
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_video_'))
def edit_single_video(call):
    user_id = call.from_user.id
    if not check_user(user_id):
        bot.answer_callback_query(call.id, "❌ Sizda bunday huquq yo'q!", show_alert=True)
        return
    
    anime_code = call.data.replace('edit_video_', '')
    
    user_states[user_id] = {
        'state': 'editing_video',
        'anime_code': anime_code
    }
    
    bot.send_message(
        call.message.chat.id,
        f"🎬 <b>Video yangilash</b>\n\n"
        f"Yangi video yuboring:",
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

# Bitta anime uchun yangi videoni qabul qilish
@bot.message_handler(content_types=['video'], func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id]['state'] == 'editing_video')
def get_new_video(msg):
    user_id = msg.from_user.id
    user_data = user_states[user_id]
    anime_code = user_data['anime_code']
    file_id = msg.video.file_id
    
    anime_data = load_data(JSON_FILE)
    
    if anime_code not in anime_data:
        bot.send_message(msg.chat.id, "❌ <b>Anime topilmadi!</b>", parse_mode="HTML")
        if user_id in user_states:
            del user_states[user_id]
        return
    
    anime_data[anime_code]["file_id"] = file_id
    save_data(anime_data, JSON_FILE)
    
    bot.send_message(
        msg.chat.id,
        f"✅ <b>Video muvaffaqiyatli yangilandi!</b>\n\n"
        f"🎬 Anime: <b>{anime_data[anime_code]['title']}</b>",
        parse_mode="HTML"
    )
    
    if user_id in user_states:
        del user_states[user_id]

# Anime ni o'chirish
@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_anime(call):
    user_id = call.from_user.id
    if not check_user(user_id):
        bot.answer_callback_query(call.id, "❌ Sizda bunday huquq yo'q!", show_alert=True)
        return
    
    anime_code = call.data.replace('delete_', '')
    anime_data = load_data(JSON_FILE)
    
    if anime_code not in anime_data:
        bot.answer_callback_query(call.id, "❌ Anime topilmadi!", show_alert=True)
        return
    
    anime_title = anime_data[anime_code]['title']
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"confirm_delete_{anime_code}"),
        types.InlineKeyboardButton("❌ Bekor qilish", callback_data=f"edit_{anime_code}")
    )
    
    bot.edit_message_text(
        f"🗑️ <b>Anime o'chirish</b>\n\n"
        f"Rostan ham <b>\"{anime_title}\"</b> animeni o'chirmoqchimisiz?\n\n"
        f"⚠️ <b>Bu amalni ortga qaytarib bo'lmaydi!</b>",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

# Anime ni tasdiqlash bilan o'chirish
@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_'))
def confirm_delete_anime(call):
    user_id = call.from_user.id
    if not check_user(user_id):
        bot.answer_callback_query(call.id, "❌ Sizda bunday huquq yo'q!", show_alert=True)
        return
    
    anime_code = call.data.replace('confirm_delete_', '')
    anime_data = load_data(JSON_FILE)
    
    if anime_code not in anime_data:
        bot.answer_callback_query(call.id, "❌ Anime topilmadi!", show_alert=True)
        return
    
    anime_title = anime_data[anime_code]['title']
    del anime_data[anime_code]
    save_data(anime_data, JSON_FILE)
    
    bot.edit_message_text(
        f"✅ <b>Anime muvaffaqiyatli o'chirildi!</b>\n\n"
        f"🗑️ <b>\"{anime_title}\"</b> animeni o'chirish yakunlandi.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

# Barcha animelar ro'yxati (PDF)
@bot.callback_query_handler(func=lambda call: call.data == 'all_anime_list')
def all_anime_list_callback(call):
    user_id = call.from_user.id
    if not check_user(user_id):
        bot.answer_callback_query(call.id, "❌ Sizda bunday huquq yo'q!", show_alert=True)
        return
    
    try:
        bot.send_message(call.message.chat.id, "📋 <b>PDF fayl yaratilmoqda...</b>", parse_mode="HTML")
        pdf_filename = create_anime_pdf()
        
        with open(pdf_filename, 'rb') as pdf_file:
            bot.send_document(
                call.message.chat.id,
                pdf_file,
                caption="📚 <b>Barcha animelar ro'yxati</b>\n\n"
                       "Har bir anime uchun:\n"
                       "• Nomi\n"
                       "• Kodi\n"
                       "• Start linki\n"
                       "• Turi (Serial/Bitta)\n"
                       "• Qismlar soni\n\n"
                       "🔗 Start linklarini yo'qotib qo'ysangiz, shu fayldan topishingiz mumkin.",
                parse_mode="HTML"
            )
        
        os.remove(pdf_filename)
        
    except Exception as e:
        logging.error(f"PDF yaratishda xato: {e}")
        # Agar PDF yaratishda xato bo'lsa, oddiy text formatda yuborish
        try:
            send_text_anime_list(call.message.chat.id)
        except Exception as e2:
            bot.send_message(call.message.chat.id, f"❌ <b>Xato:</b> Ro'yxat yaratishda muammo yuz berdi.", parse_mode="HTML")
    
    bot.answer_callback_query(call.id)

# Text formatda anime ro'yxati yuborish
def send_text_anime_list(chat_id):
    anime_data = load_data(JSON_FILE)
    
    if not anime_data:
        bot.send_message(chat_id, "❌ <b>Hozircha hech qanday anime mavjud emas.</b>", parse_mode="HTML")
        return
    
    text = "📚 <b>Barcha Animelar Ro'yxati</b>\n\n"
    
    for i, (code, anime) in enumerate(anime_data.items(), 1):
        link = f"https://t.me/AnirenXinata_bot?start={code}"
        
        text += f"<b>{i}. {anime['title']}</b>\n"
        text += f"   🆔 <code>{code}</code>\n"
        text += f"   🔗 {link}\n"
        
        if "episodes" in anime:
            text += f"   📺 Serial ({len(anime['episodes'])} qism)\n"
        else:
            text += f"   🎬 Bitta anime\n"
        
        text += "\n"
        
        if i % 10 == 0:
            bot.send_message(chat_id, text, parse_mode="HTML")
            text = ""
    
    if text:
        bot.send_message(chat_id, text, parse_mode="HTML")

# Episode tanlash
@bot.callback_query_handler(func=lambda call: call.data.startswith('ep_'))
def process_episode(call):
    # Avval obunani tekshirish
    user_id = call.from_user.id
    channels = load_data(CHANNELS_FILE)
    if channels and not check_subscription(user_id):
        keyboard = types.InlineKeyboardMarkup()
        for channel in channels:
            try:
                chat = bot.get_chat(channel)
                if chat.username:
                    url = f"https://t.me/{chat.username}"
                else:
                    url = f"https://t.me/c/{str(chat.id)[4:]}" if str(chat.id).startswith('-100') else f"https://t.me/c/{chat.id}"
                
                keyboard.add(types.InlineKeyboardButton(f"📢 {chat.title}", url=url))
            except:
                continue
        
        keyboard.add(types.InlineKeyboardButton("✅ Obuna bo'ldim", callback_data="check_subscription"))
        
        bot.send_message(
            call.message.chat.id, 
            "🤖 Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo'ling:", 
            reply_markup=keyboard
        )
        bot.answer_callback_query(call.id)
        return
        
    data_parts = call.data.split('_')
    if len(data_parts) < 3:
        return
        
    anime_code = data_parts[1]
    ep_index = int(data_parts[2])
    
    data = load_data(JSON_FILE)
    if anime_code not in data:
        bot.answer_callback_query(call.id, "❌ Anime topilmadi!")
        return
        
    anime = data[anime_code]
    if "episodes" not in anime or ep_index >= len(anime["episodes"]):
        bot.answer_callback_query(call.id, "❌ Qism topilmadi!")
        return
        
    episode = anime["episodes"][ep_index]
    
    try:
        bot.send_video(call.message.chat.id, episode["file_id"], 
                      caption=f"<b>🎌 {anime['title']}</b>\n\n<b>📺 Qism:</b> {episode['episode']}", 
                      parse_mode="HTML")
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.error(f"Video yuborishda xato: {e}")
        bot.answer_callback_query(call.id, "❌ Video yuborishda xatolik! File ID eskirgan bo'lishi mumkin.")

# Sahifa navigatsiyasi
@bot.callback_query_handler(func=lambda call: call.data.startswith('page_'))
def process_page_navigation(call):
    data_parts = call.data.split('_')
    if len(data_parts) < 3:
        return
        
    anime_code = data_parts[1]
    page = int(data_parts[2])
    
    data = load_data(JSON_FILE)
    if anime_code not in data:
        bot.answer_callback_query(call.id, "❌ Anime topilmadi!")
        return
        
    anime = data[anime_code]
    show_episodes_page(call.message.chat.id, anime, anime_code, page, call.message.message_id)
    bot.answer_callback_query(call.id)

# Hech narsa qilmaydigan callback (sahifa raqami uchun)
@bot.callback_query_handler(func=lambda call: call.data == 'no_action')
def no_action(call):
    bot.answer_callback_query(call.id)

# Obunani tekshirish
@bot.callback_query_handler(func=lambda call: call.data == 'check_subscription')
def check_subscription_callback(call):
    user_id = call.from_user.id
    
    if check_subscription(user_id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "✅ <b>Obuna tekshirildi! Endi botdan foydalanishingiz mumkin.</b>", 
                        reply_markup=main_menu(user_id), parse_mode="HTML")
    else:
        bot.answer_callback_query(call.id, "❌ Hali barcha kanallarga obuna bo'lmagansiz! Iltimos, barcha kanallarga obuna bo'ling va yana bir bor tekshirish tugmasini bosing.", show_alert=True)

# Yordam
@bot.callback_query_handler(func=lambda call: call.data == 'help')
def help_callback(call):
    help_text = (
        "🤖 Aniren Bot Yordami\n\n"
        "📥 Animelarni ko'rish — asosiy kanalga tashlanadigan maxsus link orqali kirib, sevimli animelaringizni tomosha qilishingiz mumkin.\n\n"
        "👨🏻‍💻 Reklama va savollar - bo'yicha adminga murojat qiling. Eslatma keraksiz narsalar bo'yicha adminga yozmang aks holda spam olishingiz mumkin!"
    )
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("🏷️ Asosiy kanal", url="https://t.me/AnimeUzbekca"),
        types.InlineKeyboardButton("👨🏻‍💻 Admin", url="https://t.me/shoxruhck")
    )
    
    bot.send_message(call.message.chat.id, help_text, reply_markup=keyboard, parse_mode="HTML")
    bot.answer_callback_query(call.id)

# Anime qo'shish
@bot.callback_query_handler(func=lambda call: call.data == 'add_anime')
def add_anime_callback(call):
    user_id = call.from_user.id
    if not check_user(user_id):
        bot.answer_callback_query(call.id, "❌ Sizda bunday huquq yo'q!", show_alert=True)
        return
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("🎬 Bitta Anime", callback_data="add_single"),
        types.InlineKeyboardButton("📺 Serial", callback_data="add_series")
    )
    keyboard.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu"))
    
    bot.send_message(call.message.chat.id, "📁 <b>Qanday turdagi anime qo'shmoqchisiz?</b>", 
                    reply_markup=keyboard, parse_mode="HTML")
    bot.answer_callback_query(call.id)

# Asosiy menyuga qaytish
@bot.callback_query_handler(func=lambda call: call.data == 'main_menu')
def main_menu_callback(call):
    bot.edit_message_text(
        "🏠 <b>Asosiy menyu</b>", 
        call.message.chat.id,
        call.message.message_id,
        reply_markup=main_menu(call.from_user.id), 
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

# Bitta anime qo'shish
@bot.callback_query_handler(func=lambda call: call.data == 'add_single')
def add_single_callback(call):
    user_id = call.from_user.id
    if not check_user(user_id):
        bot.answer_callback_query(call.id, "❌ Sizda bunday huquq yo'q!", show_alert=True)
        return
    
    user_states[user_id] = {'state': 'waiting_for_title', 'is_series': False}
    bot.send_message(call.message.chat.id, "🎬 <b>Bitta anime qo'shish</b>\n\nAnime nomini yuboring:", parse_mode="HTML")
    bot.answer_callback_query(call.id)

# Serial qo'shish
@bot.callback_query_handler(func=lambda call: call.data == 'add_series')
def add_series_callback(call):
    user_id = call.from_user.id
    if not check_user(user_id):
        bot.answer_callback_query(call.id, "❌ Sizda bunday huquq yo'q!", show_alert=True)
        return
    
    user_states[user_id] = {'state': 'waiting_for_title', 'is_series': True}
    bot.send_message(call.message.chat.id, "📺 <b>Serial qo'shish</b>\n\nAnime nomini yuboring:", parse_mode="HTML")
    bot.answer_callback_query(call.id)

# Anime nomi qabul qilish
@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id]['state'] == 'waiting_for_title')
def get_title(msg):
    user_id = msg.from_user.id
    user_data = user_states[user_id]
    user_data['title'] = msg.text
    
    if user_data['is_series']:
        # Serial uchun qismlar sonini so'rash
        user_data['state'] = 'waiting_for_episodes_count'
        bot.send_message(msg.chat.id, "🔢 <b>Nechta qism bor?</b>\n\nQismlar sonini raqamda yuboring. Masalan: <code>12</code>", parse_mode="HTML")
    else:
        # Bitta anime uchun videoni so'rash
        user_data['state'] = 'waiting_for_video'
        bot.send_message(msg.chat.id, "📹 Endi video yuboring:", parse_mode="HTML")

# Serial uchun qismlar sonini qabul qilish
@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id]['state'] == 'waiting_for_episodes_count')
def get_episodes_count(msg):
    user_id = msg.from_user.id
    user_data = user_states[user_id]
    
    if not msg.text.isdigit():
        bot.send_message(msg.chat.id, "❌ <b>Iltimos, faqat raqam yuboring!</b>\n\nMasalan: <code>12</code>", parse_mode="HTML")
        return
    
    episodes_count = int(msg.text)
    if episodes_count <= 0:
        bot.send_message(msg.chat.id, "❌ <b>Qismlar soni 0 dan katta bo'lishi kerak!</b>", parse_mode="HTML")
        return
    
    user_data['episodes_count'] = episodes_count
    user_data['current_episode'] = 1
    user_data['state'] = 'waiting_for_episode_video'
    
    bot.send_message(
        msg.chat.id,
        f"✅ <b>{episodes_count} qism qabul qilindi!</b>\n\n"
        f"📹 Endi <b>1-qism</b> uchun video yuboring:",
        parse_mode="HTML"
    )

# Serial anime uchun video qabul qilish
@bot.message_handler(content_types=['video'], func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id]['state'] == 'waiting_for_episode_video')
def get_episode_video(msg):
    user_id = msg.from_user.id
    user_data = user_states[user_id]
    
    if 'episodes' not in user_data:
        user_data['episodes'] = []
    
    file_id = msg.video.file_id
    current_episode = user_data['current_episode']
    
    # Qismni saqlash
    user_data['episodes'].append({
        'episode': f"{current_episode}-qism",
        'file_id': file_id
    })
    
    # Keyingi qismga o'tish
    user_data['current_episode'] += 1
    
    if user_data['current_episode'] <= user_data['episodes_count']:
        # Keyingi qismni so'rash
        bot.send_message(
            msg.chat.id,
            f"✅ <b>{current_episode}-qism</b> qo'shildi!\n\n"
            f"📹 Endi <b>{user_data['current_episode']}-qism</b> uchun video yuboring:",
            parse_mode="HTML"
        )
    else:
        # Barcha qismlar qo'shildi
        title = user_data['title']
        code = str(abs(hash(title)))[:8]
        
        anime_data = load_data(JSON_FILE)
        anime_data[code] = {
            "title": title,
            "episodes": user_data['episodes']
        }
        save_data(anime_data, JSON_FILE)
        
        link = f"https://t.me/AnirenXinata_bot?start={code}"
        bot.send_message(
            msg.chat.id,
            f"✅ <b>Serial muvaffaqiyatli qo'shildi!</b>\n\n"
            f"🎬 <b>Nomi:</b> {title}\n"
            f"📺 <b>Qismlar soni:</b> {user_data['episodes_count']}\n"
            f"🔗 <b>Link:</b> <code>{link}</code>",
            parse_mode="HTML"
        )
        
        if user_id in user_states:
            del user_states[user_id]

# Bitta anime uchun video qabul qilish
@bot.message_handler(content_types=['video'], func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id]['state'] == 'waiting_for_video')
def get_video(msg):
    user_id = msg.from_user.id
    user_data = user_states[user_id]
    
    title = user_data['title']
    file_id = msg.video.file_id
    code = str(abs(hash(title)))[:8]

    anime_data = load_data(JSON_FILE)
    anime_data[code] = {
        "title": title,
        "file_id": file_id
    }
    save_data(anime_data, JSON_FILE)

    link = f"https://t.me/AnirenXinata_bot?start={code}"
    bot.send_message(
        msg.chat.id,
        f"✅ <b>Anime muvaffaqiyatli qo'shildi!</b>\n\n"
        f"🎬 <b>Nomi:</b> {title}\n"
        f"🔗 <b>Link:</b> <code>{link}</code>",
        parse_mode="HTML"
    )
    
    if user_id in user_states:
        del user_states[user_id]

# Adminlar boshqaruvi
@bot.callback_query_handler(func=lambda call: call.data == 'admin_manage')
def admin_manage_callback(call):
    user_id = call.from_user.id
    if user_id != MAIN_ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Faqat asosiy admin adminlarni boshqara oladi!", show_alert=True)
        return
    
    admins = load_data(ADMINS_FILE)
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("➕ Admin qo'shish", callback_data="add_admin"),
        types.InlineKeyboardButton("➖ Admin o'chirish", callback_data="remove_admin")
    )
    keyboard.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu"))
    
    admin_list = "\n".join([f"• <code>{admin_id}</code> - {name}" for admin_id, name in admins.items()]) if admins else "• Hozircha adminlar mavjud emas"
    
    bot.send_message(
        call.message.chat.id, 
        f"👥 <b>Adminlar boshqaruvi</b>\n\n{admin_list}", 
        reply_markup=keyboard, 
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

# Admin qo'shish
@bot.callback_query_handler(func=lambda call: call.data == 'add_admin')
def add_admin_callback(call):
    user_id = call.from_user.id
    user_states[user_id] = {'state': 'waiting_for_new_admin'}
    bot.send_message(call.message.chat.id, "👤 <b>Yangi admin ID sini yuboring:</b>", parse_mode="HTML")
    bot.answer_callback_query(call.id)

# Yangi admin qabul qilish
@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id]['state'] == 'waiting_for_new_admin')
def get_new_admin(msg):
    user_id = msg.from_user.id
    
    if not msg.text.isdigit():
        bot.send_message(msg.chat.id, "❌ <b>ID faqat raqamlardan iborat bo'lishi kerak!</b>", parse_mode="HTML")
        return
    
    admin_id = msg.text
    admins = load_data(ADMINS_FILE)
    
    if admin_id in admins:
        bot.send_message(msg.chat.id, "❌ <b>Bu admin allaqachon qo'shilgan!</b>", parse_mode="HTML")
        if user_id in user_states:
            del user_states[user_id]
        return
    
    try:
        admins[admin_id] = f"User {admin_id}"
        save_data(admins, ADMINS_FILE)
        
        bot.send_message(msg.chat.id, f"✅ <b>Yangi admin qo'shildi:</b>\n\n👤 User\n🆔 <code>{admin_id}</code>", parse_mode="HTML")
        
        try:
            bot.send_message(admin_id, "🎉 <b>Siz admin sifatida tayinlandingiz!</b>", parse_mode="HTML")
        except:
            pass
            
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ <b>Xato:</b> Foydalanuvchi topilmadi yoki botga yozmagan", parse_mode="HTML")
    
    if user_id in user_states:
        del user_states[user_id]

# Admin o'chirish
@bot.callback_query_handler(func=lambda call: call.data == 'remove_admin')
def remove_admin_callback(call):
    admins = load_data(ADMINS_FILE)
    if not admins:
        bot.answer_callback_query(call.id, "❌ Hozircha adminlar mavjud emas!", show_alert=True)
        return
    
    keyboard = types.InlineKeyboardMarkup()
    for admin_id, name in admins.items():
        keyboard.add(types.InlineKeyboardButton(f"👤 {name} - {admin_id}", callback_data=f"remove_{admin_id}"))
    
    keyboard.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="admin_manage"))
    
    bot.send_message(call.message.chat.id, "➖ <b>O'chirish uchun adminni tanlang:</b>", reply_markup=keyboard, parse_mode="HTML")
    bot.answer_callback_query(call.id)

# Adminni o'chirish
@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_'))
def process_remove_admin(call):
    admin_id = call.data.replace('remove_', '')
    admins = load_data(ADMINS_FILE)
    
    if admin_id in admins:
        removed_name = admins[admin_id]
        del admins[admin_id]
        save_data(admins, ADMINS_FILE)
        
        bot.send_message(call.message.chat.id, f"✅ <b>Admin o'chirildi:</b>\n\n👤 {removed_name}\n🆔 <code>{admin_id}</code>", parse_mode="HTML")
        
        try:
            bot.send_message(admin_id, "❌ <b>Sizning admin huquqingiz olib tashlandi.</b>", parse_mode="HTML")
        except:
            pass
    else:
        bot.send_message(call.message.chat.id, "❌ <b>Admin topilmadi!</b>", parse_mode="HTML")
    
    bot.answer_callback_query(call.id)

# Kanal boshqaruvi
@bot.callback_query_handler(func=lambda call: call.data == 'channel_manage')
def channel_manage_callback(call):
    user_id = call.from_user.id
    if not check_user(user_id):
        bot.answer_callback_query(call.id, "❌ Sizda bunday huquq yo'q!", show_alert=True)
        return
    
    channels = load_data(CHANNELS_FILE)
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel"),
        types.InlineKeyboardButton("➖ Kanal o'chirish", callback_data="remove_channel")
    )
    keyboard.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu"))
    
    channel_list = ""
    for i, channel in enumerate(channels, 1):
        try:
            chat = bot.get_chat(channel)
            channel_list += f"{i}. {chat.title} - <code>{channel}</code>\n"
        except:
            channel_list += f"{i}. {channel} (Xato)\n"
    
    if not channel_list:
        channel_list = "Hozircha kanallar mavjud emas"
    
    bot.send_message(
        call.message.chat.id, 
        f"📢 <b>Majburiy obuna kanallari</b>\n\n{channel_list}", 
        reply_markup=keyboard, 
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

# Kanal qo'shish
@bot.callback_query_handler(func=lambda call: call.data == 'add_channel')
def add_channel_callback(call):
    user_id = call.from_user.id
    user_states[user_id] = {'state': 'waiting_for_channel_to_add'}
    bot.send_message(
        call.message.chat.id, 
        "📢 <b>Kanal qo'shish</b>\n\nKanal username yoki ID sini yuboring:\n\n<code>@username</code> yoki <code>-1001234567890</code>", 
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

# Yangi kanal qabul qilish
@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id]['state'] == 'waiting_for_channel_to_add')
def get_new_channel(msg):
    user_id = msg.from_user.id
    channel_input = msg.text.strip()
    
    if channel_input.startswith('@'):
        channel_input = channel_input[1:]
    
    channels = load_data(CHANNELS_FILE)
    
    try:
        chat = bot.get_chat(channel_input)
        
        for existing_channel in channels:
            if str(existing_channel) == str(chat.id):
                bot.send_message(msg.chat.id, "❌ <b>Bu kanal allaqachon qo'shilgan!</b>", parse_mode="HTML")
                if user_id in user_states:
                    del user_states[user_id]
                return
        
        channels.append(chat.id)
        save_data(channels, CHANNELS_FILE)
        
        bot.send_message(msg.chat.id, f"✅ <b>Kanal qo'shildi:</b>\n\n📢 {chat.title}\n🆔 <code>{chat.id}</code>", parse_mode="HTML")
        
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ <b>Xato:</b> Kanal topilmadi yoki botda huquq yo'q! Iltimos, to'g'ri kanal ID yoki username kiriting.", parse_mode="HTML")
    
    if user_id in user_states:
        del user_states[user_id]

# Kanal o'chirish
@bot.callback_query_handler(func=lambda call: call.data == 'remove_channel')
def remove_channel_callback(call):
    channels = load_data(CHANNELS_FILE)
    if not channels:
        bot.answer_callback_query(call.id, "❌ Hozircha kanallar mavjud emas!", show_alert=True)
        return
    
    keyboard = types.InlineKeyboardMarkup()
    for channel_id in channels:
        try:
            chat = bot.get_chat(channel_id)
            keyboard.add(types.InlineKeyboardButton(f"📢 {chat.title}", callback_data=f"remove_ch_{channel_id}"))
        except:
            keyboard.add(types.InlineKeyboardButton(f"📢 {channel_id}", callback_data=f"remove_ch_{channel_id}"))
    
    keyboard.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="channel_manage"))
    
    bot.send_message(call.message.chat.id, "➖ <b>O'chirish uchun kanalni tanlang:</b>", reply_markup=keyboard, parse_mode="HTML")
    bot.answer_callback_query(call.id)

# Kanalni o'chirish
@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_ch_'))
def process_remove_channel(call):
    channel_id_to_remove = call.data.replace('remove_ch_', '')
    channels = load_data(CHANNELS_FILE)
    
    try:
        if channel_id_to_remove.isdigit() or (channel_id_to_remove.startswith('-') and channel_id_to_remove[1:].isdigit()):
            channel_id_to_remove = int(channel_id_to_remove)
    except:
        pass
    
    new_channels = []
    removed_channel = None
    
    for channel in channels:
        if str(channel) == str(channel_id_to_remove):
            removed_channel = channel
        else:
            new_channels.append(channel)
    
    if removed_channel is not None:
        save_data(new_channels, CHANNELS_FILE)
        
        try:
            chat = bot.get_chat(removed_channel)
            channel_name = chat.title
        except:
            channel_name = removed_channel
            
        bot.send_message(call.message.chat.id, f"✅ <b>Kanal o'chirildi:</b>\n\n📢 {channel_name}\n🆔 <code>{removed_channel}</code>", parse_mode="HTML")
        
        bot.delete_message(call.message.chat.id, call.message.message_id)
        channel_manage_callback(call)
    else:
        bot.send_message(call.message.chat.id, "❌ <b>Kanal topilmadi!</b>", parse_mode="HTML")
    
    bot.answer_callback_query(call.id)

# Statistika
@bot.callback_query_handler(func=lambda call: call.data == 'stats')
def stats_callback(call):
    user_id = call.from_user.id
    if not check_user(user_id):
        bot.answer_callback_query(call.id, "❌ Sizda bunday huquq yo'q!", show_alert=True)
        return
    
    anime_data = load_data(JSON_FILE)
    total_anime = len(anime_data)
    
    total_episodes = 0
    for anime in anime_data.values():
        if "episodes" in anime:
            total_episodes += len(anime["episodes"])
        else:
            total_episodes += 1
    
    admins = load_data(ADMINS_FILE)
    channels = load_data(CHANNELS_FILE)
    
    stats_text = (
        f"📊 <b>Bot Statistikasi</b>\n\n"
        f"🎬 <b>Jami Anime:</b> {total_anime}\n"
        f"📺 <b>Jami Qismlar:</b> {total_episodes}\n"
        f"👥 <b>Adminlar:</b> {len(admins) + 1}\n"
        f"📢 <b>Kanallar:</b> {len(channels)}\n"
    )
    
    bot.send_message(call.message.chat.id, stats_text, parse_mode="HTML")
    bot.answer_callback_query(call.id)

if __name__ == "__main__":
    print("Bot ishga tushdi...")
    print(f"Bot username: {bot.get_me().username}")
    bot.infinity_polling()