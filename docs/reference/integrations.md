# مرجع التكاملات الخارجية

**آخر تحديث:** 2026-09-27

## قواعد البيانات

### Aiven (الإنتاج)
- Host: anter-anter.h.aivencloud.com
- Port: 28630
- DB: defaultdb
- User: anter_app (صلاحيات محدودة)
- Region: AWS Bahrain (me-south-1)
- الخطة: Free (1 GB)

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
- APK الأخير: v1.0.7 (ANTER_app.apk)
- الرابط: https://github.com/smart2ye/anter-webview-apk/releases/download/v1.0.7/ANTER_app.apk

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

## Rate Limiting (2026-09-27)
في الذاكرة — يعمل مع `--workers=1`:
- `/auth/login`: 10/دقيقة
- `/auth/register`: 5/5 دقائق
- `/auth/reset_password`, `/auth/forgot`: 10/5 دقائق
- `/api/ai/assist`: 20/دقيقة
- `/users/find-friends`: 5/دقيقة
- `/messages/send`: 60/دقيقة

## Security Headers (2026-09-27)
تُضاف على كل الردود:
- X-Frame-Options: SAMEORIGIN
- X-Content-Type-Options: nosniff
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: geolocation=(), microphone=(self), camera=(self), payment=()
- Strict-Transport-Security: max-age=31536000
- Content-Security-Policy: default-src 'self' + inline scripts/media

## Cloudflare Tunnel (للتطوير)
- الأمر: `cloudflared tunnel --protocol http2 --edge-ip-version 4 --url http://127.0.0.1:5050`
- تجربة أسرع بكثير من Render Free (بلا cold start)
