"""System messages sent from the official ANTER assistant account."""

from app.extensions import db
from app.models import Message
from app.services.anter_assistant import ensure_anter_assistant_user


WELCOME_PREFIX = "مرحباً بك في ANTER"
REPORT_ACK_PREFIX = "تم استلام بلاغك"
REPORT_RESOLVED_PREFIX = "شكراً لك — تم اتخاذ إجراء بشأن بلاغك"
REPORT_REJECTED_PREFIX = "راجعنا بلاغك"


# أسماء عربية لأنواع البلاغات (مفتاح القاموس = قيمة reason الأساسية)
REPORT_TOPICS = {
    'spam': 'المحتوى المزعج أو المكرر',
    'harassment': 'التحرش أو التنمّر',
    'hate': 'خطاب الكراهية',
    'hate_speech': 'خطاب الكراهية',
    'impersonation': 'انتحال الشخصية',
    'violence': 'العنف أو التهديد',
    'threat': 'التهديد',
    'nudity': 'المحتوى غير اللائق',
    'sexual': 'المحتوى الجنسي',
    'misinformation': 'المعلومات المضللة',
    'false_info': 'المعلومات المضللة',
    'copyright': 'انتهاك حقوق الملكية',
    'scam': 'الاحتيال أو النصب',
    'self_harm': 'إيذاء النفس',
    'terrorism': 'المحتوى الإرهابي',
    'other': 'سبب آخر',
    'support': 'طلب مساعدة',
    # أنواع طلبات النظام (غير بلاغات محتوى) — مفاتيح صريحة أوّلاً
    'password-reset-request': 'إعادة تعيين كلمة السر',
    'password-reset': 'إعادة تعيين كلمة السر',
    'verification:email': 'تأكيد البريد الإلكتروني',
    'verification:account': 'توثيق الحساب',
    'login': 'المساعدة في تسجيل الدخول',
    'verification': 'التوثيق',
}


def _resolve_topic(reason):
    """يحوّل reason الخام إلى وصف عربي واضح."""
    if not reason:
        return 'محتوى مخالف'

    raw = reason.strip().lower()

    # أزل البادئات
    for prefix in ('user-report:', 'support:', 'account-request:'):
        if raw.startswith(prefix):
            raw = raw[len(prefix):].strip()

    # جرّب المطابقة المباشرة
    if raw in REPORT_TOPICS:
        return REPORT_TOPICS[raw]

    # جرّب المطابقة الجزئية
    for key, label in REPORT_TOPICS.items():
        if key in raw:
            return label

    # إن كان نصًا عربيًا (سبب حر) — استخدمه مباشرةً
    if any('\u0600' <= ch <= '\u06FF' for ch in reason):
        return reason.strip()[:80]

    return 'محتوى مخالف'


def _safe_first_name(user):
    """اسم مختصر للاستخدام في الترحيب."""
    if not user:
        return 'صديقنا'
    name = (getattr(user, 'name', None) or getattr(user, 'username', None) or '').strip()
    return name.split()[0] if name else 'صديقنا'


def _already_sent(sender_id, receiver_id, prefix):
    return (
        Message.query.filter_by(sender_id=sender_id, receiver_id=receiver_id)
        .filter(Message.content.startswith(prefix))
        .first()
        is not None
    )


def send_welcome_message(user):
    """Send one concise onboarding message from the official assistant."""
    assistant = ensure_anter_assistant_user()
    if user.id == assistant.id or _already_sent(assistant.id, user.id, WELCOME_PREFIX):
        return None

    first_name = (user.name or "صديقنا").strip().split()[0]
    message = Message(
        sender_id=assistant.id,
        receiver_id=user.id,
        content=(
            f"{WELCOME_PREFIX} يا {first_name}. أنا مساعد أنتر، ويسعدني وجودك معنا. "
            "يمكنك مشاركة أفكارك، متابعة من يهمك، واستخدام الرسائل بأمان واحترام. "
            "إذا احتجت مساعدة في استخدام المنصة أو صياغة محتوى، اكتب لي في أي وقت."
        ),
        is_ai=True,
    )
    db.session.add(message)
    return message


def send_report_receipt(reporter, report, post):
    """Acknowledge a report without treating it as an automated moderation decision."""
    assistant = ensure_anter_assistant_user()
    receipt_key = f"{REPORT_ACK_PREFIX} رقم {report.id}"
    if _already_sent(assistant.id, reporter.id, receipt_key):
        return None

    report_summary = (
        f"{REPORT_ACK_PREFIX} رقم {report.id}. شكراً لمساعدتك في الحفاظ على مجتمع ANTER آمناً. "
        "تم تحويل البلاغ إلى قائمة المراجعة، وسيُتعامل معه بتدخل بشري وفق القواعد المعتمدة. "
        "لا يعني استلام البلاغ اتخاذ قرار نهائي أو حذف المحتوى تلقائياً."
    )
    message = Message(
        sender_id=assistant.id,
        receiver_id=reporter.id,
        content=report_summary,
        is_ai=True,
    )
    db.session.add(message)

    # تنبيه تشغيلي داخل صندوق وارد مساعد أنتر للمراجعة البشرية، من دون كشف تفاصيل أكثر من اللازم.
    # ملاحظة: هذه رسالة من المستخدم للمساعد، لذا لا تُعلَّم كـ is_ai.
    inbox_message = Message(
        sender_id=reporter.id,
        receiver_id=assistant.id,
        content=(
            f"بلاغ جديد رقم {report.id}: سبب البلاغ «{report.reason}». "
            f"المنشور المعني: /p/{post.public_id}. راجع البلاغ يدوياً من لوحة الإدارة."
        ),
    )
    db.session.add(inbox_message)
    return message

def build_report_resolution_text(reporter, report):
    """يبني نص رسالة شكر وتأكيد عند حل البلاغ.

    لا يُرسل عبر الشات — يُخزَّن في report.resolution_note
    ويُعرض في تبويب «المساعدة والدعم» وفي الإشعار.
    """
    name = _safe_first_name(reporter)
    topic = _resolve_topic(report.reason)

    return (
        f"شكراً لك — تم اتخاذ إجراء بشأن بلاغك\n\n"
        f"مرحباً {name}،\n"
        f"راجعنا بلاغك رقم {report.id} بخصوص «{topic}»، "
        f"وتأكدنا من مخالفته لمعايير مجتمع ANTER، وتم اتخاذ الإجراء المناسب.\n\n"
        f"شكراً لحرصك على جعل ANTER مساحة آمنة ومحترمة. "
        f"مساهمتك تُحدث فرقاً حقيقياً. 💙\n\n"
        f"— فريق ANTER"
    )


def build_report_rejection_text(reporter, report, admin_note=None):
    """يبني نص رسالة توضيح عند رفض البلاغ.

    لا يُرسل عبر الشات — يُخزَّن في report.resolution_note
    ويُعرض في تبويب «المساعدة والدعم» وفي الإشعار.
    """
    name = _safe_first_name(reporter)
    topic = _resolve_topic(report.reason)

    body = (
        f"راجعنا بلاغك رقم {report.id}\n\n"
        f"مرحباً {name}،\n"
        f"راجعنا بلاغك بخصوص «{topic}» بعناية. "
        f"بعد التدقيق، لم نجد أن المحتوى يخالف معايير مجتمع ANTER حالياً.\n\n"
    )

    if admin_note:
        body += f"ملاحظة الفريق: {admin_note.strip()[:400]}\n\n"

    body += (
        f"نقدّر حرصك على حماية المجتمع، ونشجّعك على الاستمرار في الإبلاغ عن أي محتوى تراه مخالفاً. "
        f"وجودك معنا يجعل ANTER أفضل. 🌟\n\n"
        f"— فريق ANTER"
    )
    return body

