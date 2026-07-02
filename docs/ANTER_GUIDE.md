# 📘 ANTER – الدليل التعريفي الشامل (مع أوامر Termux)

---

## 🌐 **ما هي ANTER؟**

**ANTER** هي منصة تواصل اجتماعي عربية حديثة، صُممت لتكون بديلاً عصرياً وآمناً للشبكات الاجتماعية التقليدية. تجمع المنصة بين البساطة والقوة، مع تركيز خاص على الخصوصية، الأداء، وتجربة المستخدم العربية (RTL). تم تطوير ANTER باستخدام **Flask** (Python) وقاعدة بيانات **SQLite**، وهي مصممة للعمل على الهواتف المحمولة عبر **Termux**.

---

## 🚀 **الميزات الأساسية**

| الميزة | الوصف |
|--------|-------|
| **نظام مستخدمين** | تسجيل، دخول، ملف شخصي، توثيق (علامة زرقاء)، إعدادات خصوصية، سجل نشاط. |
| **منشورات وتفاعلات** | إنشاء، تعديل، حذف، إعجابات (👍🥰🤣😡😢)، تعليقات متداخلة. |
| **رسائل خاصة** | محادثات فورية مع إشعارات وحالة قراءة. |
| **متابعة** | نظام متابعة وإلغاء متابعة مع اقتراحات ذكية. |
| **إشعارات فورية** | تحديث لحظي عبر Server-Sent Events (SSE). |
| **فيديوهات وريلزات** | رفع ومشاهدة فيديوهات قصيرة مع صور مصغرة تلقائية. |
| **لوحة تحكم إدارية** | مسار سري، إدارة المستخدمين، المنشورات، البلاغات. |
| **تصميم متجاوب** | واجهة عربية (RTL) تعمل على الجوال والكمبيوتر. |
| **الوضع الليلي** | تجربة مريحة للعينين. |
| **خوارزميات ذكية** | ترتيب المنشورات حسب التفاعل، اقتراح المستخدمين. |
| **تحسين SEO** | Meta Tags، Sitemap، Robots.txt. |
| **PWA** | دعم تطبيق ويب تقدمي (Manifest، Service Worker، Offline). |

---

## 🛠️ **التقنيات المستخدمة**

| الطبقة | التقنية |
|--------|---------|
| **الخلفية** | Flask (Python) + SQLAlchemy ORM |
| **قاعدة البيانات** | SQLite (محلياً) / PostgreSQL (Supabase) |
| **المصادقة** | Flask-Login + Werkzeug |
| **النماذج** | WTForms + CSRF |
| **الواجهة** | Bootstrap 5 (RTL) + CSS مخصص |
| **الأيقونات** | Font Awesome 6 |
| **الخطوط** | Google Fonts (Cairo, Tajawal) |
| **التفاعل** | JavaScript (AJAX) |
| **الإشعارات** | Server-Sent Events (SSE) |
| **رفع الصور** | Pillow |
| **الفيديو** | ffmpeg (لإنشاء الصور المصغرة) |
| **النشر** | Render (سحابي مجاني) |

---

## 📦 **متطلبات التشغيل**

- **Python 3.8+** (يفضل 3.10 أو أحدث)
- **pip** (مدير حزم Python)
- **Git** (للاستنساخ)
- **Termux** (على Android)
- **اتصال بالإنترنت** (لتحميل المكتبات وللخادم العام)

---

## 🔧 **أوامر التثبيت والتشغيل (Termux)**

انسخ الأوامر التالية والصقها في Termux بالترتيب:

```bash
# 1. تحديث الحزم الأساسية
pkg update && pkg upgrade -y

# 2. تثبيت الأدوات اللازمة
pkg install git python python-pip -y

# 3. استنساخ المشروع من GitHub
git clone https://github.com/smart2ye/ANTER.git
cd ANTER

# 4. إنشاء بيئة افتراضية وتفعيلها
python -m venv venv
source venv/bin/activate

# 5. تثبيت المتطلبات
pip install -r requirements.txt

# 6. (اختياري) إذا واجهت مشكلة في Pillow، استخدم هذا الأمر
pip install Pillow --only-binary :all:

# 7. تشغيل التطبيق
python run.py
```

افتح المتصفح على http://localhost:5050 (لاحظ المنفذ 5050).

---

📂 هيكل المشروع الأساسي

```
ANTER/
├── app/                     # كود التطبيق الرئيسي
│   ├── models/              # نماذج قاعدة البيانات
│   ├── routes/              # مسارات Flask
│   ├── templates/           # قوالب HTML (Jinja2)
│   ├── static/              # ملفات ثابتة (CSS, JS, صور)
│   └── utils/               # دوال مساعدة
├── instance/                # قاعدة البيانات المحلية (SQLite)
├── docs/                    # الوثائق (هذا الملف)
├── requirements.txt         # المكتبات المطلوبة
├── run.py                   # نقطة الدخول للتشغيل
└── README.md                # دليل سريع
```

---

🌐 أوامر النشر على Render (مجاناً)

```bash
# 1. بعد رفع الكود إلى GitHub، افتح Render.com
# 2. أنشئ Web Service جديد واربطه بالمستودع
# 3. استخدم الإعدادات التالية:
#    - Build Command: pip install -r requirements.txt
#    - Start Command: gunicorn run:app
# 4. أضف متغيرات البيئة (مثل DATABASE_URL إن وجد)
# 5. اضغط "Create Web Service"
```

---

📤 أوامر رفع التعديلات إلى GitHub

```bash
# 1. إضافة جميع التغييرات
git add .

# 2. إنشاء Commit مع وصف
git commit -m "وصف التغييرات التي أجريتها"

# 3. رفع إلى GitHub
git push origin main
```

ملاحظة: إذا طلب كلمة مرور، استخدم Token وليس كلمة مرور الحساب العادية.

---

🧪 أوامر فحص قاعدة البيانات

```bash
# عرض جميع المستخدمين
sqlite3 instance/anter.db "SELECT id, username, name, email FROM users;"

# عرض جميع المنشورات
sqlite3 instance/anter.db "SELECT id, content, author_id, created_at FROM posts ORDER BY created_at DESC;"

# عرض عدد المتابعين لكل مستخدم
sqlite3 instance/anter.db "SELECT username, (SELECT COUNT(*) FROM follows WHERE followed_id = users.id) AS followers FROM users ORDER BY followers DESC;"
```

---

🔑 تغيير كلمة مرور مستخدم (عبر SQLite)

```bash
python3 -c "
from werkzeug.security import generate_password_hash
import sqlite3

username = 'manus_ai'          # غيّر اسم المستخدم حسب الحاجة
new_password = 'Manus@2026'    # غيّر كلمة المرور

hashed = generate_password_hash(new_password)
conn = sqlite3.connect('instance/anter.db')
conn.execute('UPDATE users SET password_hash = ? WHERE username = ?', (hashed, username))
conn.commit()
conn.close()
print(f'✅ تم تغيير كلمة المرور للمستخدم {username} إلى: {new_password}')
"
```

---

🛠️ إضافة مسار API لعرض المستخدمين (للمشرفين)

أضف هذا الكود في app/routes/main.py:

```python
@main_bp.route('/api/users')
@login_required
def api_users():
    if not current_user.is_admin:
        return jsonify({'error': 'غير مصرح'}), 403
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'name': u.name,
        'email': u.email,
        'created_at': u.created_at.isoformat() if u.created_at else None,
        'is_verified': u.is_verified,
        'is_admin': u.is_admin
    } for u in users])
```

ثم اختبره عبر:

```
https://anter-1.onrender.com/api/users
```

---

🎯 الخاتمة

ANTER هي منصة متكاملة تجمع بين قوة Flask، بساطة SQLite، ومرونة الواجهات العربية. سواء كنت مطوراً تبحث عن مشروع مفتوح المصدر، أو صاحب فكرة تريد بناء شبكة اجتماعية عربية، فإن ANTER توفر لك أساساً قوياً وقابلاً للتوسع.

روابط مفيدة:

· المنصة الحية: https://anter-1.onrender.com
· المستودع: https://github.com/smart2ye/ANTER

---

شكراً لاستخدامك ANTER! 🌟
نبني معاً مستقبل التواصل الاجتماعي العربي. 🚀💙

آخر تحديث: 2 يوليو 2026
