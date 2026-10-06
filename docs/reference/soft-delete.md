# الحذف المنطقي (Soft Delete) في ANTER

**آخر تحديث:** 2026-10-06

## ما هو

عند «حذف» مستخدم من لوحة الأدمن، لا نحذف صفّه من قاعدة البيانات.
بدلًا من ذلك نضع علامات على `User`:

| العمود | المعنى |
|---|---|
| `is_deleted` | `True` = المستخدم محذوف |
| `deleted_at` | توقيت الحذف (UTC) |
| `is_active` | يُعطَّل أيضًا (`False`) |

## لماذا

الحذف الفعلي (`db.session.delete(user)`) يكسر قاعدة البيانات لأن المستخدم مرتبط بـ 20+ جدولًا:

- `messages`, `comment_likes`, `video_comment_likes`
- `reports`, `user_blocks`, `hidden_posts`
- `reposts`, `user_activities`, `push_subscriptions`
- `typing_states`, `call_logs`, `call_signals`
- `muted_conversations`, `stories`, `story_reactions`, `story_views`
- `mobile_access_tokens`, `mobile_browser_authorizations`
- `videos`, `video_comments`, `video_likes`
- `posts.wall_owner_id`

PostgreSQL يرفض الحذف لو وُجد قيد FK يشير إليه → `IntegrityError` → 500.

## قواعد أساسية

1. **البريد والهاتف يبقيان محجوزين** (unique constraint).
   - لا يستطيع أحد التسجيل بنفس البريد/الهاتف.
   - رسالة التسجيل: «هذا الحساب محذوف. لا يمكن التسجيل بنفس البريد.»
2. **تسجيل الدخول مرفوض**: `auth.py` يفحص `is_deleted` ويعرض رسالة واضحة.
3. **الأدمن يرى الكل**: `admin.py` بدون فلترة (للتصحيح والتراجع).
4. **العدّادات واقعية**: `post.like_count()` يحتسب المحذوفين (لأن الإعجاب حدث فعلًا).

## الأماكن المُغطّاة (23 نقطة)

| # | المكان | الملف |
|---|---|---|
| 1 | الملف الشخصي → 404 | `routes/users.py:profile` |
| 2 | الـ feed | `services/privacy.py:can_view_profile` |
| 3 | الاقتراحات | `services/privacy.py` |
| 4 | المتفاعلون الأخيرون | `__init__.py:get_recent_reaction_users` |
| 5 | نافذة التفاعلات | `routes/reactions.py:post_reactions_json` |
| 6 | بحث `/explore/search` | `routes/explore.py:search` |
| 7 | بحث `users/api/search` | `routes/users.py:search` |
| 8 | ترندات | `services/explore_service.py` |
| 9 | متابعة محذوف | `routes/users.py:follow` |
| 10 | شريط «متصلون» في الرسائل | `routes/messages.py:inbox` |
| 11 | صندوق الوارد | `routes/messages.py:inbox` |
| 12 | فتح محادثة | `routes/messages.py:chat` |
| 13 | قائمة المشاركة (رئيسية) | `routes/main.py:index` |
| 14 | قائمة المشاركة (ريلز) | `routes/videos.py:reels` |
| 15 | الإشارات `@username` | `utils/helpers.py` |
| 16 | القصص | `routes/stories.py:user_stories` |
| 17 | API profile | `routes/api.py:user_profile` |
| 18 | التعليقات (top-level) | `templates/comments.html` |
| 19 | الردود | `templates/comments.html` |
| 20 | الإشعارات (صفحة) | `routes/notifications.py:index` |
| 21 | عدّاد الإشعارات | `routes/notifications.py:unread_count` |
| 22 | تسجيل الدخول | `routes/auth.py:login` |
| 23 | التسجيل ببريد/هاتف محذوف | `forms/auth.py:validate_email/phone` |

## ما ليس مُغطّى (بتصميم)

- **عدّاد الإعجابات/التعليقات**: `post.like_count()` يحتسب المحذوفين.
- **مسارات API الداخلية**: `messages/send`, `messages/typing`, `messages/calls`.
  - لا تُعرض بصريًا، والـ frontend لا يستدعيها لأن `chat` مرفوض.
- **`/admin/users`**: الأدمن يرى كل شيء.
- **`delete_account`** (`routes/users.py`): ما زال حذفًا فعليًا — قرار مستقبل.

## كيف تُطبّق القاعدة على ميزة جديدة

عند إضافة استعلام يجلب مستخدمين للعرض، أضف:

```python
User.query.filter(User.is_deleted.is_(False)) أو في Python بعد الجلب:

```python
if getattr(user, 'is_deleted', False):
    continue  # أو return 404
```

القاعدة: لو الكود يعرض اسم/صورة/ملف مستخدم لمستخدم آخر — يجب أن يُفلتر.
لو الكود داخلي (typing, calls) — الفلترة اختيارية.

## الأعمدة في قاعدة البيانات

أُضيفت عبر `services/startup_maintenance.py`:

```python
'users': {
    ...
    'is_deleted': 'BOOLEAN NOT NULL DEFAULT FALSE',
    'deleted_at': 'TIMESTAMP',
}
```

على Render: STARTUP_SCHEMA_UPGRADES_ENABLED=true يُطبّقها عند الإقلاع.
