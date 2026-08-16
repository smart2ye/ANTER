import os
import requests
from flask import current_app

class AIService:
    def __init__(self):
        # يتم جلب المفتاح من إعدادات التطبيق (Config) التي تقرأ من متغيرات البيئة المشفرة
        self.gemini_key = current_app.config.get('GEMINI_API_KEY')
        self.deepseek_key = current_app.config.get('DEEPSEEK_API_KEY')

    def generate_response(self, prompt, max_tokens=300):
        # 1. Try Gemini if available (using google-genai or direct REST API)
        if self.gemini_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_key}"
                headers = {"Content-Type": "application/json"}
                data = {
                    "contents": [{"parts": [{"text": prompt}]}]
                }
                response = requests.post(url, headers=headers, json=data, timeout=15)
                if response.status_code == 200:
                    res_json = response.json()
                    candidates = res_json.get('candidates', [])
                    if candidates:
                        parts = candidates[0].get('content', {}).get('parts', [])
                        if parts:
                            return parts[0].get('text', '').strip()
            except Exception:
                current_app.logger.exception('خطأ في استدعاء Gemini API')

        # 2. Fallback / Mock response if no API key or failure
        return "🤖 عذراً، خدمة الذكاء الاصطناعي غير متوفرة مؤقتاً أو تحتاج لمفتاح API صالح."

    def summarize_text(self, text):
        prompt = f"قم بتلخيص هذا النص الاجتماعي بأسلوب موجز ومفيد في جملتين أو ثلاث باللغة العربية:\n\n{text}"
        return self.generate_response(prompt, max_tokens=150)
