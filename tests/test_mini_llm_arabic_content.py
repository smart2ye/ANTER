import unittest
from unittest.mock import Mock, patch

from app import create_app
from app.services.ai_service import AIService


class MiniLlmArabicContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(
            TESTING=True,
            MINI_LLM_ARABIC_API_KEY="test-mini-llm-key",
            MINI_LLM_ARABIC_MODEL="qwen/qwen3.6-27b",
            MINI_LLM_ARABIC_TIMEOUT_SECONDS=10,
        )

    def test_content_generation_uses_mini_llm_arabic_identity(self):
        fake_response = Mock(status_code=200)
        fake_response.json.return_value = {
            "choices": [{"message": {"content": "<think>تحليل</think> شارك فكرتك اليوم، فقد تلهم شخصاً آخر."}}]
        }

        with self.app.app_context(), patch(
            "app.services.ai_service.requests.post", return_value=fake_response
        ) as mocked_post:
            text, error = AIService().suggest_post("فكرة عن التعاون")

        self.assertIsNone(error)
        self.assertEqual(text, "شارك فكرتك اليوم، فقد تلهم شخصاً آخر.")
        _, kwargs = mocked_post.call_args
        self.assertEqual(kwargs["json"]["messages"][-1]["role"], "user")
        self.assertIn("mini-llm Arabic", kwargs["json"]["messages"][0]["content"])
        self.assertIn("عبدالقادر مهدلي", kwargs["json"]["messages"][0]["content"])
        self.assertEqual(kwargs["json"]["reasoning_effort"], "none")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-mini-llm-key")
        self.assertNotIn("Gemini", text)
        self.assertNotIn("Groq", text)

    def test_missing_configuration_does_not_expose_provider_name(self):
        with self.app.app_context():
            self.app.config["MINI_LLM_ARABIC_API_KEY"] = ""
            text, error = AIService().improve_text("مسودة قصيرة")
            self.app.config["MINI_LLM_ARABIC_API_KEY"] = "test-mini-llm-key"

        self.assertIsNone(text)
        self.assertIn("mini-llm Arabic", error)
        self.assertNotIn("Gemini", error)
        self.assertNotIn("Groq", error)


if __name__ == "__main__":
    unittest.main()
