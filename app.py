from flask import Flask, request, Response
import telegram
import json
import time
from threading import Timer
import datetime
import os

app = Flask(__name__)

# Telegram Bot Token
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8012210020:AAFIW5s6qbuqGwvCaRmRgSLmbYz52RBPAcA')  # 從環境變量獲取 Token
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '6384551034')  # 從環境變量獲取 Chat ID

# Telegram Bot 初始化
bot = telegram.Bot(token=TOKEN)

# 交易狀態
trade_state = {
    'active': False,
    'side': None,
    'start_time': None,
    'message_id': None
}

# Webhook 設置路由
@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    webhook_url = os.environ.get('WEBHOOK_URL')  # 從環境變量獲取 Webhook URL
    if not webhook_url:
        return Response('WEBHOOK_URL not set in environment variables', status=500)
    
    try:
        bot.set_webhook(url=f'{webhook_url}/webhook/telegram')
        return Response('Webhook set successfully', status=200)
    except Exception as e:
        print(f'Error setting webhook: {e}')
        return Response(f'Error setting webhook: {e}', status=500)

# Telegram Webhook 端點
@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    update = telegram.Update.de_json(request.get_json(), bot)
    if update and update.callback_query:
        handle_callback_query(update)
    return Response(status=200)

@app.route('/')
def home():
    return 'Python Server is running!'

@app.route('/webhook', methods=['GET'])
def webhook_get():
    return 'This is the /webhook endpoint. Please send a POST request.'

@app.route('/webhook', methods=['POST'])
def webhook():
    print('Received webhook request - Headers:', dict(request.headers))
    print('Received webhook request - Raw Body:', request.data)

    try:
        # 處理 JSON 和 text/plain 內容類型
        if request.content_type == 'text/plain':
            cleaned_body = request.data.decode('utf-8').replace('\n', '\\n')
            data = json.loads(cleaned_body)
        else:
            data = request.get_json()
    except Exception as e:
        print(f'Error parsing body: {e}')
        return Response('Invalid request format', status=400)

    if not data or not isinstance(data, dict) or not data:
        print('Invalid request: Empty or undefined body')
        return Response('Invalid request: Empty body', status=400)

    request_type = data.get('type')
    side = data.get('side')
    text = data.get('text')

    if request_type == 'entry':
        default_reply_markup = {
            'inline_keyboard': [[
                {'text': '✅入撚場', 'callback_data': f'activate_{side}'}
            ]]
        }

        try:
            msg = bot.send_message(
                chat_id=CHAT_ID,
                text=text,
                parse_mode='Markdown',
                reply_markup=default_reply_markup
            )
            trade_state['message_id'] = msg.message_id
            print('Message sent to Telegram:', text)
            return Response(status=200)
        except Exception as e:
            print(f'Error sending Telegram message: {e}')
            return Response(status=500)

    elif request_type == 'risk':
        try:
            bot.send_message(
                chat_id=CHAT_ID,
                text=text,
                parse_mode='Markdown'
            )
            print('Risk message sent to Telegram:', text)
            return Response(status=200)
        except Exception as e:
            print(f'Error sending risk alert: {e}')
            return Response(status=500)
    else:
        print('Invalid type:', request_type)
        return Response(status=400)

def handle_callback_query(update):
    callback_query = update.callback_query
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.message_id
    callback_data = callback_query.data

    if callback_data.startswith('activate_'):
        side = callback_data.split('_')[1]  # 提取 side（long 或 short）
        trade_state['active'] = True
        trade_state['side'] = side
        trade_state['start_time'] = time.time()

        try:
            bot.answer_callback_query(callback_query.id)
            bot.send_message(
                chat_id=chat_id,
                text='✅ 交易已啟動！開始 5 分鐘風險監控...'
            )
            # 5 分鐘後檢查風險
            Timer(300, check_risk).start()
        except Exception as e:
            print(f'Error handling callback: {e}')

def check_risk():
    if trade_state['active'] and trade_state['side']:
        risk_text = (
            f"⚠️ ETH 快速風險變化提示 📡\n"
            f"📅 時框：5分鐘 | ⏰ 檢查時間：{datetime.datetime.now().astimezone(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⭐ 風險級別：{get_stars(3)} ({round(50)}%)\n\n"
            f"📉 異常因子升幅：🌡️\n"
            f"📊 成交量壓力 (高於 MA10) ✅\n"
            f"📉 成交量/價格 (高於 MA10) ✅\n"
            f"📈 EMA5 / EMA10 下降 ✅\n"
            f"📉 MACD 死叉 ✅\n"
            f"⚠️ 優先級依據：優先級低於原單\n\n"
            f"💡 建議動作：平倉觀察 🛑\n"
            f"💰 最佳平倉價：3000.00"
        )
        try:
            bot.send_message(
                chat_id=CHAT_ID,
                text=risk_text,
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f'Error sending risk alert: {e}')

        trade_state['active'] = False
        trade_state['side'] = None
        trade_state['start_time'] = None

def get_stars(score):
    max_score = 8
    star_count = min(int((score / max_score) * 8), 8)
    percentage = round((score / max_score) * 100)
    return '⭐' * star_count + f' ({percentage}%)'

if __name__ == '__main__':
    # 設置 Webhook（僅在啟動時運行一次）
    webhook_url = os.environ.get('WEBHOOK_URL')
    if webhook_url:
        try:
            bot.set_webhook(url=f'{webhook_url}/webhook/telegram')
            print(f'Webhook set to {webhook_url}/webhook/telegram')
        except Exception as e:
            print(f'Error setting webhook: {e}')
    
    # 啟動 Flask 服務器
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
