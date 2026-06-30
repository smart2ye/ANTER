#!/data/data/com.termux/files/usr/bin/bash
echo "🚀 تشغيل تطبيق ANTER على Flask..."
cd "$(dirname "$0")"
if [ ! -d "venv" ]; then
    echo "📦 إنشاء البيئة الافتراضية..."
    python -m venv venv
fi
source venv/bin/activate
echo "📥 تثبيت المتطلبات..."
pip install -r requirements.txt
echo "🌐 تشغيل الخادم على http://localhost:5000"
python run.py
