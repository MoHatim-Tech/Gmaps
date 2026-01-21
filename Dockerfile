# استخدام صورة بايثون الرسمية كقاعدة
FROM python:3.10-slim

# منع بايثون من إنشاء ملفات .pyc وتقييد الذاكرة المؤقتة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# إعداد بيئة العمل
WORKDIR /app

# تثبيت تبعيات النظام الضرورية لـ Playwright و Streamlit
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# تثبيت متصفح Chromium وتباعيات النظام الخاصة به
RUN playwright install chromium
RUN playwright install-deps chromium

# نسخ باقي ملفات المشروع
COPY . .

# إنشاء مجلد إعدادات Streamlit
RUN mkdir -p ~/.streamlit/
RUN echo "[server]\nport = 8501\naddress = \"0.0.0.0\"\n\n[theme]\nprimaryColor = \"#2563eb\"\nbackgroundColor = \"#f1f5f9\"\nsecondaryBackgroundColor = \"#ffffff\"\ntextColor = \"#1e3a8a\"\nfont = \"serif\"" > ~/.streamlit/config.toml

# فتح المنفذ الخاص بـ Streamlit
EXPOSE 8501

# أمر التشغيل النهائي
CMD ["streamlit", "run", "app.py"]
