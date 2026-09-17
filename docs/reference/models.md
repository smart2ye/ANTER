# مرجع النماذج (Models)

**آخر تحديث:** 2026-09-17
**المجموع:** 31 موديل في app/models/

## User (users)
- id, username, email, name, password_hash
- avatar, avatar_data (BLOB), avatar_mime
- bio, gender, birth_date
- is_admin, is_verified, is_active, email_verified
- phone, phone_verified, country_code
- is_private, profile_visibility, hide_followers
- show_online_status, show_email, message_privacy
- theme_preference, terms_agreed
- last_seen, created_at
مهام: set_password, check_password, follow, unfollow, is_following, follower_count, following_count

## Post (posts)
- id, public_id, content
- image, image_data (BLOB), image_mime
- link_url, link_title, link_description, link_image
- author_id, visibility (public/followers/only_me)
- shared_video_id — لبطاقة الريل

## Comment (comments)
- id, content, author_id, post_id, parent_id
- audio_url — تسجيل صوتي
- Self-referential: replies

## Like (likes)
- user_id, post_id, reaction_type (like/love/haha/angry/sad)
- Unique: (user_id, post_id)

## المجموعة الاجتماعية
- Follow — follower_id + followed_id
- Repost — user_id + post_id
- HiddenPost — user_id + post_id
- UserBlock — blocker_id + blocked_id
- MutedConversation — user_id + muted_user_id

## Video (videos)
- id, public_id, title, description
- file_path, thumbnail_path
- duration, views, shares
- is_reel (bool)
- author_id

## VideoLike / VideoComment / VideoCommentLike
جداول التفاعل مع الريلز

## Story (story)
- media_url, media_type (image/video), caption
- expires_at — 24 ساعة
- is_active
- StoryView, StoryReaction

## Message (messages)
- content, sender_id, receiver_id
- audio_data (BLOB), audio_mime, audio_path (legacy)
- attachment_data (BLOB), attachment_mime/name/kind
- shared_video_id — مشاركة ريل
- parent_id — الرد
- is_deleted_everyone, deleted_by_sender/receiver

## TypingState
مؤشر "يكتب الآن" بين طرفين

## CallLog (call_logs)
- call_id, caller_id, receiver_id
- call_type (voice/video)
- status: ringing | answered | declined | missed | cancelled
- started_at, answered_at, ended_at, duration_seconds

## CallSignal (call_signals)
- call_id, signal_type (invite/answer/candidate/decline/hangup)
- payload (JSON), delivered_at

## المجموعة الذكية
- AssistantMemory — ذاكرة mini-llm
- AssistantDailyPublication — منع النشر المكرر
- Moment — لحظة ANTER
- MomentPost — ربط منشور بلحظة

## المجموعة الإدارية
- Report — تقارير (post/comment/message/video)
- Notification — إشعارات
- UserActivity — سجل النشاط
- OwnerAdminBootstrap — ترقية المالك
- PushSubscription — Web Push

## Mobile Auth
- MobileAccessToken — توكن جهاز
- MobileBrowserAuthorization — ربط جلسة

## Hashtags
- Hashtag — الوسوم
- PostHashtag — Many-to-Many
