"""اعرض رابط لوحة إدارة ANTER المنشورة من دون كشف إعدادات سرية."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_RENDER_URL = 'https://anter-1.onrender.com'


def build_admin_url(base_url: str, admin_path: str) -> str:
    """Compose a public admin URL without printing the value used to derive it."""
    parsed = urlsplit(base_url.strip())
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('ANTER_PUBLIC_BASE_URL يجب أن يكون رابط HTTP أو HTTPS صحيحاً.')
    origin = urlunsplit((parsed.scheme, parsed.netloc, '', '', '')).rstrip('/')
    return f"{origin}/{admin_path.strip('/')}"


def main() -> int:
    base_url = os.environ.get('ANTER_PUBLIC_BASE_URL', DEFAULT_RENDER_URL)
    admin_path = os.environ.get('ADMIN_PATH', '').strip().strip('/')
    if not admin_path:
        raise ValueError(
            'لا يمكن التحقق من مسار Render محلياً. اضبط ADMIN_PATH نفسه في Render وبيئتك المحلية.'
        )
    print(build_admin_url(base_url, admin_path))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f'خطأ: {error}', file=sys.stderr)
        raise SystemExit(2)
