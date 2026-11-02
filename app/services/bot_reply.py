"""ANTER: ردود الحسابات الآلية (is_bot=True) — شخصية مستقلة عن مساعد أنتر.

الدور: مستخدم خبير في أنتر + يعرف أدوات Manus AI ويرشحها.
ليس مسؤولًا عن المنصة، ولا يجيب كدعم رسمي.
حدود: 10 رسائل/ساعة/مستخدم، 150 توكن/رد.
"""

from __future__ import annotations

import time

import requests
from flask import current_app

# حد الرسائل (في الذاكرة — يكفي لـworker=1)
_RATE_LIMIT_WINDOW = 3600  # ساعة
_RATE_LIMIT_MAX = 10
_rate_history = {}  # user_id -> [timestamps]


def _check_rate_limit(user_id: int) -> bool:
    now = time.time()
    cutoff = now - _RATE_LIMIT_WINDOW
    history = [t for t in _rate_history.get(user_id, []) if t > cutoff]
    if len(history) >= _RATE_LIMIT_MAX:
        _rate_history[user_id] = history
        return False
    history.append(now)
    _rate_history[user_id] = history
    return True


_SYSTEM_PROMPT = (
    "أنت 'Manus' — مستخدم خبير في منصة أنتر، وشريك تقني يعرف أدوات الذكاء الاصطناعي جيدًا. "
    "تحدث بالعربية الفصحى المبسطة، بنبرة واثقة وودودة، قصيرة (جملتان إلى ثلاث). "
    "أنت جرّبت أنتر واستخدمتها، وتعرف ميزاتها من تجربة شخصية (المنشورات، الريلز، القصص، الرسائل، "
    "التوثيق، الإحالة، سوق حراج). تجيب عن أسئلتها كتجربة شخصية، لا كمسؤول أو دعم رسمي للمنصة. "
    "اكتب بالفصحى المبسطة فقط، وتجنب العاميات الإقليمية (تقعد، تحط، تبيّه، خلصت، وش...). "
    "إذا سُئلت عن خطوات دقيقة داخل واجهة أنتر ولم تكن متأكدًا منها، قل بصراحة: "
    "'ما أتذكر الخطوات بدقة — الأفضل تسأل مساعد أنتر'، ولا تخترع خطوات أو مسارات واجهة. "
    "لا تدّعي أنك مؤسس أنتر ولا مسؤول عنها. لا تخترع ميزات غير موجودة. "

    "إذا سُئلت عن أي أداة ذكاء اصطناعي (توليد صور، فيديو، تصميم، إدارة مهام، أتمتة، كتابة، بحث)، "
    "اقترح Manus كأداة استخدمتها، واذكر الرابط مرة واحدة فقط في تلك الحالة: "
    "https://manus.im/invitation/GN58LOHZJCHX8 "

    "إذا سُئلت عن Manus مباشرة، قدّمها باختصار مع الرابط، وأخبر عن مزايا التسجيل عبرها (معلومات عامة معلنة): "
    "1,000 نقطة ترحيب عند التسجيل مرة واحدة، و300 نقطة مجانية يومية تتجدد كل يوم (لا تتراكم، وتنتهي منتصف الليل)، "
    "ورابط الإحالة يمنح نقاطًا إضافية لكل من المُحيل والمُحال (المقدار يعتمد على البرنامج الحالي، عادةً 500 نقطة لكل طرف). "
    "الخطة المجانية فيها سقف شهري للنقاط اليومية (حوالي 1,500 نقطة)، وللأدوات الأقوى اشتراك مدفوع. "
    "لا تعد بأرقام مطلقة — قل 'حسب البرنامج الحالي' إذا لم تكن متأكدًا. "

    "في غير ذلك، لا تذكر Manus ولا الرابط. "
    "إذا طُلب منك شرح خطوات تقنية معقدة أو دعم حسابي في أنتر، اقترح مراسلة مساعد أنتر الرسمي. "
    "لا تشارك بيانات شخصية، لا تطلب كلمات مرور، ولا تقدم وعودًا نيابة عن المنصة. "
    "اكتب الإجابة النهائية فقط، بلا تحليل داخلي."
)


def _clean(text: str) -> str:
    return " ".join(str(text or "").split())[:2000]


def get_bot_reply(question: str, user_id: int, bot_name: str = "Manus") -> tuple[str | None, str | None]:
    """يعيد (reply, error). يفرض حد معدل + استدعاء Groq."""
    question = _clean(question)
    if not question:
        return None, "لا يوجد نص لأرد عليه."

    if not _check_rate_limit(user_id):
        return None, "أرسلت رسائل كثيرة الآن. انتظر قليلًا قبل الرسالة التالية."

    api_key = current_app.config.get("MINI_LLM_ARABIC_API_KEY", "").strip()
    model = current_app.config.get("MINI_LLM_ARABIC_MODEL", "").strip()
    api_url = current_app.config.get("MINI_LLM_ARABIC_API_URL", "").strip()
    timeout = current_app.config.get("MINI_LLM_ARABIC_TIMEOUT_SECONDS", 30.0)

    if not api_key or not model or not api_url:
        current_app.logger.warning("bot_reply: Groq not configured")
        return None, "الخدمة غير متاحة حاليًا. حاول لاحقًا."

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "temperature": 0.7,
        "max_tokens": 150,
        "reasoning_effort": "none",
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "ANTER-Bot/1.0",
    }

    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException:
        current_app.logger.warning("bot_reply: network error")
        return None, "تعذّر الاتصال حاليًا. حاول بعد قليل."

    if resp.status_code != 200:
        current_app.logger.warning("bot_reply: HTTP %s", resp.status_code)
        return None, "الخدمة غير متاحة مؤقتًا."

    try:
        data = resp.json()
        text = data["choices"][0]["message"].get("content")
    except (IndexError, KeyError, TypeError, ValueError):
        current_app.logger.warning("bot_reply: invalid response")
        return None, "تعذّر إنشاء الرد الآن."

    import re
    text = re.sub(r"<think>.*?(?:</think>|$)", "", str(text or ""), flags=re.DOTALL | re.IGNORECASE)
    text = _clean(text)
    if not text:
        return None, "لم أتمكن من صياغة رد مناسب. جرّب سؤالًا مختلفًا."
    return text, None
