import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import url_for

MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}
MAIL_USERNAME = os.environ.get("MAIL_USERNAME") or os.environ.get("MAIL_FROM")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
MAIL_FROM = os.environ.get("MAIL_FROM") or MAIL_USERNAME


def send_email(to, subject, html_content):
    """Send an HTML email via Gmail SMTP."""
    try:
        if not MAIL_USERNAME or not MAIL_PASSWORD:
            print("ERROR: MAIL_USERNAME or MAIL_PASSWORD missing")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = str(subject)
        msg["From"] = f"ANTER <{MAIL_FROM}>"
        msg["To"] = to
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        context = ssl.create_default_context()
        if MAIL_PORT == 465:
            # Implicit SSL (SMTPS) - works reliably on Termux / OpenSSL 3
            with smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT, timeout=30, context=context) as server:
                server.ehlo()
                server.login(MAIL_USERNAME, MAIL_PASSWORD)
                server.sendmail(MAIL_FROM, [to], msg.as_string())
        else:
            with smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=30) as server:
                server.ehlo()
                if MAIL_USE_TLS:
                    server.starttls(context=context)
                    server.ehlo()
                server.login(MAIL_USERNAME, MAIL_PASSWORD)
                server.sendmail(MAIL_FROM, [to], msg.as_string())

        print(f"OK: email sent to {to}")
        return True

    except Exception as e:
        print(f"ERROR: send_email failed: {type(e).__name__}: {e}")
        return False


def send_reset_email(user, token):
    reset_link = url_for('auth.reset_password', token=token, _external=True)
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; direction: rtl;">
        <h2 style="color: #003AAB;">إعادة تعيين كلمة السر</h2>
        <p>مرحباً {user.username}،</p>
        <p>اضغط على الرابط أدناه لتغيير كلمة السر (صالح لمدة 48 ساعة):</p>
        <a href="{reset_link}" style="background: #003AAB; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">تغيير كلمة السر</a>
        <p style="margin-top: 20px; color: #888; font-size: 12px;">إذا لم تطلب إعادة التعيين، يمكنك تجاهل هذا البريد.</p>
        <p style="color: #888; font-size: 12px;">فريق دعم ANTER</p>
    </div>
    """
    return send_email(user.email, "🔑 إعادة تعيين كلمة السر – ANTER", html)


def send_email_verification(user, token):
    """إرسال رسالة تأكيد البريد الإلكتروني."""
    if not user.email or user.email.endswith("@phone-only.anter.local"):
        return False

    verification_link = url_for(
        'users.confirm_email',
        token=token,
        _external=True,
    )

    first_name = (user.name or user.username or "صديقنا").strip().split()[0]

    subject = "✉️ تأكيد بريدك الإلكتروني – ANTER"

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; direction: rtl; color: #222;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #003AAB; margin-bottom: 8px;">ANTER</h1>
            <h2>✉️ تأكيد البريد الإلكتروني</h2>
        </div>

        <p>مرحباً {first_name}،</p>

        <p>
            طلبت تأكيد بريدك الإلكتروني المرتبط بحسابك في ANTER.
            اضغط على الزر التالي لإتمام عملية التأكيد:
        </p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{verification_link}"
               style="display: inline-block; background: #003AAB; color: #fff; text-decoration: none; padding: 13px 28px; border-radius: 8px; font-weight: bold;">
                تأكيد البريد الإلكتروني
            </a>
        </div>

        <div style="background: #f0f6ff; border-radius: 10px; padding: 16px; margin: 24px 0;">
            <strong>🔐 ملاحظة أمنية</strong>
            <p style="margin-bottom: 0;">
                هذا الرابط صالح لمدة 24 ساعة فقط.
                إذا لم تطلب تأكيد بريدك الإلكتروني، يمكنك تجاهل هذه الرسالة.
            </p>
        </div>

        <p style="color: #888; font-size: 12px; margin-top: 30px;">
            فريق ANTER
        </p>
    </div>
    """

    return send_email(user.email, subject, html)


def send_welcome_email(user):
    """Send a welcome email after successful registration."""
    if not user.email or user.email.endswith("@phone-only.anter.local"):
        return False

    subject = "🎉 مرحباً بك في ANTER"
    first_name = (user.name or user.username or "صديقنا").strip().split()[0]

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; direction: rtl; color: #222;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #003AAB; margin-bottom: 8px;">ANTER</h1>
            <h2>🎉 مرحباً بك يا {first_name}</h2>
        </div>

        <p>يسعدنا انضمامك إلى ANTER.</p>

        <p>
            تم إنشاء حسابك بنجاح، ويمكنك الآن الاستمتاع بالمنصة والتواصل
            ومشاركة أفكارك ومتابعة من يهمك.
        </p>

        <div style="background: #f0f6ff; border-radius: 10px; padding: 16px; margin: 24px 0;">
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
        <h2 style="color: #003AAB;">🔐 تم تغيير كلمة السر</h2>
        <p>مرحباً {user.username}،</p>
        <p>تم تغيير كلمة السر الخاصة بحسابك على <strong>ANTER</strong> بنجاح.</p>
        <p>إذا لم تكن أنت من قام بهذا التغيير، يُرجى التواصل مع فريق الدعم فوراً.</p>
        <p style="color: #888; font-size: 12px;">فريق دعم ANTER</p>
    </div>
    """
    return send_email(user.email, subject, html)
