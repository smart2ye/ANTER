#!/usr/bin/env python3
"""نقل البيانات من SQLite (نسخة Supabase) إلى Aiven PostgreSQL."""
import os
import pathlib
import sys

PROJECT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

SQLITE_PATH = PROJECT / "instance" / "anter.db.syncing"
if not SQLITE_PATH.exists():
    print(f"❌ الملف غير موجود: {SQLITE_PATH}")
    sys.exit(1)

# شغّل Flask على Aiven (يقرأ DATABASE_URL من shell أو .env)
from sqlalchemy import create_engine, select, insert, text
from app import create_app
from app.extensions import db

sqlite_engine = create_engine(f"sqlite:///{SQLITE_PATH}", future=True)

app = create_app()
with app.app_context():
    pg_engine = db.engine
    host = str(pg_engine.url).split('@')[-1].split('/')[0]
    print(f"🎯 الهدف: {host}")
    if 'aiven' not in host.lower():
        print("❌ الهدف ليس Aiven! أوقف.")
        sys.exit(1)

    print("🧹 تفريغ Aiven...")
    db.drop_all()
    db.create_all()

    metadata = db.metadata
    total = 0
    failed = []

    print("\n📦 نسخ الجداول...")
    for table in metadata.sorted_tables:
        try:
            with sqlite_engine.connect() as sconn:
                rows = sconn.execute(select(table)).mappings().all()
        except Exception as e:
            print(f"  ⚠️ {table.name}: تخطّي ({type(e).__name__})")
            continue

        if not rows:
            print(f"  ✓ {table.name}: 0")
            continue

        try:
            with pg_engine.begin() as pconn:
                pconn.execute(insert(table), [dict(r) for r in rows])
            print(f"  ✓ {table.name}: {len(rows)}")
            total += len(rows)
        except Exception as e:
            print(f"  ✗ {table.name}: {type(e).__name__}: {str(e)[:120]}")
            failed.append(table.name)

    print(f"\n📊 إجمالي: {total} صف")
    if failed:
        print(f"⚠️ جداول فشلت: {failed}")

    print("\n🔄 إعادة تسلسل IDs (Sequences)...")
    with pg_engine.begin() as conn:
        for table in metadata.sorted_tables:
            if 'id' not in table.columns:
                continue
            try:
                conn.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table.name}), 1), true)"
                ))
            except Exception as e:
                print(f"  ⚠️ {table.name}: {type(e).__name__}")
    print("✅ اكتمل.")

    # تقرير نهائي
    print("\n🎉 التقرير النهائي:")
    with pg_engine.connect() as conn:
        for t in ('users', 'posts', 'messages', 'videos', 'comments', 'follows'):
            try:
                n = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                print(f"  {t}: {n}")
            except Exception:
                pass
