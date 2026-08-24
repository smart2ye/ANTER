import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse


_TEST_DB = os.path.join(tempfile.gettempdir(), "anter_assistant_feature_test.db")
try:
    os.remove(_TEST_DB)
except FileNotFoundError:
    pass

os.environ["DATABASE_URL"] = "sqlite:///" + _TEST_DB
os.environ["ADMIN_PATH"] = "admin-antar-assistant-test"
os.environ["MINI_LLM_ARABIC_API_KEY"] = "test-mini-llm-key"
os.environ["MINI_LLM_ARABIC_MODEL"] = "qwen/qwen3.6-27b"

from app import _get_admin_path, create_app
from app.extensions import db
from app.forms.auth import ResetPasswordForm
from app.models import AssistantDailyPublication, AssistantMemory, CallLog, Comment, CommentLike, Follow, Like, Message, MobileAccessToken, MutedConversation, Notification, OwnerAdminBootstrap, Post, Report, Repost, TypingState, User, UserActivity, UserBlock
from app.services.anter_assistant import (
    ensure_anter_assistant_user,
    get_assistant_reply,
)
from app.services.anter_memory import remember_assistant_reply, remember_user_message, recent_conversation
from app.services.anter_daily_publication import ensure_daily_assistant_post
from app.services.anter_assistant import (
    ensure_anter_assistant_followed_by_all_users,
    follow_anter_assistant_for_user,
)
from app.utils.helpers import get_user_status, log_user_activity
from app.utils.media_urls import avatar_url


class AnterAssistantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            ANTER_ASSISTANT_ENABLED=True,
            ANTER_ASSISTANT_MINI_LLM_ARABIC_API_KEY="test-mini-llm-key",
            ANTER_ASSISTANT_MINI_LLM_ARABIC_MODEL="qwen/qwen3.6-27b",
            ANTER_ASSISTANT_MINI_LLM_ARABIC_MAX_TOKENS=700,
        )
        with cls.app.app_context():
            cls.assistant = ensure_anter_assistant_user()
            user = User.query.filter_by(username="assistant_test_user").first()
            if user is None:
                user = User(
                    username="assistant_test_user",
                    email="assistant-test-user@example.test",
                    name="مستخدم اختبار",
                    terms_agreed=True,
                )
                user.set_password("not-used-in-test")
                db.session.add(user)
                db.session.commit()
            cls.user_id = user.id
            cls.assistant_id = cls.assistant.id
            # يتابع مستخدم الاختبار المساعد افتراضياً، كما تفعل عملية التسجيل الفعلية.
            if follow_anter_assistant_for_user(user, cls.assistant):
                db.session.commit()

    def setUp(self):
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True

    def test_bootstrap_creates_verified_assistant_account(self):
        with self.app.app_context():
            assistant = User.query.get(self.assistant_id)
            self.assertIsNotNone(assistant)
            self.assertEqual(assistant.username, self.app.config["ANTER_ASSISTANT_USERNAME"])
            self.assertTrue(assistant.is_verified)
            self.assertEqual(assistant.message_privacy, "everyone")

    def test_mobile_api_authenticates_device_and_delivers_messages_between_mutual_follows(self):
        with self.app.app_context():
            sender = User.query.get(self.user_id)
            receiver = User.query.filter_by(username='mobile_api_receiver').first()
            if receiver is None:
                receiver = User(
                    username='mobile_api_receiver',
                    email='mobile-api-receiver@example.test',
                    name='مستلم API',
                    terms_agreed=True,
                )
                receiver.set_password('receiver-test-password')
                db.session.add(receiver)
                db.session.flush()
            if not sender.is_following(receiver):
                db.session.add(Follow(follower_id=sender.id, followed_id=receiver.id))
            if not receiver.is_following(sender):
                db.session.add(Follow(follower_id=receiver.id, followed_id=sender.id))
            db.session.commit()
            receiver_id = receiver.id

        sender_login = self.client.post('/api/mobile/v1/auth/login', json={
            'identifier': 'assistant_test_user',
            'password': 'not-used-in-test',
            'deviceName': 'هاتف المرسل',
        })
        self.assertEqual(sender_login.status_code, 201)
        sender_token = sender_login.get_json()['accessToken']
        self.assertGreater(len(sender_token), 40)
        with self.app.app_context():
            stored = MobileAccessToken.query.filter_by(user_id=self.user_id).order_by(MobileAccessToken.id.desc()).first()
            self.assertIsNotNone(stored)
            self.assertNotEqual(stored.token_hash, sender_token)

        receiver_client = self.app.test_client()
        receiver_login = receiver_client.post('/api/mobile/v1/auth/login', json={
            'identifier': 'mobile_api_receiver',
            'password': 'receiver-test-password',
        })
        self.assertEqual(receiver_login.status_code, 201)
        receiver_token = receiver_login.get_json()['accessToken']

        sender_headers = {'Authorization': f'Bearer {sender_token}'}
        receiver_headers = {'Authorization': f'Bearer {receiver_token}'}
        send_response = self.client.post(
            '/api/mobile/v1/conversations/mobile_api_receiver/messages',
            headers=sender_headers,
            json={'content': 'رسالة حية من تطبيق ANTER Messenger'},
        )
        self.assertEqual(send_response.status_code, 201)
        message_id = send_response.get_json()['message']['id']

        receive_response = receiver_client.get(
            '/api/mobile/v1/conversations/assistant_test_user/messages',
            headers=receiver_headers,
        )
        self.assertEqual(receive_response.status_code, 200)
        messages = receive_response.get_json()['messages']
        self.assertTrue(any(item['id'] == message_id and item['content'].startswith('رسالة حية') for item in messages))
        with self.app.app_context():
            self.assertTrue(Message.query.get(message_id).is_read)
            self.assertEqual(User.query.get(receiver_id).username, 'mobile_api_receiver')

    def test_browser_authorization_exchanges_one_time_code_without_sending_password_to_messenger(self):
        redirect_uri = self.app.config['MOBILE_BROWSER_AUTH_REDIRECT_URI']
        state = 'browser-state-test-123'
        authorize = self.client.get(
            '/auth/messenger/authorize',
            query_string={'redirect_uri': redirect_uri, 'state': state, 'device_name': 'اختبار Android'},
            follow_redirects=False,
        )
        self.assertEqual(authorize.status_code, 302)
        callback = urlparse(authorize.headers['Location'])
        callback_query = parse_qs(callback.query)
        self.assertEqual(f'{callback.scheme}://{callback.netloc}{callback.path}', redirect_uri)
        self.assertEqual(callback_query['state'][0], state)

        exchange = self.client.post('/api/mobile/v1/auth/browser/exchange', json={
            'code': callback_query['code'][0],
            'state': state,
            'redirectUri': redirect_uri,
        })
        self.assertEqual(exchange.status_code, 201)
        self.assertIn('accessToken', exchange.get_json())

        reused = self.client.post('/api/mobile/v1/auth/browser/exchange', json={
            'code': callback_query['code'][0],
            'state': state,
            'redirectUri': redirect_uri,
        })
        self.assertEqual(reused.status_code, 401)

    def test_messenger_release_endpoint_exposes_the_official_download_metadata(self):
        response = self.client.get('/api/messenger/release')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['version'], self.app.config['ANTER_MESSENGER_VERSION'])
        self.assertEqual(payload['downloadUrl'], self.app.config['ANTER_MESSENGER_APK_URL'])
        self.assertEqual(payload['sha256'], self.app.config['ANTER_MESSENGER_APK_SHA256'])

    def test_mobile_api_blocks_messages_without_mutual_follow(self):
        with self.app.app_context():
            outsider = User.query.filter_by(username='mobile_api_outsider').first()
            if outsider is None:
                outsider = User(
                    username='mobile_api_outsider',
                    email='mobile-api-outsider@example.test',
                    name='حساب غير متابع',
                    terms_agreed=True,
                )
                outsider.set_password('outsider-test-password')
                db.session.add(outsider)
                db.session.commit()

        login_response = self.client.post('/api/mobile/v1/auth/login', json={
            'identifier': 'assistant_test_user',
            'password': 'not-used-in-test',
        })
        token = login_response.get_json()['accessToken']
        response = self.client.post(
            '/api/mobile/v1/conversations/mobile_api_outsider/messages',
            headers={'Authorization': f'Bearer {token}'},
            json={'content': 'محاولة يجب منعها'},
        )
        self.assertEqual(response.status_code, 403)

    def test_mobile_api_shares_typing_and_read_state_only_between_mutual_follows(self):
        with self.app.app_context():
            sender = User.query.get(self.user_id)
            receiver = User.query.filter_by(username='mobile_api_typing_peer').first()
            if receiver is None:
                receiver = User(
                    username='mobile_api_typing_peer',
                    email='mobile-api-typing-peer@example.test',
                    name='طرف اختبار الكتابة',
                    terms_agreed=True,
                )
                receiver.set_password('typing-peer-password')
                db.session.add(receiver)
                db.session.flush()
            if not sender.is_following(receiver):
                db.session.add(Follow(follower_id=sender.id, followed_id=receiver.id))
            if not receiver.is_following(sender):
                db.session.add(Follow(follower_id=receiver.id, followed_id=sender.id))
            TypingState.query.filter_by(sender_id=sender.id, receiver_id=receiver.id).delete()
            db.session.commit()

        sender_login = self.client.post('/api/mobile/v1/auth/login', json={
            'identifier': 'assistant_test_user', 'password': 'not-used-in-test'
        })
        receiver_client = self.app.test_client()
        receiver_login = receiver_client.post('/api/mobile/v1/auth/login', json={
            'identifier': 'mobile_api_typing_peer', 'password': 'typing-peer-password'
        })
        sender_headers = {'Authorization': f"Bearer {sender_login.get_json()['accessToken']}"}
        receiver_headers = {'Authorization': f"Bearer {receiver_login.get_json()['accessToken']}"}

        typing_start = self.client.post(
            '/api/mobile/v1/conversations/mobile_api_typing_peer/typing',
            headers=sender_headers, json={'isTyping': True},
        )
        self.assertEqual(typing_start.status_code, 200)
        activity = receiver_client.get(
            '/api/mobile/v1/conversations/assistant_test_user/activity', headers=receiver_headers,
        )
        self.assertEqual(activity.status_code, 200)
        self.assertTrue(activity.get_json()['isTyping'])

        sent = self.client.post(
            '/api/mobile/v1/conversations/mobile_api_typing_peer/messages',
            headers=sender_headers, json={'content': 'تحقق من حالة القراءة'},
        )
        message_id = sent.get_json()['message']['id']
        receiver_client.get('/api/mobile/v1/conversations/assistant_test_user/messages', headers=receiver_headers)
        sender_view = self.client.get(
            '/api/mobile/v1/conversations/mobile_api_typing_peer/messages', headers=sender_headers,
        )
        read_message = next(row for row in sender_view.get_json()['messages'] if row['id'] == message_id)
        self.assertTrue(read_message['isRead'])

        typing_stop = self.client.post(
            '/api/mobile/v1/conversations/mobile_api_typing_peer/typing',
            headers=sender_headers, json={'isTyping': False},
        )
        self.assertEqual(typing_stop.status_code, 200)
        activity_after = receiver_client.get(
            '/api/mobile/v1/conversations/assistant_test_user/activity', headers=receiver_headers,
        )
        self.assertFalse(activity_after.get_json()['isTyping'])

    def test_mobile_api_sending_text_to_assistant_stores_assistant_reply(self):
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            assistant = db.session.get(User, self.assistant_id)
            if not user.is_following(assistant):
                db.session.add(Follow(follower_id=user.id, followed_id=assistant.id))
            if not assistant.is_following(user):
                db.session.add(Follow(follower_id=assistant.id, followed_id=user.id))
            db.session.commit()
            assistant_username = assistant.username

        login_response = self.client.post('/api/mobile/v1/auth/login', json={
            'identifier': 'assistant_test_user', 'password': 'not-used-in-test'
        })
        token = login_response.get_json()['accessToken']
        with patch(
            'app.routes.mobile_api.get_assistant_reply',
            return_value=('مرحباً، أنا مساعد أنتر.', None),
        ):
            response = self.client.post(
                f'/api/mobile/v1/conversations/{assistant_username}/messages',
                headers={'Authorization': f'Bearer {token}'},
                json={'content': 'مرحبا'},
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['assistantMessage']['content'], 'مرحباً، أنا مساعد أنتر.')
        with self.app.app_context():
            messages = Message.query.filter(
                ((Message.sender_id == self.user_id) & (Message.receiver_id == self.assistant_id))
                | ((Message.sender_id == self.assistant_id) & (Message.receiver_id == self.user_id))
            ).order_by(Message.created_at.asc()).all()
            self.assertGreaterEqual(len(messages), 2)
            self.assertEqual(messages[-1].sender_id, self.assistant_id)
            self.assertEqual(messages[-1].content, 'مرحباً، أنا مساعد أنتر.')
            self.assertEqual(messages[-1].parent_id, messages[-2].id)

    def test_mobile_api_clears_only_current_users_assistant_memory(self):
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            assistant = db.session.get(User, self.assistant_id)
            if not user.is_following(assistant):
                db.session.add(Follow(follower_id=user.id, followed_id=assistant.id))
            if not assistant.is_following(user):
                db.session.add(Follow(follower_id=assistant.id, followed_id=user.id))
            db.session.commit()
            remember_user_message(user, assistant, 'أريد أن تتذكر اسمي المفضل.')
            self.assertTrue(AssistantMemory.query.filter_by(user_id=user.id, assistant_id=assistant.id).count())
            assistant_username = assistant.username

        login_response = self.client.post('/api/mobile/v1/auth/login', json={
            'identifier': 'assistant_test_user', 'password': 'not-used-in-test'
        })
        response = self.client.post(
            f'/api/mobile/v1/conversations/{assistant_username}/assistant-memory/clear',
            headers={'Authorization': f"Bearer {login_response.get_json()['accessToken']}"},
        )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(AssistantMemory.query.filter_by(user_id=self.user_id, assistant_id=self.assistant_id).count(), 0)

    def test_mobile_api_supports_reply_and_sender_only_delete_everyone(self):
        with self.app.app_context():
            sender = db.session.get(User, self.user_id)
            receiver = User.query.filter_by(username='mobile_api_reply_receiver').first()
            if receiver is None:
                receiver = User(username='mobile_api_reply_receiver', email='mobile-reply@example.test', name='مستلم الرد', terms_agreed=True)
                receiver.set_password('reply-receiver-password')
                db.session.add(receiver)
                db.session.flush()
            if not sender.is_following(receiver):
                db.session.add(Follow(follower_id=sender.id, followed_id=receiver.id))
            if not receiver.is_following(sender):
                db.session.add(Follow(follower_id=receiver.id, followed_id=sender.id))
            db.session.commit()

        sender_login = self.client.post('/api/mobile/v1/auth/login', json={'identifier': 'assistant_test_user', 'password': 'not-used-in-test'})
        receiver_client = self.app.test_client()
        receiver_login = receiver_client.post('/api/mobile/v1/auth/login', json={'identifier': 'mobile_api_reply_receiver', 'password': 'reply-receiver-password'})
        sender_headers = {'Authorization': f"Bearer {sender_login.get_json()['accessToken']}"}
        receiver_headers = {'Authorization': f"Bearer {receiver_login.get_json()['accessToken']}"}
        original = self.client.post('/api/mobile/v1/conversations/mobile_api_reply_receiver/messages', headers=sender_headers, json={'content': 'رسالة أصلية'}).get_json()['message']
        reply = receiver_client.post('/api/mobile/v1/conversations/assistant_test_user/messages', headers=receiver_headers, json={'content': 'هذا رد', 'parentId': original['id']})
        self.assertEqual(reply.status_code, 201)
        sender_rows = self.client.get('/api/mobile/v1/conversations/mobile_api_reply_receiver/messages', headers=sender_headers).get_json()['messages']
        saved_reply = next(row for row in sender_rows if row['id'] == reply.get_json()['message']['id'])
        self.assertEqual(saved_reply['parent']['id'], original['id'])
        self.assertEqual(saved_reply['parent']['content'], 'رسالة أصلية')
        self.assertEqual(receiver_client.delete(f"/api/mobile/v1/messages/{original['id']}", headers=receiver_headers, json={'scope': 'everyone'}).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/mobile/v1/messages/{original['id']}", headers=sender_headers, json={'scope': 'everyone'}).status_code, 200)

    def test_mobile_api_forwards_only_participants_message_to_mutual_follow(self):
        with self.app.app_context():
            sender = db.session.get(User, self.user_id)
            source = User.query.filter_by(username='mobile_api_forward_source').first()
            target = User.query.filter_by(username='mobile_api_forward_target').first()
            for username, email, name, password in [
                ('mobile_api_forward_source', 'mobile-forward-source@example.test', 'مرسل المصدر', 'forward-source-password'),
                ('mobile_api_forward_target', 'mobile-forward-target@example.test', 'مستلم التحويل', 'forward-target-password'),
            ]:
                if User.query.filter_by(username=username).first() is None:
                    account = User(username=username, email=email, name=name, terms_agreed=True)
                    account.set_password(password)
                    db.session.add(account)
            db.session.flush()
            source = User.query.filter_by(username='mobile_api_forward_source').first()
            target = User.query.filter_by(username='mobile_api_forward_target').first()
            for account in (source, target):
                if not sender.is_following(account):
                    db.session.add(Follow(follower_id=sender.id, followed_id=account.id))
                if not account.is_following(sender):
                    db.session.add(Follow(follower_id=account.id, followed_id=sender.id))
            db.session.commit()

        login = self.client.post('/api/mobile/v1/auth/login', json={'identifier': 'assistant_test_user', 'password': 'not-used-in-test'})
        headers = {'Authorization': f"Bearer {login.get_json()['accessToken']}"}
        original = self.client.post('/api/mobile/v1/conversations/mobile_api_forward_source/messages', headers=headers, json={'content': 'نص قابل لإعادة التوجيه'}).get_json()['message']
        forwarded = self.client.post(f"/api/mobile/v1/messages/{original['id']}/forward", headers=headers, json={'targetUsername': 'mobile_api_forward_target'})
        self.assertEqual(forwarded.status_code, 201)
        self.assertEqual(forwarded.get_json()['message']['content'], 'نص قابل لإعادة التوجيه')
        target_client = self.app.test_client()
        target_login = target_client.post('/api/mobile/v1/auth/login', json={'identifier': 'mobile_api_forward_target', 'password': 'forward-target-password'})
        rows = target_client.get('/api/mobile/v1/conversations/assistant_test_user/messages', headers={'Authorization': f"Bearer {target_login.get_json()['accessToken']}"}).get_json()['messages']
        self.assertTrue(any(row['id'] == forwarded.get_json()['message']['id'] for row in rows))

    def test_message_safety_block_mute_and_report_routes_enforce_participant_rules(self):
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            other = User.query.filter_by(username='message_safety_other').first()
            outsider = User.query.filter_by(username='message_safety_outsider').first()
            if other is None:
                other = User(username='message_safety_other', email='message-safety-other@example.test', name='طرف المحادثة', terms_agreed=True)
                other.set_password('message-safety-other-password')
                db.session.add(other)
            if outsider is None:
                outsider = User(username='message_safety_outsider', email='message-safety-outsider@example.test', name='مستخدم خارجي', terms_agreed=True)
                outsider.set_password('message-safety-outsider-password')
                db.session.add(outsider)
            db.session.flush()
            for follower_id, followed_id in ((user.id, other.id), (other.id, user.id)):
                if Follow.query.filter_by(follower_id=follower_id, followed_id=followed_id).first() is None:
                    db.session.add(Follow(follower_id=follower_id, followed_id=followed_id))
            message = Message(sender_id=other.id, receiver_id=user.id, content='رسالة يمكن الإبلاغ عنها')
            db.session.add(message)
            db.session.commit()
            other_id, outsider_id, message_id = other.id, outsider.id, message.id

        muted = self.client.post(f'/messages/safety/{other_id}/mute', data={'muted': 'true'})
        self.assertEqual(muted.status_code, 200)
        self.assertTrue(muted.get_json()['muted'])
        with self.app.app_context():
            self.assertIsNotNone(MutedConversation.query.filter_by(user_id=self.user_id, muted_user_id=other_id).first())

        report = self.client.post(f'/messages/report/{message_id}', data={'reason': 'harassment', 'details': 'اختبار بلاغ الرسالة'})
        self.assertEqual(report.status_code, 201)
        duplicate_report = self.client.post(f'/messages/report/{message_id}', data={'reason': 'harassment'})
        self.assertEqual(duplicate_report.status_code, 409)
        with self.app.app_context():
            saved_report = Report.query.filter_by(reporter_id=self.user_id, message_id=message_id).first()
            self.assertIsNotNone(saved_report)
            self.assertEqual(saved_report.reason, 'harassment')

        outsider_client = self.app.test_client()
        with outsider_client.session_transaction() as session:
            session['_user_id'] = str(outsider_id)
            session['_fresh'] = True
        forbidden_report = outsider_client.post(f'/messages/report/{message_id}', data={'reason': 'spam'})
        self.assertEqual(forbidden_report.status_code, 403)

        blocked = self.client.post(f'/messages/safety/{other_id}/block', data={'blocked': 'true'})
        self.assertEqual(blocked.status_code, 200)
        self.assertTrue(blocked.get_json()['blocked'])
        with self.app.app_context():
            self.assertIsNotNone(UserBlock.query.filter_by(blocker_id=self.user_id, blocked_id=other_id).first())
            self.assertIsNone(Follow.query.filter_by(follower_id=self.user_id, followed_id=other_id).first())
            self.assertIsNone(Follow.query.filter_by(follower_id=other_id, followed_id=self.user_id).first())

        blocked_send = self.client.post(f'/messages/send/{other_id}', data={'content': 'لا يجب إرسالها'}, follow_redirects=False)
        self.assertEqual(blocked_send.status_code, 302)
        with self.app.app_context():
            self.assertFalse(Message.query.filter_by(sender_id=self.user_id, receiver_id=other_id, content='لا يجب إرسالها').count())

        unblocked = self.client.post(f'/messages/safety/{other_id}/block', data={'blocked': 'false'})
        self.assertEqual(unblocked.status_code, 200)
        self.assertFalse(unblocked.get_json()['blocked'])

    def test_mobile_message_safety_blocks_delivery_exposes_mute_and_accepts_report(self):
        with self.app.app_context():
            sender = db.session.get(User, self.user_id)
            receiver = User.query.filter_by(username='mobile_message_safety_receiver').first()
            if receiver is None:
                receiver = User(username='mobile_message_safety_receiver', email='mobile-message-safety@example.test', name='مستلم سلامة', terms_agreed=True)
                receiver.set_password('mobile-message-safety-password')
                db.session.add(receiver)
                db.session.flush()
            for follower_id, followed_id in ((sender.id, receiver.id), (receiver.id, sender.id)):
                if Follow.query.filter_by(follower_id=follower_id, followed_id=followed_id).first() is None:
                    db.session.add(Follow(follower_id=follower_id, followed_id=followed_id))
            db.session.commit()
            receiver_id = receiver.id

        login = self.client.post('/api/mobile/v1/auth/login', json={'identifier': 'assistant_test_user', 'password': 'not-used-in-test'})
        self.assertEqual(login.status_code, 201)
        headers = {'Authorization': f"Bearer {login.get_json()['accessToken']}"}

        muted = self.client.post('/api/mobile/v1/conversations/mobile_message_safety_receiver/mute', headers=headers, json={'muted': True})
        self.assertEqual(muted.status_code, 200)
        self.assertTrue(muted.get_json()['muted'])

        message = self.client.post('/api/mobile/v1/conversations/mobile_message_safety_receiver/messages', headers=headers, json={'content': 'رسالة للإبلاغ من الواجهة المحمولة'})
        self.assertEqual(message.status_code, 201)
        message_id = message.get_json()['message']['id']
        listed = self.client.get('/api/mobile/v1/conversations', headers=headers)
        row = next(item for item in listed.get_json()['conversations'] if item['user']['id'] == receiver_id)
        self.assertTrue(row['isMuted'])
        report = self.client.post(f'/api/mobile/v1/messages/{message_id}/report', headers=headers, json={'reason': 'spam'})
        self.assertEqual(report.status_code, 201)

        blocked = self.client.post('/api/mobile/v1/conversations/mobile_message_safety_receiver/block', headers=headers, json={'blocked': True})
        self.assertEqual(blocked.status_code, 200)
        self.assertTrue(blocked.get_json()['blocked'])
        denied_send = self.client.post('/api/mobile/v1/conversations/mobile_message_safety_receiver/messages', headers=headers, json={'content': 'يجب رفضها'})
        self.assertEqual(denied_send.status_code, 403)

    def test_service_sends_only_current_question_to_mini_llm_without_exposing_engine(self):
        fake_response = Mock(status_code=200)
        fake_response.json.return_value = {
            "choices": [{"message": {"content": "<think>تفكير داخلي</think> أهلاً بك، كيف يمكنني مساعدتك في ANTER؟"}}],
        }

        with self.app.app_context(), patch(
            "app.services.anter_assistant.requests.post", return_value=fake_response
        ) as mocked_post:
            answer, error = get_assistant_reply("كيف يمكنني تحسين منشور؟")

        self.assertIsNone(error)
        self.assertEqual(answer, "أهلاً بك، كيف يمكنني مساعدتك في ANTER؟")
        _, kwargs = mocked_post.call_args
        self.assertEqual(kwargs["json"]["model"], "qwen/qwen3.6-27b")
        self.assertEqual(kwargs["json"]["messages"][-1], {"role": "user", "content": "كيف يمكنني تحسين منشور؟"})
        self.assertIn("أنت مساعد أنتر", kwargs["json"]["messages"][0]["content"])
        self.assertIn("عبدالقادر مهدلي", kwargs["json"]["messages"][0]["content"])
        self.assertEqual(kwargs["json"]["reasoning_effort"], "none")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-mini-llm-key")
        self.assertNotIn("history", kwargs["json"])
        self.assertNotIn("Groq", answer)
        self.assertNotIn("qwen", answer.casefold())

    def test_anter_status_question_uses_concise_local_reply(self):
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            assistant = db.session.get(User, self.assistant_id)
            answer, error = get_assistant_reply(
                "وين وصلنا في أنتر ما يخص المنصة؟",
                user=user,
                assistant=assistant,
            )

        self.assertIsNone(error)
        self.assertIsNotNone(answer)
        self.assertIn("منصة ANTER", answer)
        self.assertIn("ANTER Messenger", answer)
        self.assertIn("mini-llm Arabic", answer)
        self.assertLess(len(answer), 350)
        self.assertNotIn("مزوّد", answer)

    def test_messenger_download_answer_and_about_page_use_official_local_release_data(self):
        with self.app.app_context(), patch("app.services.anter_assistant.requests.post") as mocked_post:
            answer, error = get_assistant_reply("كيف أحمل ANTER Messenger بصيغة APK لأندرويد؟")

        self.assertIsNone(error)
        self.assertIn(self.app.config["ANTER_MESSENGER_APK_URL"], answer)
        self.assertIn(self.app.config["ANTER_MESSENGER_APK_SHA256"], answer)
        self.assertIn("Android 7.0", answer)
        mocked_post.assert_not_called()

        page = self.client.get("/about")
        self.assertEqual(page.status_code, 200)
        page_html = page.get_data(as_text=True)
        self.assertIn(self.app.config["ANTER_MESSENGER_APK_URL"], page_html)
        self.assertIn(self.app.config["ANTER_MESSENGER_APK_SHA256"], page_html)

    def test_founder_can_switch_to_assistant_and_back(self):
        previous_owner = self.app.config['ANTER_ASSISTANT_SWITCH_OWNER_USERNAME']
        self.app.config['ANTER_ASSISTANT_SWITCH_OWNER_USERNAME'] = 'assistant_test_user'
        try:
            switch_response = self.client.post('/auth/switch-to-assistant', follow_redirects=False)
            self.assertEqual(switch_response.status_code, 302)
            with self.client.session_transaction() as session:
                self.assertEqual(session.get('_user_id'), str(self.assistant_id))
                self.assertEqual(session.get('anter_assistant_switch_owner_id'), self.user_id)

            return_response = self.client.post('/auth/switch-back-to-owner', follow_redirects=False)
            self.assertEqual(return_response.status_code, 302)
            with self.client.session_transaction() as session:
                self.assertEqual(session.get('_user_id'), str(self.user_id))
                self.assertIsNone(session.get('anter_assistant_switch_owner_id'))
        finally:
            self.app.config['ANTER_ASSISTANT_SWITCH_OWNER_USERNAME'] = previous_owner

    def test_non_owner_cannot_switch_to_assistant(self):
        with self.app.app_context():
            other = User(
                username='unapproved_switch_user',
                email='unapproved-switch@example.test',
                name='مستخدم غير مخول',
                terms_agreed=True,
            )
            other.set_password('not-used-in-test')
            db.session.add(other)
            db.session.commit()
            other_id = other.id

        unapproved_client = self.app.test_client()
        with unapproved_client.session_transaction() as session:
            session['_user_id'] = str(other_id)
            session['_fresh'] = True
        response = unapproved_client.post('/auth/switch-to-assistant')
        self.assertEqual(response.status_code, 403)

    def test_report_receipt_is_sent_by_assistant_and_queued_for_human_review(self):
        with self.app.app_context():
            post = Post(
                content='منشور اختبار البلاغ',
                author_id=self.assistant_id,
                public_id='p-report-assistant-test',
            )
            db.session.add(post)
            db.session.commit()
            post_id = post.id

        response = self.client.post(
            '/report',
            json={
                'post_id': post_id,
                'reason': 'spam',
                'details': 'تفاصيل اختبارية آمنة.',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])

        with self.app.app_context():
            report = Report.query.filter_by(reporter_id=self.user_id, post_id=post_id).first()
            self.assertIsNotNone(report)
            receipt = Message.query.filter_by(
                sender_id=self.assistant_id,
                receiver_id=self.user_id,
            ).order_by(Message.id.desc()).first()
            self.assertIsNotNone(receipt)
            self.assertIn('تم استلام بلاغك رقم', receipt.content)
            self.assertIn('تدخل بشري', receipt.content)
            review_inbox = Message.query.filter_by(
                sender_id=self.user_id,
                receiver_id=self.assistant_id,
            ).order_by(Message.id.desc()).first()
            self.assertIsNotNone(review_inbox)
            self.assertIn(f'بلاغ جديد رقم {report.id}', review_inbox.content)

    def test_provider_error_does_not_expose_engine_or_model(self):
        fake_response = Mock(status_code=429)
        with self.app.app_context(), patch(
            "app.services.anter_assistant.requests.post", return_value=fake_response
        ):
            answer, error = get_assistant_reply("ساعدني في كتابة منشور")

        self.assertIsNone(answer)
        self.assertIn("حد مؤقت", error)
        self.assertNotIn("groq", error.casefold())
        self.assertNotIn("qwen", error.casefold())

    def test_direct_anter_identity_and_founder_answers_do_not_call_model(self):
        with self.app.app_context(), patch("app.services.anter_assistant.requests.post") as mocked_post:
            founder_answer, founder_error = get_assistant_reply("من هو مؤسس أنتر؟")
            identity_answer, identity_error = get_assistant_reply("ما اسمك؟")
            overview_answer, overview_error = get_assistant_reply("ما هو ANTER؟")
            greeting_answer, greeting_error = get_assistant_reply("السلام عليكم ورحمة الله وبركاته، كيف حالك؟")
            founder_self_intro, founder_self_error = get_assistant_reply("أنا عبدالقادر مهدلي")
            provider_answer, provider_error = get_assistant_reply("gemini او chat gpt")
            model_answer, model_error = get_assistant_reply("من أي نموذج؟")

        self.assertIsNone(founder_error)
        self.assertIsNone(identity_error)
        self.assertIsNone(overview_error)
        self.assertIsNone(greeting_error)
        self.assertIsNone(founder_self_error)
        self.assertIsNone(provider_error)
        self.assertIsNone(model_error)
        self.assertIn("عبدالقادر مهدلي", founder_answer)
        self.assertIn("مساعد أنتر", identity_answer)
        self.assertIn("نموذج عربي يمني جديد", identity_answer)
        self.assertIn("قيد التأسيس", identity_answer)
        self.assertIn("لم يُطلق بعد", identity_answer)
        self.assertIn("عبدالقادر مهدلي", identity_answer)
        self.assertIn("شبكة اجتماعية هجينة", overview_answer)
        self.assertIn("وعليكم السلام", greeting_answer)
        self.assertIn("مؤسس شبكة ANTER", founder_self_intro)
        self.assertIn("نموذج عربي يمني جديد", provider_answer)
        self.assertIn("قيد التأسيس", provider_answer)
        self.assertIn("عبدالقادر مهدلي", provider_answer)
        self.assertIn("مساعد أنتر", model_answer)
        self.assertIn("لم يُطلق بعد", model_answer)
        self.assertNotIn("تفاصيل تشغيلية", provider_answer)
        self.assertNotIn("Gemini", provider_answer)
        self.assertNotIn("ChatGPT", provider_answer)
        self.assertNotIn("Groq", provider_answer)
        mocked_post.assert_not_called()

    def test_local_memory_personalizes_greeting_and_never_calls_provider(self):
        with self.app.app_context(), patch("app.services.anter_assistant.requests.post") as mocked_post:
            user = db.session.get(User, self.user_id)
            assistant = db.session.get(User, self.assistant_id)
            remember_user_message(user, assistant, "نادني رائد")
            remember_user_message(user, assistant, "تذكر أنني أفضل الردود المختصرة")
            remember_assistant_reply(user, assistant, "تمام يا رائد، سأجعل الردود مختصرة وواضحة.")

            greeting, greeting_error = get_assistant_reply("مرحبا", user=user, assistant=assistant)
            memory_answer, memory_error = get_assistant_reply("ماذا تتذكر عني؟", user=user, assistant=assistant)
            context_answer, context_error = get_assistant_reply("هل تتذكر سياق حديثي؟", user=user, assistant=assistant)

        self.assertIsNone(greeting_error)
        self.assertIsNone(memory_error)
        self.assertIsNone(context_error)
        self.assertIn("رائد", greeting)
        self.assertIn("أفضل الردود المختصرة", memory_answer)
        self.assertIn("كنا نتحدث عن", context_answer)
        self.assertIn("سأجعل الردود مختصرة", context_answer)
        mocked_post.assert_not_called()

    def test_local_conversation_memory_keeps_both_sides_and_excludes_sensitive_text(self):
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            assistant = db.session.get(User, self.assistant_id)
            remember_user_message(user, assistant, "أريد ترتيب أفكاري للمنشور القادم")
            remember_assistant_reply(user, assistant, "بكل سرور، لنرتب الفكرة في نقاط قصيرة.")
            remember_user_message(user, assistant, "كلمة المرور: لا تحفظ هذا النص")
            conversation = recent_conversation(user, assistant)

        self.assertEqual([item['role'] for item in conversation[-2:]], ['user', 'assistant'])
        self.assertIn('ترتيب أفكاري', conversation[-2]['text'])
        self.assertIn('لنرتب الفكرة', conversation[-1]['text'])
        self.assertNotIn('كلمة المرور', ' '.join(item['text'] for item in conversation))

    def test_local_memory_recalls_identity_and_message_two_turns_back_without_provider(self):
        with self.app.app_context(), patch("app.services.anter_assistant.requests.post") as mocked_post:
            user = db.session.get(User, self.user_id)
            assistant = db.session.get(User, self.assistant_id)
            AssistantMemory.query.filter_by(user_id=user.id, assistant_id=assistant.id).delete()
            db.session.commit()
            remember_user_message(user, assistant, "أنا عبدالقادر مهدلي")
            remember_assistant_reply(user, assistant, "أهلاً بك يا عبدالقادر.")
            remember_user_message(user, assistant, "أريد تحسين واجهة الرسائل")
            remember_assistant_reply(user, assistant, "سنركز على سهولة القراءة في الهاتف.")
            question = "لو قلت لك الآن من أنا؟ وما هي الرسالة التي سبقت قبل رسالتين؟"
            remember_user_message(user, assistant, question)
            answer, error = get_assistant_reply(question, user=user, assistant=assistant)

        self.assertIsNone(error)
        self.assertIn("أنا عبدالقادر مهدلي", answer)
        self.assertIn("وقبل رسالتين", answer)
        self.assertNotIn("تحسين واجهة الرسائل", answer)
        mocked_post.assert_not_called()

    def test_local_memory_recalls_stated_job_role_without_provider(self):
        with self.app.app_context(), patch("app.services.anter_assistant.requests.post") as mocked_post:
            user = db.session.get(User, self.user_id)
            assistant = db.session.get(User, self.assistant_id)
            AssistantMemory.query.filter_by(user_id=user.id, assistant_id=assistant.id).delete()
            db.session.commit()
            remember_user_message(
                user,
                assistant,
                "السلام عليكم ورحمة الله وبركاته، أنا محمود مدير قسم المساعدة في شبكة أنتر",
            )
            role_answer, role_error = get_assistant_reply("ماهي وظيفتي الآن؟", user=user, assistant=assistant)
            reminder_answer, reminder_error = get_assistant_reply("لكنني شاركتك قبل قليل", user=user, assistant=assistant)

        self.assertIsNone(role_error)
        self.assertIsNone(reminder_error)
        self.assertIn("محمود", role_answer)
        self.assertIn("مدير قسم المساعدة", role_answer)
        self.assertIn("مدير قسم المساعدة", reminder_answer)
        mocked_post.assert_not_called()

    def test_activity_log_masks_sensitive_details_and_uses_device_time_markup(self):
        with self.app.test_request_context('/users/settings', headers={'User-Agent': 'ANTERActivityTest/1.0'}):
            log_user_activity(
                self.user_id,
                'settings_update',
                {
                    'fields': ['البريد الإلكتروني', 'رقم الجوال'],
                    'email': 'private@example.test',
                    'phone': '+967700000000',
                    'new_password': 'do-not-store',
                },
            )

        with self.app.app_context():
            activity = UserActivity.query.filter_by(user_id=self.user_id, action='settings_update').order_by(UserActivity.id.desc()).first()
            self.assertIsNotNone(activity)
            self.assertIn('البريد الإلكتروني', activity.details)
            self.assertNotIn('private@example.test', activity.details)
            self.assertNotIn('967700000000', activity.details)
            self.assertNotIn('do-not-store', activity.details)
            self.assertEqual(activity.action_label, 'تحديث إعدادات الحساب')

        page = self.client.get('/users/activity').get_data(as_text=True)
        self.assertIn('data-local-time=', page)
        self.assertIn('ANTERFormatDeviceTimes', page)
        self.assertIn('تحديث إعدادات الحساب', page)

    def test_activity_log_records_follow_post_comment_and_reaction(self):
        with self.app.app_context():
            target = User.query.filter_by(username='activity_log_target').first()
            if target is None:
                target = User(username='activity_log_target', email='activity-log-target@example.test', name='هدف النشاط', terms_agreed=True)
                target.set_password('activity-target-password')
                db.session.add(target)
                db.session.commit()
            target_id = target.id

        follow_response = self.client.post(f'/users/follow/{target_id}')
        self.assertEqual(follow_response.status_code, 200)
        create_response = self.client.post('/create', data={'content': 'منشور اختبار سجل النشاط'}, follow_redirects=False)
        self.assertEqual(create_response.status_code, 302)

        with self.app.app_context():
            post = Post.query.filter_by(author_id=self.user_id, content='منشور اختبار سجل النشاط').order_by(Post.id.desc()).first()
            self.assertIsNotNone(post)
            post_id = post.id

        reaction_response = self.client.post(f'/like/{post_id}', json={'reaction': 'love'})
        self.assertEqual(reaction_response.status_code, 200)
        comment_response = self.client.post(f'/comment/{post_id}', data={'content': 'تعليق اختبار النشاط'}, follow_redirects=False)
        self.assertEqual(comment_response.status_code, 302)

        with self.app.app_context():
            actions = {
                activity.action for activity in UserActivity.query.filter_by(user_id=self.user_id).all()
            }
        self.assertTrue({'follow', 'post_create', 'post_reaction_add', 'comment_create'}.issubset(actions))

    def test_profile_and_post_privacy_block_non_followers_and_hide_presence(self):
        with self.app.app_context():
            owner = User.query.filter_by(username='privacy_owner').first()
            if owner is None:
                owner = User(
                    username='privacy_owner',
                    email='privacy-owner@example.test',
                    name='صاحب الخصوصية',
                    terms_agreed=True,
                    profile_visibility='followers',
                    show_online_status=False,
                )
                owner.set_password('privacy-owner-password')
                db.session.add(owner)
                db.session.flush()
            owner.profile_visibility = 'followers'
            owner.show_online_status = False
            follower_post = Post(content='منشور للمتابعين فقط', author_id=owner.id, visibility='followers')
            only_me_post = Post(content='منشور خاص بصاحبه', author_id=owner.id, visibility='only_me')
            db.session.add_all([follower_post, only_me_post])
            db.session.commit()
            owner_id = owner.id
            follower_post_id = follower_post.public_id
            only_me_post_id = only_me_post.public_id
            self.assertEqual(get_user_status(owner, User.query.get(self.user_id))['status'], 'hidden')

        self.assertEqual(self.client.get('/users/privacy_owner').status_code, 403)
        self.assertEqual(self.client.get(f'/p/{follower_post_id}').status_code, 403)

        with self.app.app_context():
            db.session.add(Follow(follower_id=self.user_id, followed_id=owner_id))
            db.session.commit()

        self.assertEqual(self.client.get('/users/privacy_owner').status_code, 200)
        self.assertEqual(self.client.get(f'/p/{follower_post_id}').status_code, 200)
        self.assertEqual(self.client.get(f'/p/{only_me_post_id}').status_code, 403)

    def test_quick_post_composer_exposes_and_persists_post_audience(self):
        page = self.client.get('/').get_data(as_text=True)
        self.assertIn('id="quickPostVisibility"', page)
        self.assertIn('name="visibility"', page)
        self.assertIn('المتابعون فقط', page)
        self.assertIn('أنا فقط', page)

        response = self.client.post(
            '/create',
            data={'content': 'منشور خصوصية من نافذة الإنشاء', 'visibility': 'only_me'},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            post = Post.query.filter_by(author_id=self.user_id, content='منشور خصوصية من نافذة الإنشاء').order_by(Post.id.desc()).first()
            self.assertIsNotNone(post)
            self.assertEqual(post.visibility, 'only_me')

    def test_memory_ignores_sensitive_text(self):
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            assistant = db.session.get(User, self.assistant_id)
            AssistantMemory.query.filter_by(user_id=user.id, assistant_id=assistant.id).delete()
            db.session.commit()

            remember_user_message(user, assistant, "تذكر أن كلمة المرور الخاصة بي سرية")
            memory = AssistantMemory.query.filter_by(user_id=user.id, assistant_id=assistant.id).first()

        self.assertIsNone(memory)

    def test_memory_clear_route_removes_only_assistant_memory(self):
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            assistant = db.session.get(User, self.assistant_id)
            remember_user_message(user, assistant, "تذكر أنني أفضل الردود المختصرة")
            self.assertIsNotNone(AssistantMemory.query.filter_by(user_id=user.id, assistant_id=assistant.id).first())
            message_count_before_clear = Message.query.filter_by(
                sender_id=self.user_id,
                receiver_id=self.assistant_id,
            ).count()

        response = self.client.post(f"/messages/assistant-memory/{self.assistant_id}/clear")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        with self.app.app_context():
            self.assertIsNone(AssistantMemory.query.filter_by(user_id=self.user_id, assistant_id=self.assistant_id).first())
            self.assertEqual(
                Message.query.filter_by(sender_id=self.user_id, receiver_id=self.assistant_id).count(),
                message_count_before_clear,
            )

    def test_assistant_is_followed_by_existing_user_and_always_online(self):
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            assistant = db.session.get(User, self.assistant_id)
            Follow.query.filter_by(follower_id=user.id, followed_id=assistant.id).delete()
            db.session.commit()

            self.assertTrue(follow_anter_assistant_for_user(user, assistant))
            db.session.commit()
            self.assertFalse(follow_anter_assistant_for_user(user, assistant))
            self.assertEqual(
                Follow.query.filter_by(follower_id=user.id, followed_id=assistant.id).count(),
                1,
            )
            self.assertEqual(get_user_status(assistant)["status"], "online")
            self.assertEqual(get_user_status(assistant)["last_seen"], "متصل الآن")

            Follow.query.filter_by(follower_id=user.id, followed_id=assistant.id).delete()
            db.session.commit()
            self.assertGreaterEqual(ensure_anter_assistant_followed_by_all_users(), 1)
            self.assertTrue(user.is_following(assistant))

    def test_review_password_allows_human_login_to_assistant(self):
        review_password = "ReviewPass1!"
        previous_password = self.app.config.get("ANTER_ASSISTANT_REVIEW_PASSWORD", "")
        self.app.config["ANTER_ASSISTANT_REVIEW_PASSWORD"] = review_password
        try:
            with self.app.app_context():
                assistant = ensure_anter_assistant_user()
                self.assertTrue(assistant.check_password(review_password))

            anonymous_client = self.app.test_client()
            response = anonymous_client.post(
                "/auth/login",
                data={"username": "anter_assistant", "password": review_password},
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 302)
        finally:
            self.app.config["ANTER_ASSISTANT_REVIEW_PASSWORD"] = previous_password

    def test_phone_registration_generates_random_profile_link_and_default_follow(self):
        anonymous_client = self.app.test_client()
        response = anonymous_client.post(
            "/auth/register",
            data={
                "name": "متابع جديد",
                "gender": "male",
                "birth_date": "1997-05-20",
                "country_code": "+967",
                "phone": "737254619",
                "email": "",
                "password": "1234",
                "confirm_password": "1234",
                "terms_agreed": "y",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            user = User.query.filter_by(phone="+967737254619").first()
            self.assertIsNotNone(user)
            self.assertTrue(user.username.startswith("u_"))
            self.assertTrue(user.email.endswith("@phone-only.anter.local"))
            self.assertEqual(user.gender, "male")
            self.assertEqual(user.avatar, "img/default_avatar_male.png")
            with self.app.test_request_context():
                self.assertEqual(avatar_url(user), "/static/img/default_avatar_male.png")
            self.assertEqual(user.birth_date.isoformat(), "1997-05-20")
            self.assertTrue(user.is_following(db.session.get(User, self.assistant_id)))
            welcome = Message.query.filter_by(
                sender_id=self.assistant_id,
                receiver_id=user.id,
            ).order_by(Message.id.desc()).first()
            self.assertIsNotNone(welcome)
            self.assertIn('مرحباً بك في ANTER', welcome.content)

        login_response = anonymous_client.post(
            "/auth/login",
            data={"username": "+967737254619", "password": "1234"},
            follow_redirects=False,
        )
        self.assertEqual(login_response.status_code, 302)

    def test_email_registration_generates_random_profile_link_and_login_works(self):
        anonymous_client = self.app.test_client()
        response = anonymous_client.post(
            "/auth/register",
            data={
                "name": "مستخدمة بريد",
                "gender": "female",
                "birth_date": "",
                "country_code": "+967",
                "phone": "",
                "email": "email-login@example.com",
                "password": "1234",
                "confirm_password": "1234",
                "terms_agreed": "y",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            user = User.query.filter_by(email="email-login@example.com").first()
            self.assertIsNotNone(user)
            self.assertTrue(user.username.startswith("u_"))
            self.assertEqual(user.avatar, "img/default_avatar_female.png")
            with self.app.test_request_context():
                self.assertEqual(avatar_url(user), "/static/img/default_avatar_female.png")
            generated_username = user.username

        login_response = anonymous_client.post(
            "/auth/login",
            data={"username": "email-login@example.com", "password": "1234"},
            follow_redirects=False,
        )
        self.assertEqual(login_response.status_code, 302)

        username_login_response = self.app.test_client().post(
            "/auth/login",
            data={"username": generated_username, "password": "1234"},
            follow_redirects=False,
        )
        self.assertEqual(username_login_response.status_code, 302)

    def test_user_can_change_username_from_settings_and_open_new_profile_link(self):
        settings_page = self.client.get("/users/settings")
        settings_html = settings_page.get_data(as_text=True)
        self.assertEqual(settings_page.status_code, 200)
        self.assertIn('id="save-username-button"', settings_html)
        self.assertIn('id="username-save-status"', settings_html)
        self.assertIn('النقطة بين أجزاء الاسم', settings_html)

        response = self.client.post(
            "/users/settings",
            data={"username": "abdulqader.mahdly"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            self.assertEqual(user.username, "abdulqader.mahdly")

        profile_response = self.client.get("/users/abdulqader.mahdly")
        self.assertEqual(profile_response.status_code, 200)
        self.assertIn("abdulqader.mahdly", profile_response.get_data(as_text=True))

    def test_username_settings_reject_leading_trailing_or_consecutive_dots(self):
        for invalid_username in (".abdulqader", "abdulqader.", "abdulqader..mahdly"):
            response = self.client.post(
                "/users/settings",
                data={"username": invalid_username},
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("النقطة بين أجزاء الاسم فقط", response.get_data(as_text=True))

    def test_terminal_username_script_changes_only_the_requested_account(self):
        with self.app.app_context():
            user = User.query.filter_by(username="terminal_script_user").first()
            if user is None:
                user = User(
                    username="terminal_script_user",
                    email="terminal-script-user@example.test",
                    name="مستخدم سكربت الطرفية",
                    terms_agreed=True,
                )
                user.set_password("not-used-in-test")
                db.session.add(user)
                db.session.commit()
            user_id = user.id

        script = Path(__file__).resolve().parents[1] / "scripts" / "change_username.py"
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--current",
                "terminal_script_user",
                "--new",
                "terminal.user",
            ],
            input="terminal.user\n",
            text=True,
            capture_output=True,
            cwd=str(Path(__file__).resolve().parents[1]),
            env=os.environ.copy(),
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("تم تغيير اسم المستخدم بنجاح", result.stdout)
        with self.app.app_context():
            db.session.expire_all()
            self.assertEqual(db.session.get(User, user_id).username, "terminal.user")

    def test_username_settings_reject_duplicate_name(self):
        with self.app.app_context():
            duplicate = User(
                username="taken_username",
                email="taken-username@example.test",
                name="اسم محجوز",
                terms_agreed=True,
            )
            duplicate.set_password("1234")
            db.session.add(duplicate)
            db.session.commit()

        response = self.client.post(
            "/users/settings",
            data={"username": "taken_username"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("اسم المستخدم هذا مستخدم بالفعل", response.get_data(as_text=True))

    def test_login_page_uses_responsive_anter_logo(self):
        login_page = self.app.test_client().get("/auth/login")
        login_html = login_page.get_data(as_text=True)

        self.assertEqual(login_page.status_code, 200)
        self.assertIn("img/logo.png", login_html)
        self.assertIn('class="auth-brand-logo"', login_html)
        self.assertIn("رقم الجوال أو البريد أو المعرف", login_html)
        self.assertIn('id="loginPasswordToggle"', login_html)
        self.assertNotIn("text-anchor=\"middle\">A</text>", login_html)

    def test_simple_password_is_accepted_with_ui_warning(self):
        registration_page = self.app.test_client().get("/auth/register")
        registration_html = registration_page.get_data(as_text=True)
        self.assertIn("تُقبل كلمة بسيطة من 4 أحرف أو أرقام", registration_html)
        self.assertIn("تحذير: يمكنك المتابعة بهذه الكلمة", registration_html)
        self.assertIn("img/logo.png", registration_html)
        self.assertIn('class="auth-brand-logo"', registration_html)
        self.assertIn("الاسم الكامل", registration_html)
        self.assertIn("تاريخ الميلاد", registration_html)
        self.assertIn("إعادة تأكيد كلمة المرور", registration_html)
        self.assertIn("data-toggle-password", registration_html)
        self.assertNotIn('name="username"', registration_html)
        self.assertNotIn("text-anchor=\"middle\">A</text>", registration_html)

        with self.app.test_request_context(
            "/auth/reset_password/test-token",
            method="POST",
            data={"password": "1234", "confirm_password": "1234"},
        ):
            form = ResetPasswordForm(meta={"csrf": False})
            self.assertTrue(form.validate())

    def test_daily_assistant_publication_is_created_once_per_day(self):
        with self.app.app_context():
            AssistantDailyPublication.query.delete()
            db.session.query(Post).filter(Post.author_id == self.assistant_id).delete()
            db.session.commit()

            first_post = ensure_daily_assistant_post()
            second_post = ensure_daily_assistant_post()

            self.assertIsNotNone(first_post)
            self.assertEqual(first_post.id, second_post.id)
            self.assertEqual(first_post.author_id, self.assistant_id)
            self.assertTrue(first_post.content.strip())
            self.assertIn("#ANTER", first_post.content)
            self.assertEqual(AssistantDailyPublication.query.count(), 1)

    def test_assistant_chat_renders_bot_identity_and_text_only_hint(self):
        response = self.client.get(f"/messages/{self.assistant_id}")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("مساعد آلي", page)
        self.assertIn("يرد مساعد أنتر على الرسائل النصية فقط", page)
        self.assertIn("يتذكر مساعد أنتر الاسم والسياق والتفضيلات داخل ANTER فقط", page)
        self.assertIn('id="clearAssistantMemoryButton"', page)
        self.assertIn("assistant-rich-text", page)
        self.assertIn("formatAssistantMessages", page)
        self.assertIn("assistant-rich-title", page)
        self.assertNotIn('id="voiceCallButton"', page)

    def test_assistant_profile_shows_online_badge_and_identity(self):
        response = self.client.get("/users/anter_assistant")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("المساعد الرسمي لشبكة ANTER", page)
        self.assertIn("متصل الآن", page)

    def test_notifications_page_handles_missing_actor_without_server_error(self):
        with self.app.app_context():
            stale_notification = Notification(
                user_id=self.user_id,
                actor_id=999999,
                action="message",
                is_read=False,
            )
            db.session.add(stale_notification)
            db.session.commit()

        response = self.client.get("/notifications/")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("حساب غير متاح", html)
        self.assertIn("notification-missing-avatar", html)

    def test_messages_inbox_shows_online_friends_strip(self):
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            assistant = db.session.get(User, self.assistant_id)
            user.follow(assistant)
            db.session.commit()

        response = self.client.get("/messages/")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("الأصدقاء المتصلون", html)
        self.assertIn("online-friends-scroll", html)
        self.assertIn(f"/messages/{self.assistant_id}", html)
        self.assertIn("مساعد أنتر", html)
        self.assertIn("online-presence-dot", html)

    def test_message_send_requires_following_target(self):
        with self.app.app_context():
            target = User.query.filter_by(username='message_follow_required_target').first()
            if target is None:
                target = User(
                    username='message_follow_required_target',
                    email='message-follow-required@example.test',
                    name='هدف اختبار المراسلة',
                    terms_agreed=True,
                )
                target.set_password('1234')
                db.session.add(target)
                db.session.commit()
            target_id = target.id

        response = self.client.post(
            f'/messages/send/{target_id}',
            data={'content': 'لا يجب أن تُحفظ هذه الرسالة'},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            blocked = Message.query.filter_by(
                sender_id=self.user_id,
                receiver_id=target_id,
                content='لا يجب أن تُحفظ هذه الرسالة',
            ).first()
        self.assertIsNone(blocked)

        chat_response = self.client.get(f'/messages/{target_id}')
        chat_html = chat_response.get_data(as_text=True)
        self.assertEqual(chat_response.status_code, 200)
        self.assertIn('تابعه أولاً', chat_html)
        self.assertIn('id="sendMessageButton" disabled', chat_html)

    def test_following_target_allows_message_send(self):
        with self.app.app_context():
            target = User.query.filter_by(username='message_follow_allowed_target').first()
            if target is None:
                target = User(
                    username='message_follow_allowed_target',
                    email='message-follow-allowed@example.test',
                    name='هدف متابعة مسموح',
                    terms_agreed=True,
                )
                target.set_password('1234')
                db.session.add(target)
                db.session.commit()
            user = db.session.get(User, self.user_id)
            if not user.is_following(target):
                db.session.add(Follow(follower_id=user.id, followed_id=target.id))
                db.session.commit()
            target_id = target.id

        response = self.client.post(
            f'/messages/send/{target_id}',
            data={'content': 'رسالة مسموح بها بعد المتابعة'},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            allowed = Message.query.filter_by(
                sender_id=self.user_id,
                receiver_id=target_id,
                content='رسالة مسموح بها بعد المتابعة',
            ).first()
        self.assertIsNotNone(allowed)

    def test_call_signals_require_mutual_following_and_are_delivered_once(self):
        with self.app.app_context():
            caller = User.query.filter_by(username='voice_call_test_caller').first()
            if caller is None:
                caller = User(
                    username='voice_call_test_caller',
                    email='voice-call-caller@example.test',
                    name='متصل اختبار',
                    terms_agreed=True,
                )
                caller.set_password('1234')
                db.session.add(caller)

            receiver = User.query.filter_by(username='voice_call_test_receiver').first()
            if receiver is None:
                receiver = User(
                    username='voice_call_test_receiver',
                    email='voice-call-receiver@example.test',
                    name='مستقبل اختبار',
                    terms_agreed=True,
                )
                receiver.set_password('1234')
                db.session.add(receiver)
            db.session.commit()
            caller_id = caller.id
            receiver_id = receiver.id

            Follow.query.filter_by(follower_id=caller_id, followed_id=receiver_id).delete()
            Follow.query.filter_by(follower_id=receiver_id, followed_id=caller_id).delete()
            db.session.add(Follow(follower_id=caller_id, followed_id=receiver_id))
            db.session.commit()

        caller_client = self.app.test_client()
        receiver_client = self.app.test_client()
        with caller_client.session_transaction() as session:
            session['_user_id'] = str(caller_id)
            session['_fresh'] = True
        with receiver_client.session_transaction() as session:
            session['_user_id'] = str(receiver_id)
            session['_fresh'] = True

        # متابعة أحادية تكفي للمراسلة، لكنها لا تكفي للاتصال الصوتي.
        unilateral = caller_client.post(
            f'/messages/calls/signal/{receiver_id}',
            json={'callId': 'voice-call-integration', 'type': 'invite', 'payload': {'description': {'type': 'offer'}}},
        )
        self.assertEqual(unilateral.status_code, 403)

        with self.app.app_context():
            db.session.add(Follow(follower_id=receiver_id, followed_id=caller_id))
            db.session.commit()

        invite = caller_client.post(
            f'/messages/calls/signal/{receiver_id}',
            json={'callId': 'voice-call-integration', 'type': 'invite', 'payload': {'description': {'type': 'offer', 'sdp': 'offer-sdp'}}},
        )
        self.assertEqual(invite.status_code, 200)
        self.assertTrue(invite.get_json()['success'])

        # يمكن لصندوق الرسائل وأي صفحة عامة إظهار المكالمة من دون استهلاك
        # الإشارة؛ تبقى دعوة WebRTC محفوظة إلى أن يفتح المستلم المحادثة.
        pending = receiver_client.get('/messages/calls/pending')
        self.assertEqual(pending.status_code, 200)
        pending_signals = pending.get_json()['signals']
        self.assertEqual(len(pending_signals), 1)
        self.assertEqual(pending_signals[0]['callId'], 'voice-call-integration')
        self.assertIn(f'/messages/{caller_id}', pending_signals[0]['chatUrl'])
        self.assertEqual(caller_client.get('/messages/calls/pending').get_json()['signals'], [])

        received_invite = receiver_client.get(f'/messages/calls/poll/{caller_id}')
        self.assertEqual(received_invite.status_code, 200)
        invite_signals = received_invite.get_json()['signals']
        self.assertEqual(len(invite_signals), 1)
        self.assertEqual(invite_signals[0]['callId'], 'voice-call-integration')
        self.assertEqual(invite_signals[0]['type'], 'invite')
        self.assertEqual(invite_signals[0]['payload']['description']['type'], 'offer')

        # تُعلّم الإشارة كمستلمة فلا تعود في عملية الاستطلاع التالية.
        self.assertEqual(receiver_client.get(f'/messages/calls/poll/{caller_id}').get_json()['signals'], [])

        answer = receiver_client.post(
            f'/messages/calls/signal/{caller_id}',
            json={'callId': 'voice-call-integration', 'type': 'answer', 'payload': {'description': {'type': 'answer', 'sdp': 'answer-sdp'}}},
        )
        self.assertEqual(answer.status_code, 200)

        received_answer = caller_client.get(f'/messages/calls/poll/{receiver_id}')
        answer_signals = received_answer.get_json()['signals']
        self.assertEqual(len(answer_signals), 1)
        self.assertEqual(answer_signals[0]['type'], 'answer')
        self.assertEqual(answer_signals[0]['payload']['description']['type'], 'answer')

        completed = caller_client.post(
            f'/messages/calls/signal/{receiver_id}',
            json={'callId': 'voice-call-integration', 'type': 'hangup', 'payload': {}},
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(receiver_client.get(f'/messages/calls/poll/{caller_id}').get_json()['signals'][0]['type'], 'hangup')

        declined_invite = caller_client.post(
            f'/messages/calls/signal/{receiver_id}',
            json={'callId': 'voice-call-declined', 'type': 'invite', 'payload': {'description': {'type': 'offer'}}},
        )
        self.assertEqual(declined_invite.status_code, 200)
        declined = receiver_client.post(
            f'/messages/calls/signal/{caller_id}',
            json={'callId': 'voice-call-declined', 'type': 'decline', 'payload': {}},
        )
        self.assertEqual(declined.status_code, 200)

        missed_invite = caller_client.post(
            f'/messages/calls/signal/{receiver_id}',
            json={'callId': 'voice-call-missed', 'type': 'invite', 'payload': {'description': {'type': 'offer'}}},
        )
        self.assertEqual(missed_invite.status_code, 200)
        missed = caller_client.post(
            f'/messages/calls/signal/{receiver_id}',
            json={'callId': 'voice-call-missed', 'type': 'hangup', 'payload': {'reason': 'no_answer'}},
        )
        self.assertEqual(missed.status_code, 200)
        received_hangup = receiver_client.get(f'/messages/calls/poll/{caller_id}').get_json()['signals']
        self.assertEqual(received_hangup[-1]['type'], 'hangup')
        self.assertEqual(received_hangup[-1]['payload']['reason'], 'no_answer')

        with self.app.app_context():
            completed_log = CallLog.query.filter_by(call_id='voice-call-integration').first()
            declined_log = CallLog.query.filter_by(call_id='voice-call-declined').first()
            missed_log = CallLog.query.filter_by(call_id='voice-call-missed').first()
            self.assertEqual(completed_log.status, 'completed')
            self.assertEqual(completed_log.call_type, 'voice')
            self.assertIsNotNone(completed_log.answered_at)
            self.assertEqual(declined_log.status, 'declined')
            self.assertEqual(missed_log.status, 'missed')
            self.assertIsNone(missed_log.answered_at)

        caller_chat = caller_client.get(f'/messages/{receiver_id}').get_data(as_text=True)
        receiver_chat = receiver_client.get(f'/messages/{caller_id}').get_data(as_text=True)
        self.assertIn('data-call-id="voice-call-integration"', caller_chat)
        self.assertIn('مكالمة صادرة مستلمة', caller_chat)
        self.assertIn('data-retry-call', caller_chat)
        self.assertIn('data-retry-call', receiver_chat)
        self.assertIn('enableCallNotificationsButton', caller_chat)
        self.assertIn('enableCallNotificationsButton', receiver_chat)
        self.assertIn('مكالمة واردة مستلمة', receiver_chat)
        self.assertIn('تم رفض مكالمتك', caller_chat)
        self.assertIn('لم يُرد على مكالمتك', caller_chat)
        self.assertIn('videoCallButton', caller_chat)

        video_invite = caller_client.post(
            f'/messages/calls/signal/{receiver_id}',
            json={'callId': 'video-call-integration', 'type': 'invite', 'payload': {
                'callType': 'video',
                'description': {'type': 'offer', 'sdp': 'video-offer-sdp'},
            }},
        )
        self.assertEqual(video_invite.status_code, 200)
        video_pending = receiver_client.get('/messages/calls/pending').get_json()['signals']
        self.assertEqual(video_pending[0]['callType'], 'video')
        with self.app.app_context():
            video_log = CallLog.query.filter_by(call_id='video-call-integration').first()
            self.assertEqual(video_log.call_type, 'video')

        receiver_inbox = receiver_client.get('/messages/').get_data(as_text=True)
        self.assertIn('pollIncomingCallsOutsideChat', receiver_inbox)
        self.assertIn('CALL_ALERT_POLL_INTERVAL_MS = 12000', receiver_inbox)
        self.assertIn('function getCallMediaUnavailableMessage(callType', receiver_chat)
        self.assertIn('افتح ANTER عبر HTTPS ثم أعد المحاولة.', receiver_chat)
        self.assertIn("reason: 'media_unavailable'", receiver_chat)

    def test_call_signal_requires_following_target(self):
        with self.app.app_context():
            target = User.query.filter_by(username='call_follow_required_target').first()
            if target is None:
                target = User(
                    username='call_follow_required_target',
                    email='call-follow-required@example.test',
                    name='هدف اتصال اختبار',
                    terms_agreed=True,
                )
                target.set_password('1234')
                db.session.add(target)
                db.session.commit()
            target_id = target.id

        response = self.client.post(
            f'/messages/calls/signal/{target_id}',
            json={'callId': 'follow-required-test', 'type': 'invite', 'payload': {}},
        )
        self.assertEqual(response.status_code, 403)

    def test_sending_text_to_assistant_stores_assistant_reply(self):
        with patch(
            "app.routes.messages.get_assistant_reply",
            return_value=("مرحباً، أنا مساعد أنتر.", None),
        ):
            response = self.client.post(
                f"/messages/send/{self.assistant_id}",
                data={"content": "مرحبا"},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            messages = Message.query.filter(
                ((Message.sender_id == self.user_id) & (Message.receiver_id == self.assistant_id))
                | ((Message.sender_id == self.assistant_id) & (Message.receiver_id == self.user_id))
            ).order_by(Message.created_at.asc()).all()
            self.assertGreaterEqual(len(messages), 2)
            self.assertEqual(messages[-1].sender_id, self.assistant_id)
            self.assertEqual(messages[-1].content, "مرحباً، أنا مساعد أنتر.")
            self.assertEqual(messages[-1].parent_id, messages[-2].id)

        page = self.client.get(f"/messages/{self.assistant_id}").get_data(as_text=True)
        self.assertIn("مرحباً، أنا مساعد أنتر.", page)
        self.assertNotIn('class="quoted-message mb-2', page)


    def test_chat_page_never_exposes_messages_between_other_users(self):
        with self.app.app_context():
            first_party = User.query.filter_by(username='chat_isolation_first_party').first()
            if first_party is None:
                first_party = User(username='chat_isolation_first_party', email='chat-isolation-first@example.test', name='الطرف الأول', terms_agreed=True)
                first_party.set_password('1234')
                db.session.add(first_party)

            second_party = User.query.filter_by(username='chat_isolation_second_party').first()
            if second_party is None:
                second_party = User(username='chat_isolation_second_party', email='chat-isolation-second@example.test', name='الطرف الثاني', terms_agreed=True)
                second_party.set_password('1234')
                db.session.add(second_party)
            db.session.commit()

            private_message = Message(
                sender_id=first_party.id,
                receiver_id=second_party.id,
                content='محتوى خاص بين طرفين آخرين لا يجب كشفه',
            )
            private_call = CallLog(
                call_id='private-call-log-not-for-third-party',
                caller_id=first_party.id,
                receiver_id=second_party.id,
                status='missed',
            )
            db.session.add_all([private_message, private_call])
            db.session.commit()
            first_party_id = first_party.id

        response = self.client.get(f'/messages/{first_party_id}')
        page = response.get_data(as_text=True)

        # حالة 200 هنا تعني فتح قناة جديدة فارغة مع الطرف الأول، لا كشف محادثته مع طرف ثالث.
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('محتوى خاص بين طرفين آخرين لا يجب كشفه', page)
        self.assertNotIn('private-call-log-not-for-third-party', page)

    def test_non_participant_cannot_forward_a_private_message(self):
        with self.app.app_context():
            sender = User.query.filter_by(username='security_message_sender').first()
            if sender is None:
                sender = User(username='security_message_sender', email='security-message-sender@example.test', name='مرسل اختبار', terms_agreed=True)
                sender.set_password('1234')
                db.session.add(sender)

            recipient = User.query.filter_by(username='security_message_recipient').first()
            if recipient is None:
                recipient = User(username='security_message_recipient', email='security-message-recipient@example.test', name='مستلم اختبار', terms_agreed=True)
                recipient.set_password('1234')
                db.session.add(recipient)

            target = User.query.filter_by(username='security_message_target').first()
            if target is None:
                target = User(username='security_message_target', email='security-message-target@example.test', name='هدف اختبار', terms_agreed=True)
                target.set_password('1234')
                db.session.add(target)
            db.session.commit()

            private_message = Message(
                sender_id=sender.id,
                receiver_id=recipient.id,
                content='رسالة خاصة لفحص الصلاحيات',
            )
            db.session.add(private_message)
            db.session.commit()
            message_id = private_message.id
            target_id = target.id

        response = self.client.post(
            f'/messages/forward/{message_id}',
            data={'target_user_id': target_id},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.get_json()['success'])

        with self.app.app_context():
            copied = Message.query.filter_by(
                receiver_id=target_id,
                content='رسالة خاصة لفحص الصلاحيات',
            ).count()
        self.assertEqual(copied, 0)

    def test_forward_message_rejects_request_without_csrf_token_when_enabled(self):
        with self.app.app_context():
            private_message = Message(
                sender_id=self.user_id,
                receiver_id=self.assistant_id,
                content='رسالة مملوكة للمستخدم لاختبار CSRF',
            )
            db.session.add(private_message)
            db.session.commit()
            message_id = private_message.id

        previous_csrf = self.app.config['WTF_CSRF_ENABLED']
        self.app.config['WTF_CSRF_ENABLED'] = True
        try:
            response = self.client.post(
                f'/messages/forward/{message_id}',
                data={'target_user_id': self.assistant_id},
            )
        finally:
            self.app.config['WTF_CSRF_ENABLED'] = previous_csrf

        self.assertEqual(response.status_code, 400)

    def test_forward_user_list_uses_dom_text_not_untrusted_html(self):
        template = Path(self.app.root_path, 'templates', 'messages', 'chat.html').read_text(encoding='utf-8')
        self.assertIn("name.textContent = String(user.name || '');", template)
        self.assertIn('list.replaceChildren();', template)
        self.assertNotIn('list.innerHTML = users.map', template)

    def test_admin_dashboard_shows_analytics_and_blocks_regular_users(self):
        now = datetime.utcnow()
        with self.app.app_context():
            admin = User(
                username='analytics_admin',
                email='analytics-admin@example.test',
                name='مدير التحليلات',
                is_admin=True,
                last_seen=now,
                terms_agreed=True,
            )
            popular = User(
                username='analytics_popular',
                email='analytics-popular@example.test',
                name='الأكثر متابعة',
                last_seen=now,
                terms_agreed=True,
            )
            active = User(
                username='analytics_active',
                email='analytics-active@example.test',
                name='الأكثر نشاطاً',
                last_seen=now,
                terms_agreed=True,
            )
            admin.set_password('analytics-admin-password')
            popular.set_password('analytics-popular-password')
            active.set_password('analytics-active-password')
            db.session.add_all([admin, popular, active])
            db.session.flush()

            followers = []
            for index in range(8):
                follower = User(
                    username=f'analytics_follower_{index}',
                    email=f'analytics-follower-{index}@example.test',
                    name=f'متابع {index}',
                    terms_agreed=True,
                )
                follower.set_password('analytics-follower-password')
                followers.append(follower)
            db.session.add_all(followers)
            db.session.flush()
            db.session.add_all([
                Follow(follower_id=follower.id, followed_id=popular.id)
                for follower in followers
            ])

            post = Post(content='منشور اختبار تحليلات الإدارة', author_id=active.id)
            db.session.add(post)
            db.session.flush()
            comment = Comment(content='تعليق اختبار', author_id=popular.id, post_id=post.id)
            db.session.add(comment)
            db.session.flush()
            db.session.add_all([
                Like(user_id=admin.id, post_id=post.id),
                CommentLike(user_id=admin.id, comment_id=comment.id),
                Repost(user_id=popular.id, post_id=post.id),
            ])
            db.session.add_all([
                UserActivity(
                    user_id=active.id,
                    action='post_create',
                    created_at=now - timedelta(minutes=index),
                )
                for index in range(12)
            ])
            db.session.commit()
            admin_id = admin.id
            regular_user_id = popular.id

        admin_client = self.app.test_client()
        with admin_client.session_transaction() as session:
            session['_user_id'] = str(admin_id)
            session['_fresh'] = True
        admin_response = admin_client.get(f'/{self.app.config["ADMIN_PATH"]}/')
        page = admin_response.get_data(as_text=True)
        self.assertEqual(admin_response.status_code, 200)
        self.assertIn('إجمالي التفاعلات', page)
        self.assertIn('المتصلون الآن', page)
        self.assertIn('الأكثر متابعة', page)
        self.assertIn('الأكثر نشاطاً', page)
        self.assertIn('@analytics_popular', page)
        self.assertIn('@analytics_active', page)

        regular_client = self.app.test_client()
        with regular_client.session_transaction() as session:
            session['_user_id'] = str(regular_user_id)
            session['_fresh'] = True
        regular_response = regular_client.get(f'/{self.app.config["ADMIN_PATH"]}/')
        self.assertEqual(regular_response.status_code, 302)

    def test_startup_owner_admin_promotion_is_limited_to_configured_account(self):
        from app.services.owner_admin import ensure_configured_owner_is_admin

        with self.app.app_context():
            owner = User(
                username='configured_owner_admin',
                email='configured-owner-admin@example.test',
                name='مالك محدد',
                is_admin=False,
                terms_agreed=True,
            )
            other = User(
                username='unrelated_regular_user',
                email='unrelated-regular-user@example.test',
                name='مستخدم آخر',
                is_admin=False,
                terms_agreed=True,
            )
            owner.set_password('owner-admin-test-password')
            other.set_password('regular-user-test-password')
            db.session.add_all([owner, other])
            db.session.commit()
            owner_id = owner.id
            other_id = other.id

            previous_username = self.app.config['ANTER_OWNER_ADMIN_USERNAME']
            self.app.config['ANTER_OWNER_ADMIN_USERNAME'] = owner.username
            try:
                self.assertTrue(ensure_configured_owner_is_admin())
                self.assertFalse(ensure_configured_owner_is_admin())
            finally:
                self.app.config['ANTER_OWNER_ADMIN_USERNAME'] = previous_username

            self.assertTrue(User.query.get(owner_id).is_admin)
            self.assertFalse(User.query.get(other_id).is_admin)
            bootstrap = OwnerAdminBootstrap.query.get('primary-owner-admin')
            self.assertIsNotNone(bootstrap)
            self.assertEqual(bootstrap.user_id, owner_id)

    def test_admin_can_toggle_account_verification_and_regular_user_is_blocked(self):
        with self.app.app_context():
            admin = User(
                username='verification_admin',
                email='verification-admin@example.test',
                name='مدير التوثيق',
                is_admin=True,
                terms_agreed=True,
            )
            target = User(
                username='verification_target',
                email='verification-target@example.test',
                name='حساب للتوثيق',
                is_verified=False,
                terms_agreed=True,
            )
            admin.set_password('verification-admin-password')
            target.set_password('verification-target-password')
            db.session.add_all([admin, target])
            db.session.commit()
            admin_id = admin.id
            target_id = target.id

        admin_client = self.app.test_client()
        with admin_client.session_transaction() as session:
            session['_user_id'] = str(admin_id)
            session['_fresh'] = True

        users_response = admin_client.get(f'/{self.app.config["ADMIN_PATH"]}/users')
        users_page = users_response.get_data(as_text=True)
        self.assertEqual(users_response.status_code, 200)
        self.assertIn('غير موثّق', users_page)
        self.assertIn('toggle-verification', users_page)

        verify_response = admin_client.post(
            f'/{self.app.config["ADMIN_PATH"]}/users/verify/{target_id}'
        )
        self.assertEqual(verify_response.status_code, 200)
        self.assertTrue(verify_response.get_json()['is_verified'])
        with self.app.app_context():
            self.assertTrue(User.query.get(target_id).is_verified)

        remove_response = admin_client.post(
            f'/{self.app.config["ADMIN_PATH"]}/users/verify/{target_id}'
        )
        self.assertEqual(remove_response.status_code, 200)
        self.assertFalse(remove_response.get_json()['is_verified'])

        regular_client = self.app.test_client()
        with regular_client.session_transaction() as session:
            session['_user_id'] = str(target_id)
            session['_fresh'] = True
        blocked_response = regular_client.post(
            f'/{self.app.config["ADMIN_PATH"]}/users/verify/{admin_id}'
        )
        self.assertEqual(blocked_response.status_code, 302)


class AdminPathSecurityTests(unittest.TestCase):
    def test_explicit_admin_path_is_normalized(self):
        with patch.dict(os.environ, {"ADMIN_PATH": "/admin-fixed-route/"}, clear=False):
            self.assertEqual(
                _get_admin_path({"SECRET_KEY": "unused-when-explicit"}),
                "admin-fixed-route",
            )

    def test_fallback_path_is_stable_for_same_secret(self):
        with patch.dict(os.environ, {"ADMIN_PATH": ""}, clear=False):
            config = {"SECRET_KEY": "stable-test-secret"}
            first_path = _get_admin_path(config)
            second_path = _get_admin_path(config)

        self.assertEqual(first_path, second_path)
        self.assertTrue(first_path.startswith("admin-"))
        self.assertGreater(len(first_path), len("admin-"))

    def test_fallback_path_changes_when_secret_changes(self):
        with patch.dict(os.environ, {"ADMIN_PATH": ""}, clear=False):
            first_path = _get_admin_path({"SECRET_KEY": "first-secret"})
            second_path = _get_admin_path({"SECRET_KEY": "second-secret"})

        self.assertNotEqual(first_path, second_path)


if __name__ == '__main__':
    unittest.main()
