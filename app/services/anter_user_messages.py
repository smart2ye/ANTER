"""System messages sent from the official ANTER assistant account."""

from app.extensions import db
from app.models import Message
from app.services.anter_assistant import ensure_anter_assistant_user


WELCOME_PREFIX = "مرحباً بك في ANTER"
REPORT_ACK_PREFIX = "تم استلام بلاغك"


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
    )
    db.session.add(message)

    # تنبيه تشغيلي داخل صندوق وارد مساعد أنتر للمراجعة البشرية، من دون كشف تفاصيل أكثر من اللازم.
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
