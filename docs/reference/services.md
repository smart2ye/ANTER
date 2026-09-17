# مرجع الخدمات (Services)

**آخر تحديث:** 2026-09-17
**المجموع:** 18 خدمة في app/services/

## AI والمحتوى الذكي

### ai_service.py
- AIService — واجهة mini-llm Arabic
- generate_response(prompt, max_tokens)
- suggest_post, improve_text, suggest_comment
- النموذج: qwen/qwen3.8-27b (Groq)
- URL: https://api.groq.com/openai/v1/chat/completions

### anter_assistant.py
- إدارة حساب "مساعد أنتر"
- ensure_anter_assistant_user()
- get_assistant_reply()
- is_anter_assistant(user)

### anter_memory.py
- ذاكرة المساعد لكل مستخدم
- remember_user_message, remember_assistant_reply
- local_memory_reply

### anter_daily_publication.py
- منشور يومي تلقائي
- ensure_daily_assistant_post()

### anter_user_messages.py
- رسائل ترحيب
- send_welcome_message, send_report_receipt

### anter_account_switching.py
- تبديل بين المالك والمساعد
- can_switch_to_assistant, can_switch_back

## الترتيب والتوصية

### feed_ranker.py
- ترتيب منشورات الـFeed
- rank_post(created_at, likes, comments, reposts, similarity, is_following, is_own_post)
- مكونات: Freshness (36h) + Engagement + Interest + Relationship

### reels_ranker.py
- ترتيب الريلز
- rank_reels(user, limit, exclude_ids)
- إشارات: متابع (+35), like (+18), comment (+22)
- engagement: likes×1.5, comments×2.5, shares×3
- freshness: 24h (+18), 72h (+12), 168h (+7)

### moment_detector.py
- كشف ANTER Moments
- detect_for_post(post)
- الشروط: 3 منشورات على الأقل بنفس الهاشتاق خلال 24 ساعة

## السلامة والخصوصية

### message_safety.py
- is_blocked_between(a, b)
- blocked_counterparty_ids
- block_user, unblock_user

### privacy.py
- can_view_profile, can_view_post, visible_posts
- is_owner_or_admin, follows

## المصادقة

### mobile_api_auth.py
- issue_mobile_token(user, device_name)
- current_mobile_token()
- mobile_api_required (decorator)
- Tokens: SHA-256 hash فقط

### owner_admin.py
- ensure_configured_owner_is_admin()

## الصيانة

### startup_maintenance.py
- run_startup_schema_upgrades(app)
- يضمن وجود أعمدة/جداول جديدة

## الملفات المساعدة (app/utils/)

### email.py
- Resend API (verify, reset, welcome)
- send_reset_email, send_email_verification
- send_welcome_email, send_password_change_confirmation

### helpers.py
- save_uploaded_image, save_video_file, save_audio_file
- create_thumbnail
- extract_hashtags, process_hashtags
- extract_link_metadata
- parse_mentions
- log_user_activity
- get_user_activity_summary
- get_user_status, get_status_icon
- allowed_file, allowed_audio_file, allowed_video_file

### image_storage.py
- prepare_image_data — يقص + يضغط

### media_urls.py
- avatar_url(user) — يفضّل BLOB
- post_image_url(post)

### public_ids.py
- generate_public_id(prefix) — p_xxx للمنشورات، r_xxx للريلز

### story_cleanup.py
- delete_expired_stories(app)

### profile_text.py
- normalize_bio(value)
