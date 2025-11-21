import time
import requests
import logging
import json
import os
import re
import threading
import hashlib
import base64
from datetime import datetime, date, timedelta

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "8369536092:AAH7eVlnHwDTV7oO4zYOwTovZiThCUrJvmo")
DEFAULT_CHAT_ID = '-1002727903062'
USERNAME = 'Rifay1'
PASSWORD = 'Riufat1'
BASE_URL = "http://51.89.99.105"
LOGIN_PAGE_URL = BASE_URL + "/NumberPanel/login"
LOGIN_POST_URL = BASE_URL + "/NumberPanel/signin"
DATA_URL = BASE_URL + "/NumberPanel/client/res/data_smscdr.php"

# Encoded URLs for security - Developer URL encoded, Help Group URL normal
ENCODED_DEVELOPER_URL = "aHR0cHM6Ly90Lm1lL2FidWJva2thcmRldg=="  # t.me/abubokkardev (encoded)
HELP_GROUP_URL = "https://t.me/smarttipschat"  # Help group URL (normal - anyone can change)

# Admin configuration
ADMIN_CHAT_IDS = {
    -1002727903062,  # Default chat ID as admin
    1584045588,      # Admin user ID
}

# Global variables
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})
monitoring_active = True
last_update_id = 0
recovery_timer = None

# Logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Security functions to decode URLs
def decode_developer_url():
    """Decode base64 encoded developer URL - hidden from users"""
    try:
        return base64.b64decode(ENCODED_DEVELOPER_URL).decode('utf-8')
    except:
        return "https://t.me/abubokkardev"  # fallback URL

def get_developer_url():
    """Get developer contact URL - encoded and hidden"""
    return decode_developer_url()

def get_help_group_url():
    """Get help group URL - normal URL that can be changed"""
    return HELP_GROUP_URL

# Configuration management functions
def load_config():
    """Load configuration from JSON file"""
    default_config = {
        "monitoring_active": True,
        "last_check_date": str(date.today()),
        "last_recovery": "Never",
        "last_recovery_sent": None
    }
    
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r", encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
    
    return default_config

def save_config(config):
    """Save configuration to JSON file"""
    try:
        with open("config.json", "w", encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving config: {e}")

def load_groups():
    """Load group list from JSON file"""
    try:
        if os.path.exists("groups.json"):
            with open("groups.json", "r", encoding='utf-8') as f:
                groups_data = json.load(f)
                if isinstance(groups_data, list):
                    return set(groups_data)
                else:
                    return {DEFAULT_CHAT_ID}
    except Exception as e:
        logger.error(f"Error loading groups: {e}")
    
    return {DEFAULT_CHAT_ID}

def save_groups(groups):
    """Save group list to JSON file"""
    try:
        with open("groups.json", "w", encoding='utf-8') as f:
            json.dump(list(groups), f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving groups: {e}")

def load_stats():
    """Load statistics from JSON file"""
    default_stats = {
        "today_sms_count": 0,
        "last_date": str(date.today()),
        "total_sms_sent": 0
    }
    
    try:
        if os.path.exists("stats.json"):
            with open("stats.json", "r", encoding='utf-8') as f:
                stats = json.load(f)
                # Reset daily count if date changed
                if stats.get("last_date") != str(date.today()):
                    stats["today_sms_count"] = 0
                    stats["last_date"] = str(date.today())
                return stats
    except Exception as e:
        logger.error(f"Error loading stats: {e}")
    
    return default_stats

def save_stats(stats):
    """Save statistics to JSON file"""
    try:
        with open("stats.json", "w", encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving stats: {e}")

def load_already_sent():
    """Load already sent OTPs from JSON file"""
    try:
        if os.path.exists("already_sent.json"):
            with open("already_sent.json", "r", encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
                else:
                    return set()
    except Exception as e:
        logger.error(f"Error loading already_sent: {e}")
    
    return set()

def save_already_sent(already_sent):
    """Save already sent OTPs to JSON file"""
    try:
        with open("already_sent.json", "w", encoding='utf-8') as f:
            json.dump(list(already_sent), f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving already_sent: {e}")

def send_message(chat_id, text, parse_mode=None, reply_markup=None):
    """Send a message to a chat"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text
    }
    if parse_mode:
        data["parse_mode"] = parse_mode
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
        
    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        if result.get("ok"):
            return True
        else:
            logger.error(f"Failed to send message: {result}")
            return False
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False

def edit_message(chat_id, message_id, text, parse_mode=None, reply_markup=None):
    """Edit an existing message"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }
    if parse_mode:
        data["parse_mode"] = parse_mode
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
        
    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        return result.get("ok", False)
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        return False

def get_updates(offset=0, timeout=10):
    """Get updates from Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {
        "offset": offset,
        "timeout": timeout
    }
    
    try:
        response = requests.get(url, params=params, timeout=timeout+5)
        return response.json()
    except Exception as e:
        logger.error(f"Error getting updates: {e}")
        return {"ok": False, "result": []}

def handle_commands(update):
    """Handle incoming commands"""
    if "message" not in update:
        # Handle callback queries
        if "callback_query" in update:
            handle_callback_query(update["callback_query"])
        return
        
    message = update["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    
    if not text.startswith("/"):
        return
    
    # Check if user is admin
    if chat_id not in ADMIN_CHAT_IDS:
        send_message(chat_id, "❌ You are not authorized to use this bot.")
        return
    
    command = text.split()[0].lower()
    args = text.split()[1:] if len(text.split()) > 1 else []
    
    if command == "/start":
        handle_start(chat_id)
    elif command == "/panel":
        handle_panel(chat_id)
    elif command == "/on":
        handle_on(chat_id)
    elif command == "/off":
        handle_off(chat_id)
    elif command == "/status":
        handle_status(chat_id)
    elif command == "/groupadd":
        handle_groupadd(chat_id, args)
    elif command == "/grouplist":
        handle_grouplist(chat_id)
    elif command == "/groupremove":
        handle_groupremove(chat_id, args)
    elif command == "/stats":
        handle_stats(chat_id)
    elif command == "/recovery":
        handle_recovery(chat_id)
    elif command == "/test_recovery":
        handle_test_recovery(chat_id)

def handle_callback_query(callback_query):
    """Handle callback queries from inline keyboards"""
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]
    data = callback_query["data"]
    
    if chat_id not in ADMIN_CHAT_IDS:
        send_message(chat_id, "❌ You are not authorized to use this bot.")
        return
    
    if data == "panel":
        handle_panel(chat_id, message_id)
    elif data == "monitoring_on":
        handle_on(chat_id, message_id)
    elif data == "monitoring_off":
        handle_off(chat_id, message_id)
    elif data == "status":
        handle_status(chat_id, message_id)
    elif data == "stats":
        handle_stats(chat_id, message_id)
    elif data == "grouplist":
        handle_grouplist(chat_id, message_id)
    elif data == "recovery":
        handle_recovery(chat_id, message_id)

def create_admin_panel():
    """Create admin panel inline keyboard"""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔄 Monitoring ON", "callback_data": "monitoring_on"},
                {"text": "⏸️ Monitoring OFF", "callback_data": "monitoring_off"}
            ],
            [
                {"text": "📊 Status", "callback_data": "status"},
                {"text": "📈 Statistics", "callback_data": "stats"}
            ],
            [
                {"text": "👥 Group List", "callback_data": "grouplist"},
                {"text": "🔄 Recovery", "callback_data": "recovery"}
            ],
            [
                {"text": "🔄 Refresh Panel", "callback_data": "panel"}
            ]
        ]
    }
    return keyboard

def create_otp_message_keyboard():
    """Create keyboard for OTP messages with developer contact and help group"""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📢 Numbers Channel", "url": "https://t.me/Serverpanel00"},
                {"text": "👨‍💻 Developer", "url": get_developer_url()}
            ],
            [
                {"text": "🆘 Help & Support", "url": get_help_group_url()}
            ]
        ]
    }
    return keyboard

def create_recovery_keyboard():
    """Create keyboard for recovery messages"""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔄 Recover Bot Now", "url": "https://play.google.com/store/apps/details?id=com.hosting.hosting"}
            ],
            [
                {"text": "👨‍💻 Contact Developer", "url": get_developer_url()},
                {"text": "🆘 Get Help", "url": get_help_group_url()}
            ]
        ]
    }
    return keyboard

def handle_start(chat_id):
    """Handle /start command"""
    text = (
        "🤖 <b>OTP Monitoring Bot</b>\n\n"
        "Available commands:\n"
        "/panel - Open Admin Control Panel\n"
        "/on - Start SMS monitoring\n"
        "/off - Stop SMS monitoring\n"
        "/status - Check monitoring status\n"
        "/stats - View detailed statistics\n"
        "/groupadd &lt;group_id&gt; - Add new group for SMS forwarding\n"
        "/grouplist - List all groups\n"
        "/groupremove &lt;group_id&gt; - Remove a group\n"
        "/recovery - Send recovery message\n"
        "/test_recovery - Test recovery message\n"
    )
    send_message(chat_id, text, parse_mode="HTML")

def handle_panel(chat_id, message_id=None):
    """Handle /panel command - Show admin control panel"""
    config = load_config()
    stats = load_stats()
    groups = load_groups()
    
    status_text = "🎛️ <b>Admin Control Panel</b>\n\n"
    status_text += f"🔄 <b>Monitoring:</b> {'🟢 ACTIVE' if config.get('monitoring_active', True) else '🔴 STOPPED'}\n"
    status_text += f"📅 <b>Current Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    status_text += f"📱 <b>Today's SMS Count:</b> {stats.get('today_sms_count', 0)}\n"
    status_text += f"📊 <b>Total SMS Sent:</b> {stats.get('total_sms_sent', 0)}\n"
    status_text += f"👥 <b>Active Groups:</b> {len(groups)}\n"
    status_text += f"⏰ <b>Last Recovery:</b> {config.get('last_recovery', 'Never')}\n\n"
    status_text += "<i>Use buttons below to control the bot:</i>"
    
    keyboard = create_admin_panel()
    
    if message_id:
        edit_message(chat_id, message_id, status_text, parse_mode="HTML", reply_markup=keyboard)
    else:
        send_message(chat_id, status_text, parse_mode="HTML", reply_markup=keyboard)

def handle_on(chat_id, message_id=None):
    """Handle monitoring ON"""
    global monitoring_active
    monitoring_active = True
    
    config = load_config()
    config["monitoring_active"] = True
    save_config(config)
    
    text = "✅ SMS monitoring has been <b>STARTED</b>."
    
    if message_id:
        edit_message(chat_id, message_id, text, parse_mode="HTML", reply_markup=create_admin_panel())
    else:
        send_message(chat_id, text, parse_mode="HTML")
    
    logger.info(f"Monitoring started by admin {chat_id}")

def handle_off(chat_id, message_id=None):
    """Handle monitoring OFF"""
    global monitoring_active
    monitoring_active = False
    
    config = load_config()
    config["monitoring_active"] = False
    save_config(config)
    
    text = "⏸️ SMS monitoring has been <b>STOPPED</b>."
    
    if message_id:
        edit_message(chat_id, message_id, text, parse_mode="HTML", reply_markup=create_admin_panel())
    else:
        send_message(chat_id, text, parse_mode="HTML")
    
    logger.info(f"Monitoring stopped by admin {chat_id}")

def handle_status(chat_id, message_id=None):
    """Handle status check"""
    config = load_config()
    stats = load_stats()
    groups = load_groups()
    
    status_text = "📊 <b>Bot Status</b>\n\n"
    status_text += f"🔄 <b>Monitoring:</b> {'🟢 ACTIVE' if config.get('monitoring_active', True) else '🔴 STOPPED'}\n"
    status_text += f"📅 <b>Current Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    status_text += f"📱 <b>Today's SMS Count:</b> {stats.get('today_sms_count', 0)}\n"
    status_text += f"📊 <b>Total SMS Sent:</b> {stats.get('total_sms_sent', 0)}\n"
    status_text += f"👥 <b>Active Groups:</b> {len(groups)}\n"
    status_text += f"⏰ <b>Last Recovery:</b> {config.get('last_recovery', 'Never')}\n"
    status_text += f"🖥️ <b>Web Login:</b> {'✅ OK' if check_web_login() else '❌ FAILED'}\n"
    
    if message_id:
        edit_message(chat_id, message_id, status_text, parse_mode="HTML", reply_markup=create_admin_panel())
    else:
        send_message(chat_id, status_text, parse_mode="HTML")

def handle_stats(chat_id, message_id=None):
    """Handle detailed statistics"""
    stats = load_stats()
    groups = load_groups()
    
    stats_text = "📈 <b>Detailed Statistics</b>\n\n"
    stats_text += f"📱 <b>Today's SMS Count:</b> {stats.get('today_sms_count', 0)}\n"
    stats_text += f"📊 <b>Total SMS Sent:</b> {stats.get('total_sms_sent', 0)}\n"
    stats_text += f"📅 <b>Last Reset:</b> {stats.get('last_date', 'Unknown')}\n"
    stats_text += f"👥 <b>Active Groups:</b> {len(groups)}\n\n"
    
    # Group list
    if groups:
        stats_text += "<b>Active Groups:</b>\n"
        for i, group_id in enumerate(groups, 1):
            stats_text += f"{i}. <code>{group_id}</code>\n"
    
    if message_id:
        edit_message(chat_id, message_id, stats_text, parse_mode="HTML", reply_markup=create_admin_panel())
    else:
        send_message(chat_id, stats_text, parse_mode="HTML")

def handle_grouplist(chat_id, message_id=None):
    """Handle group list display"""
    groups = load_groups()
    
    if not groups:
        text = "❌ No groups added yet."
    else:
        text = "👥 <b>Active Groups</b>\n\n"
        for i, group_id in enumerate(groups, 1):
            text += f"{i}. <code>{group_id}</code>\n"
        text += f"\nTotal: {len(groups)} groups"
    
    if message_id:
        edit_message(chat_id, message_id, text, parse_mode="HTML", reply_markup=create_admin_panel())
    else:
        send_message(chat_id, text, parse_mode="HTML")

def handle_groupadd(chat_id, args):
    """Handle /groupadd command"""
    if not args:
        send_message(chat_id, "❌ Please provide a group ID. Usage: /groupadd &lt;group_id&gt;", parse_mode="HTML")
        return
    
    try:
        group_id = args[0]
        # Try to convert to int if it's a numeric ID
        if group_id.lstrip('-').isdigit():
            group_id = int(group_id)
        else:
            # Handle @username format
            if group_id.startswith('@'):
                group_id = group_id[1:]
        
        groups = load_groups()
        if group_id in groups:
            send_message(chat_id, f"⚠️ Group <code>{group_id}</code> is already in the list.", parse_mode="HTML")
            return
            
        groups.add(group_id)
        save_groups(groups)
        
        send_message(chat_id, f"✅ Group <code>{group_id}</code> has been added to the broadcast list.", parse_mode="HTML")
        logger.info(f"Group {group_id} added by admin {chat_id}")
        
    except Exception as e:
        send_message(chat_id, f"❌ Error adding group: {str(e)}")
        logger.error(f"Error adding group: {e}")

def handle_groupremove(chat_id, args):
    """Handle /groupremove command"""
    if not args:
        send_message(chat_id, "❌ Please provide a group ID. Usage: /groupremove &lt;group_id&gt;", parse_mode="HTML")
        return
    
    try:
        group_id = args[0]
        # Try to convert to int if it's a numeric ID
        if group_id.lstrip('-').isdigit():
            group_id = int(group_id)
        
        groups = load_groups()
        if group_id not in groups:
            send_message(chat_id, f"❌ Group <code>{group_id}</code> not found in the list.", parse_mode="HTML")
            return
            
        groups.remove(group_id)
        save_groups(groups)
        
        send_message(chat_id, f"✅ Group <code>{group_id}</code> has been removed from the broadcast list.", parse_mode="HTML")
        logger.info(f"Group {group_id} removed by admin {chat_id}")
        
    except Exception as e:
        send_message(chat_id, f"❌ Error removing group: {str(e)}")
        logger.error(f"Error removing group: {e}")

def handle_recovery(chat_id, message_id=None):
    """Handle recovery message"""
    send_recovery_message(chat_id, message_id, is_test=False)

def handle_test_recovery(chat_id):
    """Handle test recovery message"""
    send_recovery_message(chat_id, is_test=True)

def send_recovery_message(chat_id, message_id=None, is_test=False):
    """Send recovery message to admin"""
    if is_test:
        recovery_text = "🧪 <b>TEST - Recovery Required</b>\n\n"
    else:
        recovery_text = "🔄 <b>Recovery Required</b>\n\n"
    
    recovery_text += "⚠️ <b>System recovery needed!</b>\n\n"
    recovery_text += "Please recover the bot system by clicking the button below to ensure continuous operation.\n\n"
    recovery_text += "<i>This is an automated recovery message.</i>"
    
    recovery_keyboard = create_recovery_keyboard()
    
    # Update last recovery time
    config = load_config()
    config["last_recovery"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if not is_test:
        config["last_recovery_sent"] = datetime.now().isoformat()
    save_config(config)
    
    if message_id:
        success = edit_message(chat_id, message_id, recovery_text, parse_mode="HTML", reply_markup=recovery_keyboard)
    else:
        success = send_message(chat_id, recovery_text, parse_mode="HTML", reply_markup=recovery_keyboard)
    
    if success:
        logger.info(f"{'Test ' if is_test else ''}Recovery message sent to admin {chat_id}")
    else:
        logger.error(f"Failed to send {'test ' if is_test else ''}recovery message to admin {chat_id}")

def schedule_recovery_messages():
    """Schedule recovery messages every 22 hours"""
    global recovery_timer
    
    def send_recovery_to_admins():
        try:
            config = load_config()
            last_sent = config.get("last_recovery_sent")
            
            # Check if 22 hours have passed since last recovery message
            if last_sent:
                last_sent_time = datetime.fromisoformat(last_sent)
                time_diff = datetime.now() - last_sent_time
                if time_diff.total_seconds() < 22 * 3600:  # 22 hours in seconds
                    logger.info(f"Skipping recovery message, {time_diff.total_seconds()/3600:.1f} hours passed")
                    # Schedule next check
                    schedule_recovery_messages()
                    return
            
            recovery_text = "🔄 <b>Automated Recovery Required</b>\n\n"
            recovery_text += "⏰ <b>22-Hour System Check</b>\n\n"
            recovery_text += "The bot system requires regular recovery to maintain optimal performance.\n\n"
            recovery_text += "Please click the button below to complete the recovery process:\n\n"
            recovery_text += "<i>This is an automated message sent every 22 hours.</i>"
            
            recovery_keyboard = create_recovery_keyboard()
            
            # Send to all admins
            success_count = 0
            for admin_id in ADMIN_CHAT_IDS:
                try:
                    if send_message(admin_id, recovery_text, parse_mode="HTML", reply_markup=recovery_keyboard):
                        success_count += 1
                        logger.info(f"22-hour recovery message sent to admin {admin_id}")
                    time.sleep(1)  # Rate limiting
                except Exception as e:
                    logger.error(f"Failed to send recovery message to admin {admin_id}: {e}")
            
            # Update last recovery time only if sent successfully to at least one admin
            if success_count > 0:
                config = load_config()
                config["last_recovery"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                config["last_recovery_sent"] = datetime.now().isoformat()
                save_config(config)
                logger.info(f"Recovery messages sent to {success_count}/{len(ADMIN_CHAT_IDS)} admins")
            
        except Exception as e:
            logger.error(f"Error in recovery scheduler: {e}")
        
        # Schedule next recovery regardless of success/failure
        schedule_recovery_messages()
    
    # Cancel existing timer if any
    if recovery_timer:
        recovery_timer.cancel()
    
    # Schedule next recovery in 22 hours
    recovery_timer = threading.Timer(22 * 60 * 60, send_recovery_to_admins)
    recovery_timer.daemon = True
    recovery_timer.start()
    
    next_time = datetime.now() + timedelta(hours=22)
    logger.info(f"Recovery messages scheduled for every 22 hours. Next: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")

def check_web_login():
    """Check if web login is working"""
    try:
        url = build_api_url()
        headers = {"X-Requested-With": "XMLHttpRequest"}
        response = session.get(url, headers=headers, timeout=10)
        return response.status_code == 200
    except:
        return False

def login():
    """Login to the web interface"""
    try:
        # First, get the login page to get cookies and captcha
        resp = session.get(LOGIN_PAGE_URL, timeout=10)
        
        # Look for captcha math problem
        match = re.search(r'What is (\d+) \+ (\d+)', resp.text)
        if not match:
            logger.error("Captcha not found on login page.")
            return False
            
        num1, num2 = int(match.group(1)), int(match.group(2))
        captcha_answer = num1 + num2
        logger.info(f"Solved captcha: {num1} + {num2} = {captcha_answer}")

        # Prepare login payload
        payload = {
            "username": USERNAME,
            "password": PASSWORD,
            "capt": captcha_answer
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": LOGIN_PAGE_URL
        }

        # Perform login
        resp = session.post(LOGIN_POST_URL, data=payload, headers=headers, timeout=10)
        
        # Check if login was successful
        if "dashboard" in resp.text.lower() or "logout" in resp.text.lower() or resp.status_code == 200:
            logger.info("Login successful ✅")
            return True
        else:
            logger.error("Login failed ❌ - Invalid credentials or session issue")
            return False
            
    except requests.exceptions.Timeout:
        logger.error("Login timeout - server not responding")
        return False
    except requests.exceptions.ConnectionError:
        logger.error("Connection error - cannot reach server")
        return False
    except Exception as e:
        logger.error(f"Login error: {e}")
        return False

def build_api_url():
    """Build API URL for data fetching - Last 24 hours data"""
    now = datetime.now()
    yesterday = now - timedelta(hours=24)
    
    start_date = yesterday.strftime("%Y-%m-%d")
    start_time = yesterday.strftime("%H:%M:%S")
    end_date = now.strftime("%Y-%m-%d")
    end_time = now.strftime("%H:%M:%S")
    
    return f"{DATA_URL}?fdate1={start_date}%20{start_time}&fdate2={end_date}%20{end_time}&"

def fetch_data():
    """Fetch SMS data from the web interface"""
    url = build_api_url()
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": BASE_URL + "/NumberPanel/client/smscdr"
    }

    try:
        logger.info(f"Fetching data from URL: {url}")
        response = session.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            try:
                data = response.json()
                if data and 'aaData' in data:
                    logger.info(f"Fetched {len(data['aaData'])} SMS records")
                    return data
                else:
                    logger.info("No SMS records found in response")
                    return None
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                logger.error(f"Response text: {response.text[:500]}")
                return None
        elif response.status_code == 403 or "login" in response.text.lower():
            logger.warning("Session expired. Re-logging...")
            if login():
                return fetch_data()
            else:
                logger.error("Re-login failed")
                return None
        else:
            logger.error(f"HTTP Error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        return None

def mask_number(number: str) -> str:
    """Mask phone number for privacy"""
    if len(number) >= 11:
        return number[:6] + "***" + number[-4:]
    return number

def get_country_by_number(number: str) -> str:
    """Get country name by phone number prefix"""
    number = number.lstrip('+')
    country_codes = {
        '964': 'Iraq', '221': 'Senegal', '44': 'United Kingdom', '91': 'India',
        '880': 'Bangladesh', '92': 'Pakistan', '7': 'Russia', '968': 'Oman',
        '49': 'Germany', '34': 'Spain', '39': 'Italy', '81': 'Japan',
        '86': 'China', '62': 'Indonesia', '63': 'Philippines', '55': 'Brazil',
        '84': 'Vietnam', '66': 'Thailand', '20': 'Egypt', '998': 'Uzbekistan',
        '976': 'Mongolia', '60': 'Malaysia', '970': 'Palestine', '972': 'Israel',
        '961': 'Lebanon', '94': 'Sri Lanka', '48': 'Poland', '46': 'Sweden',
        '234': 'Nigeria', '256': 'Uganda', '212': 'Morocco', '249': 'Sudan',
        '228': 'Togo', '254': 'Kenya', '251': 'Ethiopia', '235': 'Chad',
        '213': 'Algeria', '263': 'Zimbabwe', '218': 'Libya', '93': 'Afghanistan',
        '58': 'Venezuela', '27': 'South Africa', '992': 'Tajikistan', '966': 'Saudi Arab',
        '222': 'Mauritania', '223': 'Mali', '224': 'Guinea', '225': 'Ivory Coast',
        '226': 'Burkina Faso', '227': 'Niger', '229': 'Benin', '230': 'Mauritius',
        '231': 'Liberia', '232': 'Sierra Leone', '233': 'Ghana', '234': 'Nigeria',
        '235': 'Chad', '236': 'Central African Republic', '237': 'Cameroon',
        '238': 'Cape Verde', '239': 'Sao Tome and Principe', '240': 'Equatorial Guinea',
        '241': 'Gabon', '242': 'Republic of the Congo', '243': 'Democratic Republic of the Congo',
        '244': 'Angola', '245': 'Guinea-Bissau', '246': 'British Indian Ocean Territory',
        '247': 'Ascension Island', '248': 'Seychelles', '249': 'Sudan', '250': 'Rwanda',
        '251': 'Ethiopia', '252': 'Somalia', '253': 'Djibouti', '254': 'Kenya',
        '255': 'Tanzania', '256': 'Uganda', '257': 'Burundi', '258': 'Mozambique',
        '260': 'Zambia', '261': 'Madagascar', '262': 'Reunion', '263': 'Zimbabwe',
        '264': 'Namibia', '265': 'Malawi', '266': 'Lesotho', '267': 'Botswana',
        '268': 'Swaziland', '269': 'Comoros', '290': 'Saint Helena', '291': 'Eritrea',
        '297': 'Aruba', '298': 'Faroe Islands', '299': 'Greenland'
    }

    for code in sorted(country_codes.keys(), key=lambda x: -len(x)):
        if number.startswith(code):
            return country_codes[code]
    return "Unknown"

def get_country_flag(country: str) -> str:
    """Get country flag emoji by country name"""
    flags = {
        'Iraq': '🇮🇶', 'Senegal': '🇸🇳', 'United Kingdom': '🇬🇧', 'India': '🇮🇳',
        'Bangladesh': '🇧🇩', 'Pakistan': '🇵🇰', 'Russia': '🇷🇺', 'Oman': '🇴🇲',
        'Germany': '🇩🇪', 'Spain': '🇪🇸', 'Italy': '🇮🇹', 'Japan': '🇯🇵',
        'China': '🇨🇳', 'Indonesia': '🇮🇩', 'Philippines': '🇵🇭', 'Brazil': '🇧🇷',
        'Vietnam': '🇻🇳', 'Thailand': '🇹🇭', 'Egypt': '🇪🇬', 'Uzbekistan': '🇺🇿',
        'Mongolia': '🇲🇳', 'Malaysia': '🇲🇾', 'Palestine': '🇵🇸', 'Israel': '🇮🇱',
        'Lebanon': '🇱🇧', 'Sri Lanka': '🇱🇰', 'Poland': '🇵🇱', 'Sweden': '🇸🇪',
        'Nigeria': '🇳🇬', 'Uganda': '🇺🇬', 'Morocco': '🇲🇦', 'Sudan': '🇸🇩',
        'Togo': '🇹🇬', 'Kenya': '🇰🇪', 'Ethiopia': '🇪🇹', 'Burundi': '🇧🇮',
        'Algeria': '🇩🇿', 'Zimbabwe': '🇿🇼', 'Libya': '🇱🇾', 'Afghanistan': '🇦🇫',
        'Venezuela': '🇻🇪', 'South Africa': '🇿🇦', 'Tajikistan': '🇹🇯', 'Saudi Arab': '🇸🇦',
        'Mauritania': '🇲🇷', 'Mali': '🇲🇱', 'Guinea': '🇬🇳', 'Ivory Coast': '🇨🇮',
        'Burkina Faso': '🇧🇫', 'Niger': '🇳🇪', 'Benin': '🇧🇯', 'Mauritius': '🇲🇺',
        'Liberia': '🇱🇷', 'Sierra Leone': '🇸🇱', 'Ghana': '🇬🇭', 'Cameroon': '🇨🇲',
        'Cape Verde': '🇨🇻', 'Sao Tome and Principe': '🇸🇹', 'Equatorial Guinea': '🇬🇶',
        'Gabon': '🇬🇦', 'Republic of the Congo': '🇨🇬', 'Democratic Republic of the Congo': '🇨🇩',
        'Angola': '🇦🇴', 'Guinea-Bissau': '🇬🇼', 'Rwanda': '🇷🇼', 'Somalia': '🇸🇴',
        'Djibouti': '🇩🇯', 'Tanzania': '🇹🇿', 'Mozambique': '🇲🇿', 'Zambia': '🇿🇲',
        'Madagascar': '🇲🇬', 'Namibia': '🇳🇦', 'Malawi': '🇲🇼', 'Lesotho': '🇱🇸',
        'Botswana': '🇧🇼', 'Swaziland': '🇸🇿', 'Comoros': '🇰🇲', 'Eritrea': '🇪🇷'
    }
    return flags.get(country, '🏳️')

def process_sms_messages():
    """Process SMS messages and send to all groups"""
    # Check both global variable and config file
    config = load_config()
    current_monitoring_status = config.get("monitoring_active", True)
    
    if not current_monitoring_status:
        logger.info("Monitoring is disabled in config")
        return
    
    data = fetch_data()
    
    if not data or 'aaData' not in data:
        logger.info("No data received or invalid data format")
        return
    
    already_sent = load_already_sent()
    groups = load_groups()
    stats = load_stats()
    new_messages = 0
    
    for row in data['aaData']:
        try:
            if len(row) < 5:
                continue
                
            date_str = str(row[0]).strip()
            number = str(row[2]).strip()
            service = str(row[3]).strip()
            message = str(row[4]).strip()

            # Improved OTP pattern matching
            otp_patterns = [
                r'\b\d{3}-\d{3}\b',  # 123-456
                r'\b\d{4,6}\b',      # 1234 or 123456
                r'\b\d{3}\s\d{3}\b', # 123 456
            ]
            
            otp = None
            for pattern in otp_patterns:
                match = re.search(pattern, message)
                if match:
                    otp = match.group().replace(' ', '')
                    break

            if otp:
                unique_key = f"{number}|{otp}|{date_str}"
                if unique_key not in already_sent:
                    already_sent.add(unique_key)
                    country = get_country_by_number(number)
                    country_flag = get_country_flag(country)

                    text = (
                        f"🔔 <b>NEW OTP DETECTED</b> 🆕\n\n"
                        f"🕐 <b>Time:</b> <code>{date_str}</code>\n"
                        f"🌍 <b>Country:</b> <code>{country}</code> {country_flag}\n"
                        f"⚙️ <b>Service:</b> <code>{service}</code>\n"
                        f"📞 <b>Number:</b> <code>{mask_number(number)}</code>\n"
                        f"🔑 <b>OTP:</b> <code>{otp}</code>\n"
                        f"📩 <b>Full Message:</b>\n<code>{message}</code>\n\n"
                    )

                    # Use the new keyboard with developer contact and help group
                    keyboard = create_otp_message_keyboard()

                    # Send to all groups with rate limiting
                    success_count = 0
                    for group_id in groups:
                        try:
                            if send_message(group_id, text, parse_mode="HTML", reply_markup=keyboard):
                                success_count += 1
                                logger.info(f"Sent OTP to group {group_id}: {otp}")
                            time.sleep(1)  # Add 1 second delay between messages
                        except Exception as e:
                            logger.error(f"Telegram error for group {group_id}: {e}")

                    if success_count > 0:
                        # Update statistics only if message was sent successfully
                        stats["today_sms_count"] += 1
                        stats["total_sms_sent"] += 1
                        stats["last_date"] = str(date.today())
                        new_messages += 1
                        
                        save_already_sent(already_sent)
                        save_stats(stats)
        except Exception as e:
            logger.error(f"Error processing row: {e}")
            continue
    
    if new_messages > 0:
        logger.info(f"Processed {new_messages} new OTP messages")

def bot_polling():
    """Handle bot polling for commands"""
    global last_update_id
    
    logger.info("Bot polling started")
    
    while True:
        try:
            updates = get_updates(offset=last_update_id + 1, timeout=5)
            
            if updates.get("ok") and updates.get("result"):
                for update in updates["result"]:
                    last_update_id = update["update_id"]
                    handle_commands(update)
            
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error in bot polling: {e}")
            time.sleep(5)

def monitoring_loop():
    """Main monitoring loop"""
    logger.info("Monitoring loop started")
    
    while True:
        try:
            # Check config file for monitoring status
            config = load_config()
            current_monitoring_status = config.get("monitoring_active", True)
            
            if current_monitoring_status:
                process_sms_messages()
            else:
                logger.debug("Monitoring is currently disabled.")
            time.sleep(3)
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            time.sleep(10)

def main():
    """Main function to run the bot"""
    global monitoring_active
    
    logger.info("🚀 Starting OTP Monitoring Bot...")
    
    # Load initial configuration
    config = load_config()
    monitoring_active = config.get("monitoring_active", True)
    
    # Create necessary files if they don't exist
    for filename in ["config.json", "groups.json", "stats.json", "already_sent.json"]:
        if not os.path.exists(filename):
            if filename == "config.json":
                save_config(config)
            elif filename == "groups.json":
                save_groups({DEFAULT_CHAT_ID})
            elif filename == "stats.json":
                save_stats(load_stats())
            elif filename == "already_sent.json":
                save_already_sent(set())
    
    # Login to web interface
    logger.info("Attempting to login to web interface...")
    if not login():
        logger.error("Initial login failed. Retrying in 10 seconds...")
        time.sleep(10)
        if not login():
            logger.error("Login failed after retry. Exiting...")
            return
    
    # Schedule recovery messages (22 hours)
    schedule_recovery_messages()
    
    logger.info("✅ Bot started successfully!")
    logger.info(f"📊 Bot monitoring: {'🟢 ACTIVE' if monitoring_active else '🔴 STOPPED'}")
    logger.info(f"👥 Admin IDs: {list(ADMIN_CHAT_IDS)}")
    logger.info("🕐 Recovery messages scheduled every 22 hours")
    
    # Start bot polling in separate thread
    polling_thread = threading.Thread(target=bot_polling, daemon=True)
    polling_thread.start()
    
    # Start monitoring loop
    monitoring_loop()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")