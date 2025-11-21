import requests
import json
import re
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler
import asyncio
import logging
import sqlite3
import hashlib

# Constants
SMS_URL = "http://94.23.120.156/ints/client/res/data_smscdr.php"
BASE_URL = "http://94.23.120.156/ints/"
LOGIN_URL = BASE_URL + "login"
SIGNIN_URL = BASE_URL + "signin"
DASHBOARD_URL = BASE_URL + "client/SMSCDRStats"
USERNAME = "Sha5im01"
PASSWORD = "Shafim"
TELEGRAM_TOKEN = "8369536092:AAH7eVlnHwDTV7oO4zYOwTovZiThCUrJvmo"
GROUP_ID = -1002727903062
POLL_INTERVAL = 60
MAX_LOGIN_RETRIES = 3
MESSAGE_DELAY = 2  
DATABASE_NAME = "sms_otp_bot.db"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Welcome message
welcome_msg = (
    "✨ *Welcome to OTP Bot* ✨\n\n"
    "I will automatically detect and forward OTP messages to this chat.\n\n"
    
    "━━━━━━━━━━━━━━━━━━━━━━━━"
)

# Country emojis
country_emojis = {
    "Russia": "🇷🇺", "Bulgaria": "🇧🇬", "Syria": "🇸🇾", "Afghanistan": "🇦🇫",
    "Belarus": "🇧🇾", "Togo": "🇹🇬", "Egypt": "🇪🇬", "Tanzania": "🇹🇿",
    "Tunisia": "🇹🇳", "Jordan": "🇯🇴", "Venezuela": "🇻🇪", "Kenya": "🇰🇪",
    "Nepal": "🇳🇵", "Morocco": "🇲🇦", "Tajikistan": "🇹🇯", "Lebanon": "🇱🇧",
    "Ethiopia": "🇪🇹", "Angola": "🇦🇴", "Bosnia": "🇧🇦"
}

class DatabaseManager:
    def __init__(self, db_name=DATABASE_NAME):
        self.db_name = db_name
        self.init_database()

    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Create messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                otp_code TEXT NOT NULL,
                service TEXT NOT NULL,
                country TEXT NOT NULL,
                full_message TEXT NOT NULL,
                message_hash TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                sent_to_telegram BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # Create statistics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_messages INTEGER DEFAULT 0,
                unique_otps INTEGER DEFAULT 0,
                duplicate_otps INTEGER DEFAULT 0,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Initialize statistics if not exists
        cursor.execute('SELECT COUNT(*) FROM statistics')
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO statistics (total_messages, unique_otps, duplicate_otps) VALUES (0, 0, 0)')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")

    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_name)

    def is_duplicate_message(self, phone_number, otp_code, full_message):
        """Check if message is duplicate based on number, OTP and message content"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        
        message_hash = hashlib.md5(f"{phone_number}{otp_code}{full_message}".encode()).hexdigest()
        
        cursor.execute(
            'SELECT id FROM messages WHERE message_hash = ?', 
            (message_hash,)
        )
        result = cursor.fetchone()
        conn.close()
        
        return result is not None

    def save_message(self, timestamp, phone_number, otp_code, service, country, full_message, sent_to_telegram=True):
        """Save message to database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        message_hash = hashlib.md5(f"{phone_number}{otp_code}{full_message}".encode()).hexdigest()
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO messages 
                (timestamp, phone_number, otp_code, service, country, full_message, message_hash, sent_to_telegram)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, phone_number, otp_code, service, country, full_message, message_hash, sent_to_telegram))
            
            
            if cursor.rowcount > 0:  # New message inserted
                cursor.execute('UPDATE statistics SET total_messages = total_messages + 1, unique_otps = unique_otps + 1')
            else:  # Duplicate message
                cursor.execute('UPDATE statistics SET duplicate_otps = duplicate_otps + 1')
            
            conn.commit()
            return cursor.rowcount > 0
            
        except sqlite3.IntegrityError:
            
            cursor.execute('UPDATE statistics SET duplicate_otps = duplicate_otps + 1')
            conn.commit()
            return False
        finally:
            conn.close()

    def get_statistics(self):
        """Get bot statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT total_messages, unique_otps, duplicate_otps FROM statistics LIMIT 1')
        stats = cursor.fetchone()
        
        cursor.execute('SELECT COUNT(*) FROM messages WHERE sent_to_telegram = 1')
        sent_messages = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT phone_number) FROM messages')
        unique_numbers = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT service) FROM messages')
        unique_services = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_messages': stats[0],
            'unique_otps': stats[1],
            'duplicate_otps': stats[2],
            'sent_messages': sent_messages,
            'unique_numbers': unique_numbers,
            'unique_services': unique_services
        }

    def get_recent_messages(self, limit=10):
        """Get recent messages for stats"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, phone_number, otp_code, service, country 
            FROM messages 
            WHERE sent_to_telegram = 1 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        messages = cursor.fetchall()
        conn.close()
        return messages

class SMSBot:
    def __init__(self):
        self.session = requests.Session()
        self.bot = Bot(token=TELEGRAM_TOKEN)
        self.db = DatabaseManager()
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 12; Z60 plus Build/SP1A.210812.016) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.7258.143 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        })

    async def test_telegram_connection(self):
        try:
            await self.bot.send_message(
                chat_id=GROUP_ID,
                text=welcome_msg,
                parse_mode='Markdown'
            )
            print("Telegram connection test successful")
            return True
        except Exception as e:
            print(f"Telegram connection test failed: {e}")
            return False

    def login(self):
        """Login to the Proton SMS system."""
        retry_count = 0
        while retry_count < MAX_LOGIN_RETRIES:
            try:
                logger.info(f"Testing server accessibility: {BASE_URL}")
                test_response = self.session.get(BASE_URL, timeout=30)
                logger.info(f"Server test response: Status {test_response.status_code}, URL: {test_response.url}")

                logger.info(f"Attempting login page fetch: {LOGIN_URL}")
                response = self.session.get(LOGIN_URL, timeout=30)
                logger.info(f"Login page status: {response.status_code}, URL: {response.url}")
                
                if response.status_code != 200:
                    error_msg = f"Failed to fetch login page. Status: {response.status_code}"
                    logger.error(error_msg)
                    retry_count += 1
                    time.sleep(5)
                    continue

                
                captcha_pattern = r'What is (\d+) \+ (\d+) = \? :'
                match = re.search(captcha_pattern, response.text)
                if not match:
                    error_msg = "Captcha not found"
                    logger.error(error_msg)
                    retry_count += 1
                    time.sleep(5)
                    continue
                    
                num1, num2 = match.groups()
                capt_answer = int(num1) + int(num2)
                logger.info(f"Captcha solved: {num1} + {num2} = {capt_answer}")

                
                data = {
                    'username': USERNAME,
                    'password': PASSWORD,
                    'capt': str(capt_answer)
                }

                login_headers = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': BASE_URL.rstrip('/'),
                    'Referer': LOGIN_URL,
                }

                logger.info(f"Login attempt with username {USERNAME}: {SIGNIN_URL}")
                response = self.session.post(
                    SIGNIN_URL, 
                    data=urlencode(data), 
                    headers=login_headers, 
                    timeout=30, 
                    allow_redirects=False
                )
                
                logger.info(f"Login status: {response.status_code}, Location: {response.headers.get('location', 'N/A')}")
                
                
                if response.status_code == 302 and 'client' in response.headers.get('location', ''):
                    
                    dashboard_response = self.session.get(DASHBOARD_URL, timeout=30)
                    if dashboard_response.status_code == 200 and 'login' not in dashboard_response.url:
                        logger.info("Login successful - Dashboard accessible")
                        return True
                
                logger.error(f"Login failed. Status: {response.status_code}")
                retry_count += 1
                time.sleep(5)
                    
            except requests.RequestException as e:
                logger.error(f"Error during login: {str(e)}")
                retry_count += 1
                time.sleep(5)
                
        print("Max login retries exceeded")
        return False

    def mask_number(self, number):
        if len(number) <= 8:
            return number
        return number[:4] + '*' * (len(number) - 8) + number[-4:]

    def extract_otp(self, msg):
        match = re.search(r'\b\d{4,6}\b', msg)
        return match.group(0) if match else "N/A"

    def is_valid_timestamp(self, timestamp):
        """Check if timestamp is valid and not malformed"""
        if not isinstance(timestamp, str):
            return False
        if timestamp == "0,0,0,50" or ',' in timestamp:
            return False
        try:
            datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            return True
        except ValueError:
            return False

    def get_sms_data(self):
        """Fetch SMS data with proper headers and referer"""
        try:
            
            dashboard_response = self.session.get(DASHBOARD_URL, timeout=30)
            if dashboard_response.status_code != 200:
                logger.error(f"Failed to access dashboard: {dashboard_response.status_code}")
                return {}

           
            current_date = datetime.utcnow().strftime("%Y-%m-%d")

            
            params = {
                "fdate1": f"{current_date} 00:00:00",
                "fdate2": f"{current_date} 23:59:59",
                "frange": "", "fnum": "", "fcli": "", "fgdate": "", "fgmonth": "",
                "fgrange": "", "fgnumber": "", "fgcli": "", "fg": "0", "sEcho": "1",
                "iColumns": "7", "sColumns": ",,,,,,", "iDisplayStart": "0",
                "iDisplayLength": "-1",
                "mDataProp_0": "0", "sSearch_0": "", "bRegex_0": "false",
                "bSearchable_0": "true", "bSortable_0": "true",
                "mDataProp_1": "1", "sSearch_1": "", "bRegex_1": "false",
                "bSearchable_1": "true", "bSortable_1": "true",
                "mDataProp_2": "2", "sSearch_2": "", "bRegex_2": "false",
                "bSearchable_2": "true", "bSortable_2": "true",
                "mDataProp_3": "3", "sSearch_3": "", "bRegex_3": "false",
                "bSearchable_3": "true", "bSortable_3": "true",
                "mDataProp_4": "4", "sSearch_4": "", "bRegex_4": "false",
                "bSearchable_4": "true", "bSortable_4": "true",
                "mDataProp_5": "5", "sSearch_5": "", "bRegex_5": "false",
                "bSearchable_5": "true", "bSortable_5": "true",
                "mDataProp_6": "6", "sSearch_6": "", "bRegex_6": "false",
                "bSearchable_6": "true", "bSortable_6": "true",
                "sSearch": "", "bRegex": "false", 
                "iSortCol_0": "0", "sSortDir_0": "desc",
                "iSortingCols": "1"
            }

            
            sms_headers = {
                'Referer': DASHBOARD_URL,
                'X-Requested-With': 'XMLHttpRequest'
            }

            response = self.session.get(
                SMS_URL, 
                params=params, 
                headers=sms_headers,
                timeout=30
            )
            
            logger.info(f"SMS data response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"SMS fetch failed with status: {response.status_code}")
                return {}

            
            try:
                data = json.loads(response.text)
                return data
            except json.JSONDecodeError:
                logger.error(f"JSON decode error. Response text: {response.text[:200]}...")
                return {}

        except requests.RequestException as e:
            logger.error(f"SMS fetch error: {e}")
            return {}

    async def send_telegram_message(self, message_data):
        if len(message_data) < 5:
            return
            
        timestamp, range_name, number, service, full_message = message_data[:5]
        
        
        if not self.is_valid_timestamp(timestamp):
            logger.warning(f"Skipping message with invalid timestamp: {timestamp}")
            return
            
        try:
            dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            formatted_date = dt.strftime("%Y-%m-%d")
            formatted_time = dt.strftime("%H:%M:%S")
        except ValueError:
            print(f"Invalid timestamp format: {timestamp}")
            return
            
        country = range_name.split()[0] if range_name else "Unknown"
        country_emoji = country_emojis.get(country, "🌍")
        otp = self.extract_otp(full_message)
        masked_number = self.mask_number(number)
        
       
        if self.db.is_duplicate_message(number, otp, full_message):
            print(f"⚠️ Skipping duplicate OTP: {otp} for number {masked_number}")
            return
        
        message = (
            f"<blockquote><b>📨 New {service} OTP Detected</b></blockquote>\n\n"
            f"<blockquote><b>⏰ Time:</b> <code>{formatted_date} {formatted_time}</code></blockquote>\n"
            f"<blockquote><b>🌍 Country:</b> {country_emoji} <code>{country}</code></blockquote>\n"
            f"<blockquote><b>🛠️ Service:</b> <code>{service}</code></blockquote>\n"
            f"<blockquote><b>📞 Number:</b> <code>{masked_number}</code></blockquote>\n"
            f"<blockquote><b>🔑 OTP:</b> <code>{otp}</code></blockquote>\n"
            f"<blockquote><b>📩 Full Message:</b> <code>{full_message}</code></blockquote>\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("Developer", url="https://t.me/AbuBakkarGlobal")],
            [
                InlineKeyboardButton("📱 number channel", url="https://t.me/devearnzone"),
                InlineKeyboardButton("🔔 backup channel", url="https://t.me/smarttipsbd25")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await self.bot.send_message(
                chat_id=GROUP_ID,
                text=message,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
          
            self.db.save_message(timestamp, number, otp, service, country, full_message, True)
            print(f"✅ Sent Telegram message for OTP {otp} at {timestamp}")
            
            
            await asyncio.sleep(MESSAGE_DELAY)
            
        except Exception as e:
            print(f"Failed to send Telegram message: {e}")
            
            self.db.save_message(timestamp, number, otp, service, country, full_message, False)
            
            # If we hit flood control, wait longer
            if "Flood control" in str(e):
                wait_time = 30
                print(f"Flood control detected. Waiting {wait_time} seconds...")
                await asyncio.sleep(wait_time)

    async def send_statistics(self, update=None):
        """Send statistics to user or group"""
        stats = self.db.get_statistics()
        recent_messages = self.db.get_recent_messages(5)
        
        stats_message = (
            f"📊 *OTP Bot Statistics*\n\n"
            f"• Total Messages Processed: `{stats['total_messages']}`\n"
            f"• Unique OTPs Sent: `{stats['unique_otps']}`\n"
            f"• Duplicate OTPs Filtered: `{stats['duplicate_otps']}`\n"
            f"• Unique Phone Numbers: `{stats['unique_numbers']}`\n"
            f"• Unique Services: `{stats['unique_services']}`\n\n"
            f"*Recent OTPs:*\n"
        )
        
        for msg in recent_messages:
            timestamp, number, otp, service, country = msg
            stats_message += f"• `{number[-4:]}` - {service} - `{otp}`\n"
        
        stats_message += f"\n_Database: `{DATABASE_NAME}`_"
        
        if update:
            await update.message.reply_text(stats_message, parse_mode='Markdown')
        else:
            await self.bot.send_message(chat_id=GROUP_ID, text=stats_message, parse_mode='Markdown')

    async def run(self):
        if not await self.test_telegram_connection():
            print("Stopping bot due to Telegram connection failure")
            return
            
        if not self.login():
            print("Initial login failed")
            return
            
        print("Bot started successfully with database storage")
        
        while True:
            try:
                data = self.get_sms_data()
                if data and "aaData" in data and data["aaData"]:
                    new_messages = []
                    for message_data in data["aaData"]:
                        if isinstance(message_data, list) and len(message_data) >= 5:
                            timestamp, range_name, number, service, full_message = message_data[:5]
                            
                            # Skip invalid timestamps
                            if not self.is_valid_timestamp(timestamp):
                                continue
                            
                            # Extract OTP to check for duplicates
                            otp = self.extract_otp(full_message)
                            
                            # Skip if no OTP found
                            if otp == "N/A":
                                continue
                                
                            new_messages.append(message_data)
                    
                    # Process new messages in chronological order
                    if new_messages:
                        print(f"Processing {len(new_messages)} new messages with database duplicate checking...")
                        for message_data in sorted(new_messages, key=lambda x: x[0]):
                            await self.send_telegram_message(message_data)
                    else:
                        print("No new messages found")
                        
                else:
                    print("No valid SMS data received")
                    # Try to re-login if no data received
                    if not self.login():
                        print("Re-login failed")
                        break
                        
            except Exception as e:
                print(f"Error in main loop: {e}")
                if not self.login():
                    print("Re-login failed")
                    break
                    
            await asyncio.sleep(POLL_INTERVAL)

async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    bot = SMSBot()
    
    async def start_command(update, context):
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    async def dashboard_command(update, context):
        await update.message.reply_text(f"SMS Dashboard: {DASHBOARD_URL}")
    
    async def stats_command(update, context):
        await bot.send_statistics(update)
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("dashboard", dashboard_command))
    app.add_handler(CommandHandler("stats", stats_command))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    await bot.run()

if __name__ == '__main__':
    asyncio.run(main())
