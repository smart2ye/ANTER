"""ANTER: المراقبة الآلية للبلاغات — يستخدم مساعد أنتر (mini-llm Arabic).

يُرسل سياق البلاغ + المحتوى إلى Groq → يصنّف → يُعيد JSON:
{
    "violation": bool,
    "category": str (spam/harassment/hate/violence/nudity/fraud/misleading/other/none),
    "confidence": int (0-100),
    "reason": str (ملخص عربي قصير)
}

القاعدة:
- confidence ≥ 70 AND violation = True → status = 'under_review'
- غير ذلك → status = 'clean'
"""

from __future__ import annotations
import json
import re

import requests
from flask import current_app

MODERATION_TIMEOUT = 15
CONFIDENCE_THRESHOLD = 70

CATEGORY_LABELS = {
    'spam': 'محتوى مزعج/مكرر',
    'harassment': 'تحرش أو تنمّر',
    'hate': 'خطاب كراهية',
    'violence': 'تهديد أو عنف',
    'nudity': 'محتوى غير لائق',
    'fraud': 'احتيال',
    'misleading': 'معلومات مضللة',
    'other': 'مخالفة أخرى',
    'none': 'لا مخالفة',
}


SYSTEM_PROMPT = """أنت مصنّف محتوى لمنصة تواصل اجتماعي عربية.
تستقبل بلاغًا عن منشور + نص المنشور.
تُعيد JSON فقط — بلا شرح، بلا تنسيق — بالصيغة:

{"violation": true|false, "category": "spam|harassment|hate|violence|nudity|fraud|misleading|other|none", "confidence": 0-100, "reason": "جملة عربية قصيرة (أقل من 120 حرفًا)"}

معايير:
- انتهاكات واضحة فقط (سب، تهديد، تحرش جنسي، محتوى غير لائق، احتيال، معلومات مضللة).
- انتقاد سياسي، رأي شخصي، جدال عادي → ليست مخالفة.
- إن كان البلاغ كيديًا أو ضعيف الدليل → violation=false.
- confidence = مدى ثقتك بالتصنيف (لا بوجود البلاغ).
- لا تقل confidence عن 50 إن لم تكن متأكدًا — فقط اجعل violation=false حينها.
"""


def classify_post(content: str, report_reason: str, report_details: str = "") -> dict:
    """يُصنّف المنشور المُبلَّغ عنه. يعيد dict دائماً (آمن في حال الفشل)."""
    fallback = {
        'violation': False,
        'category': 'none',
        'confidence': 0,
        'reason': 'تعذر تحليل البلاغ آليًا.',
    }

    if not content or not content.strip():
        return fallback

    api_key = (current_app.config.get('ANTER_ASSISTANT_MINI_LLM_ARABIC_API_KEY') or '').strip()
    if not api_key:
        return fallback

    api_url = current_app.config.get(
        'ANTER_ASSISTANT_MINI_LLM_ARABIC_API_URL',
        'https://api.groq.com/openai/v1/chat/completions',
    )
    model = current_app.config.get(
        'ANTER_ASSISTANT_MINI_LLM_ARABIC_MODEL',
        'qwen/qwen3.8-27b',
    )

    user_prompt = (
        f"سبب البلاغ المختار من المُبلِّغ: {report_reason}\n"
        f"تفاصيل إضافية: {report_details[:400] if report_details else 'لا شيء'}\n\n"
        f"نص المنشور:\n---\n{content[:1500]}\n---\n\n"
        "أعد JSON فقط."
    )

    try:
        r = requests.post(
            api_url,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_prompt},
                ],
                'temperature': 0.1,
                'max_tokens': 200,
            },
            timeout=MODERATION_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        raw = data['choices'][0]['message']['content'].strip()

        # استخراج JSON من الرد (قد يحتوي ```json```)
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if not m:
            return fallback
        parsed = json.loads(m.group(0))

        return {
            'violation': bool(parsed.get('violation', False)),
            'category': str(parsed.get('category', 'none')).lower(),
            'confidence': int(parsed.get('confidence', 0)),
            'reason': str(parsed.get('reason', ''))[:200],
        }
    except Exception as e:
        current_app.logger.warning(f'[moderation] فشل التصنيف: {type(e).__name__}: {e}')
        return fallback


def should_hide(classification: dict) -> bool:
    """هل يستحق الإخفاء المؤقت؟"""
    return (
        classification.get('violation') is True
        and classification.get('confidence', 0) >= CONFIDENCE_THRESHOLD
    )
