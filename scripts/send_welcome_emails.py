"""ANTER: إرسال رسائل ترحيب/تذكير للمستخدمين المؤكدين بالبريد.

الاستخدام:
    source venv-termux/bin/activate
    unset DATABASE_URL
    export DATABASE_URL="$(python3 -c "...")"   # Aiven
    python3 scripts/send_welcome_emails.py --dry-run    # عرض
    python3 scripts/send_welcome_emails.py --to me@example.com   # اختبار
    python3 scripts/send_welcome_emails.py --send        # إرسال للجميع
"""
import sys
import time
import argparse
from pathlib import Path

# مسار الجذر
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import create_app
from app.extensions import db
from app.models import User, UserActivity
from app.utils.email import send_email
from app.services.email_templates import build_welcome_email
from app.services.unsubscribe import get_or_create_token

BASE_URL = 'https://anter-1.onrender.com'
RATE_LIMIT_SECONDS = 6  # 10 رسائل/دقيقة — ضمن حدود Gmail


def get_targets():
    """يجلب المؤكدين بالبريد، غير الملغين، غير المحذوفين، النشطين."""
    return (
        User.query
        .filter(
            User.email_verified.is_(True),
            User.email_opted_out.is_(False),
            User.is_deleted.is_(False),
            User.email.isnot(None),
            User.email != '',
            User.email.notlike('%@phone-only.anter.local'),
            User.email.notlike('%@merged.anter.local'),
        )
        .order_by(User.last_seen.desc().nullslast())
        .all()
    )


def send_to_one(app, user, dry_run=False, override_to=None):
    """يبني ويرسل رسالة لمستخدم واحد."""
    with app.app_context():
        # جلب مستخدم محدّث داخل السياق
        u = User.query.get(user.id)
        if not u:
            return False, 'not found'
        if u.email_opted_out:
            return False, 'opted out'

        token = get_or_create_token(u)
        unsubscribe_url = f'{BASE_URL}/unsubscribe/{token}'
        subject, html = build_welcome_email(u, unsubscribe_url, BASE_URL)

        to = override_to or u.email
        if dry_run:
            print(f"  [DRY-RUN] → {u.username} | {to} | {subject[:50]}")
            return True, 'dry-run'

        ok = send_email(to, subject, html)
        if ok:
            try:
                db.session.add(UserActivity(
                    user_id=u.id,
                    action='welcome_email_sent',
                    details=f'to={to}',
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()
        return ok, 'sent' if ok else 'failed'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='عرض فقط')
    parser.add_argument('--to', help='إرسال نسخة واحدة لبريد محدد (اختبار)')
    parser.add_argument('--send', action='store_true', help='إرسال فعلي')
    args = parser.parse_args()

    if not (args.dry_run or args.to or args.send):
        print("يجب تحديد أحد الخيارات: --dry-run, --to, --send")
        return 1

    app = create_app()

    # وضع الاختبار: بريد واحد
    if args.to:
        with app.app_context():
            target = User.query.filter_by(id=1).first()
            if not target:
                print("user id=1 not found")
                return 1
            ok, status = send_to_one(app, target, override_to=args.to)
            print(f"result: {ok} ({status})")
            return 0 if ok else 1

    # وضع الإرسال الجماعي
    with app.app_context():
        targets = get_targets()
        print(f"targets: {len(targets)}")
        ids = [(u.id, u.username, u.email) for u in targets]

    sent = failed = 0
    for i, (uid, uname, email) in enumerate(ids, 1):
        with app.app_context():
            u = User.query.get(uid)
            ok, status = send_to_one(app, u, dry_run=args.dry_run)
        print(f"[{i}/{len(ids)}] {uname} ({email}): {status}")
        if ok:
            sent += 1
        else:
            failed += 1
        if not args.dry_run and i < len(ids):
            time.sleep(RATE_LIMIT_SECONDS)

    print(f"\n=== النتيجة ===")
    print(f"sent: {sent}")
    print(f"failed: {failed}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
