"""مهام صيانة قاعدة البيانات التي لا ينبغي تشغيلها في كل إيقاظ للخادم."""

from __future__ import annotations

from sqlalchemy import inspect, text

from app.extensions import db
from app.models import Post, Video
from app.utils.public_ids import generate_public_id


def should_run_schema_upgrades(app, inspector) -> bool:
    """شغّل الترقية فقط عند طلبها أو عندما تكون قاعدة البيانات جديدة تماماً."""
    return bool(app.config['STARTUP_SCHEMA_UPGRADES_ENABLED']) or not inspector.has_table('users')


def run_startup_schema_upgrades(app) -> bool:
    """أنشئ أو رقِّ المخطط عند الحاجة، وأعد ما إذا نُفذت ترقية ثقيلة.

    تفحُّص كل جدول وأعمدته وقراءة كل المنشورات في كل إيقاظ يطيل بدء خدمة
    PostgreSQL على الاستضافة ذات الإيقاف التلقائي. قواعد الإنتاج القائمة تُرقّى
    مرةً واحدة عبر المتغير البيئي ثم تبدأ سريعاً في التشغيلات اللاحقة.
    """
    inspector = inspect(db.engine)
    if not should_run_schema_upgrades(app, inspector):
        return False

    # كل النماذج محمّلة قبل استدعاء هذه الدالة، لذلك يكفي هذا لإنشاء الجداول الجديدة.
    db.create_all()
    inspector = inspect(db.engine)
    binary_type = 'BYTEA' if db.engine.dialect.name == 'postgresql' else 'BLOB'
    required_columns_by_table = {
        'messages': {
            'audio_path': 'VARCHAR(255)',
            'audio_data': binary_type,
            'audio_mime': 'VARCHAR(100)',
            'attachment_data': binary_type,
            'attachment_mime': 'VARCHAR(150)',
            'attachment_name': 'VARCHAR(255)',
            'attachment_kind': 'VARCHAR(20)',
            'parent_id': 'INTEGER',
            'is_deleted_everyone': 'BOOLEAN DEFAULT FALSE',
            'deleted_by_sender': 'BOOLEAN DEFAULT FALSE',
            'deleted_by_receiver': 'BOOLEAN DEFAULT FALSE',
        },
        'users': {
            'avatar_data': binary_type,
            'avatar_mime': 'VARCHAR(100)',
            'profile_visibility': "VARCHAR(20) NOT NULL DEFAULT 'public'",
            'show_online_status': 'BOOLEAN NOT NULL DEFAULT TRUE',
        },
        'posts': {
            'image_data': binary_type,
            'image_mime': 'VARCHAR(100)',
            'public_id': 'VARCHAR(40)',
            'link_url': 'VARCHAR(500)',
            'link_title': 'VARCHAR(255)',
            'link_description': 'TEXT',
            'link_image': 'VARCHAR(500)',
            'visibility': "VARCHAR(20) NOT NULL DEFAULT 'public'",
        },
        'videos': {'public_id': 'VARCHAR(40)'},
        'comments': {'audio_url': 'VARCHAR(255)'},
        'call_logs': {'call_type': "VARCHAR(16) NOT NULL DEFAULT 'voice'"},
        'reports': {'message_id': 'INTEGER'},
    }

    table_names = set(inspector.get_table_names())
    with db.engine.begin() as connection:
        for table_name, required_columns in required_columns_by_table.items():
            if table_name not in table_names:
                continue
            columns = {column['name'] for column in inspector.get_columns(table_name)}
            for name, sql_type in required_columns.items():
                if name not in columns:
                    connection.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {name} {sql_type}'))

        for table_name in ('posts', 'videos'):
            if table_name in table_names:
                connection.execute(text(
                    f'CREATE UNIQUE INDEX IF NOT EXISTS ix_{table_name}_public_id ON {table_name} (public_id)'
                ))
        if 'reports' in table_names:
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_reports_message_id ON reports (message_id)'))

    # ترحيل المعرفات العامة يُنفذ مرة عند الترقية، لا مع كل طلب إيقاظ.
    for model, prefix in ((Post, 'p'), (Video, 'r')):
        for entity in model.query.filter(model.public_id.is_(None)).all():
            public_id = generate_public_id(prefix)
            while model.query.filter_by(public_id=public_id).first() is not None:
                public_id = generate_public_id(prefix)
            entity.public_id = public_id
    db.session.commit()
    return True
