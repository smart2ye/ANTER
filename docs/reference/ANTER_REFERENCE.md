# ANTER — المرجع الشامل

**آخر تحديث:** 2026-11-02

## نظرة عامة
منصة تواصل اجتماعي عربية مبنية على Flask + SQLAlchemy + Jinja2.

- Backend: Python 3.14 + Flask 3.1.3
- Database: PostgreSQL (Aiven) للإنتاج + SQLite للتطوير
- Frontend: Vanilla JS + Bootstrap 5
- Hosting: Render (Free Tier)

## الأحجام
- المشروع: 340 MB (مع .git و venv)
- 102 ملف Python (داخل app/)
- 67 قالب HTML
- 3 ملفات JS (+ vendor)
- 3 ملفات CSS (+ vendor)
- 43 موديل
- 20 blueprint (246 route)
- 26 خدمة

## البنية
app/
  __init__.py          create_app + load_user + قبل الطلب
  config.py            الإعدادات
  extensions.py        db, csrf, login_manager
  forms/               نماذج WTForms
  models/              43 موديل
  routes/              20 blueprint
  services/            25 خدمة
  templates/           67 قالب
  static/              css, js, icons, uploads
  utils/               أدوات مساعدة
docs/reference/        هذا المرجع
scripts/               سكربتات صيانة
tests/                 12 ملف اختبار
instance/anter.db      SQLite محلي (10 MB)

## الأنظمة الرئيسية
- منشورات · ريلز · قصص · رسائل · مكالمات WebRTC
- سوق حراج (156 مدينة سعودية + 230 يمنية)
- مساعد ذكي (Groq qwen/qwen3.8-27b)
- نظام إحالة (referral_code + 5 إحالات = توثيق)
- مسار التوثيق (7 مهام → توثيق تلقائي)
- اقتباس منشور (quoted_post_id)
- شريط إعلان ديناميكي (site_settings)

## الروابط
- الإنتاج: https://anter-1.onrender.com
- GitHub: https://github.com/smart2ye/ANTER
- APK: https://github.com/smart2ye/anter-webview-apk/releases/latest/download/ANTER_app.apk (v1.0.18)
- Aiven DB: anter-anter.h.aivencloud.com:28630

## التشغيل المحلي
cd ~/ANTER
source venv-termux/bin/activate
unset DATABASE_URL
PORT=5050 python3 run.py

أو استخدم:
./run_local.sh   (يفرض SQLite دائمًا)

## Stack
- Flask 3.1.3 + SQLAlchemy 2.0 + Flask-SQLAlchemy 3.1.1
- Flask-Login + Werkzeug 3.1.8
- Flask-WTF + WTForms
- PostgreSQL (Aiven Free)
- WebRTC: Metered TURN + Google STUN
- AI: Groq qwen/qwen3.8-27b
- Push: pywebpush + VAPID
- Email: SMTP Gmail + Resend (غير مفعّل)

## المراجع التفصيلية
- routes.md · models.md · services.md · templates.md
- integrations.md · identity.md · soft-delete.md
- INVENTORY.md (جرد شامل)
