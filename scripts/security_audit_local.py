"""فحص أمني محلي مصرح به لنسخة ANTER المعزولة.

يفحص التحكم في الوصول إلى إعادة توجيه الرسائل، وحماية CSRF لمسار حساس،
وهروب محتوى HTML في واجهة المنشورات. لا يتصل بأي خدمة خارجية.
"""

import json
import os
import tempfile

TEST_DB = os.path.join(tempfile.gettempdir(), "anter_security_probe.db")
try:
    os.remove(TEST_DB)
except FileNotFoundError:
    pass

os.environ["DATABASE_URL"] = "sqlite:///" + TEST_DB
os.environ["SECRET_KEY"] = "local-security-probe-only"
os.environ["ANTER_ASSISTANT_ENABLED"] = "false"

from app import create_app
from app.extensions import db
from app.models import Message, Post, User


def make_user(username):
    user = User(
        username=username,
        email=f"{username}@security.test",
        name=username,
        terms_agreed=True,
    )
    user.set_password("test-pass-1234")
    db.session.add(user)
    db.session.commit()
    return user


def authenticated_client(app, user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return client


def main():
    app = create_app()
    # يبدأ اختبار التحكم في الوصول بلا CSRF حتى يصل الطلب إلى فحص ملكية الكائن.
    app.config.update(TESTING=True, ANTER_ASSISTANT_ENABLED=False, WTF_CSRF_ENABLED=False)

    with app.app_context():
        owner = make_user("security_owner")
        recipient = make_user("security_recipient")
        outsider = make_user("security_outsider")
        target = make_user("security_target")
        message = Message(
            sender_id=owner.id,
            receiver_id=recipient.id,
            content="رسالة خاصة لا يجوز إعادة توجيهها من غير طرفيها",
        )
        xss_post = Post(
            author_id=owner.id,
            content='<img src=x onerror="window.__xss_probe=1">نص آمن',
            public_id="security-xss-probe",
        )
        db.session.add_all([message, xss_post])
        db.session.commit()
        message_id = message.id
        target_id = target.id
        outsider_id = outsider.id
        owner_id = owner.id

    outsider_client = authenticated_client(app, outsider_id)
    unauthorized_forward = outsider_client.post(
        f"/messages/forward/{message_id}",
        data={"target_user_id": target_id},
    )

    owner_client = authenticated_client(app, owner_id)
    # يعاد تفعيل CSRF لاختبار أن نفس المسار الحساس يرفض طلباً بلا رمز.
    app.config["WTF_CSRF_ENABLED"] = True
    csrf_probe = owner_client.post(
        f"/messages/forward/{message_id}",
        data={"target_user_id": target_id},
    )
    page = owner_client.get("/p/security-xss-probe")
    html = page.get_data(as_text=True)

    report = {
        "unauthorized_forward_status": unauthorized_forward.status_code,
        "csrf_free_sensitive_post_status": csrf_probe.status_code,
        "xss_raw_img_present": '<img src=x onerror="window.__xss_probe=1">' in html,
        "xss_escaped_img_present": "&lt;img" in html,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
