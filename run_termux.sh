#!/data/data/com.termux/files/usr/bin/bash
echo "🚀 تشغيل تطبيق ANTER على Flask..."
cd "$(dirname "$0")"
if [ ! -d "venv-termux" ]; then
    echo "📦 إنشاء البيئة الافتراضية..."
    python -m venv venv-termux
fi
source venv-termux/bin/activate
echo "📥 تثبيت المتطلبات..."
pip install -r requirements.txt
echo "🌐 تشغيل الخادم على http://localhost:5000"
python run.py
