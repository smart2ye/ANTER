import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
from flask import url_for

SMTP_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("MAIL_PORT", 587))
SMTP_USERNAME = os.environ.get("MAIL_USERNAME")
SMTP_PASSWORD = os.environ.get("MAIL_PASSWORD")
SMTP_FROM = os.environ.get("MAIL_FROM", SMTP_USERNAME)

def send_email(to, subject, html_content):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = str(Header(subject, "utf-8"))
        msg["From"] = formataddr(("ANTER", SMTP_FROM))
        msg["To"] = to
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to], msg.as_string())
            print(f"✅ تم إرسال البريد إلى {to}")
            return True
    except Exception as e:
        print(f"❌ فشل الإرسال: {e}")
        return False

def send_reset_email(user, token):
    reset_link = url_for('auth.reset_password', token=token, _external=True)
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; direction: rtl;">
        <h2 style="color: #6C3CE1;">إعادة تعيين كلمة السر</h2>
        <p>مرحباً {user.username}،</p>
        <p>اضغط على الرابط أدناه لتغيير كلمة السر (صالح لمدة ساعة):</p>
        <a href="{reset_link}" style="background: #6C3CE1; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">تغيير كلمة السر</a>
        <p style="margin-top: 20px; color: #888; font-size: 12px;">إذا لم تطلب إعادة التعيين، يمكنك تجاهل هذا البريد.</p>
        <p style="color: #888; font-size: 12px;">فريق دعم ANTER</p>
    </div>
    """
    return send_email(user.email, "🔑 إعادة تعيين كلمة السر – ANTER", html)


def send_welcome_email(user):
    """Send a welcome email after successful registration."""
    if not user.email or user.email.endswith("@phone-only.anter.local"):
        return False

    subject = "🎉 مرحباً بك في ANTER"
    first_name = (user.name or user.username or "صديقنا").strip().split()[0]

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; direction: rtl; color: #222;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #6C3CE1; margin-bottom: 8px;">ANTER</h1>
            <h2>🎉 مرحباً بك يا {first_name}</h2>
        </div>

        <p>يسعدنا انضمامك إلى ANTER.</p>

        <p>
            تم إنشاء حسابك بنجاح، ويمكنك الآن الاستمتاع بالمنصة والتواصل
            ومشاركة أفكارك ومتابعة من يهمك.
        </p>

        <div style="background: #f7f5ff; border-radius: 10px; padding: 16px; margin: 24px 0;">
            <strong>🔐 نصيحة لحماية حسابك</strong>
            <p style="margin-bottom: 0;">
                بريدك الإلكتروني غير مؤكد حتى الآن.
                ننصحك بتأكيده من إعدادات الحساب لاحقاً،
                حتى تتمكن من إثبات ملكية بريدك واستعادة الوصول إلى حسابك بسهولة عند الحاجة.
            </p>
        </div>

        <p>
            نتمنى لك تجربة جميلة وممتعة مع ANTER 💜
        </p>

        <p style="color: #888; font-size: 12px; margin-top: 30px;">
            فريق ANTER
        </p>
    </div>
    """

    return send_email(user.email, subject, html)

def send_password_change_confirmation(user):
    subject = "🔐 تم تغيير كلمة السر بنجاح – ANTER"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; direction: rtl;">
        <h2 style="color: #6C3CE1;">🔐 تم تغيير كلمة السر</h2>
        <p>مرحباً {user.username}،</p>
        <p>تم تغيير كلمة السر الخاصة بحسابك على <strong>ANTER</strong> بنجاح.</p>
        <p>إذا لم تكن أنت من قام بهذا التغيير، يُرجى التواصل مع فريق الدعم فوراً.</p>
        <p style="color: #888; font-size: 12px;">فريق دعم ANTER</p>
    </div>
    """
    return send_email(user.email, subject, html)
