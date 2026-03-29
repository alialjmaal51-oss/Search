# استخدام نسخة بايثون مستقرة وخفيفة
FROM python:3.9-slim

# تحديث النظام وتثبيت بعض الأدوات الأساسية (اختياري لزيادة الاستقرار)
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# تحديد مجلد العمل داخل السيرفر
WORKDIR /app

# نسخ ملف المكتبات أولاً لتسريع عملية البناء (Caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ بقية ملفات الكود (main.py وأي ملفات أخرى)
COPY . .

# أمر تشغيل البوت عند بدء تشغيل الـ Space
CMD ["python", "main.py"]
