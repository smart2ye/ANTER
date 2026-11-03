"""ANTER: إرسال تذكير تأكيد البريد لغير المؤكدين — بدفعات.

الاستخدام:
    python3 scripts/send_confirm_emails.py --dry-run --batch 1
    python3 scripts/send_confirm_emails.py --to me@example.com
    python3 scripts/send_confirm_emails.py --send --batch 1
    python3 scripts/send_confirm_emails.py --send --batch 2
"""
import sys
import time
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import create_app
from app.extensions import db
from app.models import User, UserActivity
from app.utils.email import send_email
from app.services.email_templates import build_confirm_email
from app.services.unsubscribe import get_or_create_token
from app.routes.users import create_email_verification_token

BASE_URL = 'https://anter-1.onrender.com'
RATE_LIMIT_SECONDS = 12


def get_targets():
    """غير المؤكدين، غير الملغين، ببريد حقيقي."""
    return (
        User.query
        .filter(
            User.email_verified.is_(False),
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


def split_batches(items, n):
    """يقسّم إلى دفعات بحجم متساوٍ تقريبًا."""
    size = (len(items) + n - 1) // n
    return [items[i:i+size] for i in range(0, len(items), size)]


def send_one(app, uid, dry_run=False, override_to=None):
    with app.app_context():
        u = User.query.get(uid)
        if not u:
            return False, 'not found'
        if u.email_opted_out:
            return False, 'opted out'
        # في وضع الاختبار (override_to)، تجاوز فحص "مؤكد بالفعل"
        if u.email_verified and not override_to:
            return False, 'already verified'

        try:
            verify_token = create_email_verification_token(u)
            verification_url = f'{BASE_URL}/users/settings/email/verify/{verify_token}'

            unsub_token = get_or_create_token(u)
            unsubscribe_url = f'{BASE_URL}/unsubscribe/{unsub_token}'

            subject, html = build_confirm_email(u, verification_url, unsubscribe_url, BASE_URL)
            to = override_to or u.email

            if dry_run:
                print(f"  [DRY-RUN] {u.username} -> {to} | {subject[:60]}")
                return True, 'dry-run'

            ok = send_email(to, subject, html)
            if ok:
                try:
                    db.session.add(UserActivity(
                        user_id=u.id,
                        action='confirm_email_sent',
                        details=f'to={to}',
                    ))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
            return ok, 'sent' if ok else 'failed'
        except Exception as e:
            return False, f'error: {type(e).__name__}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--to', help='بريد واحد للاختبار')
    parser.add_argument('--send', action='store_true')
    parser.add_argument('--batch', type=int, choices=[1, 2], help='دفعة 1 أو 2')
    args = parser.parse_args()

    if not (args.dry_run or args.to or args.send):
        print("حدد: --dry-run أو --to أو --send")
        return 1

    app = create_app()

    # وضع الاختبار — يستخدم حساب المؤسس (id=1) للتوكن
    if args.to:
        with app.app_context():
            target = User.query.get(1)
            if not target:
                print("founder (id=1) not found")
                return 1
            ok, status = send_one(app, target.id, override_to=args.to)
            print(f"result: {ok} ({status})")
            return 0 if ok else 1

    # دفعات
    with app.app_context():
        targets = get_targets()
        batches = split_batches(targets, 2)
        if not args.batch:
            print(f"total: {len(targets)}")
            print(f"batch 1: {len(batches[0])}")
            print(f"batch 2: {len(batches[1])}")
            return 0
        selected = batches[args.batch - 1]
        info = [(u.id, u.username, u.email) for u in selected]

    print(f"batch {args.batch}: {len(info)} recipients")
    sent = failed = 0
    for i, (uid, un, em) in enumerate(info, 1):
        ok, status = send_one(app, uid, dry_run=args.dry_run)
        print(f"[{i}/{len(info)}] {un} ({em}): {status}")
        if ok:
            sent += 1
        else:
            failed += 1
        if not args.dry_run and i < len(info):
            time.sleep(RATE_LIMIT_SECONDS)

    print(f"\n=== {sent} sent · {failed} failed ===")
    return 0


if __name__ == '__main__':
    sys.exit(main())
