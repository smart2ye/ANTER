#!/usr/bin/env python3
"""
ANTER — سحب نسخة من القاعدة السحابية إلى SQLite المحلي.

آمن:
- قراءة فقط من السحابة.
- يكتب في instance/anter.db.syncing (ملف جديد).
- لا يلمس instance/anter.db حتى تنفّذ خطوة استبدال منفصلة.
"""
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

CLOUD_URL = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI')
if not CLOUD_URL or CLOUD_URL.startswith('sqlite'):
    print("ERROR: DATABASE_URL للسحابة غير محمّل. شغّل أولًا: source ~/.bashrc")
    sys.exit(1)

LOCAL_DB = PROJECT / 'instance' / 'anter.db.syncing'
if LOCAL_DB.exists():
    LOCAL_DB.unlink()

os.environ.pop('DATABASE_URL', None)
os.environ['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{LOCAL_DB}'

from app import create_app
from app.extensions import db

app = create_app()
print(f"✔ تم تهيئة التطبيق على: {LOCAL_DB}")

from sqlalchemy import create_engine, select, insert, inspect

cloud_engine = create_engine(
    CLOUD_URL,
    connect_args={
        'connect_timeout': 20,
        'keepalives': 1,
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 5,
    },
    pool_pre_ping=True,
)

cloud_insp = inspect(cloud_engine)
cloud_tables = set(cloud_insp.get_table_names())

metadata = db.metadata
copy_order = [t.name for t in metadata.sorted_tables if t.name in cloud_tables]

print(f"عدد جداول الموديلات: {len(metadata.tables)}")
print(f"عدد جداول السحابة: {len(cloud_tables)}")
print(f"جداول ستُنسخ: {len(copy_order)}")
print("----")

import time
from sqlalchemy.exc import OperationalError


def fetch_with_retry(t, max_attempts=4):
    """يسحب جدولًا كاملًا مع إعادة محاولة عند انقطاع SSL."""
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            with cloud_engine.connect() as cloud_conn:
                return cloud_conn.execute(select(t)).mappings().all()
        except OperationalError as e:
            msg = str(e)
            last_err = e
            if 'SSL' in msg or 'eof' in msg.lower() or 'server closed' in msg.lower():
                wait = attempt * 3
                print(f"    ⏳ محاولة {attempt} فشلت (SSL) — إعادة بعد {wait}s...")
                time.sleep(wait)
                cloud_engine.dispose()  # أجبر SQLAlchemy على فتح اتصالات جديدة
                continue
            raise
    raise RuntimeError(f"فشل السحب من {t.name} بعد {max_attempts} محاولات: {last_err}")


total = 0
failed = []
with app.app_context():
    # نُفرغ أي مستخدمين/بيانات زرعها create_app() تلقائيًا،
    # حتى نبدأ بملف نظيف تمامًا قبل السحب من السحابة.
    db.drop_all()
    db.create_all()

    local_engine = db.engine

    for tname in copy_order:
        t = metadata.tables[tname]
        try:
            rows = fetch_with_retry(t)
        except Exception as e:
            print(f"  ✗ {tname}: {type(e).__name__}: {e}")
            failed.append(tname)
            continue

        if rows:
            with local_engine.begin() as local_conn:
                local_conn.execute(insert(t), [dict(r) for r in rows])
        total += len(rows)
        print(f"  ✓ {tname}: {len(rows)}")

print("----")
print(f"✔ إجمالي: {total} صف")
if failed:
    print(f"⚠️ جداول فشلت: {failed}")
    print("أعد تشغيل السكربت لإكمالها (الملف سيُعاد إنشاؤه).")
else:
    print("✔ كل الجداول نُسخت بنجاح.")
print(f"الملف الجديد: {LOCAL_DB}")
print("لم يُلمس instance/anter.db — الخطوة التالية استبدال منفصل.")
