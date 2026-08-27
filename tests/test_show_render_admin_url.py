import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / 'scripts' / 'show_render_admin_url.py'


def test_script_prints_only_configured_render_admin_url_without_secret():
    environment = os.environ.copy()
    environment.update({
        'ADMIN_PATH': 'admin-test-route',
        'ANTER_PUBLIC_BASE_URL': 'https://example.onrender.com/ignored-path',
    })

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == 'https://example.onrender.com/admin-test-route'
    assert result.stderr == ''


def test_script_refuses_to_guess_render_admin_path_from_local_secret():
    environment = os.environ.copy()
    environment.pop('ADMIN_PATH', None)
    environment['SECRET_KEY'] = 'test-secret-must-not-appear'

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stdout == ''
    assert 'ADMIN_PATH' in result.stderr
    assert 'test-secret-must-not-appear' not in result.stderr
