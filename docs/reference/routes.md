# مرجع المسارات (Routes)

**آخر تحديث:** 2026-10-23
**المجموع:** 235 route · 20 blueprint

## admin — `/admin`

- `GET` `/admin` — _admin.py_
- `POST` `/admin/account-requests/<int:request_id>/email-link` — _admin.py_
- `POST` `/admin/account-requests/<int:request_id>/password-link` — _admin.py_
- `POST` `/admin/account-requests/<int:request_id>/reject` — _admin.py_
- `GET` `/admin/posts` — _admin.py_
- `POST` `/admin/posts/delete/<int:post_id>` — _admin.py_
- `GET` `/admin/posts/view/<int:post_id>` — _admin.py_
- `GET` `/admin/reports` — _admin.py_
- `POST` `/admin/reports/delete/<int:report_id>` — _admin.py_
- `POST` `/admin/reports/reject/<int:report_id>` — _admin.py_
- `POST` `/admin/reports/resolve/<int:report_id>` — _admin.py_
- `GET` `/admin/support-requests` — _admin.py_
- `GET` `/admin/users` — _admin.py_
- `POST` `/admin/users/ban/<int:user_id>` — _admin.py_
- `POST` `/admin/users/delete/<int:user_id>` — _admin.py_
- `POST` `/admin/users/early-member/<int:user_id>` — _admin.py_
- `POST` `/admin/users/email-verify-link/<int:user_id>` — _admin.py_
- `POST` `/admin/users/make_admin/<int:user_id>` — _admin.py_
- `POST` `/admin/users/password-reset-link/<int:user_id>` — _admin.py_
- `POST` `/admin/users/phone-verify-link/<int:user_id>` — _admin.py_
- `POST` `/admin/users/send-email/<int:user_id>` — _admin.py_
- `POST` `/admin/users/suspend-24h/<int:user_id>` — _admin.py_
- `POST` `/admin/users/suspend-7d/<int:user_id>` — _admin.py_
- `POST` `/admin/users/toggle/<int:user_id>` — _admin.py_
- `POST` `/admin/users/unban/<int:user_id>` — _admin.py_
- `POST` `/admin/users/verify/<int:user_id>` — _admin.py_
- `GET` `/admin/verification-requests` — _admin.py_
- `POST` `/admin/verification-requests/<int:request_id>/approve` — _admin.py_
- `POST` `/admin/verification-requests/<int:request_id>/reject` — _admin.py_
- `GET` `/admin/videos` — _admin.py_
- `POST` `/admin/videos/delete/<int:video_id>` — _admin.py_

## ai — `/api`

- `POST` `/api/ai/assist` — _ai.py_
- `POST` `/api/ai/complete` — _ai.py_
- `GET` `/api/ai/summarize/<int:post_id>` — _ai.py_

## api

- `GET` `/moments` — _api.py_
- `GET` `/moments/<int:moment_id>` — _api.py_
- `GET` `/posts` — _api.py_
- `GET` `/users/<username>` — _api.py_
- `GET` `/videos/reels` — _api.py_

## auth — `/auth`

- `GET` `/auth/accounts` — _auth.py_
- `POST` `/auth/accounts/clear` — _auth.py_
- `POST` `/auth/accounts/remove/<int:user_id>` — _auth.py_
- `GET,POST` `/auth/login` — _auth.py_
- `GET` `/auth/logout` — _auth.py_
- `GET` `/auth/messenger/authorize` — _auth.py_
- `GET,POST` `/auth/register` — _auth.py_
- `GET,POST` `/auth/reset_password/<token>` — _auth.py_
- `GET,POST` `/auth/reset_password_request` — _auth.py_
- `POST` `/auth/switch` — _auth.py_
- `GET,POST` `/auth/switch-back-to-owner` — _auth.py_
- `POST` `/auth/switch-to-assistant` — _auth.py_

## explore — `/explore`

- `GET` `/explore` — _explore.py_
- `GET` `/explore/hashtag/<string:tag>` — _explore.py_
- `GET` `/explore/search` — _explore.py_
- `GET` `/explore/search-all` — _explore.py_

## haraj

- `GET` `/` — _haraj.py_
- `GET` `/admin/reports` — _haraj.py_
- `POST` `/admin/reports/<int:report_id>/<action>` — _haraj.py_
- `GET` `/api/cities` — _haraj.py_
- `POST` `/comment/<int:comment_id>/delete` — _haraj.py_
- `GET` `/listing/<public_id>` — _haraj.py_
- `POST` `/listing/<public_id>/comment` — _haraj.py_
- `POST` `/listing/<public_id>/contact` — _haraj.py_
- `POST` `/listing/<public_id>/delete` — _haraj.py_
- `GET,POST` `/listing/<public_id>/edit` — _haraj.py_
- `POST` `/listing/<public_id>/rate` — _haraj.py_
- `POST` `/listing/<public_id>/react` — _haraj.py_
- `POST` `/listing/<public_id>/renew` — _haraj.py_
- `POST` `/listing/<public_id>/report` — _haraj.py_
- `POST` `/listing/<public_id>/sold` — _haraj.py_
- `GET` `/media/listing/<int:image_id>` — _haraj.py_
- `GET` `/messages` — _haraj.py_
- `GET,POST` `/messages/<listing_public_id>/<other_username>` — _haraj.py_
- `GET` `/messages/unread_count` — _haraj.py_
- `GET` `/my-listings` — _haraj.py_
- `GET,POST` `/new` — _haraj.py_
- `GET` `/notifications` — _haraj.py_
- `POST` `/notifications/mark_all_read` — _haraj.py_
- `GET` `/notifications/unread_count` — _haraj.py_
- `GET` `/seller/<username>` — _haraj.py_
- `GET,POST` `/settings` — _haraj.py_
- `GET` `/terms` — _haraj.py_
- `GET` `/unread_total` — _haraj.py_

## main

- `GET` `/` — _main.py_
- `GET` `/about` — _main.py_
- `GET` `/admin` — _main.py_
- `GET` `/api/messenger/release` — _main.py_
- `GET` `/api/posts` — _main.py_
- `GET` `/api/users` — _main.py_
- `GET` `/d5a1393ec6a04f07aaacd9561975b833.txt` — _main.py_
- `GET` `/google-site-verification-7Uaxo4sE9avUI6VqAsGp-ldxoslHE10dRIa2Q-Skak0.html` — _main.py_
- `GET` `/google314e5a2210182885.html` — _main.py_
- `GET` `/googleC7pvqXYOiyvCVZLYRAyUb48doCONYF_GTzyQqPSUKfk.html` — _main.py_
- `GET,POST` `/help` — _main.py_
- `GET` `/login` — _main.py_
- `GET` `/offline.html` — _main.py_
- `GET` `/privacy` — _main.py_
- `GET` `/profile` — _main.py_
- `GET` `/register` — _main.py_
- `GET` `/robots.txt` — _main.py_
- `GET` `/settings` — _main.py_
- `GET` `/sitemap.xml` — _main.py_
- `GET` `/terms` — _main.py_
- `POST` `/update_interests` — _main.py_

## media — `/media`

- `GET` `/media/avatar/<int:user_id>` — _media.py_
- `GET` `/media/p/<public_id>` — _media.py_
- `GET` `/media/post/<int:post_id>` — _media.py_
- `GET` `/media/story/<int:story_id>` — _media.py_
- `GET` `/media/video-thumb/<public_id>` — _media.py_
- `GET` `/media/video/<public_id>` — _media.py_

## messages — `/messages`

- `GET` `/messages` — _messages.py_
- `GET` `/messages/<int:user_id>` — _messages.py_
- `POST` `/messages/assistant-memory/<int:user_id>/clear` — _messages.py_
- `GET` `/messages/attachment/<int:message_id>` — _messages.py_
- `GET` `/messages/audio/<int:message_id>` — _messages.py_
- `GET` `/messages/calls/pending` — _messages.py_
- `GET` `/messages/calls/poll/<int:user_id>` — _messages.py_
- `POST` `/messages/calls/signal/<int:user_id>` — _messages.py_
- `POST` `/messages/delete/<int:message_id>` — _messages.py_
- `POST` `/messages/forward/<int:message_id>` — _messages.py_
- `POST` `/messages/report/<int:message_id>` — _messages.py_
- `POST` `/messages/safety/<int:user_id>/block` — _messages.py_
- `POST` `/messages/safety/<int:user_id>/mute` — _messages.py_
- `POST` `/messages/send-audio/<int:user_id>` — _messages.py_
- `POST` `/messages/send/<int:user_id>` — _messages.py_
- `POST` `/messages/typing/<int:user_id>` — _messages.py_
- `GET` `/messages/typing/<int:user_id>` — _messages.py_
- `GET` `/messages/unread_count` — _messages.py_

## mobile_api — `/api/mobile`

- `POST` `/api/mobile/auth/browser/exchange` — _mobile_api.py_
- `POST` `/api/mobile/auth/login` — _mobile_api.py_
- `POST` `/api/mobile/auth/logout` — _mobile_api.py_
- `GET` `/api/mobile/blocked-users` — _mobile_api.py_
- `GET` `/api/mobile/calls` — _mobile_api.py_
- `POST` `/api/mobile/calls/<string:username>/signal` — _mobile_api.py_
- `GET` `/api/mobile/contacts` — _mobile_api.py_
- `GET` `/api/mobile/conversations` — _mobile_api.py_
- `GET` `/api/mobile/conversations/<string:username>/activity` — _mobile_api.py_
- `POST` `/api/mobile/conversations/<string:username>/assistant-memory/clear` — _mobile_api.py_
- `POST` `/api/mobile/conversations/<string:username>/block` — _mobile_api.py_
- `GET` `/api/mobile/conversations/<string:username>/messages` — _mobile_api.py_
- `POST` `/api/mobile/conversations/<string:username>/messages` — _mobile_api.py_
- `POST` `/api/mobile/conversations/<string:username>/mute` — _mobile_api.py_
- `GET` `/api/mobile/conversations/<string:username>/safety` — _mobile_api.py_
- `POST` `/api/mobile/conversations/<string:username>/typing` — _mobile_api.py_
- `GET` `/api/mobile/devices` — _mobile_api.py_
- `DELETE` `/api/mobile/devices/<int:device_id>` — _mobile_api.py_
- `POST` `/api/mobile/find-friends` — _mobile_api.py_
- `GET` `/api/mobile/me` — _mobile_api.py_
- `DELETE` `/api/mobile/messages/<int:message_id>` — _mobile_api.py_
- `GET` `/api/mobile/messages/<int:message_id>/attachment` — _mobile_api.py_
- `POST` `/api/mobile/messages/<int:message_id>/forward` — _mobile_api.py_
- `POST` `/api/mobile/messages/<int:message_id>/report` — _mobile_api.py_
- `GET` `/api/mobile/settings` — _mobile_api.py_
- `POST` `/api/mobile/settings` — _mobile_api.py_
- `POST` `/api/mobile/suggested-follows` — _mobile_api.py_
- `GET` `/api/mobile/users/<string:username>` — _mobile_api.py_
- `POST` `/api/mobile/users/<string:username>/block` — _mobile_api.py_
- `DELETE` `/api/mobile/users/<string:username>/block` — _mobile_api.py_
- `POST` `/api/mobile/users/<string:username>/report` — _mobile_api.py_

## moments

- `GET` `/` — _moments.py_
- `GET` `/<int:moment_id>` — _moments.py_

## notifications — `/notifications`

- `GET` `/notifications` — _notifications.py_
- `POST` `/notifications/delete/<int:notification_id>` — _notifications.py_
- `GET` `/notifications/latest` — _notifications.py_
- `POST` `/notifications/mark_all_read` — _notifications.py_
- `POST` `/notifications/mark_read/<int:notification_id>` — _notifications.py_
- `POST` `/notifications/mark_unread/<int:notification_id>` — _notifications.py_
- `POST` `/notifications/subscribe` — _notifications.py_
- `GET` `/notifications/unread_count` — _notifications.py_
- `POST` `/notifications/unsubscribe` — _notifications.py_

## posts

- `POST` `/comment/<int:comment_id>/delete` — _posts.py_
- `POST` `/comment/<int:comment_id>/edit` — _posts.py_
- `POST` `/comment/<int:post_id>` — _posts.py_
- `GET` `/comments/<int:post_id>/fragment` — _posts.py_
- `GET,POST` `/create` — _posts.py_
- `POST` `/delete/<int:post_id>` — _posts.py_
- `GET,POST` `/edit/<int:post_id>` — _posts.py_
- `POST` `/hide/<int:post_id>` — _posts.py_
- `POST` `/like/<int:post_id>` — _posts.py_
- `POST` `/like_comment/<int:comment_id>` — _posts.py_
- `GET` `/p/<public_id>` — _posts.py_
- `POST` `/p/<public_id>/appeal` — _posts.py_
- `GET` `/post/<int:post_id>` — _posts.py_
- `POST` `/report` — _posts.py_
- `POST` `/report/<int:post_id>` — _posts.py_
- `POST` `/repost/<int:post_id>` — _posts.py_
- `POST` `/share-video/<int:video_id>` — _posts.py_
- `POST` `/wall/<username>` — _posts.py_

## reactions

- `GET` `/post/<int:post_id>/reactions.json` — _reactions.py_

## sse — `/sse`

- `GET` `/sse/notifications` — _sse.py_

## stories — `/api`

- `POST` `/api/stories` — _stories.py_
- `DELETE` `/api/stories/<int:story_id>` — _stories.py_
- `POST` `/api/stories/<int:story_id>/react` — _stories.py_
- `POST` `/api/stories/<int:story_id>/view` — _stories.py_
- `GET` `/api/stories/<int:story_id>/viewers` — _stories.py_
- `GET` `/api/stories/feed` — _stories.py_
- `GET` `/api/user-stories/<int:user_id>` — _stories.py_

## trends — `/trends`

- `GET` `/trends` — _trends.py_

## users — `/users`

- `GET` `/users/<username>` — _users.py_
- `GET` `/users/<username>/followers` — _users.py_
- `GET` `/users/<username>/following` — _users.py_
- `POST` `/users/<username>/report` — _users.py_
- `GET` `/users/<username>/videos` — _users.py_
- `GET` `/users/activity` — _users.py_
- `GET` `/users/api/search` — _users.py_
- `POST` `/users/change-avatar` — _users.py_
- `POST` `/users/delete_account` — _users.py_
- `GET` `/users/download_data` — _users.py_
- `GET,POST` `/users/edit` — _users.py_
- `POST` `/users/find-friends` — _users.py_
- `POST` `/users/follow/<int:user_id>` — _users.py_
- `POST` `/users/set-avatar-from-post/<int:post_id>` — _users.py_
- `GET,POST` `/users/settings` — _users.py_
- `POST` `/users/settings/bio` — _users.py_
- `GET,POST` `/users/settings/email/verify/<token>` — _users.py_
- `POST` `/users/settings/email/verify/send` — _users.py_
- `GET,POST` `/users/settings/phone/verify/<token>` — _users.py_
- `POST` `/users/unfollow/<int:user_id>` — _users.py_
- `POST` `/users/verification-request` — _users.py_

## videos — `/videos`

- `POST` `/videos/comment/<int:comment_id>/delete` — _videos.py_
- `POST` `/videos/comment/<int:comment_id>/edit` — _videos.py_
- `POST` `/videos/comment/<int:video_id>` — _videos.py_
- `GET` `/videos/comments/<int:video_id>` — _videos.py_
- `POST` `/videos/delete/<int:video_id>` — _videos.py_
- `POST` `/videos/like/<int:video_id>` — _videos.py_
- `POST` `/videos/like_comment/<int:comment_id>` — _videos.py_
- `GET` `/videos/r/<public_id>` — _videos.py_
- `GET` `/videos/reels` — _videos.py_
- `POST` `/videos/report/<int:video_id>` — _videos.py_
- `GET,POST` `/videos/upload` — _videos.py_
- `POST` `/videos/view/<public_id>` — _videos.py_
- `GET` `/videos/watch/<int:video_id>` — _videos.py_

## year_in_review

- `GET` `/year-in-review` — _year_in_review.py_
- `GET` `/year-in-review/<int:year>` — _year_in_review.py_
- `GET` `/year-in-review/<int:year>/card.png` — _year_in_review.py_
