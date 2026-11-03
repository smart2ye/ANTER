"""ANTER: قوالب البريد (HTML)."""

from flask import url_for


def _build_html(user, body_html, unsubscribe_url, base_url):
    """يبني HTML بالهوية البصرية لأنتر."""
    first_name = (user.name or user.username or 'صديقنا').strip().split()[0]
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>أنتر</title>
</head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:'Cairo','Tajawal',Arial,sans-serif;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f0f2f5;">
<tr><td align="center" style="padding:24px 12px;">

<table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);">

<!-- Header -->
<tr><td style="background:linear-gradient(135deg,#031E64 0%,#003AAB 55%,#160B8E 100%);padding:24px 20px;text-align:center;">
    <img src="{base_url}/static/img/logo.png" alt="ANTER" width="72" height="72" style="display:block;margin:0 auto 10px;border:0;outline:none;text-decoration:none;border-radius:12px;">
    <div style="font-size:26px;font-weight:900;color:#ffffff;letter-spacing:-0.5px;">أنتر</div>
    <div style="font-size:11px;color:#78F7FD;margin-top:2px;letter-spacing:3px;">ANTER</div>
</td></tr>

<!-- Body -->
<tr><td style="padding:32px 28px;color:#1a1a1a;font-size:15px;line-height:1.7;">
    <p style="margin:0 0 16px;">أهلاً <strong style="color:#031E64;">{first_name}</strong>،</p>
    {body_html}
</td></tr>

<!-- Footer -->
<tr><td style="background:#f8fafc;padding:20px 28px;text-align:center;border-top:1px solid #e4e6eb;">
    <p style="margin:0 0 8px;font-size:12px;color:#6b7280;">
        أنتر — شبكة التواصل العربي
    </p>
    <p style="margin:0 0 8px;font-size:12px;color:#6b7280;">
        <a href="{base_url}" style="color:#003AAB;text-decoration:none;">anter-1.onrender.com</a>
    </p>
    <p style="margin:0;font-size:11px;color:#9ca3af;">
        <a href="{unsubscribe_url}" style="color:#9ca3af;text-decoration:underline;">إلغاء الاشتراك</a>
    </p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def _cta_button(url, text):
    """زر CTA قابل للضغط."""
    return f'''<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:20px 0;">
<tr><td style="background:#003AAB;border-radius:10px;">
<a href="{url}" style="display:inline-block;padding:12px 28px;color:#ffffff;text-decoration:none;font-weight:700;font-size:14px;">{text}</a>
</td></tr></table>'''


def build_welcome_email(user, unsubscribe_url, base_url):
    """بريد ترحيب + ميزات جديدة + دعوة للإحالة."""
    first = (user.name or user.username or '').strip().split()[0] if (user.name or user.username) else 'صديقنا'
    posts_count = user.posts.count() if hasattr(user, 'posts') else 0
    followers = user.followers.count() if hasattr(user, 'followers') else 0

    # اقتراح مخصص حسب حالته
    if posts_count == 0:
        suggestion = """<p style="margin:0 0 16px;padding:12px 16px;background:#eff6ff;border-right:4px solid #003AAB;border-radius:8px;">
        <strong>💡 خطوتك الأولى:</strong> شارك منشورًا واحدًا — حتى سطرًا واحدًا. ستجد من يتفاعل معك.
        </p>"""
    elif followers == 0:
        suggestion = """<p style="margin:0 0 16px;padding:12px 16px;background:#eff6ff;border-right:4px solid #003AAB;border-radius:8px;">
        <strong>💡 خطوة مقترحة:</strong> تابع 3 حسابات تعجبك، وستجد من يتابعك.
        </p>"""
    else:
        suggestion = """<p style="margin:0 0 16px;padding:12px 16px;background:#eff6ff;border-right:4px solid #003AAB;border-radius:8px;">
        <strong>💡 جديد منذ زيارتك:</strong> اقتباس المنشورات، وتنسيق الإعلانات، وتحسين الكومبوزر.
        </p>"""

    body = f"""
    <p style="margin:0 0 16px;">
        لم نرك منذ فترة في <strong>أنتر</strong>، واشتقنا لك 💙
    </p>

    <p style="margin:0 0 16px;">
        المنصة تُبنى كل يوم، وهناك أشياء جديدة تنتظرك:
    </p>

    <ul style="margin:0 0 16px;padding-right:20px;color:#4b5563;">
        <li style="margin-bottom:6px;"><strong>اقتباس المنشورات</strong> — أضف تعليقك مع البطاقة الأصلية</li>
        <li style="margin-bottom:6px;"><strong>إشعارات فورية</strong> عند أي تفاعل معك</li>
        <li style="margin-bottom:6px;"><strong>مساعد ذكي</strong> يساعدك في الصياغة والأفكار</li>
    </ul>

    {suggestion}

    <p style="margin:0 0 16px;padding:16px;background:#fef3c7;border:1px solid #fcd34d;border-radius:10px;color:#78350f;">
        <strong>🎁 ميزة جديدة — الإحالة:</strong><br>
        شارك رابط دعوتك مع أصدقائك. عندما يسجّل 5 أشخاص عبره ويؤكدوا حساباتهم، تحصل أنت على <strong>العلامة الزرقاء ✔️</strong> تلقائيًا.
        <br><a href="{base_url}/users/invite" style="color:#b45309;font-weight:700;">احصل على رابط الدعوة →</a>
    </p>

    {_cta_button(base_url, 'زيارة أنتر')}

    <p style="margin:16px 0 0;color:#6b7280;font-size:13px;">
        إن كنت تواجه أي مشكلة، رد على هذه الرسالة — أقرأها بنفسي.
    </p>
    """

    html = _build_html(user, body, unsubscribe_url, base_url)
    subject = f"أنتر اشتاق لك يا {first} 💙 — ميزات جديدة تنتظرك"
    return subject, html
