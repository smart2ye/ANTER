# ANTER — دليل المشروع

> **ANTER** شبكة اجتماعية عربية تجمع بين التواصل الإنساني والمساعدة الذكية داخل تجربة واحدة، وتُبنى لتكون سهلة الاستخدام على الهاتف، وقريبة من احتياجات المجتمع العربي.

**المؤسس وصاحب الرؤية:** عبدالقادر مهدلي
**المستودع الرسمي:** [smart2ye/ANTER](https://github.com/smart2ye/ANTER)
**المنصة:** [anter-1.onrender.com](https://anter-1.onrender.com/)

---

## ما هو ANTER؟

ANTER منصة اجتماعية عربية RTL تتيح للمستخدم إنشاء ملف شخصي، متابعة الحسابات، مشاركة المنشورات والريلز والقصص، التعليق والرد، تبادل الرسائل والمكالمات الصوتية، ومتابعة الإشعارات — مع مساعد ذكي عربي مدمج باسم **مساعد أنتر**.

| المبدأ | تطبيقه داخل ANTER |
|---|---|
| البساطة | تسجيل مختصر، واجهات عربية RTL، أزرار واضحة، تجربة للهاتف أولًا. |
| الخصوصية | المفاتيح في متغيرات بيئة الخادم فقط. |
| التفاعل | منشورات، تعليقات، ردود، إعجابات، إعادة نشر، إشعارات، متابعة، رسائل. |
| الهوية | Navy / Blue / Cyan / Purple · خط Cairo. |
| التطور التدريجي | ميزة كل يوم — بناء واختبار وتحسين. |

---

## الأرقام التقنية (12 أكتوبر 2026)

| المقياس | العدد |
|---|---|
| Routes | 199 |
| Blueprints | 19 |
| Models | 34 |
| Templates | 49 |
| Services | 20 |

---

## تجربة المستخدم الأساسية

### التسجيل والدخول

الاسم الكامل، الجنس (يحدد الصورة الافتراضية)، ثم رقم جوال أو بريد — يكفي واحد. يُنشَأ معرف عشوائي آمن، ويمكن اختيار اسم مستخدم لاحقًا.

**طرق الدخول:** رقم الجوال · البريد · اسم المستخدم.

### الملف الشخصي

```text
/users/<username>
```

### الخصوصية في الملف

- `profile_visibility`: عام / خاص
- `wall_visibility`: عام / خاص
- `message_privacy`: everyone / followers / nobody
- `show_email`, `show_online_status`, `hide_followers`

---

## ميزات التواصل

### المنشورات

- نصوص + صور (WebP، حد 1600px)
- `defer(Post.image_data)` في feed للأداء

### التعليقات والردود

- إعجابات + إشعارات `comment`, `reply`, `like_comment`
- عند حذف صاحب الإشعار يبقى الإشعار آمنًا

### الرسائل

- محادثات فردية · شريط المتصلين
- رسائل صوتية (`voice_message`) · مرفقات (`file_message`)
- **مكالمات صوتية WebRTC** (Google STUN + Metered TURN)
- مؤشر «يكتب الآن» · إشعارات قراءة

### القصص (Stories)

- صور فقط (الفيديو موقوف)
- BLOB في `media_data`
- `/media/story/<id>`
- مؤقّت لا يتخطى قبل التحميل
- `story_view` + `story_reaction`

### الريلز (Reels)

- BLOB فيديو + صورة مصغّرة
- `/media/video-thumb/<public_id>`
- توحيد URL عبر `media.video_thumbnail`

---

## مساعد أنتر — mini-llm Arabic

محرّك Groq (`qwen/qwen3.8-27b`)، تحت الاسم التسويقي **mini-llm Arabic**.

### القدرات

- فهم المنصة والردّ عن ميزاتها
- صياغة محتوى وردود
- إجابات تقنية (Python / Flask / PostgreSQL)
- ذاكرة لكل مستخدم: اسم + username + 24 رسالة × 800 حرف
- فلترة ضوضاء · anti-hallucination
- يعلّم رسائله مقروءة تلقائيًا

### الهوية

- `anter_assistant` · متابَع تلقائيًا · متصل دائمًا
- يرسل رسائل النظام (ترحيب، بلاغات، رد آلي)

### الذاكرة

- محلية في `assistant_memories`
- ترفض كلمات المرور والمفاتيح والبطاقات
- يُرسل السياق القصير (حتى ~3000 حرف) إلى Groq API عند الحاجة لإجابة عامة — خدمة خارجية
- يمكن للمستخدم طلب مسح الذاكرة

**ميزانية Groq:** ~3000 حرف · 24 رسالة · تقليل تلقائي عند 413/429.

---

## الشارات

| الشارة | الرمز | المنح | الإشعار |
|---|---|---|---|
| موثّق | ✅ | `/admin/users` | `verification_approved` / `rejected` |
| مؤسس | ✴️ | مؤسس واحد فقط | — |
| عضو مبكّر | 🌟 | تلقائي لأول 100 / يدوي | `early_member` / `early_member_revoked` |

---

## تطبيقات الجوال

### 1. ANTER WebView APK

- المستودع: `smart2ye/anter-webview-apk`
- الإصدار: **v1.0.10** · ~0.91 MB
- Android 7.0+ · UA: `ANTERApp/1.0.10`
- كاميرا · ميكروفون · موقع · ملفات · جهات اتصال
- فتح روابط `anter-1.onrender.com` داخل التطبيق (intent-filter)

رابط التحميل:

```text
https://github.com/smart2ye/anter-webview-apk/releases/latest/download/ANTER_app.apk
```

### 2. Plus Messenger

- المستودع: `smart2ye/plus-messenger-android`
- Kotlin + Compose + Hilt + Room
- v1.0.0 · REST API (`MOBILE_API_TOKEN_TTL_SECONDS = 43200`)

---

## الحصاد السنوي (Year in Review)

- `services/year_in_review.py`
- بطاقة PNG 1080×1920: `services/year_card.py`
- خط Cairo مضمّن: `app/static/fonts/Cairo.ttf`
- RTL عبر Pillow 12
- Route: `/year-in-review`

---

## الإشعارات

الأنواع المدعومة (24+):

like, comment, reply, follow, message, voice_message, voice_call,
file_message, wall_post, mention, repost, like_comment, like_video,
comment_video, reply_video, verification_approved, verification_rejected,
report_resolved, report_rejected, founder_post, early_member,
early_member_revoked, story_issue_fixed, video_lost

Push: pywebpush + VAPID · جدول push_subscriptions · SW v5.

---

## الخصوصية والأمان

| القاعدة | الممارسة |
|---|---|
| المفاتيح | `.env` فقط — لا Git، لا DB |
| SECRET_KEY | 43–64 حرفًا عشوائيًا |
| كلمات المرور | scrypt (32768:8:1) |
| كوكي الجلسة | HttpOnly + Secure + SameSite |
| CSRF | Flask-WTF + `X-CSRFToken` |
| Rate Limiting | على المسارات الحساسة |
| Security Headers | 5 + COOP + CORP + CSP + block-all-mixed-content |

الحماية: Blocklist 30+ نطاق مزيّف · reset token مرتبط بـ password_hash · Path Traversal مُصلح · Open Redirect مُصلح · magic bytes للرفع · منع تسجيل ببريد/هاتف محذوف · GA4 anonymize.

### Soft Delete

- `User.is_deleted` + `User.deleted_at`
- 23 نقطة إخفاء عبر 15+ ملفًا
- البريد والهاتف محجوزان
- تسجيل الدخول مرفوض
- التفاصيل: `docs/reference/soft-delete.md`

### تعدد الحسابات

`account_vault.py` — كوكي `anter_accounts` موقّع بـ `password_hash`.

---

## الأداء

- Brotli + gzip · Cache-Control سنة
- FontAwesome subset (~3 KB)
- Bootstrap + Cairo + FontAwesome محليًا
- 96 فهرس
- WebP (حد 1600px)
- gunicorn --workers=1 --threads=2 --worker-class=gthread --timeout=120 --max-requests=200 --max-requests-jitter=30

---

## SEO

- `title` / `description` ديناميكيان
- OpenGraph + Twitter Card
- Canonical + JSON-LD (SocialMediaPosting / ProfilePage / VideoObject)
- sitemap + robots
- IndexNow

---

## التشغيل المحلي (Termux)

التشغيل:

    cd ~/ANTER
    git pull --ff-only origin main
    set -a; . ./.env; set +a
    python run.py

الرابط: `http://127.0.0.1:5050`

إيقاف:

    pkill -f "python3 run.py"

خلفي + مراقبة:

    nohup python3 run.py > ~/anter.log 2>&1 &
    tail -f ~/anter.log

SQLite محلي:

    unset DATABASE_URL

بيئة افتراضية:

    source venv-termux/bin/activate

توليد الوثائق:

    unset DATABASE_URL
    export SECRET_KEY="temp"
    python3 scripts/generate_reference.py

---

## النشر على Render

**الخطة:** Free (Oregon) · CDN: Cloudflare
**RAM:** 512 MB · ينام بعد 15 دقيقة · Cold start 30–60s
**قيود:** Aiven Free → كل ALTER مستقلة · TIMESTAMP NULL غير صالح · SMTP محجوب.

### متغيرات البيئة

SECRET_KEY=<43-64 حرفًا عشوائيًا>
DATABASE_URL=<Aiven PostgreSQL URL>
MINI_LLM_ARABIC_API_KEY=<Groq API Key>
MINI_LLM_ARABIC_MODEL=qwen/qwen3.8-27b
MINI_LLM_ARABIC_ENABLED=true
ANTER_ASSISTANT_ENABLED=true
ANTER_ASSISTANT_DAILY_POSTS_ENABLED=true
ANTER_ASSISTANT_USERNAME=anter_assistant
ANTER_FOUNDER_NAME=عبدالقادر مهدلي
STARTUP_SCHEMA_UPGRADES_ENABLED=true
WEBRTC_STUN_URL=stun:stun.l.google.com:19302
WEBRTC_TURN_URL=<Metered TURN>
WEBRTC_TURN_USERNAME=<...>
WEBRTC_TURN_CREDENTIAL=<...>
VAPID_PUBLIC_KEY=<...>
VAPID_PRIVATE_KEY=<...>
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=465
MAIL_USERNAME=support.anter@gmail.com
MAIL_PASSWORD=<App Password>

**لا تُنسخ هذه القيم إلى قاعدة البيانات، ولا تُنشر في صور الشاشة أو المستودع أو المحادثات العامة.**

---

## الوثائق المرجعية

| الملف | الغرض |
|---|---|
| `routes.md` | جميع المسارات (199 route · 19 blueprint) |
| `models.md` | الجداول (34 model) |
| `services.md` | الخدمات (20 service) |
| `templates.md` | القوالب (49 template) |
| `INVENTORY.md` | جرد: إعدادات، بيئة، أمان، نشر، أولويات |
| `soft-delete.md` | نظام الحذف المنطقي |
| `integrations.md` | تكاملات خارجية (AI · WebRTC · Push · Email) |
| `identity.md` | الهوية البصرية |

يُولَّد جزء منها آليًا عبر `scripts/generate_reference.py`.

---

## الهوية البصرية

| اللون | الكود |
|---|---|
| ANTER Navy | `#031E64` |
| ANTER Blue | `#003AAB` (الأساسي) |
| ANTER Cyan | `#00C8F8` |
| ANTER Purple | `#160B8E` |

**التدرّج:** `#031E64` → `#003AAB` → `#00C8F8` → `#160B8E`

**الخطوط:** Cairo (افتراضي) + Tajawal

---

## مساهمة المجتمع

تركيز مقترح: تجربة الهاتف · سهولة التسجيل · تحسين المحتوى والوصولية · حماية الخصوصية · اختبار الميزات الجديدة.

قبل الرفع: نفّذ اختبارك، لا تكشف بيانات خاصة، لا تعطّل وظيفة قائمة.

---

## كلمة المؤسس

> ANTER مشروع ينمو من الفضول والتعلّم والتجربة. غايته بناء مجتمع عربي قريب من المستخدم، يجمع بين التواصل الإنساني والمساعدة الذكية.

**عبدالقادر مهدلي** — مؤسس ANTER وصاحب رؤيتها.

---

*آخر تحديث: 12 أكتوبر 2026*

*هذا الملف دليل خاص بمشروع ANTER، ولا ينسب إلى أي مشروع أو شركة أخرى.*

---

## الترخيص

هذا المشروع مملوك بالكامل لـ **عبدالقادر مهدلي**. جميع الحقوق محفوظة © 2026.

**غير مرخّص** للنسخ أو إعادة التوزيع أو التعديل أو الاستخدام التجاري دون إذن كتابي مسبق.

للتفاصيل: [LICENSE](LICENSE)
للاستفسارات: smart2ye@gmail.com
