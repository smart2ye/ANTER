# ANTER — المرجع الشامل

**آخر تحديث:** 2026-09-17
**الإصدار:** 1.0.1

## نظرة عامة
منصة تواصل اجتماعي عربية مبنية على Flask + SQLAlchemy + Jinja2.

- Backend: Python 3.14.6 + Flask 2.3.3
- Database: PostgreSQL (Aiven) للإنتاج + SQLite للتطوير
- Frontend: Vanilla JS + Bootstrap 5
- Hosting: Render (Free Tier)

## الأحجام
- المشروع: 118 MB
- 108 ملف Python
- 47 قالب HTML
- 5 ملفات JS
- 31 موديل
- 19 blueprint (156 سطر route)

## البنية
app/
  __init__.py          create_app + load_user
  config.py            الإعدادات
  extensions.py        db, csrf, login_manager
  forms/               نماذج WTForms
  models/              31 موديل
  routes/              19 blueprint
  services/            18 خدمة
  templates/           47 قالب
  static/              css, js, icons, uploads
  utils/               أدوات مساعدة
docs/reference/        هذا المرجع
scripts/               سكربتات (sync, migrate)
tests/                 12 ملف اختبار
instance/anter.db      SQLite محلي

## الروابط
- الإنتاج: https://anter-1.onrender.com
- GitHub: https://github.com/smart2ye/ANTER
- APK: https://github.com/smart2ye/anter-webview-apk/releases/download/v1.0.1/ANTER.apk
- Aiven DB: anter-anter.h.aivencloud.com:28630

## التشغيل المحلي
cd ~/ANTER
source venv-termux/bin/activate
unset DATABASE_URL
PORT=5051 python3 run.py

## Stack
- Flask 2.3.3
- SQLAlchemy 2.0 + Flask-SQLAlchemy 3.1.1
- Flask-Login 0.6.2 + Werkzeug
- Flask-WTF 1.1.1 + WTForms 3.0.1
- PostgreSQL 18.6 (Aiven)
- WebRTC: Metered TURN + Google STUN
- AI: Groq qwen/qwen3.8-27b
- Push: pywebpush + VAPID
- Email: Resend

## المراجع التفصيلية
- routes.md
- models.md
- services.md
- templates.md
- integrations.md
