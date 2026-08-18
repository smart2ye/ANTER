"""خدمة كتابة ANTER عبر mini-llm Arabic.

لا تحتفظ هذه الخدمة بمسودات المستخدم أو سجل طلباته. يرسل كل طلب المحتوى
المطلوب لتلك العملية فقط، ويظهر للمستخدم اسم mini-llm Arabic لا اسم البنية التحتية.
"""

from __future__ import annotations

import re

import requests
from flask import current_app


MINI_LLM_ARABIC_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
_THINKING_BLOCK = re.compile(r"<think>.*?(?:</think>|$)", flags=re.IGNORECASE | re.DOTALL)


class AIService:
    """واجهة كتابة موحدة داخل ANTER تعتمد على mini-llm Arabic."""

    MAX_SOURCE_LENGTH = 2000
    DISPLAY_NAME = "mini-llm Arabic"

    def _settings(self):
        """يقرأ الإعدادات من بيئة الخادم فقط ومن دون إظهار مفاتيح في النتائج أو السجل."""
        return (
            current_app.config.get("MINI_LLM_ARABIC_API_KEY", "").strip(),
            current_app.config.get("MINI_LLM_ARABIC_MODEL", "").strip(),
            current_app.config.get("MINI_LLM_ARABIC_TIMEOUT_SECONDS", 30.0),
        )

    @staticmethod
    def _clean_response(value) -> str:
        text = _THINKING_BLOCK.sub("", str(value or ""))
        return " ".join(text.split()).strip()

    def _system_prompt(self) -> str:
        return (
            "أنت mini-llm Arabic، مساعد الكتابة الرسمي في شبكة ANTER الاجتماعية. "
            "أنت جزء من منظومة ANTER التي أسسها عبدالقادر مهدلي. "
            "اكتب بالعربية الفصحى السهلة وبأسلوب طبيعي ودود ومحترف. "
            "ركز على صياغة منشورات وتعليقات محسنة، ولا تضف حقائق أو ادعاءات لا توجد في طلب المستخدم. "
            "احترم الخصوصية: عالج النص المرسل في الطلب الحالي فقط، ولا تطلب كلمات مرور أو مفاتيح أو بيانات خاصة. "
            "أعد النص النهائي المطلوب فقط بلا مقدمة عن نفسك، وبلا تحليل داخلي أو وسوم تفكير."
        )

    def generate_response(self, prompt, max_tokens=300):
        """ينشئ نصاً واحداً لمسودة المستخدم الحالية فقط عبر mini-llm Arabic."""
        api_key, model, timeout = self._settings()
        if not api_key or not model:
            return None, "mini-llm Arabic غير مهيأ حالياً. تحقق من إعدادات الخادم ثم حاول مجدداً."

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": str(prompt or "")},
            ],
            "temperature": 0.65,
            "max_tokens": max(64, min(int(max_tokens), 600)),
            "reasoning_effort": "none",
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ANTER-mini-llm-Arabic/1.0",
        }

        try:
            response = requests.post(MINI_LLM_ARABIC_CHAT_URL, json=payload, headers=headers, timeout=timeout)
        except requests.RequestException:
            current_app.logger.warning("تعذر الاتصال بخدمة mini-llm Arabic.")
            return None, "تعذر الاتصال بـ mini-llm Arabic حالياً. حاول مرة أخرى بعد قليل."

        if response.status_code != 200:
            current_app.logger.warning("تعذر طلب mini-llm Arabic: HTTP %s", response.status_code)
            return None, "mini-llm Arabic غير متاح مؤقتاً. حاول مرة أخرى بعد قليل."

        try:
            data = response.json()
            text = self._clean_response(data["choices"][0]["message"].get("content"))
        except (IndexError, KeyError, TypeError, ValueError):
            current_app.logger.warning("استجابة mini-llm Arabic غير صالحة.")
            return None, "تعذر إنشاء الاقتراح حالياً. حاول مرة أخرى."

        if not text:
            return None, "لم يتمكن mini-llm Arabic من إنشاء نص هذه المرة."
        return text, None

    @classmethod
    def _clean_source(cls, text):
        return " ".join((text or "").strip().split())[:cls.MAX_SOURCE_LENGTH]

    def summarize_text(self, text):
        source = self._clean_source(text)
        if not source:
            return None, "لا يوجد نص صالح للتلخيص."
        return self.generate_response(
            f"لخّص المنشور التالي في جملتين أو ثلاث فقط، مع المحافظة على المعنى:\n\n{source}",
            max_tokens=160,
        )

    def suggest_comment(self, post_text):
        source = self._clean_source(post_text)
        if not source:
            return None, "لا يمكن اقتراح تعليق لمنشور فارغ."
        return self.generate_response(
            "اقترح تعليقاً واحداً فقط لهذا المنشور. يجب أن يكون قصيراً (حد أقصى 280 حرفاً)، "
            "طبيعياً، محترماً، ولا يدّعي حقائق غير موجودة. أعد نص التعليق فقط دون مقدمة أو علامات اقتباس.\n\n"
            f"المنشور:\n{source}",
            max_tokens=120,
        )

    def suggest_post(self, topic):
        source = self._clean_source(topic)
        instruction = (
            "أنشئ منشوراً اجتماعياً عربياً واحداً مناسباً لمنصة ANTER، واضحاً وجذاباً "
            "ولا يتجاوز 500 حرف. أعد نص المنشور فقط بلا عنوان أو مقدمة."
        )
        if source:
            instruction += f" استخدم هذا الموضوع أو المسودة كفكرة أساسية:\n\n{source}"
        else:
            instruction += " اختر فكرة عامة إيجابية تشجع على نقاش هادئ بين المستخدمين."
        return self.generate_response(instruction, max_tokens=220)

    def improve_text(self, text):
        source = self._clean_source(text)
        if not source:
            return None, "اكتب مسودة أولاً ليتمكن mini-llm Arabic من تحسينها."
        return self.generate_response(
            "حسّن صياغة النص التالي لغوياً وأسلوبياً مع المحافظة التامة على المعنى المقصود. "
            "اجعله مناسباً للنشر الاجتماعي، ولا تضف معلومات أو ادعاءات جديدة. "
            "أعد النص المحسن فقط دون مقدمة.\n\n"
            f"النص:\n{source}",
            max_tokens=260,
        )
