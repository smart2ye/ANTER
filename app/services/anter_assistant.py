"""مساعد أنتر داخل الدردشة.

تُحفظ الذاكرة والسياق محلياً داخل ANTER. وعند الحاجة إلى إجابة عامة، لا يرسل
المساعد إلى الخدمة الخارجية سوى نص الرسالة الحالية، ولا يذكر المزوّد أو اسم
النموذج في واجهة المستخدم.
"""

from __future__ import annotations

import re
import secrets
from typing import Any

import requests
from flask import current_app

from app.extensions import db
from app.models import User
from app.services.anter_memory import display_name, local_memory_reply


GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
ASSISTANT_UNAVAILABLE_REPLY = (
    "أنا مساعد أنتر. أحتاج إلى لحظة قبل أن أتمكن من الرد؛ حاول إرسال رسالتك مجدداً بعد قليل."
)
ASSISTANT_TEXT_ONLY_REPLY = "أستطيع حالياً قراءة الرسائل النصية فقط. اكتب سؤالك أو طلبك في رسالة نصية واضحة."
ANTER_OVERVIEW_REPLY = (
    "ANTER شبكة اجتماعية هجينة تجمع المستخدمين البشريين مع مزايا ذكاء اصطناعي مساندة. "
    "تدعم النشر والتعليقات والقصص والريلز والمراسلة، بواجهة عربية واتجاه كتابة من اليمين إلى اليسار."
)
ANTER_MINI_MODEL_REPLY = (
    "أنا مساعد أنتر، نموذج عربي يمني جديد قيد التأسيس داخل شبكة ANTER. "
    "لم يُطلق بعد، ويطوّره عبدالقادر مهدلي لخدمة مجتمع أنتر."
)
THINKING_BLOCK = re.compile(r"<think>.*?(?:</think>|$)", flags=re.IGNORECASE | re.DOTALL)


def is_anter_assistant(user: User | None) -> bool:
    """يتحقق من هوية الحساب الآلي من دون الاعتماد على رقمه في قاعدة البيانات."""
    if user is None:
        return False
    username = current_app.config.get("ANTER_ASSISTANT_USERNAME", "anter_assistant")
    return user.username == username


def ensure_anter_assistant_user() -> User:
    """إنشاء حساب مساعد أنتر مرة واحدة، أو إعادة استخدامه في كل تشغيل."""
    username = current_app.config["ANTER_ASSISTANT_USERNAME"]
    assistant = User.query.filter_by(username=username).first()
    if assistant is not None:
        changed = False
        if not assistant.is_verified:
            assistant.is_verified = True
            changed = True
        if assistant.message_privacy != "everyone":
            assistant.message_privacy = "everyone"
            changed = True
        if changed:
            db.session.commit()
        return assistant

    assistant = User(
        username=username,
        email=current_app.config["ANTER_ASSISTANT_EMAIL"],
        name=current_app.config["ANTER_ASSISTANT_NAME"],
        bio="مساعد آلي داخل ANTER للمساعدة في الأسئلة وصياغة المحتوى بأسلوب مهذب.",
        avatar="default.png",
        is_verified=True,
        is_private=False,
        message_privacy="everyone",
        terms_agreed=True,
    )
    # الحساب الخدمي لا يستخدم تسجيل الدخول؛ تبقى كلمة المرور عشوائية وغير معروضة.
    assistant.set_password(secrets.token_urlsafe(48))
    db.session.add(assistant)
    db.session.commit()
    return assistant


def _clean_question(value: Any) -> str:
    return " ".join(str(value or "").split())


def _clean_answer(value: Any) -> str:
    """يزيل أي تفكير داخلي أو فراغات زائدة قبل عرض النص للمستخدم."""
    answer = THINKING_BLOCK.sub("", str(value or ""))
    return _clean_question(answer)


def _direct_anter_reply(
    question: str,
    user: User | None = None,
    assistant: User | None = None,
) -> str | None:
    """إجابات تعريفية مؤكدة لا تحتاج إلى استدعاء نموذج لغوي."""
    normalized = question.casefold()
    name = display_name(user, assistant) if user is not None and assistant is not None else "صديقي"

    founder = current_app.config.get("ANTER_FOUNDER_NAME", "عبدالقادر مهدلي")
    founder_normalized = founder.casefold()
    if founder_normalized and founder_normalized in normalized:
        return f"أهلاً بك يا {founder}. يسعدني التواصل معك بوصفك مؤسس شبكة ANTER. كيف يمكنني مساعدتك اليوم؟"

    greeting_markers = ("السلام عليكم", "مرحبا", "مرحباً", "اهلا", "أهلاً", "هلا")
    wellbeing_markers = ("كيف حالك", "كيفك", "كيف الحال")
    if any(marker in normalized for marker in greeting_markers):
        if "السلام عليكم" in normalized:
            return f"وعليكم السلام ورحمة الله وبركاته يا {name}. أنا مساعد أنتر، بخير وجاهز لمساعدتك في ANTER. كيف يمكنني خدمتك؟"
        return f"مرحباً يا {name}. أنا مساعد أنتر، بخير وجاهز لمساعدتك في ANTER. كيف يمكنني خدمتك؟"
    if any(marker in normalized for marker in wellbeing_markers):
        return f"أنا مساعد أنتر، بخير يا {name} وجاهز لمساعدتك في ANTER. ما الذي تود معرفته أو إنجازه؟"

    identity_markers = ("ما اسمك", "ما اسمك؟", "من انت", "من أنت", "من تكون", "انت هنا", "أنت هنا")
    if any(marker in normalized for marker in identity_markers):
        return f"{ANTER_MINI_MODEL_REPLY} أساعدك في فهم المنصة وصياغة المحتوى والردود بأسلوب مهذب."

    technical_identity_markers = (
        "انت groq", "أنت groq", "من groq", "grok", "gemini", "chatgpt", "chat gpt",
        "من اي نموذج", "من أي نموذج", "ما النموذج", "اي نموذج", "أي نموذج",
        "ما هي تقنيتك", "كيف تعمل تقنيا", "كيف تعمل تقنياً",
    )
    if any(marker in normalized for marker in technical_identity_markers):
        return f"{ANTER_MINI_MODEL_REPLY} كيف يمكنني مساعدتك اليوم؟"

    mentions_anter = "anter" in normalized or "انتر" in normalized or "أنتر" in normalized
    if not mentions_anter:
        return None

    founder_markers = ("مؤسس", "المؤسس", "اسس", "أسس")
    if any(marker in normalized for marker in founder_markers):
        return f"مؤسس شبكة ANTER هو {founder}."

    overview_markers = ("ماهو", "ما هو", "ماهي", "ما هي", "عرف", "عرّف", "عن anter", "عن انتر", "عن أنتر")
    if any(marker in normalized for marker in overview_markers):
        return ANTER_OVERVIEW_REPLY
    return None


def _assistant_system_prompt() -> str:
    """هوية ثابتة لا تحتوي على بيانات المستخدم أو تفاصيل البنية الداخلية."""
    founder = current_app.config.get("ANTER_FOUNDER_NAME", "عبدالقادر مهدلي")
    return (
        "أنت مساعد أنتر الرسمي داخل شبكة ANTER الاجتماعية. "
        "تحدث بالعربية الفصحى فقط وبأسلوب مهذب ومباشر ومفيد. "
        f"مؤسس شبكة ANTER هو {founder}. "
        "ANTER منصة اجتماعية هجينة تدعم النشر والتعليقات والقصص والريلز والمراسلة. "
        "عرّف نفسك دائماً باسم «مساعد أنتر» عند الحاجة. "
        "إذا سُئلت عن النموذج أو التقنية، اذكر أنك نموذج عربي يمني جديد قيد التأسيس داخل شبكة ANTER، ولم يُطلق بعد، ويطوّره عبدالقادر مهدلي. "
        "لا تذكر اسم أي شركة أو مزوّد ذكاء اصطناعي أو واجهة برمجية، ولا تدخل في تفاصيل تشغيلية. "
        "لا تخلط ANTER بالكيانات الرياضية أو بأي منصة أخرى. "
        "لا تدّع أنك إنسان، ولا تخترع حقائق عن المنصة. "
        "إن لم تكن متأكداً، وضّح ذلك باختصار واقترح طريقة آمنة للتحقق. "
        "اكتب الإجابة النهائية فقط من دون أي وسوم تفكير أو تحليل داخلي."
    )


def _safe_provider_error(status_code: int | None = None) -> str:
    """رسالة عامة لا تكشف هوية المزوّد أو تفاصيل الشبكة."""
    if status_code == 429:
        return "أنا مساعد أنتر. وصلت خدمة المساعد إلى حد مؤقت؛ انتظر قليلاً ثم أرسل رسالتك مجدداً."
    return ASSISTANT_UNAVAILABLE_REPLY


def get_assistant_reply(
    question: str,
    user: User | None = None,
    assistant: User | None = None,
) -> tuple[str | None, str | None]:
    """إرجاع جواب مساعد أنتر باستخدام السؤال الحالي وذاكرة محلية محدودة.

    تُعالَج أوامر الذاكرة والترحيب بالاسم محلياً. أما الطلب الخارجي فيتضمن
    السؤال الحالي فقط، ولا يرسل الاسم أو التفضيلات أو سياق الذاكرة.
    """
    if not current_app.config.get("ANTER_ASSISTANT_ENABLED", True):
        return None, "مساعد أنتر معطل مؤقتاً من إعدادات الخادم."

    question = _clean_question(question)
    if not question:
        return None, "اكتب رسالة نصية أولاً لأتمكن من مساعدتك."

    maximum = current_app.config["ANTER_ASSISTANT_MAX_QUESTION_CHARACTERS"]
    if len(question) > maximum:
        return None, f"اجعل رسالتك أقصر من {maximum} حرفاً ثم أرسلها مجدداً."

    memory_reply = local_memory_reply(question, user, assistant)
    if memory_reply:
        return memory_reply, None

    direct_reply = _direct_anter_reply(question, user=user, assistant=assistant)
    if direct_reply:
        return direct_reply, None

    api_key = current_app.config.get("ANTER_ASSISTANT_GROQ_API_KEY", "").strip()
    if not api_key:
        current_app.logger.warning("مفتاح موفّر مساعد أنتر غير مضبوط.")
        return None, ASSISTANT_UNAVAILABLE_REPLY

    payload = {
        "model": current_app.config["ANTER_ASSISTANT_GROQ_MODEL"],
        "messages": [
            {"role": "system", "content": _assistant_system_prompt()},
            {"role": "user", "content": question},
        ],
        "temperature": 0.45,
        "max_tokens": current_app.config["ANTER_ASSISTANT_GROQ_MAX_TOKENS"],
        "reasoning_effort": "none",
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "ANTER-Assistant/1.1",
    }
    timeout = current_app.config["ANTER_ASSISTANT_GROQ_TIMEOUT_SECONDS"]

    try:
        response = requests.post(GROQ_CHAT_URL, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException:
        current_app.logger.warning("تعذر الوصول إلى مزود مساعد أنتر.")
        return None, _safe_provider_error()

    if response.status_code != 200:
        current_app.logger.warning("تعذر طلب مزود مساعد أنتر: HTTP %s", response.status_code)
        return None, _safe_provider_error(response.status_code)

    try:
        data = response.json()
        answer = _clean_answer(data["choices"][0]["message"].get("content"))
    except (IndexError, KeyError, TypeError, ValueError):
        current_app.logger.warning("استجابة مساعد أنتر غير صالحة.")
        return None, _safe_provider_error()

    if not answer:
        return None, _safe_provider_error()

    max_reply = current_app.config["ANTER_ASSISTANT_MAX_REPLY_CHARACTERS"]
    if len(answer) > max_reply:
        answer = answer[:max_reply].rsplit(" ", 1)[0].rstrip("،؛:.") + "…"
    return answer, None
