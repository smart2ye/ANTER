#!/usr/bin/env python3
"""تغيير اسم مستخدم ANTER من الطرفية مع التحقق والتأكيد.

الاستخدام:
    python scripts/change_username.py --current u_old --new new.username
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.models import User, UserActivity
from app.routes.users import USERNAME_PATTERN
from app.services.anter_assistant import is_anter_assistant


def normalize_username(value: str) -> str:
    return (value or "").strip().lstrip("@")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="تغيير اسم مستخدم ANTER بأمان من الطرفية.",
    )
    command.add_argument("--current", help="اسم المستخدم الحالي للحساب")
    command.add_argument("--new", dest="new_username", help="اسم المستخدم الجديد")
    return command


def prompt_if_missing(value: str | None, label: str) -> str:
    return value if value is not None else input(label).strip()


def main() -> int:
    args = parser().parse_args()
    current_username = normalize_username(prompt_if_missing(args.current, "اسم المستخدم الحالي: "))
    new_username = normalize_username(prompt_if_missing(args.new_username, "اسم المستخدم الجديد: "))

    if not current_username:
        print("توقف: أدخل اسم المستخدم الحالي.", file=sys.stderr)
        return 2
    if not USERNAME_PATTERN.fullmatch(new_username):
        print(
            "توقف: الاسم يجب أن يكون من 3 إلى 30 حرفاً أو رقماً، دون مسافات. "
            "يسمح بالشرطة السفلية والنقطة بين أجزاء الاسم فقط.",
            file=sys.stderr,
        )
        return 2

    app = create_app()
    with app.app_context():
        user = User.query.filter(User.username.ilike(current_username)).first()
        if user is None:
            print(f"توقف: لم يُعثر على الحساب @{current_username}.", file=sys.stderr)
            return 3
        if is_anter_assistant(user):
            print("توقف: اسم مستخدم مساعد أنتر الرسمي محجوز ولا يمكن تغييره.", file=sys.stderr)
            return 4

        existing = User.query.filter(User.username.ilike(new_username)).first()
        if existing is not None and existing.id != user.id:
            print(f"توقف: اسم المستخدم @{new_username} مستخدم بالفعل.", file=sys.stderr)
            return 5
        if user.username == new_username:
            print("لا تغيير: اسم المستخدم الحالي مطابق للاسم المطلوب.")
            return 0

        print(f"سيُغيّر الحساب @{user.username} إلى @{new_username}.")
        confirmation = input(f"اكتب {new_username} للتأكيد: ").strip()
        if confirmation != new_username:
            print("أُلغي التغيير: لم تتطابق عبارة التأكيد.", file=sys.stderr)
            return 6

        user.username = new_username
        db.session.add(
            UserActivity(
                user_id=user.id,
                action="username_change",
                details='{"source":"terminal"}',
            )
        )
        db.session.commit()
        print(f"تم تغيير اسم المستخدم بنجاح إلى @{new_username}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
