# مرجع النماذج (Models)

**آخر تحديث:** 2026-10-05
**المجموع:** 34 موديل

## AssistantDailyPublication

- **الجدول:** `assistant_daily_publications`
- **الملف:** `assistant_daily_publication.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `published_on` | DATE |  |  |
| `post_id` | INTEGER |  |  |
| `created_at` | DATETIME |  |  |

## AssistantMemory

- **الجدول:** `assistant_memories`
- **الملف:** `assistant_memory.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `assistant_id` | INTEGER |  |  |
| `user_id` | INTEGER |  |  |
| `preferences_json` | TEXT |  |  |
| `recent_context_json` | TEXT |  |  |
| `created_at` | DATETIME |  |  |
| `updated_at` | DATETIME |  |  |

## CallLog

- **الجدول:** `call_logs`
- **الملف:** `call_log.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `call_id` | VARCHAR(64) |  |  |
| `caller_id` | INTEGER |  |  |
| `receiver_id` | INTEGER |  |  |
| `call_type` | VARCHAR(16) |  |  |
| `status` | VARCHAR(20) |  |  |
| `started_at` | DATETIME |  |  |
| `answered_at` | DATETIME | ✓ |  |
| `ended_at` | DATETIME | ✓ |  |
| `duration_seconds` | INTEGER | ✓ |  |

## CallSignal

- **الجدول:** `call_signals`
- **الملف:** `call_signal.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `call_id` | VARCHAR(64) |  |  |
| `signal_type` | VARCHAR(20) |  |  |
| `payload` | TEXT | ✓ |  |
| `created_at` | DATETIME |  |  |
| `delivered_at` | DATETIME | ✓ |  |
| `sender_id` | INTEGER |  |  |
| `receiver_id` | INTEGER |  |  |

## Comment

- **الجدول:** `comments`
- **الملف:** `comment.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `content` | TEXT |  |  |
| `created_at` | DATETIME | ✓ |  |
| `author_id` | INTEGER |  |  |
| `post_id` | INTEGER |  |  |
| `parent_id` | INTEGER | ✓ |  |
| `edited_at` | DATETIME | ✓ |  |
| `audio_url` | VARCHAR(255) | ✓ |  |

## CommentLike

- **الجدول:** `comment_likes`
- **الملف:** `comment_like.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `user_id` | INTEGER |  |  |
| `comment_id` | INTEGER |  |  |
| `created_at` | DATETIME | ✓ |  |

## Follow

- **الجدول:** `follows`
- **الملف:** `follow.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `follower_id` | INTEGER |  |  |
| `followed_id` | INTEGER |  |  |
| `created_at` | DATETIME | ✓ |  |

## Hashtag

- **الجدول:** `hashtags`
- **الملف:** `hashtag.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `name` | VARCHAR(50) |  |  |
| `created_at` | DATETIME | ✓ |  |

## HiddenPost

- **الجدول:** `hidden_posts`
- **الملف:** `hidden_post.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `user_id` | INTEGER |  |  |
| `post_id` | INTEGER |  |  |
| `created_at` | DATETIME | ✓ |  |

## Like

- **الجدول:** `likes`
- **الملف:** `like.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `user_id` | INTEGER |  |  |
| `post_id` | INTEGER |  |  |
| `reaction_type` | VARCHAR(20) | ✓ |  |
| `created_at` | DATETIME | ✓ |  |

## Message

- **الجدول:** `messages`
- **الملف:** `message.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `content` | TEXT |  |  |
| `audio_path` | VARCHAR(255) | ✓ |  |
| `audio_data` | BLOB | ✓ |  |
| `audio_mime` | VARCHAR(100) | ✓ |  |
| `attachment_data` | BLOB | ✓ |  |
| `attachment_mime` | VARCHAR(150) | ✓ |  |
| `attachment_name` | VARCHAR(255) | ✓ |  |
| `attachment_kind` | VARCHAR(20) | ✓ |  |
| `created_at` | DATETIME | ✓ |  |
| `is_read` | BOOLEAN | ✓ |  |
| `sender_id` | INTEGER |  |  |
| `receiver_id` | INTEGER |  |  |
| `shared_video_id` | INTEGER | ✓ |  |
| `parent_id` | INTEGER | ✓ |  |
| `is_deleted_everyone` | BOOLEAN | ✓ |  |
| `deleted_by_sender` | BOOLEAN | ✓ |  |
| `deleted_by_receiver` | BOOLEAN | ✓ |  |
| `is_ai` | BOOLEAN |  |  |
| `read_at` | TIMESTAMP | ✓ |  |

## MobileAccessToken

- **الجدول:** `mobile_access_tokens`
- **الملف:** `mobile_access_token.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `token_hash` | VARCHAR(64) |  |  |
| `user_id` | INTEGER |  |  |
| `device_name` | VARCHAR(120) |  |  |
| `created_at` | DATETIME |  |  |
| `expires_at` | DATETIME |  |  |
| `last_used_at` | DATETIME | ✓ |  |
| `revoked_at` | DATETIME | ✓ |  |

## MobileBrowserAuthorization

- **الجدول:** `mobile_browser_authorizations`
- **الملف:** `mobile_browser_authorization.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `code_hash` | VARCHAR(64) |  |  |
| `state` | VARCHAR(120) |  |  |
| `redirect_uri` | VARCHAR(255) |  |  |
| `device_name` | VARCHAR(120) |  |  |
| `user_id` | INTEGER |  |  |
| `created_at` | DATETIME |  |  |
| `expires_at` | DATETIME |  |  |
| `consumed_at` | DATETIME | ✓ |  |

## Moment

- **الجدول:** `moments`
- **الملف:** `moment.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `title` | VARCHAR(255) |  |  |
| `description` | TEXT | ✓ |  |
| `cover_media` | VARCHAR(500) | ✓ |  |
| `status` | VARCHAR(20) |  |  |
| `created_at` | DATETIME |  |  |
| `updated_at` | DATETIME |  |  |
| `expires_at` | DATETIME | ✓ |  |

## MomentPost

- **الجدول:** `moment_posts`
- **الملف:** `moment.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `moment_id` | INTEGER |  |  |
| `post_id` | INTEGER |  |  |
| `created_at` | DATETIME |  |  |

## MutedConversation

- **الجدول:** `muted_conversations`
- **الملف:** `muted_conversation.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `user_id` | INTEGER |  |  |
| `muted_user_id` | INTEGER |  |  |
| `created_at` | DATETIME |  |  |

## Notification

- **الجدول:** `notifications`
- **الملف:** `notification.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `user_id` | INTEGER |  |  |
| `actor_id` | INTEGER |  |  |
| `action` | VARCHAR(50) |  |  |
| `post_id` | INTEGER | ✓ |  |
| `is_read` | BOOLEAN | ✓ |  |
| `created_at` | DATETIME | ✓ |  |
| `extra_text` | VARCHAR(500) | ✓ |  |
| `report_id` | INTEGER | ✓ |  |

## OwnerAdminBootstrap

- **الجدول:** `owner_admin_bootstrap`
- **الملف:** `owner_admin_bootstrap.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `key` | VARCHAR(64) |  | ✓ |
| `user_id` | INTEGER |  |  |
| `username_at_promotion` | VARCHAR(80) |  |  |
| `promoted_at` | DATETIME |  |  |

## Post

- **الجدول:** `posts`
- **الملف:** `post.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `public_id` | VARCHAR(40) |  |  |
| `content` | TEXT |  |  |
| `image` | VARCHAR(200) | ✓ |  |
| `image_data` | BLOB | ✓ |  |
| `image_mime` | VARCHAR(100) | ✓ |  |
| `link_url` | VARCHAR(500) | ✓ |  |
| `link_title` | VARCHAR(255) | ✓ |  |
| `link_description` | TEXT | ✓ |  |
| `link_image` | VARCHAR(500) | ✓ |  |
| `created_at` | DATETIME | ✓ |  |
| `updated_at` | DATETIME | ✓ |  |
| `author_id` | INTEGER |  |  |
| `visibility` | VARCHAR(20) |  |  |
| `shared_video_id` | INTEGER | ✓ |  |
| `wall_owner_id` | INTEGER | ✓ |  |

## PostHashtag

- **الجدول:** `post_hashtags`
- **الملف:** `post_hashtag.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `post_id` | INTEGER |  |  |
| `hashtag_id` | INTEGER |  |  |
| `created_at` | DATETIME | ✓ |  |

## PushSubscription

- **الجدول:** `push_subscriptions`
- **الملف:** `push_subscription.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `user_id` | INTEGER |  |  |
| `endpoint` | VARCHAR(500) |  |  |
| `p256dh` | VARCHAR(200) |  |  |
| `auth` | VARCHAR(100) |  |  |
| `created_at` | DATETIME | ✓ |  |
| `updated_at` | DATETIME | ✓ |  |

## Report

- **الجدول:** `reports`
- **الملف:** `report.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `reporter_id` | INTEGER |  |  |
| `post_id` | INTEGER | ✓ |  |
| `comment_id` | INTEGER | ✓ |  |
| `message_id` | INTEGER | ✓ |  |
| `video_id` | INTEGER | ✓ |  |
| `reason` | VARCHAR(200) |  |  |
| `details` | TEXT | ✓ |  |
| `status` | VARCHAR(20) | ✓ |  |
| `created_at` | DATETIME | ✓ |  |
| `resolved_at` | DATETIME | ✓ |  |
| `resolved_by` | INTEGER | ✓ |  |
| `rejection_reason` | VARCHAR(500) | ✓ |  |
| `resolution_note` | TEXT | ✓ |  |

## Repost

- **الجدول:** `reposts`
- **الملف:** `repost.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `user_id` | INTEGER |  |  |
| `post_id` | INTEGER |  |  |
| `created_at` | DATETIME | ✓ |  |

## Story

- **الجدول:** `story`
- **الملف:** `story.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `user_id` | INTEGER |  |  |
| `media_url` | VARCHAR(255) | ✓ |  |
| `media_data` | BLOB | ✓ |  |
| `media_mime` | VARCHAR(100) | ✓ |  |
| `media_type` | VARCHAR(10) | ✓ |  |
| `caption` | VARCHAR(200) | ✓ |  |
| `created_at` | DATETIME | ✓ |  |
| `expires_at` | DATETIME |  |  |
| `is_active` | BOOLEAN | ✓ |  |

## StoryReaction

- **الجدول:** `story_reaction`
- **الملف:** `story.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `story_id` | INTEGER |  |  |
| `user_id` | INTEGER |  |  |
| `reaction_type` | VARCHAR(20) |  |  |
| `created_at` | DATETIME | ✓ |  |

## StoryView

- **الجدول:** `story_view`
- **الملف:** `story.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `story_id` | INTEGER |  |  |
| `viewer_id` | INTEGER |  |  |
| `viewed_at` | DATETIME | ✓ |  |

## TypingState

- **الجدول:** `typing_states`
- **الملف:** `typing_state.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `sender_id` | INTEGER |  |  |
| `receiver_id` | INTEGER |  |  |
| `updated_at` | DATETIME |  |  |

## User

- **الجدول:** `users`
- **الملف:** `user.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `username` | VARCHAR(80) |  |  |
| `email` | VARCHAR(120) |  |  |
| `email_verified` | BOOLEAN |  |  |
| `name` | VARCHAR(100) |  |  |
| `password_hash` | VARCHAR(256) |  |  |
| `bio` | VARCHAR(200) | ✓ |  |
| `avatar` | VARCHAR(200) | ✓ |  |
| `avatar_data` | BLOB | ✓ |  |
| `avatar_mime` | VARCHAR(100) | ✓ |  |
| `gender` | VARCHAR(20) | ✓ |  |
| `birth_date` | DATE | ✓ |  |
| `is_private` | BOOLEAN | ✓ |  |
| `profile_visibility` | VARCHAR(20) |  |  |
| `hide_followers` | BOOLEAN | ✓ |  |
| `show_online_status` | BOOLEAN |  |  |
| `show_email` | BOOLEAN | ✓ |  |
| `message_privacy` | VARCHAR(20) | ✓ |  |
| `is_admin` | BOOLEAN | ✓ |  |
| `is_verified` | BOOLEAN | ✓ |  |
| `created_at` | DATETIME | ✓ |  |
| `is_active` | BOOLEAN | ✓ |  |
| `country_code` | VARCHAR(10) | ✓ |  |
| `phone` | VARCHAR(20) | ✓ |  |
| `phone_verified` | BOOLEAN | ✓ |  |
| `last_seen` | DATETIME | ✓ |  |
| `theme_preference` | VARCHAR(20) | ✓ |  |
| `terms_agreed` | BOOLEAN | ✓ |  |
| `wall_visibility` | VARCHAR(20) |  |  |

## UserActivity

- **الجدول:** `user_activities`
- **الملف:** `user_activity.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `user_id` | INTEGER |  |  |
| `action` | VARCHAR(50) |  |  |
| `ip_address` | VARCHAR(50) | ✓ |  |
| `user_agent` | TEXT | ✓ |  |
| `browser` | VARCHAR(50) | ✓ |  |
| `os` | VARCHAR(50) | ✓ |  |
| `device_type` | VARCHAR(50) | ✓ |  |
| `details` | TEXT | ✓ |  |
| `created_at` | DATETIME | ✓ |  |

## UserBlock

- **الجدول:** `user_blocks`
- **الملف:** `user_block.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `blocker_id` | INTEGER |  |  |
| `blocked_id` | INTEGER |  |  |
| `created_at` | DATETIME |  |  |

## Video

- **الجدول:** `videos`
- **الملف:** `video.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `public_id` | VARCHAR(40) |  |  |
| `title` | VARCHAR(200) |  |  |
| `description` | TEXT | ✓ |  |
| `file_path` | VARCHAR(300) |  |  |
| `video_data` | BLOB | ✓ |  |
| `video_mime` | VARCHAR(100) | ✓ |  |
| `thumbnail_path` | VARCHAR(300) | ✓ |  |
| `thumbnail_data` | BLOB | ✓ |  |
| `thumbnail_mime` | VARCHAR(100) | ✓ |  |
| `duration` | INTEGER | ✓ |  |
| `views` | INTEGER | ✓ |  |
| `shares` | INTEGER | ✓ |  |
| `is_reel` | BOOLEAN | ✓ |  |
| `author_id` | INTEGER |  |  |
| `created_at` | DATETIME | ✓ |  |
| `updated_at` | DATETIME | ✓ |  |

## VideoComment

- **الجدول:** `video_comments`
- **الملف:** `video_comment.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `content` | TEXT |  |  |
| `author_id` | INTEGER |  |  |
| `video_id` | INTEGER |  |  |
| `parent_id` | INTEGER | ✓ |  |
| `created_at` | DATETIME | ✓ |  |
| `edited_at` | DATETIME | ✓ |  |

## VideoCommentLike

- **الجدول:** `video_comment_likes`
- **الملف:** `video_comment_like.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `user_id` | INTEGER |  |  |
| `comment_id` | INTEGER |  |  |
| `created_at` | DATETIME | ✓ |  |

## VideoLike

- **الجدول:** `video_likes`
- **الملف:** `video_like.py`

| العمود | النوع | Nullable | PK |
|---|---|---|---|
| `id` | INTEGER |  | ✓ |
| `user_id` | INTEGER |  |  |
| `video_id` | INTEGER |  |  |
| `created_at` | DATETIME | ✓ |  |
