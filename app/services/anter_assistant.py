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
from app.models import Follow, User
from app.services.anter_memory import conversation_for_ai, display_name, local_memory_reply


ASSISTANT_UNAVAILABLE_REPLY = (
    "أنا مساعد أنتر. أحتاج إلى لحظة قبل أن أتمكن من الرد؛ حاول إرسال رسالتك مجدداً بعد قليل."
)
ASSISTANT_TEXT_ONLY_REPLY = "أستطيع حالياً قراءة الرسائل النصية فقط. اكتب سؤالك أو طلبك في رسالة نصية واضحة."
ANTER_OVERVIEW_REPLY = (
    "ANTER شبكة تواصل اجتماعي عربية تجمع المستخدمين البشريين مع مزايا ذكاء اصطناعي مساندة. "
    "تدعم النشر والتعليقات (النصية والصوتية)، والقصص، والريلز، والمراسلة الفورية، والمكالمات الصوتية والمرئية. "
    "كما تتضمن مساعد أنتر — مساعد ذكي عربي مبني داخل المنصة. "
    "واجهتها عربية بالكامل باتجاه كتابة من اليمين إلى اليسار."
)
ANTER_MINI_MODEL_REPLY = (
    "أنا مساعد أنتر، نموذج عربي يمني جديد قيد التأسيس داخل شبكة ANTER. "
    "لم يُطلق بعد، ويطوّره عبدالقادر مهدلي لخدمة مجتمع أنتر."
)
ANTER_STATUS_REPLY = (
    "يتقدم العمل في ثلاثة مسارات مترابطة:\n"
    "1) منصة ANTER: نشر، تعليقات نصية وصوتية، قصص، ريلز، مراسلة فورية، مكالمات صوتية ومرئية، وحصاد سنوي.\n"
    "2) ANTER Messenger: تطبيق Android مرتبط بحسابات الشبكة ورسائلها.\n"
    "3) mini-llm Arabic: طبقة ذكاء عربية محلية تُشغّل مساعد أنتر.\n"
    "ما الجزء الذي تريد مراجعته؟"
)
THINKING_BLOCK = re.compile(r"<think>.*?(?:</think>|$)", flags=re.IGNORECASE | re.DOTALL)


def _messenger_download_reply() -> str:
    """إجابة محلية موثقة لتنزيل ANTER Messenger من دون استدعاء نموذج خارجي."""
    apk_url = current_app.config.get("ANTER_MESSENGER_APK_URL", "").strip()
    apk_sha256 = current_app.config.get("ANTER_MESSENGER_APK_SHA256", "").strip().lower()
    if not apk_url:
        return "رابط تنزيل ANTER Messenger غير متاح مؤقتاً. يمكنك مراجعة صفحة «عن ANTER» لاحقاً."
    return (
        "يمكنك تنزيل ANTER Messenger لأجهزة Android 7.0 فما فوق من الرابط التالي: "
        f"{apk_url}\n\n"
        "وللتحقق من سلامة الملف بعد التنزيل، بصمة SHA-256 الرسمية هي: "
        f"{apk_sha256}"
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
        if assistant.name != current_app.config["ANTER_ASSISTANT_NAME"]:
            assistant.name = current_app.config["ANTER_ASSISTANT_NAME"]
            changed = True
        assistant_bio = (
            "نموذج عربي يمني جديد قيد التأسيس داخل شبكة ANTER. "
            "لم يُطلق بعد، ويطوّره عبدالقادر مهدلي لخدمة مجتمع أنتر."
        )
        if assistant.bio != assistant_bio:
            assistant.bio = assistant_bio
            changed = True
        if assistant.message_privacy != "everyone":
            assistant.message_privacy = "everyone"
            changed = True
        review_password = current_app.config.get("ANTER_ASSISTANT_REVIEW_PASSWORD", "").strip()
        if review_password and not assistant.check_password(review_password):
            assistant.set_password(review_password)
            changed = True
        if changed:
            db.session.commit()
        return assistant

    assistant = User(
        username=username,
        email=current_app.config["ANTER_ASSISTANT_EMAIL"],
        name=current_app.config["ANTER_ASSISTANT_NAME"],
        bio=(
            "نموذج عربي يمني جديد قيد التأسيس داخل شبكة ANTER. "
            "لم يُطلق بعد، ويطوّره عبدالقادر مهدلي لخدمة مجتمع أنتر."
        ),
        avatar="default.png",
        is_verified=True,
        is_private=False,
        message_privacy="everyone",
        terms_agreed=True,
    )
    # تبقى كلمة المرور عشوائية ما لم يضبط المؤسس كلمة مراجعة بشرية في بيئة الخادم.
    review_password = current_app.config.get("ANTER_ASSISTANT_REVIEW_PASSWORD", "").strip()
    assistant.set_password(review_password or secrets.token_urlsafe(48))
    db.session.add(assistant)
    db.session.commit()
    return assistant


def follow_anter_assistant_for_user(user: User, assistant: User | None = None) -> bool:
    """يتأكد من أن المستخدم يتابع حساب مساعد أنتر مرة واحدة فقط."""
    assistant = assistant or ensure_anter_assistant_user()
    if user.id == assistant.id:
        return False
    exists = Follow.query.filter_by(follower_id=user.id, followed_id=assistant.id).first()
    if exists is not None:
        return False
    db.session.add(Follow(follower_id=user.id, followed_id=assistant.id))
    return True


def ensure_anter_assistant_followed_by_all_users() -> int:
    """ترقية الحسابات القائمة لتتابع مساعد أنتر مع تجنب التكرار."""
    assistant = ensure_anter_assistant_user()
    user_ids = [
        row[0] for row in db.session.query(User.id).filter(User.id != assistant.id).all()
    ]
    existing_follower_ids = {
        row[0]
        for row in db.session.query(Follow.follower_id).filter(
            Follow.followed_id == assistant.id,
            Follow.follower_id.in_(user_ids) if user_ids else False,
        ).all()
    }
    created = 0
    for user_id in user_ids:
        if user_id not in existing_follower_ids:
            db.session.add(Follow(follower_id=user_id, followed_id=assistant.id))
            created += 1
    if created:
        db.session.commit()
    return created


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
    # الاسم الأول للمؤسس (مثال: "عبدالقادر" من "عبدالقادر مهدلي")
    founder_first = founder_normalized.split()[0] if founder_normalized.split() else founder_normalized

    # هل السؤال يذكر المؤسس (بالاسم الكامل أو الأول)؟
    mentions_founder = (
        (founder_normalized and founder_normalized in normalized)
        or (founder_first and len(founder_first) >= 4 and founder_first in normalized)
    )

    if mentions_founder:
        # === أسئلة الهوية المباشرة: «هل أنت فلان؟» ===
        identity_question_markers = (
            "هل انت", "هل أنت", "انت هو", "أنت هو",
            "هل انت هو", "هل أنت هو",
            "انت تكون", "أنت تكون",
            "هل انت فلان", "هل أنت فلان",
        )
        # أيضاً: "انت <الاسم>" حيث الاسم هو المؤسس مباشرة
        direct_identity = (
            f"انت {founder_first}" in normalized
            or f"أنت {founder_first}" in normalized
            or f"انت {founder_normalized}" in normalized
            or f"أنت {founder_normalized}" in normalized
        )

        if any(m in normalized for m in identity_question_markers) or direct_identity:
            return (
                f"لا، أنا مساعد أنتر — نموذج ذكاء اصطناعي عربي مبني داخل منصة ANTER. "
                f"لست {founder}، بل أساعده في خدمة المجتمع. "
                f"{founder} هو مؤسس الشبكة وصاحب الرؤية. "
                f"كيف يمكنني مساعدتك اليوم؟"
            )

        # === أسئلة الغائب: «من هو فلان؟» ===
        third_person_markers = (
            "من هو", "من هي", "عرفني", "عرّفني", "حدثني عن", "أخبرني عن",
            "من مؤسس", "من هو مؤسس", "من صاحب", "من هو صاحب",
            "معلومات عن", "من يكون",
        )
        if any(m in normalized for m in third_person_markers):
            return f"{founder} هو مؤسس شبكة ANTER وصاحب رؤيتها."

        # === استثناء: إن كان المستخدم نفسه المؤسس ===
        user_is_founder = (
            user is not None
            and (user.name or '').strip() == founder.strip()
        )
        if user_is_founder:
            return f"أهلاً بك يا {founder}. يسعدني التواصل معك بوصفك مؤسس شبكة ANTER. كيف يمكنني مساعدتك اليوم؟"
        return f"{founder} هو مؤسس شبكة ANTER."

    greeting_markers = ("السلام عليكم", "مرحبا", "مرحباً", "اهلا", "أهلاً", "هلا")
    wellbeing_markers = ("كيف حالك", "كيفك", "كيف الحال")
    _strip_chars = " \t،,.!؟?-—\u060c\u061f\n"
    greeting_match = next((m for m in greeting_markers if m in normalized), None)
    if greeting_match:
        remainder = normalized.replace(greeting_match, "", 1).strip(_strip_chars)
        if len(remainder) < 20:
            if "السلام عليكم" in normalized:
                return f"وعليكم السلام يا {name}، أهلاً بك. أنا بخير، ويسعدني أن نكمل الحديث هنا. ما الذي يدور في بالك؟"
            return f"أهلاً يا {name}، نورت ANTER. أنا بخير وجاهز نتكلم أو ننجز أي شيء يخص المنصة."
    wellbeing_match = next((m for m in wellbeing_markers if m in normalized), None)
    if wellbeing_match:
        remainder = normalized.replace(wellbeing_match, "", 1).strip(_strip_chars)
        if len(remainder) < 20:
            return f"أنا بخير يا {name}، شكراً لسؤالك. ما الموضوع الذي تحب نبدأ به؟"

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

    messenger_markers = ("anter messenger", "messenger", "ماسنجر", "تطبيق انتر", "تطبيق أنتر")
    download_markers = ("تحميل", "تنزيل", "apk", "اندرويد", "android")
    if any(marker in normalized for marker in messenger_markers) and any(marker in normalized for marker in download_markers):
        return _messenger_download_reply()

    mentions_anter = "anter" in normalized or "انتر" in normalized or "أنتر" in normalized
    if not mentions_anter:
        return None

    # الردود الجاهزة عن ANTER مخصّصة للأسئلة القصيرة المركّزة فقط.
    # الرسائل الطويلة (مثل نص بريد مُلصَق) قد تذكر ANTER عرضاً، فتُحوَّل إلى النموذج.
    if len(normalized) > 200:
        return None

    founder_markers = ("مؤسس", "المؤسس", "اسس", "أسس")
    if any(marker in normalized for marker in founder_markers):
        return f"مؤسس شبكة ANTER هو {founder}."

    overview_markers = ("ماهو", "ما هو", "ماهي", "ما هي", "عرف", "عرّف", "عن anter", "عن انتر", "عن أنتر")
    if any(marker in normalized for marker in overview_markers):
        return ANTER_OVERVIEW_REPLY

    status_markers = ("وين وصلنا", "أين وصلنا", "حالة انتر", "حالة أنتر", "وضع انتر", "وضع أنتر", "ما يخص المنصة")
    if any(marker in normalized for marker in status_markers):
        return ANTER_STATUS_REPLY
    return None


def _assistant_system_prompt(user: User | None = None, assistant: User | None = None) -> str:
    """هوية ثابتة + تعريف بالمستخدم الحالي (اسمه ومعرّفه) لتفادي سؤاله كل مرة."""
    founder = current_app.config.get("ANTER_FOUNDER_NAME", "عبدالقادر مهدلي")
    identity_line = ""
    if user is not None and assistant is not None:
        try:
            name = display_name(user, assistant)
        except Exception:
            name = (user.name or user.username or "").strip()
        username = (user.username or "").strip()
        if name:
            if username and username != name:
                identity_line = (
                    f"المستخدم الذي تتحدث معه الآن هو {name} (معرّفه: @{username}). "
                    "خاطبه باسمه عند الحاجة، ولا تسأله عن اسمه مجدداً إن كان معروفاً في السياق. "
                )
            else:
                identity_line = (
                    f"المستخدم الذي تتحدث معه الآن هو {name}. "
                    "خاطبه باسمه عند الحاجة، ولا تسأله عن اسمه مجدداً إن كان معروفاً في السياق. "
                )
    return (
        "أنت مساعد أنتر الرسمي داخل شبكة ANTER الاجتماعية. "
        "تحدث بالعربية الفصحى المبسطة، وبنبرة ودودة وقريبة وطبيعية؛ كأنك زميل موثوق داخل المنصة. "
        "لا تكن متشدداً أو رسمياً أكثر من اللازم، ولا تكرر تعريفك بنفسك في كل رد، ولا تستخدم عبارات خدمة جامدة مثل «كيف يمكنني خدمتك» إلا عند الحاجة. "
        "يمكنك استخدام تحيات خفيفة مثل «أهلاً» و«تمام» و«بكل سرور»، لكن تجنب العامية المحلية المفرطة أو المبالغة العاطفية. "
        f"مؤسس شبكة ANTER هو {founder}. "
        + identity_line +
        "ANTER منصة تواصل اجتماعي تدعم النشر والتعليقات (النصية والصوتية)، والقصص، والريلز، والمراسلة، "
        "والمكالمات الصوتية والمرئية، والحصاد السنوي، وتعدد الحسابات على الجهاز. "
        "مساعد أنتر هو المساعد الذكي الرسمي داخل المنصة. "
        "توجد ذاكرة محلية قصيرة لكل مستخدم تحفظ الاسم والتفضيلات والسياق الحديث داخل ANTER فقط؛ ابنِ إجابتك على ما يذكره المستخدم في الرسالة الحالية ولا تدّع تذكّر ما لا تعرفه. "
        "إذا سُئلت عن النموذج أو التقنية، اذكر أنك نموذج عربي يمني جديد قيد التأسيس داخل شبكة ANTER، ولم يُطلق بعد، ويطوّره عبدالقادر مهدلي. "
        "لا تذكر اسم أي شركة أو مزوّد ذكاء اصطناعي أو واجهة برمجية، ولا تدخل في تفاصيل تشغيلية. "
        "لا تخلط ANTER بالكيانات الرياضية أو بأي منصة أخرى. "
        "لا تدّع أنك إنسان، ولا تخترع حقائق عن المنصة. "
        "إن لم تكن متأكداً، قل ذلك ببساطة واقترح الخطوة التالية المناسبة. "
        "في التحيات والأسئلة العابرة، اجعل الرد قصيراً: فقرتان صغيرتان كحد أقصى أو نحو 4 جمل. "
        "أما إذا طلب المستخدم صراحة شرحاً، أو تفصيلاً، أو خطوات، أو مقارنة، أو مثالاً ملموساً، "
        "فأجب بنبرة تعليمية منظّمة: استخدم عناوين فرعية قصيرة أو قوائم مرقّمة عند الحاجة، واذكر مثالاً عملياً واحداً على الأقل، "
        "دون إطالة لا فائدة فيها ودون تكرار. "
        "لا تسرد مراحل التأسيس أو خطط التطوير أو تفاصيل تشغيل المنصة إلا إذا طلب المستخدم ذلك صراحة. "
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

    api_key = current_app.config.get("ANTER_ASSISTANT_MINI_LLM_ARABIC_API_KEY", "").strip()
    if not api_key:
        current_app.logger.warning("مفتاح محرك mini-llm Arabic غير مضبوط.")
        return None, ASSISTANT_UNAVAILABLE_REPLY

    # سياق المحادثة السابقة (إن وُجد) — يُرسل قبل السؤال الحالي.
    prior_turns: list[dict[str, str]] = []
    if user is not None and assistant is not None:
        try:
            prior_turns = conversation_for_ai(user, assistant, budget_chars=3000)
        except Exception:
            current_app.logger.warning("تعذر بناء سياق مساعد أنتر.")
            prior_turns = []

    messages_payload: list[dict[str, str]] = [
        {"role": "system", "content": _assistant_system_prompt(user=user, assistant=assistant)},
    ]
    messages_payload.extend(prior_turns)
    messages_payload.append({"role": "user", "content": question})

    payload = {
        "model": current_app.config["ANTER_ASSISTANT_MINI_LLM_ARABIC_MODEL"],
        "messages": messages_payload,
        "temperature": 0.45,
        "max_tokens": current_app.config["ANTER_ASSISTANT_MINI_LLM_ARABIC_MAX_TOKENS"],
        "reasoning_effort": "none",
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "ANTER-Assistant/1.1",
    }
    timeout = current_app.config["ANTER_ASSISTANT_MINI_LLM_ARABIC_TIMEOUT_SECONDS"]
    api_url = current_app.config.get("MINI_LLM_ARABIC_API_URL", "").strip()
    if not api_url:
        current_app.logger.warning("عنوان محرك mini-llm Arabic غير مضبوط.")
        return None, ASSISTANT_UNAVAILABLE_REPLY

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException:
        current_app.logger.warning("تعذر الوصول إلى محرك مساعد أنتر.")
        return None, _safe_provider_error()

    if response.status_code != 200:
        current_app.logger.warning("تعذر طلب محرك مساعد أنتر: HTTP %s", response.status_code)
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
