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
            'is_ai': "BOOLEAN NOT NULL DEFAULT FALSE",
            'read_at': 'TIMESTAMP',
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
            'wall_visibility': "VARCHAR(20) NOT NULL DEFAULT 'public'",
            'show_online_status': 'BOOLEAN NOT NULL DEFAULT TRUE',
            'email_verified': 'BOOLEAN NOT NULL DEFAULT FALSE',
            'is_deleted': 'BOOLEAN NOT NULL DEFAULT FALSE',
            'deleted_at': 'TIMESTAMP',
            'is_founder': 'BOOLEAN NOT NULL DEFAULT FALSE',
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
            'shared_video_id': 'INTEGER',
            'wall_owner_id': 'INTEGER',
        },
        'story': {
            'media_data': binary_type,
            'media_mime': 'VARCHAR(100)',
        },
        'video_comments': {'edited_at': 'TIMESTAMP'},
        'notifications': {
            'extra_text': 'VARCHAR(500)',
            'report_id': 'INTEGER',
        },
        'videos': {
            'public_id': 'VARCHAR(40)',
            'shares': 'INTEGER DEFAULT 0',
            'video_data': binary_type,
            'video_mime': "VARCHAR(100) DEFAULT 'video/mp4'",
            'thumbnail_data': binary_type,
            'thumbnail_mime': "VARCHAR(100) DEFAULT 'image/jpeg'",
        },
        'comments': {'audio_url': 'VARCHAR(255)', 'edited_at': 'TIMESTAMP'},
        'call_logs': {'call_type': "VARCHAR(16) NOT NULL DEFAULT 'voice'"},
        'reports': {
            'message_id': 'INTEGER',
            'video_id': 'INTEGER',
            'rejection_reason': 'VARCHAR(500)',
            'resolution_note': 'TEXT',
        },
    }

    table_names = set(inspector.get_table_names())

    # ANTER: كل ALTER في transaction مستقلة، حتى لا "يسمّم" الفشل الجلسة كاملة.
    for table_name, required_columns in required_columns_by_table.items():
        if table_name not in table_names:
            continue
        try:
            existing_columns = {
                column['name']
                for column in inspect(db.engine).get_columns(table_name)
            }
        except Exception:
            continue

        for name, sql_type in required_columns.items():
            if name in existing_columns:
                continue
            try:
                with db.engine.begin() as connection:
                    connection.execute(
                        text(f'ALTER TABLE {table_name} ADD COLUMN {name} {sql_type}')
                    )
                app.logger.info(
                    'Added column %s.%s (%s)', table_name, name, sql_type
                )
            except Exception as exc:
                # نُسجّل الخطأ ونُكمل — الفشل هنا ليس حرجًا.
                app.logger.warning(
                    'Could not add %s.%s: %s', table_name, name, exc
                )

    with db.engine.begin() as connection:
        for table_name in ('posts', 'videos'):
            if table_name in table_names:
                connection.execute(text(
                    f'CREATE UNIQUE INDEX IF NOT EXISTS ix_{table_name}_public_id ON {table_name} (public_id)'
                ))

        if 'posts' in table_names:
            connection.execute(text(
                'CREATE INDEX IF NOT EXISTS ix_posts_shared_video_id ON posts (shared_video_id)'
            ))
        if 'messages' in table_names:
            message_columns = {
                column['name']
                for column in inspect(db.engine).get_columns('messages')
            }

            if 'shared_video_id' in message_columns:
                connection.execute(text(
                    'CREATE INDEX IF NOT EXISTS ix_messages_shared_video_id ON messages (shared_video_id)'
                ))

        if 'reports' in table_names:
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_reports_message_id ON reports (message_id)'))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_reports_video_id ON reports (video_id)'))

        if 'notifications' in table_names:
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_notifications_report_id ON notifications (report_id)'))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications (created_at)'))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_notifications_is_read ON notifications (is_read)'))

        if 'posts' in table_names:
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_posts_created_at ON posts (created_at)'))

        if 'videos' in table_names:
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_videos_created_at ON videos (created_at)'))

        if 'messages' in table_names:
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_messages_created_at ON messages (created_at)'))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_messages_is_read ON messages (is_read)'))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_messages_is_ai ON messages (is_ai)'))

        if 'story' in table_names:
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_story_created_at ON story (created_at)'))

    # ترحيل المعرفات العامة يُنفذ مرة عند الترقية، لا مع كل طلب إيقاظ.
    for model, prefix in ((Post, 'p'), (Video, 'r')):
        for entity in model.query.filter(model.public_id.is_(None)).all():
            public_id = generate_public_id(prefix)
            while model.query.filter_by(public_id=public_id).first() is not None:
                public_id = generate_public_id(prefix)
            entity.public_id = public_id
    db.session.commit()
    return True
