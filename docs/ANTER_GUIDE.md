# 📘 ANTER — الدليل الشامل (Termux + Render + Aiven)

**آخر تحديث:** 2026-11-01
**الإنتاج:** https://anter-1.onrender.com
**المستودع:** https://github.com/smart2ye/ANTER

---

## 🌐 ما هي ANTER؟

**ANTER** منصة تواصل اجتماعي عربية حديثة، صُممت لتكون بديلًا عربيًا حقيقيًا للشبكات الاجتماعية التقليدية. تجمع بين البساطة، الخصوصية، والأداء، بواجهة عربية (RTL) كاملة.

- **Backend:** Python 3.14 + Flask 3.1.3 + SQLAlchemy 2.0
- **قاعدة البيانات:** PostgreSQL (Aiven، البحرين) للإنتاج · SQLite للتطوير
- **الاستضافة:** Render Free (Oregon)
- **التطوير:** Termux على Android — بلا كمبيوتر

---

## 🚀 الميزات الأساسية

| الميزة | الوصف |
|--------|-------|
| **حسابات** | تسجيل، دخول، ملف شخصي، إعدادات خصوصية، سجل نشاط |
| **منشورات** | إنشاء، تعديل، حذف، صور، اقتباس منشور، جمهور (عام/متابعون/خاص) |
| **تفاعلات** | إعجابات متعددة (👍🥰🤣😡😢)، تعليقات وردود متداخلة |
| **ريلز وقصص** | رفع فيديو مع صورة مصغرة، قصص 24 ساعة |
| **رسائل** | محادثات فورية، تسجيل صوتي، مرفقات، مكالمات WebRTC |
| **حراج** | سوق بيع/شراء (156 مدينة سعودية + 230 يمنية)، تقييم بائع |
| **مساعد أنتر** | مساعد ذكي عربي (Groq qwen/qwen3.8-27b) مدمج في المنصة |
| **إشعارات** | 27+ نوع، فورية عبر SSE + polling كل 3 ثوانٍ |
| **توثيق** | مسار 7 مهام + إحالة (5 أصدقاء) + مراجعة يدوية → علامة زرقاء |
| **إحالة** | كود فريد لكل مستخدم، 5 إحالات مؤكدة = توثيق تلقائي |
| **عقوبات** | تصعيد تلقائي (تحذير → تعليق 24س → 7أ → إشعار مؤسس) |
| **إدارة** | لوحة تحكم، بلاغات، استعادة حسابات محذوفة، شريط إعلان ديناميكي |
| **PWA** | Manifest + Service Worker + تثبيت مفتوح (cache فقط) |

---

## 🛠️ التقنيات

| الطبقة | التقنية |
|--------|---------|
| Backend | Flask 3.1.3 + SQLAlchemy 2.0 + Flask-SQLAlchemy 3.1.1 |
| المصادقة | Flask-Login + Werkzeug 3.1.8 (scrypt) |
| النماذج | WTForms + Flask-WTF + CSRF |
| الواجهة | Bootstrap 5 RTL + CSS مخصص (3 ملفات) |
| الأيقونات | Font Awesome 6 (subset — 213 أيقونة) |
| الخط | Cairo (محلي — vendor/cairo) |
| التفاعل | Vanilla JS + AJAX (3 ملفات) |
| الإشعارات | SSE + polling (كل 3s) |
| الصور | Pillow (تحويل WebP، 1600px) |
| الفيديو | ffmpeg (صور مصغرة) |
| AI | Groq qwen/qwen3.8-27b |
| Push | pywebpush + VAPID |
| البريد | SMTP Gmail + Resend (غير مفعّل) |
| APK | WebView APK (v1.0.18) — AnterShare + AnterDownload |


---

## 📦 متطلبات التشغيل

- **Python 3.14** (المشروع يعمل على 3.14 — لا 3.8)
- **Termux** على Android
- **Git**
- اتصال إنترنت

---

## 🔧 التثبيت (Termux)

```bash
pkg update && pkg upgrade -y
pkg install git python python-pip -y
git clone https://github.com/smart2ye/ANTER.git
cd ANTER
python -m venv venv-termux
source venv-termux/bin/activate
pip install -r requirements.txt
```

---

💻 التشغيل المحلي

الآمن (SQLite إجباريًا — لا يمس Aiven)

```bash
./run_local.sh
```

اليدوي

```bash
source venv-termux/bin/activate
unset DATABASE_URL
PORT=5050 python3 run.py
```

⚠️ لا تشغّل python3 run.py مباشرة بلا unset DATABASE_URL — يتصل بـ Aiven الإنتاجي.

الخلفية والإيقاف

```bash
nohup ./run_local.sh > ~/anter.log 2>&1 &
tail -f ~/anter.log
pkill -f "python3 run.py"
```

---

🌐 النشر على Render

النشر تلقائي عبر GitHub → Render. ارفع إلى main، Render يبني وينشر.

Procfile

```
web: gunicorn --bind 0.0.0.0:$PORT run:app --workers=1 --threads=2 --worker-class=gthread --timeout=120 --max-requests=1000 --max-requests-jitter=100
```

مهم: Start Command في Render Dashboard يجب أن يكون فارغًا — Procfile يُقرأ تلقائيًا.

متغيرات البيئة (Render)

SECRET_KEY · DATABASE_URL · GROQ_API_KEY · GROQ_MODEL · MAIL_* · WEBRTC_TURN_* · ANTER_ASSISTANT_* · ANTER_APK_*

---

## 📂 البنية

```

ANTER/
├── app/
│   ├── models/          # 42 موديل
│   ├── routes/          # 20 blueprint (245 route)
│   ├── services/        # 25 خدمة
│   ├── templates/       # 67 قالب
│   ├── static/          # css, js, img, uploads
│   ├── forms/           # WTForms
│   └── utils/           # أدوات مساعدة
├── instance/anter.db    # SQLite محلي (10 MB)
├── docs/                # الوثائق
├── scripts/             # سكربتات صيانة (17)
├── run.py               # نقطة الدخول
├── run_local.sh         # تشغيل محلي (SQLite فقط)
├── Procfile             # أمر التشغيل على Render
└── requirements.txt

```

---

## 🧪 أوامر الفحص

```bash
sqlite3 instance/anter.db "SELECT id, username, name, email FROM users;"
sqlite3 instance/anter.db "SELECT id, content, author_id FROM posts ORDER BY created_at DESC LIMIT 5;"
```

---

🛡️ ملاحظات مهمة

1. python3 run.py بلا unset DATABASE_URL = اتصال بالإنتاج. استخدم ./run_local.sh دائمًا.
2. Aiven Free: كل ALTER في transaction مستقلة · TIMESTAMP NULL غير صالح · 5 GB.
3. Render Free: عامل واحد، 512 MB. Start Command = فارغ.
4. /health يبقى فوريًا.
5. fa-*: افحص في subset قبل الاستخدام.

---

🎯 الخاتمة

ANTER منصة متكاملة: Flask + PostgreSQL + واجهة عربية RTL. تُبنى يوميًا من Termux.

· المنصة: https://anter-1.onrender.com
· المستودع: https://github.com/smart2ye/ANTER
· APK: https://github.com/smart2ye/anter-webview-apk/releases/latest/download/ANTER_app.apk
