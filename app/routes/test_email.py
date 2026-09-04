from flask import Blueprint, current_app
from app.utils.email import send_email
import os
from datetime import datetime

test_email_bp = Blueprint('test_email', __name__)

@test_email_bp.route('/test-email')
def test_email():
    to_email = os.environ.get('TEST_EMAIL', os.environ.get('MAIL_USERNAME'))
    if not to_email:
        return "❌ لم يتم تحديد TEST_EMAIL أو MAIL_USERNAME في البيئة"

    subject = "🧪 اختبار البريد من ANTER على Render"
    html = f"""
    <h2>✅ تم إرسال هذا البريد بنجاح من خادم Render</h2>
    <p>إذا وصلت هذه الرسالة، فإن إعدادات SMTP تعمل بشكل صحيح.</p>
    <p>وقت الإرسال: <strong>{datetime.now()}</strong></p>
    """
    success = send_email(to_email, subject, html)
    if success:
        return f"✅ تم إرسال بريد اختبار إلى <strong>{to_email}</strong> بنجاح. تحقق من صندوق الوارد (أو البريد المزعج)."
    else:
        return f"❌ فشل إرسال البريد إلى {to_email}. تحقق من سجلات Render لمزيد من التفاصيل."
