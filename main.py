import os
import asyncio
import time
import json
from pyrogram import Client, filters
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, FloodWait

# ---------------- إعدادات API ----------------
API_ID = 34792538
API_HASH = "17823293064e1721661b01d486e91baa"
BOT_TOKEN = "8627786932:AAEJxYVGHpYW3ALZ3JT2Libfr0bdr6kDpw8"

# ---------------- ملفات السيشن ----------------
SESSIONS_FILE = "sessions.json"

# تحميل السيشن من ملف
if os.path.exists(SESSIONS_FILE):
    with open(SESSIONS_FILE, "r") as f:
        saved_sessions = json.load(f)
else:
    saved_sessions = {}

# ---------------- البوت ----------------
bot = Client(
    "ControlBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    sleep_threshold=60
)

# ---------------- متغيرات العمل ----------------
user_sessions = {}       # مؤقت لكل مستخدم أثناء تسجيل الدخول
active_searches = {}     # لإيقاف البحث عند الحاجة

# ================= دالة Progress Bar =================
async def progress(current, total, message, start_time, action):
    now = time.time()
    diff = now - start_time
    if diff < 1: diff = 1
    percentage = current * 100 / total
    speed = current / diff
    time_left = (total - current) / speed if speed > 0 else 0
    bar = "●" * int(percentage/10) + "○" * (10 - int(percentage/10))
    txt = (
        f"{action}...\n"
        f"[{bar}] {percentage:.2f}%\n"
        f"المنجز: {current}/{total}\n"
        f"السرعة: {speed:.2f} ملف/ث\n"
        f"الوقت المتبقي: {time_left:.2f} ث"
    )
    await message.edit_text(txt)

# ================= أوامر البداية =================
@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    chat_id = str(message.chat.id)

    # إذا السيشن موجود مسبقًا، نستخدمه مباشرة
    if chat_id in saved_sessions:
        try:
            app = Client(
                name=f"user_{chat_id}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=saved_sessions[chat_id],
                in_memory=True,
                sleep_threshold=60
            )
            await app.connect()
            user_sessions[chat_id] = {"authorized": True, "user": app}
            await message.reply_text(
                "✅ تم استدعاء السيشن من الملف!\n"
                "الآن أرسل اسم أي ملف للبحث عنه."
            )
            return
        except Exception as e:
            await message.reply_text(
                f"⚠️ تعذر استخدام السيشن القديم، يرجى إعادة تسجيل الدخول.\n{e}"
            )

    await message.reply_text(
        "👋 أهلاً بك\n"
        "📱 أرسل رقمك مع رمز الدولة (مثال: +9677XXXXXXX) لتسجيل الدخول."
    )

# ================= التعامل مع الرسائل =================
@bot.on_message(filters.text & filters.private)
async def handle_logic(client, message):
    chat_id = str(message.chat.id)
    text = message.text.strip()

    # --------- المرحلة 1: رقم الهاتف ---------
    if text.startswith("+") and chat_id not in user_sessions:
        app = Client(
            name=f"user_{chat_id}",
            api_id=API_ID,
            api_hash=API_HASH,
            in_memory=True,
            sleep_threshold=60
        )
        await app.connect()
        try:
            sent = await app.send_code(text)
            user_sessions[chat_id] = {
                "client": app,
                "phone": text,
                "hash": sent.phone_code_hash
            }
            await message.reply_text("📩 تم إرسال كود التحقق، أرسله هنا الآن:")
        except Exception as e:
            await message.reply_text(f"❌ خطأ: {e}")
        return

    # --------- المرحلة 2: كود التحقق ---------
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

            # حفظ السيشن في الملف
            saved_sessions[chat_id] = session_str
            with open(SESSIONS_FILE, "w") as f:
                json.dump(saved_sessions, f)

            await message.reply_text(
                "✅ تم تسجيل الدخول بنجاح!\n"
                "الآن أرسل اسم أي ملف للبحث عنه."
            )
        except SessionPasswordNeeded:
            user_sessions[chat_id]["need_password"] = True
            await message.reply_text("🔐 الحساب عليه كلمة مرور، أرسلها الآن:")
        except PhoneCodeInvalid:
            await message.reply_text("❌ الكود غير صحيح.")
        except Exception as e:
            await message.reply_text(f"❌ خطأ: {e}")
        return

    # --------- المرحلة 3: كلمة المرور ---------
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

            await message.reply_text("✅ تم تسجيل الدخول بالكلمة السرية بنجاح، أرسل اسم الملف للبحث الآن.")
        except Exception as e:
            await message.reply_text(f"❌ كلمة المرور خطأ: {e}")
        return

    # --------- المرحلة 4: البحث الشامل ---------
    if chat_id in user_sessions and user_sessions[chat_id].get("authorized"):
        query = text
        user_app = user_sessions[chat_id]["user"]

        waiting_msg = await message.reply_text(f"🔍 جاري البحث عن: {query}\n📊 تحديث النتائج لحظيًا")

        active_searches[chat_id] = True
        count = 0

        try:
            async for msg in user_app.search_global(query, limit=500):
                if not active_searches.get(chat_id):
                    await waiting_msg.edit_text("⏹ تم إيقاف البحث.")
                    break

                if not (msg.document or msg.video or msg.audio or msg.photo or msg.animation or msg.voice):
                    continue

                count += 1
                link = msg.link or f"https://t.me/c/{str(msg.chat.id)[4:]}/{msg.id}"

                file_msg = await message.reply_text(f"📂 جاري إرسال الملف رقم {count}...")
                start_time = time.time()
                try:
                    await msg.copy(
                        chat_id=message.chat.id,
                        caption=f"📁 نتيجة {count}\n🔗 رابط الملف:\n{link}\nتم البحث بواسطة بوت هيثم الجمال",
                        progress=progress,
                        progress_args=(file_msg, start_time, "يتم النقل")
                    )
                    await file_msg.delete()
                except Exception:
                    await file_msg.edit_text(f"⚠️ تم العثور على ملف لكنه محمي\n🔗 {link}")

                await waiting_msg.edit_text(f"🔍 جاري البحث عن: {query}\n📊 عدد الملفات حتى الآن: {count}")

        except Exception as e:
            await waiting_msg.edit_text(f"❌ خطأ أثناء البحث: {e}")

        if count == 0:
            await waiting_msg.edit_text("❌ لم يتم العثور على أي ملفات")
        else:
            await waiting_msg.edit_text(f"✅ انتهى البحث\nعدد الملفات: {count}")

# --------- إيقاف البحث ---------
@bot.on_message(filters.command("stop") & filters.private)
async def stop_search(client, message):
    chat_id = str(message.chat.id)
    if chat_id in active_searches:
        active_searches[chat_id] = False
        await message.reply_text("⏹ تم إيقاف البحث مؤقتًا.")
    else:
        await message.reply_text("⚠️ لا يوجد بحث جاري.")

# ================= تشغيل البوت =================
print("🚀 البوت يعمل الآن...")
bot.run()