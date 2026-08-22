from werkzeug.security import generate_password_hash
import sqlite3
import getpass

# طلب اسم المستخدم
username = input("👤 أدخل اسم المستخدم: ").strip()

# طلب كلمة المرور الجديدة (مع إخفاء النص)
password = getpass.getpass("🔑 أدخل كلمة المرور الجديدة: ")
confirm = getpass.getpass("🔄 أعد إدخال كلمة المرور: ")

if password != confirm:
    print("❌ كلمة المرور غير متطابقة!")
    exit(1)

# توليد الهاش
hashed = generate_password_hash(password)

# الاتصال بقاعدة البيانات وتحديثها
conn = sqlite3.connect('instance/anter.db')
cursor = conn.cursor()

cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hashed, username))

if cursor.rowcount == 0:
    print(f"❌ المستخدم '{username}' غير موجود!")
else:
    conn.commit()
    print(f"✅ تم تحديث كلمة المرور للمستخدم '{username}' بنجاح!")

conn.close()
