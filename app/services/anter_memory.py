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


MAX_CONTEXT_ITEMS = 6
MAX_CONTEXT_CHARS = 220
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


def remember_user_message(user: User, assistant: User, question: str) -> None:
    """يحفظ سياقاً محلياً محدوداً، ولا يحفظ المحتوى الحساس أو طلب محو الذاكرة."""
    question = _clean_text(question, MAX_CONTEXT_CHARS)
    if not question or _is_sensitive(question) or is_memory_clear_request(question):
        return

    memory = _get_memory(user, assistant, create=True)
    changed = False
    preferences = _load_list(memory.preferences_json)
    recent_context = _load_list(memory.recent_context_json)

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

    recent_context.append({
        "role": "user",
        "text": question,
        "at": datetime.utcnow().isoformat(timespec="seconds"),
    })
    recent_context = recent_context[-MAX_CONTEXT_ITEMS:]
    memory.recent_context_json = _save_list(recent_context)
    memory.preferences_json = _save_list(preferences[-MAX_PREFERENCE_ITEMS:])
    db.session.commit()


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


def recent_user_context(user: User, assistant: User) -> list[str]:
    memory = _get_memory(user, assistant)
    if memory is None:
        return []
    values: list[str] = []
    for item in _load_list(memory.recent_context_json):
        if isinstance(item, dict) and item.get("role") == "user":
            value = _clean_text(item.get("text"), MAX_CONTEXT_CHARS)
            if value:
                values.append(value)
    return values[-MAX_CONTEXT_ITEMS:]


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

    if any(marker in normalized for marker in ("ما آخر ما سألته", "ما الذي قلته سابقا", "ما الذي قلته سابقاً", "هل تتذكر سياق")):
        context = recent_user_context(user, assistant)
        if not context:
            return "لا يوجد سياق محفوظ بعد لهذه المحادثة."
        last_item = context[-2] if len(context) > 1 else context[-1]
        return f"آخر ما أتذكره من سياقك في هذه المحادثة: «{last_item}»."

    return None
