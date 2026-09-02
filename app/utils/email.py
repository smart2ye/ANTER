import os
import resend
from flask import url_for

resend.api_key = os.environ.get("RESEND_API_KEY")

def send_email(to, subject, html_content):
    """إرسال بريد إلكتروني عبر Resend"""
    try:
        params = {
            "from": os.environ.get("RESEND_FROM_EMAIL", "ANTER <noreply@resend.dev>"),
            "to": [to],
            "subject": subject,
            "html": html_content,
        }
        email = resend.Emails.send(params)
        print(f"✅ تم إرسال البريد إلى {to} (ID: {email['id']})")
        return True
    except Exception as e:
        print(f"❌ فشل إرسال البريد: {e}")
        return False

def send_verification_email(user):
    """إرسال بريد ترحيب وتأكيد الحساب"""
    subject = "مرحباً بك في ANTER – حسابك موثق الآن ✅"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; direction: rtl;">
        <h2 style="color: #6C3CE1;">مرحباً {user.username} 👋</h2>
        <p>نحن في <strong>ANTER</strong> نُرحّب بك ترحيباً خاصاً، ونشكرك على ثقتك باختيار منصتنا.</p>
        <p><strong>يسرّنا أن نُعلمك بأن حسابك قد حصل على العلامة الزرقاء</strong> ✅ كتقدير منا لانضمامك المبكّر.</p>
        <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 0;">✨ <strong>ما الذي ينتظرك الآن؟</strong><br>
            - استكشف المنشورات والريلز والقصص.<br>
            - تواصل مع المستخدمين الآخرين عبر الرسائل.<br>
            - استعن بـ <strong>مساعد أنتر</strong> الذكي.</p>
        </div>
        <p>أهلاً بك في ANTER، حيث تبدأ رحلتك الرقمية بثقة.</p>
        <a href="https://anter-1.onrender.com" style="background: #6C3CE1; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">زيارة المنصة</a>
        <p style="margin-top: 20px; color: #888; font-size: 12px;">فريق دعم ANTER</p>
    </div>
    """
    return send_email(user.email, subject, html)

def send_reset_email(user, token):
    """إرسال رابط إعادة تعيين كلمة السر (باستخدام itsdangerous token)"""
    reset_link = url_for('auth.reset_password', token=token, _external=True)
    subject = "🔑 إعادة تعيين كلمة السر – ANTER"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; direction: rtl;">
        <h2 style="color: #6C3CE1;">إعادة تعيين كلمة السر</h2>
        <p>مرحباً {user.username}،</p>
        <p>لقد تلقينا طلباً لإعادة تعيين كلمة السر الخاصة بحسابك على ANTER.</p>
        <p>اضغط على الرابط أدناه لتغيير كلمة السر (صالح لمدة ساعة):</p>
        <a href="{reset_link}" style="background: #6C3CE1; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">تغيير كلمة السر</a>
        <p style="margin-top: 20px; color: #888; font-size: 12px;">إذا لم تطلب إعادة التعيين، يمكنك تجاهل هذا البريد.</p>
        <p style="color: #888; font-size: 12px;">فريق دعم ANTER</p>
    </div>
    """
    return send_email(user.email, subject, html)
