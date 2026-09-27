# مرجع الخدمات (Services)

**آخر تحديث:** 2026-09-27
**المجموع:** 16 خدمة

## ai_service.py

**الفئات:** AIService

**دوال الفئات (methods):**
- `._settings()`
- `._clean_response()`
- `._system_prompt()`
- `.generate_response()`
- `._clean_source()`
- `.summarize_text()`
- `.suggest_comment()`
- `.suggest_post()`
- `.improve_text()`

## anter_account_switching.py

**دوال مستقلة:**
- `is_switch_owner()`
- `get_managed_assistant()`
- `can_switch_to_assistant()`
- `can_switch_back()`
- `db_get_user()`

## anter_assistant.py

**دوال مستقلة:**
- `_messenger_download_reply()`
- `is_anter_assistant()`
- `ensure_anter_assistant_user()`
- `follow_anter_assistant_for_user()`
- `ensure_anter_assistant_followed_by_all_users()`
- `_clean_question()`
- `_clean_answer()`
- `_direct_anter_reply()`
- `_assistant_system_prompt()`
- `_safe_provider_error()`
- `get_assistant_reply()`

## anter_daily_publication.py

**دوال مستقلة:**
- `anter_today()`
- `ensure_daily_assistant_post()`

## anter_memory.py

**دوال مستقلة:**
- `_clean_text()`
- `_load_list()`
- `_save_list()`
- `_get_memory()`
- `_is_sensitive()`
- `is_memory_clear_request()`
- `display_name()`
- `_append_context()`
- `remember_user_message()`
- `remember_assistant_reply()`
- `recent_conversation()`
- `conversation_for_ai()`
- `clear_memory()`
- `preference_values()`
- `role_description()`
- `recent_user_context()`
- `_prior_user_messages()`
- `local_memory_reply()`

## anter_user_messages.py

**دوال مستقلة:**
- `_already_sent()`
- `send_welcome_message()`
- `send_report_receipt()`

## explore_service.py

**دوال مستقلة:**
- `_hot_score()`
- `_post_engagement()`
- `_reel_engagement()`
- `trending_posts()`
- `trending_reels()`
- `trending_users()`
- `normalize_arabic()`
- `search_users()`

**دوال الفئات (methods):**
- `._score()`

## feed_ranker.py

**دوال مستقلة:**
- `freshness_score()`
- `engagement_score()`
- `interest_score()`
- `relationship_score()`
- `geo_score()`
- `rank_post()`

## geo_ranker.py

**دوال مستقلة:**
- `normalize_country_code()`
- `country_score()`
- `geo_score_for_post()`
- `geo_score_for_user()`

## message_safety.py

**دوال مستقلة:**
- `is_blocked_between()`
- `blocked_counterparty_ids()`
- `block_user()`
- `unblock_user()`

## mobile_api_auth.py

**دوال مستقلة:**
- `_token_hash()`
- `issue_mobile_token()`
- `issue_mobile_browser_authorization()`
- `exchange_mobile_browser_authorization()`
- `revoke_mobile_token()`
- `current_mobile_token()`
- `mobile_api_required()`

**دوال الفئات (methods):**
- `.wrapped()`

## moment_detector.py

**دوال مستقلة:**
- `_normalize_hashtag()`
- `_post_hashtags()`
- `find_matching_moment()`
- `detect_for_post()`

## owner_admin.py

**دوال مستقلة:**
- `ensure_configured_owner_is_admin()`

## privacy.py

**دوال مستقلة:**
- `is_owner_or_admin()`
- `follows()`
- `can_view_profile()`
- `can_view_post()`
- `can_post_on_wall()`
- `visible_posts()`

## reels_ranker.py

**دوال مستقلة:**
- `_activity_video_ids()`
- `_followed_author_ids()`
- `_score_video()`
- `rank_reels()`

## startup_maintenance.py

**دوال مستقلة:**
- `should_run_schema_upgrades()`
- `run_startup_schema_upgrades()`
