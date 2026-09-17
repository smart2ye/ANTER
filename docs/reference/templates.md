# مرجع القوالب (Templates)

**آخر تحديث:** 2026-09-17
**المجموع:** 47 قالب في app/templates/

## القوالب الأساسية

| الملف | الأسطر | الوظيفة |
|---|---|---|
| base.html | 550 | القالب الأساسي |
| index.html | 882 | الصفحة الرئيسية |
| about.html | 118 | عن ANTER |
| _post_card.html | 292 | بطاقة منشور |
| _feed_recommendations.html | 13 | توصيات |
| comments.html | 283 | التعليقات |
| post_reactions.html | 21 | التفاعلات |
| post_detail.html | 4 | صفحة منشور (شبه فارغة) |

## المصادقة (auth/)
- login.html — 104
- register.html — 177
- reset_password_request.html — 19
- reset_password.html — 19
- confirm_email.html — 50

## المستخدمون
- profile.html — 192
- profile_edit.html — 46
- profile_videos.html — 89
- followers.html — 114
- settings.html — 255
- activity_log.html — 59

## المنشورات (posts/)
- create.html — 190
- edit.html — 29

## الريلز (videos/)
- reels.html — 918
- _reel_stream.html — 1249
- _reel_grid.html — 34
- watch.html — 756
- upload.html — 96
- main_reels.html — 16 (قد لا يُستخدم)

## الرسائل (messages/)
- chat.html — 1528 (الأكبر — Chat + Call UI)
- inbox.html — 119

## ANTER Moments
- moments/index.html — 134
- moments/detail.html — 64

## Admin
- _navigation.html — 30
- dashboard.html — 152
- users.html — 232
- posts.html — 54
- post_detail.html — 30
- reports.html — 106
- verification_requests.html — 70
- support_requests.html — 50

## القوالب الثابتة
- privacy.html — 64
- terms.html — 64
- help.html — 91
- notifications.html — 104
- explore.html — 150
- explore/hashtag.html — 34
- trends/index.html — 68

## الملفات الثابتة (app/static/)
- manifest.json — PWA manifest
- sw.js — Service Worker v3
- offline.html — صفحة عدم الاتصال
- robots.txt — SEO
- css/style.css — التنسيق الرئيسي
- css/stories.css — القصص
- js/main.js — Lightbox + Image Menu + AI
- js/stories.js — القصص + Composer

## قوالب تحتاج مراجعة
| القالب | الحجم | الوضع |
|---|---|---|
| post_detail.html | 4 أسطر | شبه فارغ |
| main_reels.html | 16 سطرًا | قد لا يُستخدم |
| post_reactions.html | 21 سطرًا | صغير جدًا |
| posts/edit.html | 29 سطرًا | قد يحتاج تحسين |
