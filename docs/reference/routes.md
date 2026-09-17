# مرجع المسارات (Routes)

**آخر تحديث:** 2026-09-17
**المجموع:** 156 سطر route · 19 blueprint

## تسجيل الـBlueprints

| Blueprint | Prefix |
|---|---|
| stories_bp | /api |
| auth_bp | /auth |
| main_bp | (بدون) |
| users_bp | /users |
| posts_bp | (بدون) |
| admin_bp | /admin |
| messages_bp | /messages |
| mobile_api_bp | /api/mobile |
| api_bp | (بدون) |
| notifications_bp | /notifications |
| videos_bp | /videos |
| explore_bp | /explore |
| trends_bp | /trends |
| media_bp | /media |
| ai_bp | /api |
| sse_bp | /sse |
| reactions_bp | (بدون) |
| moments_bp | (بدون) |
| test_email_bp | غير مسجل (ملف ميت) |

## عدد الـroutes لكل ملف

| الملف | العدد |
|---|---|
| mobile_api.py | 23 |
| messages.py | 18 |
| admin.py | 17 |
| main.py | 17 |
| users.py | 17 |
| posts.py | 14 |
| videos.py | 10 |
| auth.py | 8 |
| stories.py | 7 |
| api.py | 5 |
| notifications.py | 5 |
| ai.py | 3 |
| explore.py | 3 |
| media.py | 3 |
| moments.py | 2 |
| reactions.py | 1 |
| sse.py | 1 |
| test_email.py | 1 |
| trends.py | 1 |

## المسارات الرئيسية

### الصفحة الرئيسية (main.py)
- GET / — index
- GET /api/posts?page=N — Pagination
- GET /about, /privacy, /terms, /help
- GET /sitemap.xml
- POST /update_interests
- GET /api/users

### المصادقة (auth.py + /auth)
- GET,POST /auth/login
- GET,POST /auth/register
- GET /auth/logout
- POST /auth/switch-to-assistant
- POST /auth/switch-back-to-owner
- GET,POST /auth/reset_password_request
- GET,POST /auth/reset_password/<token>

### المستخدمون (users.py + /users)
- GET /users/<username>
- GET /users/<username>/followers
- GET /users/<username>/following
- GET,POST /users/settings
- POST /users/set-avatar-from-post/<post_id>
- POST /users/follow/<user_id>
- POST /users/unfollow/<user_id>
- GET /users/activity
- GET /users/download_data

### المنشورات (posts.py بدون prefix)
- POST /create
- GET,POST /edit/<post_id>
- POST /delete/<post_id>
- POST /like/<post_id>
- POST /comment/<post_id>
- POST /share-video/<video_id>
- POST /repost/<post_id>
- POST /report و /report/<post_id>
- POST /hide/<post_id>
- GET /comments/<post_id>/fragment
- GET /p/<public_id>

### الريلز (videos.py + /videos)
- GET /videos/reels
- GET /videos/r/<public_id>
- POST /videos/upload
- POST /videos/view/<public_id>
- POST /videos/like/<video_id>
- POST /videos/report/<video_id> — يحتاج @csrf.exempt
- GET /videos/comments/<video_id>

### الرسائل والمكالمات (messages.py + /messages)
- GET /messages/
- GET /messages/<user_id>
- POST /messages/send/<user_id>
- POST /messages/send-audio/<user_id>
- GET /messages/audio/<message_id>
- GET /messages/attachment/<message_id>
- POST /messages/typing/<user_id>
- POST /messages/safety/<user_id>/block
- POST /messages/safety/<user_id>/mute
- POST /messages/delete/<message_id>
- POST /messages/forward/<message_id>
- GET /messages/unread_count
- POST /messages/calls/signal/<user_id>
- GET /messages/calls/poll/<user_id>
- GET /messages/calls/pending

### القصص (stories.py + /api)
- POST /api/stories
- GET /api/stories/feed
- GET /api/user-stories/<user_id>
- POST /api/stories/<story_id>/view
- POST /api/stories/<story_id>/react
- GET /api/stories/<story_id>/viewers
- DELETE /api/stories/<story_id>

### Mobile API (mobile_api.py + /api/mobile)
- POST /api/mobile/auth/login
- GET /api/mobile/me
- GET /api/mobile/conversations
- GET /api/mobile/conversations/<username>/messages
- POST /api/mobile/conversations/<username>/messages
- POST /api/mobile/suggested-follows
- GET /api/mobile/contacts
- GET /api/mobile/devices

### AI (ai.py + /api)
- POST /api/ai/complete
- GET /api/ai/summarize/<post_id>
- POST /api/ai/assist

### الإشعارات (notifications.py + /notifications)
- GET /notifications/
- GET /notifications/unread_count
- POST /notifications/subscribe
- POST /notifications/mark_read/<id>

### SSE (sse.py + /sse)
- GET /sse/notifications

### Admin (admin.py + /admin)
- GET /admin/
- GET /admin/users
- POST /admin/users/verify/<id>
- GET /admin/reports
- GET /admin/verification-requests

### Media (media.py + /media)
- GET /media/avatar/<user_id> — ETag + no-cache
- GET /media/p/<public_id>

## ملاحظات مهمة
- /api/mobile بدون /v1
- /share-video بدون /posts
- /report له مساران
- @csrf.exempt ضروري في POST من JS
