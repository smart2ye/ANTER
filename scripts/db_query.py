#!/usr/bin/env python3
"""أداة سريعة لعرض معلومات من قاعدة البيانات النشطة."""
import sys, pathlib
PROJECT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from sqlalchemy import inspect, text
from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    insp = inspect(db.engine)
    tables = sorted(insp.get_table_names())
    print(f"🎯 Host: {str(db.engine.url).split('@')[-1].split('/')[0]}")
    print(f"📊 عدد الجداول: {len(tables)}\n")

    if len(sys.argv) < 2:
        # عرض موجز لكل الجداول
        with db.engine.connect() as conn:
            print("جدول | عدد الصفوف")
            print("-" * 40)
            for t in tables:
                try:
                    n = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
                    print(f"  {t:35s} {n}")
                except Exception as e:
                    print(f"  {t:35s} ✗")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "users":
        with db.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT id, username, name, email, phone, is_admin, is_active FROM users ORDER BY id"
            )).all()
            for r in rows:
                print(f"  #{r[0]:3d} | {r[1]:25s} | {r[2] or '':25s} | {r[3] or '':30s} | phone={r[4] or '-'} | admin={r[5]} active={r[6]}")

    elif cmd == "posts":
        with db.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT id, author_id, substr(content,1,60), created_at FROM posts ORDER BY id DESC LIMIT 20"
            )).all()
            for r in rows:
                print(f"  #{r[0]:3d} | author={r[1]} | {r[2]} | {r[3]}")

    elif cmd == "messages":
        with db.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT id, sender_id, receiver_id, substr(content,1,40), created_at FROM messages ORDER BY id DESC LIMIT 20"
            )).all()
            for r in rows:
                print(f"  #{r[0]:3d} | {r[1]}→{r[2]} | {r[3] or '':40s} | {r[4]}")

    elif cmd == "videos":
        with db.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT id, title, is_reel, file_path, views FROM videos ORDER BY id"
            )).all()
            for r in rows:
                print(f"  #{r[0]:3d} | reel={r[2]} | {r[1] or '':30s} | {r[3]} | views={r[4]}")

    elif cmd == "follows":
        with db.engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT f.follower_id, u1.username, f.followed_id, u2.username
                FROM follows f
                JOIN users u1 ON u1.id = f.follower_id
                JOIN users u2 ON u2.id = f.followed_id
                ORDER BY f.follower_id, f.followed_id
            """)).all()
            for r in rows:
                print(f"  {r[1]:25s} → {r[3]}")

    elif cmd == "sql":
        if len(sys.argv) < 3:
            print("الاستخدام: python3 scripts/db_query.py sql \"SELECT ...\"")
            sys.exit(1)
        query = sys.argv[2]
        with db.engine.connect() as conn:
            rows = conn.execute(text(query)).all()
            for r in rows:
                print("  ", r)

    else:
        print(f"أمر غير معروف: {cmd}")
        print("المتاح: users | posts | messages | videos | follows | sql")
