import os
import asyncio
import re
import time
from flask import Flask
from threading import Thread
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, MessageIdInvalid

# --- إعدادات Flask لتجنب إغلاق السيرفر في Render/HuggingFace ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "البوت يعمل بنجاح! المطور: هيثم محمود الجمال"

def run_flask():
    # Render و Hugging Face يستخدمان منفذ متغير، غالباً 10000 أو 7860
    port = int(os.environ.get("PORT", 7860))
    web_app.run(host="0.0.0.0", port=port)

# --- إعدادات التليجرام (جلب البيانات من Secrets) ---
API_ID = int(os.environ.get("API_ID", "12345"))
API_HASH = os.environ.get("API_HASH", "your_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
SESSION_STRING = os.environ.get("SESSION_STRING")

class DeepSearchBot:
    def __init__(self):
        self.bot = Client("ControlBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
        # حساب المستخدم للبحث الشامل (Global Search)
        self.user = Client("UserSearch", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

    def clean_query(self, query):
        # تنظيف الكلمات الطويلة لزيادة دقة نتائج تليجرام
        words = re.findall(r'\w+', query)
        return " ".join(words[:4]) if len(words) > 4 else query

    async def start_clients(self):
        await self.bot.start()
        print("✅ Bot Client Started")
        if SESSION_STRING:
            await self.user.start()
            print("✅ User Client Started (Global Search Active)")
        else:
            print("⚠️ SESSION_STRING missing! Global search disabled.")

    async def run(self):
        await self.start_clients()

        @self.bot.on_message(filters.command("start") & filters.private)
        async def start_msg(client, message):
            await message.reply_text(
                f"أهلاً بك.. أنا بوت البحث العميق الخاص بالمطور **هيثم محمود الجمال**.\n\n"
                f"🔍 أرسل اسم أي ملف (فيديو، كتاب، تطبيق) وسأبحث عنه في كل قنوات تليجرام العامة."
            )

        @self.bot.on_message(filters.text & filters.private)
        async def search_handler(client, message):
            query = message.text
            search_text = self.clean_query(query)
            waiting = await message.reply_text(f"🔍 جاري البحث العميق عن: **{search_text}**...")
            
            count = 0
            found_ids = set()

            try:
                # محرك البحث الشامل عبر حساب المستخدم
                async for msg in self.user.search_global(search_text, limit=30):
                    if msg.media and msg.id not in found_ids:
                        found_ids.add(msg.id)
                        count += 1
                        
                        # جلب الرابط الأصلي للملف
                        link = msg.link if msg.link else f"https://t.me/c/{str(msg.chat.id)[4:]}/{msg.id}"
                        caption = f"✅ نتيجة رقم {count}\n🔗 الرابط: {link}\n\nالمطور: هيثم الجمال"

                        try:
                            # محاولة إرسال الملف مباشرة
                            await msg.copy(chat_id=message.chat.id, caption=caption)
                        except Exception:
                            # إذا فشل الإرسال (حماية محتوى) نرسل الرابط
                            await message.reply_text(f"⚠️ الملف {count} محمي من النسخ.\n🔗 يمكنك تحميله من الرابط:\n{link}")
                        
                        if count >= 15: break # حد أقصى للنتائج لمنع الحظر

                if count == 0:
                    await waiting.edit_text("❌ لم يتم العثور على نتائج مشابهة. جرب اسماً أبسط.")
                else:
                    await waiting.delete()

            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception as e:
                await waiting.edit_text(f"حدث خطأ أثناء البحث: {str(e)}")

        # إبقاء البوت يعمل
        await asyncio.Event().wait()

if __name__ == "__main__":
    # 1. تشغيل سيرفر الويب في خيط منفصل لتجنب Port Timeout
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    # 2. تشغيل محرك البحث
    bot_engine = DeepSearchBot()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(bot_engine.run())
