import os
import asyncio
import time
import json
from pyrogram import Client, filters
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid

# ---------------- إعدادات API من المتغيرات البيئية ----------------
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise Exception("⚠️ يرجى تعيين API_ID و API_HASH و BOT_TOKEN في Secrets أو Environment Variables")

# ---------------- ملفات السيشن ----------------
SESSIONS_FILE = "sessions.json"
if os.path.exists(SESSIONS_FILE):
    with open(SESSIONS_FILE, "r") as f:
        saved_sessions = json.load(f)
else:
    saved_sessions = {}

# ---------------- متغيرات العمل ----------------
user_sessions = {}       # لكل مستخدم أثناء تسجيل الدخول
active_searches = {}     # للتحكم في البحث

# ================= دالة Progress =================
async def progress(current, total, start_time, action="جاري النقل"):
    now = time.time()
    diff = max(now - start_time, 1)
    percentage = current * 100 / total
    speed = current / diff
    time_left = (total - current) / speed if speed > 0 else 0
    bar = "●" * int(percentage / 10) + "○" * (10 - int(percentage / 10))
    print(f"{action} [{bar}] {percentage:.2f}% | {current}/{total} | سرعة: {speed:.2f} ملف/ث | متبقي: {time_left:.2f}s")

# ================= البوت =================
bot = Client(
    "ControlBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    sleep_threshold=60
)

# ================= START =================
@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    chat_id = str(message.chat.id)
    # إذا السيشن موجود مسبقًا
    if chat_id in saved_sessions:
        try:
            app = Client(
                name=f"user_{chat_id}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=saved_sessions[chat_id],
                in_memory=True
            )
            await app.connect()
            user_sessions[chat_id] = {"authorized": True, "user": app}
            await message.reply("✅ تم استدعاء السيشن من الملف! أرسل اسم أي ملف للبحث عنه.")
            return
        except Exception as e:
            await message.reply(f"⚠️ تعذر استخدام السيشن القديم، يرجى إعادة تسجيل الدخول.\n{e}")
    await message.reply("👋 أهلاً بك\n📱 أرسل رقم هاتفك مع رمز الدولة (مثال: +9677XXXXXXX) لتسجيل الدخول.")

# ================= الرسائل =================
@bot.on_message(filters.text & filters.private)
async def handle_logic(client, message):
    chat_id = str(message.chat.id)
    text = message.text.strip()

    # -------- المرحلة 1: رقم الهاتف --------
    if text.startswith("+") and chat_id not in user_sessions:
        app = Client(
            name=f"user_{chat_id}",
            api_id=API_ID,
            api_hash=API_HASH,
            in_memory=True
        )
        await app.connect()
        try:
            sent = await app.send_code(text)
            user_sessions[chat_id] = {"client": app, "phone": text, "hash": sent.phone_code_hash}
            await message.reply("📩 تم إرسال كود التحقق، أرسله هنا الآن:")
        except Exception as e:
            await message.reply(f"❌ خطأ: {e}")
        return

    # -------- المرحلة 2: كود التحقق --------
    if chat_id in user_sessions and "hash" in user_sessions[chat_id] and "authorized" not in user_sessions[chat_id]:
        app = user_sessions[chat_id]["client"]
        try:
            await app.sign_in(
                phone_number=user_sessions[chat_id]["phone"],
                phone_code_hash=user_sessions[chat_id]["hash"],
                phone_code=text
            )
            session_str = await app.export_session_string()
            user_sessions[chat_id]["authorized"] = True
            user_sessions[chat_id]["user"] = app

            # حفظ السيشن
            saved_sessions[chat_id] = session_str
            with open(SESSIONS_FILE, "w") as f:
                json.dump(saved_sessions, f)

            await message.reply("✅ تم تسجيل الدخول بنجاح! الآن أرسل اسم أي ملف للبحث عنه.")
        except SessionPasswordNeeded:
            user_sessions[chat_id]["need_password"] = True
            await message.reply("🔐 الحساب عليه كلمة مرور، أرسلها الآن:")
        except PhoneCodeInvalid:
            await message.reply("❌ الكود غير صحيح.")
        except Exception as e:
            await message.reply(f"❌ خطأ: {e}")
        return

    # -------- المرحلة 3: كلمة المرور --------
    if chat_id in user_sessions and user_sessions[chat_id].get("need_password"):
        app = user_sessions[chat_id]["client"]
        try:
            await app.check_password(text)
            session_str = await app.export_session_string()
            user_sessions[chat_id]["authorized"] = True
            user_sessions[chat_id]["user"] = app

            saved_sessions[chat_id] = session_str
            with open(SESSIONS_FILE, "w") as f:
                json.dump(saved_sessions, f)

            await message.reply("✅ تم تسجيل الدخول بالكلمة السرية! أرسل اسم الملف للبحث الآن.")
        except Exception as e:
            await message.reply(f"❌ كلمة المرور خطأ: {e}")
        return

    # -------- المرحلة 4: البحث الشامل --------
    if chat_id in user_sessions and user_sessions[chat_id].get("authorized"):
        query = text
        user_app = user_sessions[chat_id]["user"]
        await message.reply(f"🔍 جاري البحث عن: {query} | 📊 تحديث النتائج لحظيًا")
        active_searches[chat_id] = True
        count = 0
        try:
            async for msg in user_app.search_global(query, limit=500):
                if not active_searches.get(chat_id):
                    print("⏹ تم إيقاف البحث.")
                    break
                if not (msg.document or msg.video or msg.audio or msg.photo or msg.animation or msg.voice):
                    continue
                count += 1
                link = msg.link or f"https://t.me/c/{str(msg.chat.id)[4:]}/{msg.id}"
                await msg.copy(chat_id=message.chat.id, caption=f"📁 نتيجة {count}\n🔗 {link}")
                await progress(count, 500, time.time(), action=f"البحث عن {query}")
            await message.reply(f"✅ انتهى البحث | عدد الملفات: {count}")
        except Exception as e:
            await message.reply(f"❌ خطأ أثناء البحث: {e}")

# --------- إيقاف البحث ---------
@bot.on_message(filters.command("stop") & filters.private)
async def stop_search(client, message):
    chat_id = str(message.chat.id)
    if chat_id in active_searches:
        active_searches[chat_id] = False
        await message.reply("⏹ تم إيقاف البحث مؤقتًا.")
    else:
        await message.reply("⚠️ لا يوجد بحث جاري.")

# ================= تشغيل البوت =================
async def main():
    print("🚀 البوت يعمل الآن على Hugging Face مع استخدام Secrets...")
    await bot.start()
    await asyncio.Event().wait()  # يبقي البوت يعمل في الخلفية

asyncio.run(main())
