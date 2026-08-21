import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PrivacySchemaUpgradeTests(unittest.TestCase):
    def test_existing_sqlite_database_is_upgraded_before_user_query(self):
        """يماثل قاعدة Termux قديمة لا تحتوي أعمدة خصوصية المستخدم والمنشور."""
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / 'legacy-anter.db'
            connection = sqlite3.connect(database_path)
            connection.execute(
                '''
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    username VARCHAR(80) NOT NULL UNIQUE,
                    email VARCHAR(120) NOT NULL UNIQUE,
                    name VARCHAR(100) NOT NULL,
                    password_hash VARCHAR(256) NOT NULL,
                    bio VARCHAR(200), avatar VARCHAR(200), avatar_data BLOB,
                    avatar_mime VARCHAR(100), gender VARCHAR(20), birth_date DATE,
                    is_private BOOLEAN, hide_followers BOOLEAN, show_email BOOLEAN,
                    message_privacy VARCHAR(20), is_admin BOOLEAN, is_verified BOOLEAN,
                    created_at DATETIME, is_active BOOLEAN, country_code VARCHAR(10),
                    phone VARCHAR(20), phone_verified BOOLEAN, last_seen DATETIME,
                    theme_preference VARCHAR(20), terms_agreed BOOLEAN
                )
                '''
            )
            connection.commit()
            connection.close()

            environment = os.environ.copy()
            environment.update({
                'DATABASE_URL': f'sqlite:///{database_path}',
                'ADMIN_PATH': 'legacy-schema-test-admin',
                'GROQ_API_KEY': 'test-groq-key',
                'GROQ_MODEL': 'qwen/qwen3.6-27b',
            })
            verification = '''
from app import create_app
from app.extensions import db
from sqlalchemy import inspect
app = create_app()
with app.app_context():
    users = {column['name'] for column in inspect(db.engine).get_columns('users')}
    posts = {column['name'] for column in inspect(db.engine).get_columns('posts')}
    assert {'profile_visibility', 'show_online_status'}.issubset(users)
    assert 'visibility' in posts
'''
            completed = subprocess.run(
                [sys.executable, '-c', verification],
                cwd=PROJECT_ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=20,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)


if __name__ == '__main__':
    unittest.main()
