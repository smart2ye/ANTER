# جرد شامل — ANTER

**آخر تحديث:** 2026-10-06
**الغرض:** مرجع سريع لكل ما هو مهم داخل المشروع، بخلاف `models.md` و `routes.md` و `services.md` و `templates.md`.

---

## 1. البيئة والإعدادات

### ملفات البيئة
| الملف | الحالة |
|---|---|
| `.env` | الحالي (سري) |
| `.env.example` | نموذج مدفوع (بلا أسرار) |
| `.env.bak_model`, `.env.bak_supabase_20260916` | نسخ احتياطية (لا تُدفع) |
| `.env.pre_migration`, `.env.pre_turn` | نسخ احتياطية (لا تُدفع) |

**الحماية في `.gitignore`:** `.env`, `.env.local`, `.env.pre_*`, `.env.bak*`.
**التحقق:** `git ls-files | grep .env` يُظهر فقط `.env.example` — لا تسريب.

### متغيرات البيئة الأساسية (أسماء فقط)
- **Flask:** `SECRET_KEY`, `FLASK_APP`, `DEBUG`, `PORT`
- **Database:** `DATABASE_URL` (Aiven / Supabase / SQLite)
- **AI:** `GROQ_API_KEY`, `GROQ_MODEL`, `MINI_LLM_ARABIC_*`
- **Messenger:** `WEBRTC_TURN_URLS`, `WEBRTC_TURN_USERNAME`, `WEBRTC_TURN_CREDENTIAL`
- **Assistant:** `ANTER_ASSISTANT_*`, `ANTER_FOUNDER_NAME`
- **Email:** `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM`, `MAIL_USE_TLS`
- **Alternate email:** `UNOSEND_API_KEY`, `UNOSEND_FROM_EMAIL` (غير مُفعّل)
- **Server:** `WEB_CONCURRENCY`, `GUNICORN_TIMEOUT`

### الإعدادات الرئيسية في `config.py`
- `MAX_CONTENT_LENGTH = 55 MB`, `MAX_VIDEO_UPLOAD_BYTES = 50 MB`, `MAX_IMAGE_BYTES = 5 MB`
- `FEED_PAGE_SIZE = 5`, `FEED_CANDIDATE_LIMIT = 30`
- `SESSION_COOKIE_*` — HttpOnly, Secure (على Render), SameSite=Lax
- `PERMANENT_SESSION_LIFETIME = 86400`
- `STARTUP_SCHEMA_UPGRADES_ENABLED` — يعتمد على نوع DB أو متغير البيئة
- `ANTER_PUBLIC_URL = https://anter-1.onrender.com`
- `WEBRTC_STUN_URL = stun:stun.l.google.com:19302` (افتراضي)

---

## 2. الملفات الثابتة (Static)

### CSS
| الملف | الأسطر | الحجم |
|---|---|---|
| `app/static/css/style.css` | 9,182 | 193 KB |
| `app/static/css/stories.css` | 831 | 17.8 KB |
| `vendor/cairo/cairo.css` | 25 | — |
| `vendor/fontawesome/css/anter-icons.min.css` | 142 | subset (3 KB) |
| `vendor/bootstrap/bootstrap.rtl.min.css` | 5 | مضغوط |

### JS
| الملف | الأسطر | الحجم |
|---|---|---|
| `app/static/js/main.js` | 1,914 | 73 KB |
| `app/static/js/stories.js` | 659 | 27 KB |
| `app/static/sw.js` | 168 | — |
| `vendor/bootstrap/bootstrap.bundle.min.js` | 6 | مضغوط |

### نسخ احتياطية محلية (خارج Git)
- `style.css.pre_color`, `style.css.pre_comments`, `stories.css.pre_color`
- **قرار:** تبقى حتى التأكد من استقرار Render.

### ملاحظات
- `style.css` ضخم — يحتاج تفكيرًا في التقسيم مستقبلًا (لكن ليس الآن).
- `main.js` يحتوي كل JS المشترك — مقبول.
- `vendor/` مضغوط بالكامل — ممتاز.

---

## 3. Scripts والأدوات (17)

### توليد / صيانة
| السكربت | الأسطر | الغرض |
|---|---|---|
| `scripts/generate_reference.py` | 327 | توليد `docs/reference/` |
| `scripts/migrate_large_images.py` | 146 | ترحيل الصور الكبيرة |
| `scripts/sync_from_cloud.py` | 117 | مزامنة من السحابة |
| `scripts/migrate_to_aiven.py` | 87 | ترحيل DB إلى Aiven |
| `scripts/indexnow_submit.py` | 84 | إشعار IndexNow |
| `scripts/show_render_admin_url.py` | 43 | مسار الأدمن |
| `scripts/maintenance/reset_password.py` | 31 | إعادة تعيين كلمة مرور |
| `scripts/maintenance/check_verified.py` | 9 | فحص التوثيق |
| `scripts/maintenance/show_chat.py` | 46 | عرض محادثة |

### أمني / استعلامات
| السكربت | الأسطر |
|---|---|
| `scripts/security_audit_local.py` | 100 |
| `scripts/change_username.py` | 97 |
| `scripts/db_query.py` | 90 |

### اختبارات (verification/)
| السكربت | الأسطر |
|---|---|
| `verify_local_messaging.py` | 80 |
| `verify_chat_attachments.py` | 80 |
| `verify_local_images.py` | 66 |
| `verify_typing.py` | 55 |
| `verify_comments.py` | 45 |

---

## 4. قاعدة البيانات

### الفهارس
- **96 فهرسًا** (بين `index=True` و `CREATE INDEX`).
- **13 فهرسًا** يُنشأ في `services/startup_maintenance.py`:
  - `posts.public_id`, `posts.created_at`, `posts.shared_video_id`
  - `videos.public_id`, `videos.created_at`
  - `messages.created_at`, `messages.is_read`, `messages.is_ai`, `messages.shared_video_id`
  - `notifications.report_id`, `notifications.created_at`, `notifications.is_read`
  - `reports.message_id`, `reports.video_id`
  - `story.created_at`

### الأعمدة الجديدة (تُضاف عبر `startup_maintenance`)
- `users.is_deleted`, `users.deleted_at` (2026-10-06)
- `posts.public_id`, `posts.link_url`, `posts.visibility`, `posts.shared_video_id`, `posts.wall_owner_id`
- `messages.is_ai`, `messages.read_at`, `messages.audio_*`, `messages.attachment_*`, `messages.parent_id`, `messages.is_deleted_everyone`, `messages.deleted_by_*`
- `videos.public_id`, `videos.shares`, `videos.video_*`, `videos.thumbnail_*`
- `comments.audio_url`, `comments.edited_at`
- `video_comments.edited_at`
- `reports.message_id`, `reports.video_id`, `reports.rejection_reason`, `reports.resolution_note`

### قواعد حرجة
- كل ALTER في transaction مستقلة (لا تُسمّم الجلسة).
- `TIMESTAMP NULL` غير صالح في PostgreSQL.
- Aiven Free: لا migrations ثقيلة عند startup.

---

## 5. النشر (Deployment)

### `Procfile`


web: gunicorn --bind 0.0.0.0:$PORT run:app --workers=1 --threads=4 --timeout=300 --max-requests=300 --max-requests-jitter=30



### `requirements.txt` (أهم الحزم)
- Flask 3.1.3, Flask-SQLAlchemy 3.1.1, Flask-Login 0.6.3, Flask-WTF 1.3.0
- Werkzeug 3.1.8, WTForms 3.2.2, python-dotenv 1.0.0
- SQLAlchemy 2.0.30+, psycopg2-binary 2.9.13+
- gunicorn 23.0.0
- Pillow 11.0.0+, email-validator 2.3.0
- requests, beautifulsoup4, markdown, bleach
- pywebpush 1.14.1 (push notifications)
- flask-compress 1.15+, Brotli 1.1.0+
- whitenoise 6.6.0+ (static serving)
- resend (غير مُفعّل — Render يحجب SMTP)

### لا يوجد `render.yaml` — الإعداد يدوي على Render dashboard.

---

## 6. الأمان

### الهيدرات (على كل الردود — `app/__init__.py`)
- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(self), camera=(self), payment=()`
- `Strict-Transport-Security` (HTTPS فقط)
- `Content-Security-Policy` (متساهل — `unsafe-inline`, `unsafe-eval`)
- إزالة `X-Render-Origin-Server`

### Rate Limiting (في الذاكرة — `_RATE_LIMITS`)
| المسار | الحد |
|---|---|
| `/auth/login` | 10 / دقيقة |
| `/auth/register` | 5 / 5 دقائق |
| `/auth/reset_password` | 10 / 5 دقائق |
| `/auth/forgot` | 10 / 5 دقائق |
| `/api/ai/assist` | 20 / دقيقة |
| `/users/find-friends` | 5 / دقيقة |
| `/messages/send` | 60 / دقيقة |

**⚠️ هشّ:** يعمل فقط مع `--workers=1`. أي ترقية لاحقة تكسره.

### CSRF
- `WTF_CSRF_SSL_STRICT = False` (خلف Cloudflare)
- `@csrf.exempt` على مسارات AJAX + `X-CSRFToken` في headers

### Account Vault
- كوكي `anter_accounts` موقّع بـ `password_hash`.
- `services/account_vault.py`

### Password Reset
- الرمز مربوط بـ `password_hash` (منع إعادة الاستخدام).

---

## 7. المساعد (Assistant)

### الحساب
- Username: `anter_assistant` (id=4)
- Name: `مساعد أنتر`
- Email: `assistant@anter.local`

### النشر اليومي
- `services/anter_daily_publication.py`
- 7 منشورات جاهزة (واحد لكل يوم من الأسبوع).
- تُنشر مرة واحدة يوميًا عند أول استدعاء `/health`.

### الذاكرة
- `services/anter_memory.py` + `models/assistant_memory.py`
- 24 رسالة × 800 حرف.
- فلترة ضوضاء.
- 3000 حرف ميزانية لـ Groq.

### القيود
- Groq 413/429 → قلّل السياق.
- `ANTER_ASSISTANT_MAX_QUESTION_CHARACTERS = 3000`
- `ANTER_ASSISTANT_MAX_REPLY_CHARACTERS = 1200`


---

## 8. WebRTC و Push و Mobile

### WebRTC (المكالمات)
- STUN: `stun:stun.l.google.com:19302`
- TURN: Metered.ca (عبر `WEBRTC_TURN_URLS`)
- `services/mobile_api_auth.py` — tokens للأجهزة.

### Push
- `pywebpush` + VAPID.
- `models/push_subscription.py`

### APK / Mobile
| التطبيق | الإصدار | الرابط |
|---|---|---|
| `anter-webview-apk` | 1.0.7 (حديث) | GitHub Releases |
| `plus-messenger-android` | 1.1.0 | `releases/latest/download/PlusMessenger.apk` |
| `anter-dev-assistant` | — | APK مساعد |
| `anter-assistant` | — | مساعد محلي |

**ملاحظة:** `ANTER_APK_URL` و `ANTER_MESSENGER_APK_URL` في `config.py` قديمان (v1.0.3 / manuscdn). قرار مؤجّل.

---

## 9. SEO / Public

### صفحات عامة
- `landing.html` — للزوار غير المسجلين (`GET /`).
- `robots.txt`, `sitemap.xml` (119 رابط، يُولَّد ديناميكيًا).
- `about.html`, `privacy.html`, `terms.html`, `help.html`.

### البيانات المنظمة
- JSON-LD: `SocialMediaPosting`, `ProfilePage`, `VideoObject`.

### التحقق
- Google + Bing مفهرس.
- IndexNow (`scripts/indexnow_submit.py`).

---

## 10. Startup & Health

### `run.py`
- `app = create_app()`
- `delete_expired_stories(app)` عند التشغيل (try/except).
- `GET /health` — ينشئ منشور المساعد اليومي + يرد `OK`.

### `app/__init__.py` — عند الإقلاع
- Compress (اختياري).
- `db.init_app`, `login_manager.init_app`, `csrf.init_app`.
- `ADMIN_PATH` عشوائي (`admin-{token_urlsafe(24)}`) — يُثبّت عبر env.
- Blueprints.
- `run_startup_schema_upgrades(app)`.
- `ensure_anter_assistant_user()` + (إن كان upgrade) `ensure_anter_assistant_followed_by_all_users()`.
- `ensure_configured_owner_is_admin()`.

### `before_request` hooks
1. `_anter_clean_session` — `db.session.rollback()`.
2. `update_last_seen` — throttle دقيقتين.
3. `_anter_rate_limit`.

### `after_request` hooks
1. `_anter_security_headers`.
2. `_anter_static_cache_and_compress` (Brotli → gzip).


---

## 11. قيود معروفة / دَين تقني

### حرجة (يجب معالجتها)
- **Rate Limiting في الذاكرة:** يعمل مع `--workers=1` فقط. ترقية → كسر صامت.
- **CSP شكلي:** `unsafe-inline` + `unsafe-eval` — لا يحمي فعليًا.
- **قوالب ثقيلة:** `messages/chat.html` (1,951 سطر)، `_reel_stream.html` (1,555 سطر).
- **`style.css` ضخم:** 9,182 سطر / 193 KB.

### متوسطة
- **`docs/reference/` قديم جزئيًا** — يعاد توليده عبر `scripts/generate_reference.py`.
- **`delete_account`** (المستخدم يحذف نفسه) — ما زال حذفًا فعليًا (بلا soft).
- **APK قديم** في `config.py`.
- **Resend غير مُفعّل** (Render يحجب SMTP).
- **`ANTER_ASSISTANT_SWITCH_OWNER_USERNAME`** في الكود كافتراضي — مكشوف.

### منخفضة
- **ملفات `.pre_*` و `.bak_*`** محليًا — تنظيف مؤجّل.
- **`admin.py` بلا فلترة `is_deleted`** — مقصود.

---

## 12. Soft Delete — ملخص

**راجع `docs/reference/soft-delete.md` للتفاصيل.**

- `User.is_deleted`, `User.deleted_at` (2026-10-06).
- 23 نقطة إخفاء موزّعة على 15+ ملف.
- البريد/الهاتف محجوزان (unique) بعد الحذف.
- العدّادات واقعية.

---

## 13. مسار العمل اليومي

```bash
# تشغيل محلي
cd ~/ANTER && source venv-termux/bin/activate
python3 run.py

# تشغيل خلفي
nohup python3 run.py > ~/anter.log 2>&1 &
tail -f ~/anter.log

# إيقاف
pkill -f "python3 run.py"

# تحديث الوثائق
unset DATABASE_URL
export SECRET_KEY="x"
python3 scripts/generate_reference.py

# اختبار أمني
python3 scripts/security_audit_local.py
```

---

## 14. أرقام المشروع الحالية

| العنصر | العدد |
|---|---|
| Routes | 194 |
| Blueprints | 18 |
| Models | 34 |
| Templates | 48 |
| Services | 18 |
| Python files | 108 |
| Scripts | 17 |
| CSS files | 3 (+ vendor) |
| JS files | 3 (+ vendor) |
| Indexes | 96 |

---

## 15. أولويات مقترحة

1. **إصلاح `delete_account`** → soft delete.
2. **تحديث APK في `config.py`** → v1.0.7 + GitHub.
3. **معالجة Rate Limiting الهشّ** → Redis أو DB مشتركة.
4. **تفعيل Resend** → يحتاج دومين.
5. **مراجعة `chat.html`** → فصل JS/CSS.
6. **CSP أقوى** → نقل inline scripts تدريجيًا.

