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
os.environ["GROQ_API_KEY"] = "test-groq-key"
os.environ["GROQ_MODEL"] = "qwen/qwen3.6-27b"

from app import create_app
from app.extensions import db
from app.models import AssistantMemory, Message, User
from app.services.anter_assistant import (
    ensure_anter_assistant_user,
    get_assistant_reply,
)
from app.services.anter_memory import remember_user_message


class AnterAssistantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            ANTER_ASSISTANT_ENABLED=True,
            ANTER_ASSISTANT_GROQ_API_KEY="test-groq-key",
            ANTER_ASSISTANT_GROQ_MODEL="qwen/qwen3.6-27b",
            ANTER_ASSISTANT_GROQ_MAX_TOKENS=700,
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

    def test_service_sends_only_current_question_to_groq_without_exposing_provider(self):
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
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-groq-key")
        self.assertNotIn("history", kwargs["json"])
        self.assertNotIn("Groq", answer)
        self.assertNotIn("qwen", answer.casefold())

    def test_provider_error_does_not_expose_groq_or_model(self):
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

            greeting, greeting_error = get_assistant_reply("مرحبا", user=user, assistant=assistant)
            memory_answer, memory_error = get_assistant_reply("ماذا تتذكر عني؟", user=user, assistant=assistant)
            context_answer, context_error = get_assistant_reply("هل تتذكر سياق حديثي؟", user=user, assistant=assistant)

        self.assertIsNone(greeting_error)
        self.assertIsNone(memory_error)
        self.assertIsNone(context_error)
        self.assertIn("رائد", greeting)
        self.assertIn("أفضل الردود المختصرة", memory_answer)
        self.assertIn("آخر ما أتذكره", context_answer)
        mocked_post.assert_not_called()

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

    def test_assistant_chat_renders_bot_identity_and_text_only_hint(self):
        response = self.client.get(f"/messages/{self.assistant_id}")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("مساعد آلي", page)
        self.assertIn("يرد مساعد أنتر على الرسائل النصية فقط", page)
        self.assertIn("يتذكر مساعد أنتر الاسم والسياق والتفضيلات داخل ANTER فقط", page)
        self.assertIn('id="clearAssistantMemoryButton"', page)
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
