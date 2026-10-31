#!/data/data/com.termux/files/usr/bin/bash
# ANTER — تشغيل محلي على SQLite فقط. لا يمس Aiven أبدًا.
cd "$(dirname "$0")" || exit 1
export DATABASE_URL=""
export FLASK_ENV=development
export FLASK_DEBUG=1
pkill -f "python3 run.py" 2>/dev/null
sleep 1
echo "→ SQLite: instance/anter.db"
echo "→ http://127.0.0.1:5050"
exec python3 run.py
