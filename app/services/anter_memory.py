"""ذاكرة محلية ومحدودة لمساعد أنتر.

هذه الطبقة لا تستدعي أي خدمة خارجية. وهي تحفظ فقط سياقاً قصيراً وتفضيلات
يصرّح بها المستخدم بوضوح، مع تجاهل كلمات المرور والمفاتيح والبيانات الحساسة.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from app.extensions import db
from app.models import AssistantMemory, User


MAX_CONTEXT_ITEMS = 24
MAX_CONTEXT_CHARS = 800

# ANTER: رسائل النظام الإدارية — لا تُمرَّر إلى المساعد
# (بلاغات، طلبات مساعدة، طلبات إعادة تعيين، طلبات توثيق)
SYSTEM_MESSAGE_PREFIXES = (
    'بلاغ جديد رقم',
    'طلب مساعدة',
    'طلب إعادة تعيين',
    'طلب تأكيد البريد',
    'طلب توثيق',
    'user-report:',
    'verification:',
    'support:',
    'password-reset',
    'تحديث جديد لتطبيق ANTER',
    'تم استلام بلاغك',
    'شكراً لك — تم اتخاذ إجراء بشأن بلاغك',
)


def _is_system_message(text: str) -> bool:
    """هل هذه رسالة نظام إدارية؟"""
    if not text:
        return False
    stripped = text.strip()
    return any(stripped.startswith(p) for p in SYSTEM_MESSAGE_PREFIXES)


MAX_PREFERENCE_ITEMS = 6
MAX_PREFERENCE_CHARS = 180

_SENSITIVE_PATTERN = re.compile(
    r"(?:كلمة\s*المرور|password|api[ _-]?key|مفتاح\s*(?:api|واجهة|سري)|"
    r"رمز\s*(?:التحقق|سري)|token|بطاقة|cvv|iban)",
    flags=re.IGNORECASE,
)
_FORGET_PATTERN = re.compile(
    r"(?:امسح|احذف|انس|لا\s+تتذكر|امح)\s*(?:ال)?ذاكر(?:ة|تك|تي)?",
    flags=re.IGNORECASE,
)
_NAME_PATTERN = re.compile(
    r"(?:اسمي|نادني|نادِني|يمكنك\s+مناداتي)\s+(?:هو\s+)?([\u0600-\u06FF\w\s-]{2,60})",
    flags=re.IGNORECASE,
)
_MEMORY_PATTERN = re.compile(
    r"^\s*(?:تذكر|تذكّر|احفظ|سجل|سجّل|تعلم|تعلّم)\s+(?:أنني|اني|أني|إنني)?\s*(.+)",
    flags=re.IGNORECASE,
)
_SELF_ROLE_PATTERN = re.compile(
    r"(?:^|[،؛.!؟]\s*)(?:أنا|انا)\s+(?P<name>[\u0600-\u06FF][\u0600-\u06FF\w-]{1,30})\s+"
    r"(?P<role>(?:مدير|مسؤول|رئيس|مؤسس|مطور|مشرف|منسق)[^.!؟\n]{0,140})",
    flags=re.IGNORECASE,
)


def _clean_text(value: Any, maximum: int) -> str:
    text = " ".join(str(value or "").split()).strip(" ،؛:.")
    return text[:maximum].rstrip(" ،؛:.")


def _load_list(value: str) -> list[Any]:
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _save_list(items: list[Any]) -> str:
    return json.dumps(items, ensure_ascii=False, separators=(",", ":"))


def _get_memory(user: User, assistant: User, create: bool = False) -> AssistantMemory | None:
    memory = AssistantMemory.query.filter_by(
        user_id=user.id,
        assistant_id=assistant.id,
    ).first()
    if memory is None and create:
        memory = AssistantMemory(user_id=user.id, assistant_id=assistant.id)
        db.session.add(memory)
    return memory


def _is_sensitive(text: str) -> bool:
    return bool(_SENSITIVE_PATTERN.search(text or ""))


def is_memory_clear_request(question: str) -> bool:
    return bool(_FORGET_PATTERN.search(question or ""))


def display_name(user: User, assistant: User) -> str:
    """يستخدم الاسم الذي يحدده المستخدم للنداء، ثم اسم ملفه الشخصي."""
    memory = _get_memory(user, assistant)
    if memory:
        preferences = _load_list(memory.preferences_json)
        for item in reversed(preferences):
            if isinstance(item, dict) and item.get("kind") == "preferred_name":
                name = _clean_text(item.get("value"), 60)
                if name:
                    return name
    return _clean_text(user.name or user.username, 60) or "صديقي"


def _append_context(memory: AssistantMemory, role: str, text: str) -> None:
    recent_context = _load_list(memory.recent_context_json)
    recent_context.append({
        "role": role,
        "text": text,
        "at": datetime.utcnow().isoformat(timespec="seconds"),
    })
    memory.recent_context_json = _save_list(recent_context[-MAX_CONTEXT_ITEMS:])


def remember_user_message(user: User, assistant: User, question: str) -> None:
    """يحفظ سياقاً محلياً محدوداً، ولا يحفظ المحتوى الحساس أو طلب محو الذاكرة."""
    question = _clean_text(question, MAX_CONTEXT_CHARS)
    if not question or _is_sensitive(question) or is_memory_clear_request(question):
        return

    memory = _get_memory(user, assistant, create=True)
    changed = False
    preferences = _load_list(memory.preferences_json)
    name_match = _NAME_PATTERN.search(question)
    if name_match:
        preferred_name = _clean_text(name_match.group(1), 60)
        if preferred_name and not _is_sensitive(preferred_name):
            preferences = [
                item for item in preferences
                if not isinstance(item, dict) or item.get("kind") != "preferred_name"
            ]
            preferences.append({"kind": "preferred_name", "value": preferred_name})
            changed = True

    role_match = _SELF_ROLE_PATTERN.search(question)
    if role_match:
        stated_name = _clean_text(role_match.group("name"), 60)
        stated_role = _clean_text(role_match.group("role"), MAX_PREFERENCE_CHARS)
        if stated_name and stated_role and not _is_sensitive(stated_role):
            preferences = [
                item for item in preferences
                if not isinstance(item, dict) or item.get("kind") not in {"preferred_name", "role_description"}
            ]
            preferences.append({"kind": "preferred_name", "value": stated_name})
            preferences.append({"kind": "role_description", "value": stated_role})
            changed = True

    preference_match = _MEMORY_PATTERN.search(question)
    if preference_match:
        preference = _clean_text(preference_match.group(1), MAX_PREFERENCE_CHARS)
        if preference and not _is_sensitive(preference):
            duplicate = any(
                isinstance(item, dict)
                and item.get("kind") == "preference"
                and item.get("value") == preference
                for item in preferences
            )
            if not duplicate:
                preferences.append({"kind": "preference", "value": preference})
                changed = True

    _append_context(memory, "user", question)
    memory.preferences_json = _save_list(preferences[-MAX_PREFERENCE_ITEMS:])
    db.session.commit()


def remember_assistant_reply(user: User, assistant: User, answer: str) -> None:
    """Keep the assistant side of the short local conversation for useful recall."""
    answer = _clean_text(answer, MAX_CONTEXT_CHARS)
    if not answer or _is_sensitive(answer):
        return
    memory = _get_memory(user, assistant, create=True)
    _append_context(memory, "assistant", answer)
    db.session.commit()


def recent_conversation(user: User, assistant: User) -> list[dict[str, str]]:
    """Return a small local-only transcript suitable for recall and continuity prompts."""
    memory = _get_memory(user, assistant)
    if memory is None:
        return []
    items: list[dict[str, str]] = []
    for item in _load_list(memory.recent_context_json):
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        text = _clean_text(item.get("text"), MAX_CONTEXT_CHARS)
        if role in {"user", "assistant"} and text:
            items.append({"role": role, "text": text})
    return items[-MAX_CONTEXT_ITEMS:]


def conversation_for_ai(
    user: User,
    assistant: User,
    budget_chars: int = 3000,
) -> list[dict[str, str]]:
    """يبني سياق المحادثة السابقة لإرساله إلى محرك AI.

    - يُعيد آخر الرسائل (الأحدث أولاً في الاقتطاع).
    - يستبعد آخر رسالة للمستخدم (لأنها السؤال الحالي وسيُمرَّر منفصلًا).
    - يحترم ميزانية أحرف صارمة لتفادي تجاوز حد المزوّد.
    """
    items: list[dict[str, str]] = []
    memory = _get_memory(user, assistant)
    if memory is None:
        return items

    raw = _load_list(memory.recent_context_json)
    turns: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        text = _clean_text(item.get("text"), MAX_CONTEXT_CHARS)
        if role not in {"user", "assistant"} or not text:
            continue
        # ANTER: تجاهل رسائل النظام الإدارية (بلاغات، طلبات) — ليست حواراً.
        if _is_system_message(text):
            continue
        # تجاهل الرسائل القصيرة جدًا (حرف أو رمز) لأنها تشوّش السياق.
        if len(text.strip()) < 3:
            continue
        # تجاهل ردود الفشل المتكررة من المساعد — ليست جزءًا من الحوار الحقيقي.
        if role == "assistant" and text.startswith("أنا مساعد أنتر. أحتاج إلى لحظة"):
            continue
        turns.append({"role": role, "text": text})

    # استبعاد آخر رسالة للمستخدم (السؤال الحالي)
    if turns and turns[-1]["role"] == "user":
        turns = turns[:-1]

    # نأخذ من الأحدث للأقدم حتى نستهلك الميزانية
    selected: list[dict[str, str]] = []
    used = 0
    for turn in reversed(turns):
        cost = len(turn["text"]) + 8  # هامش صغير للدور
        if used + cost > budget_chars:
            break
        selected.append(turn)
        used += cost

    selected.reverse()
    for turn in selected:
        items.append({"role": turn["role"], "content": turn["text"]})
    return items


def clear_memory(user: User, assistant: User) -> bool:
    """يمحو ذاكرة المساعد فقط ولا يحذف رسائل المستخدم."""
    memory = _get_memory(user, assistant)
    if memory is None:
        return False
    db.session.delete(memory)
    db.session.commit()
    return True


def preference_values(user: User, assistant: User) -> list[str]:
    memory = _get_memory(user, assistant)
    if memory is None:
        return []
    values: list[str] = []
    for item in _load_list(memory.preferences_json):
        if isinstance(item, dict) and item.get("kind") == "preference":
            value = _clean_text(item.get("value"), MAX_PREFERENCE_CHARS)
            if value:
                values.append(value)
    return values[-MAX_PREFERENCE_ITEMS:]


def role_description(user: User, assistant: User) -> str:
    memory = _get_memory(user, assistant)
    if memory is None:
        return ""
    for item in reversed(_load_list(memory.preferences_json)):
        if isinstance(item, dict) and item.get("kind") == "role_description":
            value = _clean_text(item.get("value"), MAX_PREFERENCE_CHARS)
            if value and not _is_sensitive(value):
                return value
    return ""


def recent_user_context(user: User, assistant: User) -> list[str]:
    return [item["text"] for item in recent_conversation(user, assistant) if item["role"] == "user"]


def _prior_user_messages(question: str, user: User, assistant: User) -> list[str]:
    """يعيد رسائل المستخدم السابقة فقط، ويستثني السؤال الحالي إن كان قد حُفظ للتو."""
    messages = recent_user_context(user, assistant)
    cleaned_question = _clean_text(question, MAX_CONTEXT_CHARS)
    if messages and _clean_text(messages[-1], MAX_CONTEXT_CHARS) == cleaned_question:
        messages = messages[:-1]
    return messages


def local_memory_reply(question: str, user: User | None, assistant: User | None) -> str | None:
    """يعالج أوامر الذاكرة والاستدعاءات محلياً بلا إرسال أي بيانات للخارج."""
    if user is None or assistant is None:
        return None

    normalized = (question or "").casefold()
    if is_memory_clear_request(normalized):
        clear_memory(user, assistant)
        return "تم مسح ذاكرة مساعد أنتر الخاصة بك. بقي سجل رسائلك في الدردشة كما هو."

    name_match = _NAME_PATTERN.search(question or "")
    if name_match and not _is_sensitive(name_match.group(1)):
        return f"حسناً، سأناديك {display_name(user, assistant)} في محادثاتك مع مساعد أنتر."

    preference_match = _MEMORY_PATTERN.search(question or "")
    if preference_match and not _is_sensitive(preference_match.group(1)):
        return "تم حفظ هذا التفضيل محلياً لمساعدتك بصورة أفضل. يمكنك طلب ما أتذكره أو مسح الذاكرة في أي وقت."

    if any(marker in normalized for marker in ("ما اسمي", "ماذا تناديني", "بأي اسم تناديني")):
        return f"سأناديك {display_name(user, assistant)}. يمكنك كتابة «نادني …» لتغيير الاسم."

    if any(marker in normalized for marker in ("ماذا تتذكر عني", "ما الذي تتذكره عني", "ما تفضيلاتي", "ماذا حفظت")):
        preferences = preference_values(user, assistant)
        if not preferences:
            return "لا أحتفظ بتفضيلات عنك بعد. يمكنك أن تكتب مثلاً: «تذكر أنني أفضل الردود المختصرة»."
        listed = "، ".join(f"«{value}»" for value in preferences)
        return f"أتذكر التفضيلات التي طلبت مني حفظها: {listed}. يمكنك طلب مسح الذاكرة في أي وقت."

    role_markers = ("ماهي وظيفتي", "ما هي وظيفتي", "ما وظيفتي", "ما عملي", "ما هو دوري", "ما دوري")
    reminder_markers = ("لكنني شاركتك", "لكنني قلت لك", "قلت لك قبل قليل", "اخبرتك قبل قليل", "أخبرتك قبل قليل")
    if any(marker in normalized for marker in role_markers + reminder_markers):
        saved_role = role_description(user, assistant)
        if saved_role:
            return f"صحيح، أخبرتني أنك {display_name(user, assistant)}، {saved_role}."
        return "لا أرى دوراً وظيفياً صريحاً محفوظاً في هذه المحادثة بعد. يمكنك كتابته بهذه الصيغة: «أنا … مدير …» وسأتذكره داخل هذه المحادثة."

    identity_markers = ("من انا", "من أنا", "من كنت", "من أكون")
    previous_turn_markers = ("قبل رسالتين", "قبل رسالتان", "الرسالة التي سبقت", "ما الرسالة السابقة")
    asks_identity = any(marker in normalized for marker in identity_markers)
    asks_previous_turn = any(marker in normalized for marker in previous_turn_markers)
    if asks_identity or asks_previous_turn:
        previous_messages = _prior_user_messages(question, user, assistant)
        parts: list[str] = []
        if asks_identity:
            identity_message = next(
                (
                    item for item in reversed(previous_messages)
                    if re.search(r"(?:^|\s)(?:أنا|اني|اسمي)\s+", item, flags=re.IGNORECASE)
                ),
                "",
            )
            if identity_message:
                parts.append(f"ذكرت لي قبل قليل: «{identity_message}».")
            else:
                parts.append(f"لا أرى تعريفاً صريحاً باسمك في هذه المحادثة، وسأناديك {display_name(user, assistant)}.")
        if asks_previous_turn:
            if len(previous_messages) >= 2:
                parts.append(f"وقبل رسالتين قلت: «{previous_messages[-2]}».")
            elif previous_messages:
                parts.append(f"آخر رسالة سابقة وجدتها هي: «{previous_messages[-1]}».")
            else:
                parts.append("لا توجد رسائل سابقة محفوظة في سياق هذه المحادثة بعد.")
        return " ".join(parts)

    if any(marker in normalized for marker in ("ما آخر ما سألته", "ما الذي قلته سابقا", "ما الذي قلته سابقاً", "هل تتذكر سياق")):
        context = recent_conversation(user, assistant)
        if not context:
            return "لم نتبادل رسائل كافية بعد لأحتفظ بسياق هذه المحادثة."
        last_user = next((item["text"] for item in reversed(context) if item["role"] == "user"), "")
        last_assistant = next((item["text"] for item in reversed(context) if item["role"] == "assistant"), "")
        if last_user and last_assistant:
            return f"نعم، أتذكر أننا كنا نتحدث عن: «{last_user}». وكان آخر ردي: «{last_assistant}»."
        return f"نعم، أتذكر أننا كنا نتحدث عن: «{last_user or context[-1]['text']}»."

    return None
