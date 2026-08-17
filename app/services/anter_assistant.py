"""مساعد أنتر داخل الدردشة.

يرسل نص الرسالة الحالية فقط إلى mini-llm عبر واجهته الخادمية المحمية.
لا تُرسل مفاتيح أو ملفات مرفقة أو تاريخ المحادثة إلى الخدمة.
"""

from __future__ import annotations

import secrets
from typing import Any

import requests
from flask import current_app

from app.extensions import db
from app.models import User


ASSISTANT_UNAVAILABLE_REPLY = (
    "أنا مساعد أنتر. تعذر الوصول إلى خدمة المساعد الآن، لذا أستطيع المساعدة "
    "مجدداً بعد تشغيل mini-llm والتحقق من إعداد الاتصال المحلي."
)
ASSISTANT_TEXT_ONLY_REPLY = "أستطيع حالياً قراءة الرسائل النصية فقط. اكتب سؤالك أو طلبك في رسالة نصية واضحة."
ANTER_OVERVIEW_REPLY = (
    "ANTER شبكة اجتماعية هجينة تجمع المستخدمين البشريين مع مزايا ذكاء اصطناعي مساندة. "
    "تدعم النشر والتعليقات والقصص والريلز والمراسلة، بواجهة عربية واتجاه كتابة من اليمين إلى اليسار."
)


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


def _direct_anter_reply(question: str) -> str | None:
    """إجابات تعريفية مؤكدة لا تحتاج إلى استدعاء نموذج لغوي."""
    normalized = question.casefold()
    identity_markers = ("ما اسمك", "ما اسمك؟", "من انت", "من أنت", "من تكون", "انت هنا", "أنت هنا")
    if any(marker in normalized for marker in identity_markers):
        return "أنا مساعد أنتر، المساعد الآلي داخل شبكة ANTER. أساعدك في فهم المنصة وصياغة المحتوى والردود بأسلوب مهذب."

    mentions_anter = "anter" in normalized or "انتر" in normalized or "أنتر" in normalized
    if not mentions_anter:
        return None

    founder_markers = ("مؤسس", "المؤسس", "اسس", "أسس")
    if any(marker in normalized for marker in founder_markers):
        founder = current_app.config.get("ANTER_FOUNDER_NAME", "عبدالقادر مهدلي")
        return f"مؤسس شبكة ANTER هو {founder}."

    overview_markers = ("ماهو", "ما هو", "ماهي", "ما هي", "عرف", "عرّف", "عن anter", "عن انتر", "عن أنتر")
    if any(marker in normalized for marker in overview_markers):
        return ANTER_OVERVIEW_REPLY
    return None


def _assistant_question(question: str) -> str:
    """سياق عام ثابت؛ لا يضيف تاريخ محادثة أو أي بيانات مستخدم أخرى."""
    founder = current_app.config.get("ANTER_FOUNDER_NAME", "عبدالقادر مهدلي")
    return (
        "أنت مساعد أنتر داخل شبكة ANTER، ولست مساعد إنتر ميلان ولا أي جهة أخرى. "
        "تحدث بالعربية الفصحى فقط وبأسلوب مهذب ومباشر. "
        f"مؤسس شبكة ANTER هو {founder}. "
        "ANTER منصة اجتماعية هجينة تدعم النشر والتعليقات والقصص والريلز والمراسلة. "
        "لا تقل إنك نموذج من شركة أخرى، ولا تخلط اسم ANTER بالكيانات الرياضية. "
        "أجب عن السؤال التالي فقط:\n\n"
        f"{question}"
    )


def get_assistant_reply(question: str) -> tuple[str | None, str | None]:
    """طلب جواب من mini-llm باستخدام السؤال الحالي فقط.

    يعيد ``(text, None)`` عند النجاح، أو ``(None, public_message)`` عند التعذر.
    لا تمرر تفاصيل الشبكة أو مفاتيح API إلى واجهة الدردشة أو السجل.
    """
    if not current_app.config.get("ANTER_ASSISTANT_ENABLED", True):
        return None, "مساعد أنتر معطل مؤقتاً من إعدادات الخادم."

    question = _clean_question(question)
    if not question:
        return None, "اكتب رسالة نصية أولاً لأتمكن من مساعدتك."

    maximum = current_app.config["ANTER_ASSISTANT_MAX_QUESTION_CHARACTERS"]
    if len(question) > maximum:
        return None, f"اجعل رسالتك أقصر من {maximum} حرفاً ثم أرسلها مجدداً."

    direct_reply = _direct_anter_reply(question)
    if direct_reply:
        return direct_reply, None

    api_url = current_app.config.get("MINI_LLM_API_URL", "").strip()
    api_key = current_app.config.get("MINI_LLM_API_KEY", "").strip()
    if not api_url or not api_key:
        return None, ASSISTANT_UNAVAILABLE_REPLY

    payload = {
        "question": _assistant_question(question),
        "mode": current_app.config.get("ANTER_ASSISTANT_MODE", "hybrid"),
    }
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
        "User-Agent": "ANTER-Assistant/1.0",
    }
    timeout = current_app.config["MINI_LLM_TIMEOUT_SECONDS"]

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException:
        current_app.logger.warning("تعذر الوصول إلى خدمة mini-llm لمساعد أنتر.")
        return None, ASSISTANT_UNAVAILABLE_REPLY

    if response.status_code != 200:
        current_app.logger.warning("تعذر طلب mini-llm لمساعد أنتر: HTTP %s", response.status_code)
        return None, ASSISTANT_UNAVAILABLE_REPLY

    try:
        data = response.json()
    except ValueError:
        current_app.logger.warning("استجابة mini-llm لمساعد أنتر ليست JSON صالحاً.")
        return None, ASSISTANT_UNAVAILABLE_REPLY

    answer = _clean_question(data.get("answer"))
    if not data.get("ok") or not answer:
        return None, ASSISTANT_UNAVAILABLE_REPLY

    max_reply = current_app.config["ANTER_ASSISTANT_MAX_REPLY_CHARACTERS"]
    if len(answer) > max_reply:
        answer = answer[:max_reply].rsplit(" ", 1)[0].rstrip("،؛:.") + "…"
    return answer, None
