import os
import tempfile
import unittest
from unittest.mock import Mock, patch


_TEST_DB = os.path.join(tempfile.gettempdir(), "anter_assistant_feature_test.db")
try:
    os.remove(_TEST_DB)
except FileNotFoundError:
    pass

os.environ["DATABASE_URL"] = "sqlite:///" + _TEST_DB
os.environ["ADMIN_PATH"] = "admin-antar-assistant-test"
os.environ["MINI_LLM_API_KEY"] = "test-mini-llm-key"

from app import create_app
from app.extensions import db
from app.models import Message, User
from app.services.anter_assistant import (
    ensure_anter_assistant_user,
    get_assistant_reply,
)


class AnterAssistantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            ANTER_ASSISTANT_ENABLED=True,
            MINI_LLM_API_URL="http://127.0.0.1:5050/api/v1/assistant/ask",
            MINI_LLM_API_KEY="test-mini-llm-key",
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

    def test_service_sends_only_current_question_to_mini_llm(self):
        fake_response = Mock(status_code=200)
        fake_response.json.return_value = {
            "ok": True,
            "answer": "أهلاً بك، كيف يمكنني مساعدتك في ANTER؟",
        }

        with self.app.app_context(), patch(
            "app.services.anter_assistant.requests.post", return_value=fake_response
        ) as mocked_post:
            answer, error = get_assistant_reply("ما هي ANTER؟")

        self.assertIsNone(error)
        self.assertEqual(answer, "أهلاً بك، كيف يمكنني مساعدتك في ANTER؟")
        _, kwargs = mocked_post.call_args
        self.assertEqual(kwargs["json"], {"question": "ما هي ANTER؟", "mode": "hybrid"})
        self.assertEqual(kwargs["headers"]["X-API-Key"], "test-mini-llm-key")
        self.assertNotIn("history", kwargs["json"])

    def test_assistant_chat_renders_bot_identity_and_text_only_hint(self):
        response = self.client.get(f"/messages/{self.assistant_id}")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("مساعد آلي", page)
        self.assertIn("يرد مساعد أنتر على الرسائل النصية فقط", page)
        self.assertNotIn('id="voiceCallButton"', page)

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


if __name__ == "__main__":
    unittest.main()
