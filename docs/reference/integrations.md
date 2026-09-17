# مرجع التكاملات الخارجية

**آخر تحديث:** 2026-09-17

## قواعد البيانات

### Aiven (الإنتاج)
- Host: anter-anter.h.aivencloud.com
- Port: 28630
- DB: defaultdb
- User: avnadmin
- Region: AWS Bahrain (me-south-1)
- الخطة: Free (5 GB)

### SQLite (التطوير المحلي)
- Path: instance/anter.db
- الحجم: ~9 MB
- يُستخدم عند عدم وجود DATABASE_URL

### Supabase (قديم — موقوف)
- مشروع: gjuptzntlwdcqxzvvpnp
- الحالة: موقوف (quota)
- للاستخدام الطارئ: فك التعليق في .env

## AI

### Groq (mini-llm Arabic)
- النموذج: qwen/qwen3.8-27b
- URL: https://api.groq.com/openai/v1/chat/completions
- المتغيرات: GROQ_API_KEY, GROQ_MODEL, MINI_LLM_ARABIC_*

## WebRTC

### STUN
- stun:stun.l.google.com:19302

### TURN (Metered.ca)
- URLs:
  - turn:global.relay.metered.ca:80
  - turn:global.relay.metered.ca:80?transport=tcp
  - turn:global.relay.metered.ca:443
  - turns:global.relay.metered.ca:443?transport=tcp
- الخطة: Free 20GB/شهر
- المتغيرات: WEBRTC_TURN_URLS, WEBRTC_TURN_USERNAME, WEBRTC_TURN_CREDENTIAL

## Email
- Resend API
- المتغير: RESEND_API_KEY

## Push Notifications
- Web Push (VAPID)
- المكتبة: pywebpush
- المتغيرات: VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY

## Hosting
- Render
- الخدمة: ANTER-1
- URL: https://anter-1.onrender.com
- الخطة: Free (ينام بعد 15 دقيقة)
- Health Check: /health

## GitHub
- smart2ye/ANTER — المنصة
- smart2ye/anter-webview-apk — APK
- smart2ye/plus-messenger-android — تطبيق المراسلة
- smart2ye/anter-twa — تجربة TWA (مهجورة)

### Releases
- APK الأخير: v1.0.1
- الرابط: https://github.com/smart2ye/anter-webview-apk/releases/download/v1.0.1/ANTER.apk

## متغيرات البيئة الكاملة
- SECRET_KEY — Flask sessions
- DATABASE_URL — اتصال القاعدة
- GROQ_API_KEY — mini-llm
- GROQ_MODEL — نموذج AI
- MINI_LLM_ARABIC_* — إعدادات AI
- WEBRTC_STUN_URL — STUN
- WEBRTC_TURN_* — TURN (3 متغيرات)
- RESEND_API_KEY — بريد
- MAIL_* — SMTP (احتياطي)
- VAPID_* — Push
- UPLOAD_FOLDER — مسار الرفع
- ADMIN_PATH — مسار الأدمن
- ANTER_APK_URL, ANTER_APK_VERSION, ANTER_APK_SIZE, ANTER_APK_DATE — صفحة about
