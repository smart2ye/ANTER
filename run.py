import os
from flask import make_response
from app import create_app
from app.extensions import db
from app.services.anter_daily_publication import ensure_daily_assistant_post
from app.utils.story_cleanup import delete_expired_stories

app = create_app()

# تنظيف القصص المنتهية عند بدء التشغيل (مرة واحدة لكل عملية).
# مُغلّف بـ try/except حتى لا يمنع أي خطأ بدء السيرفر.
try:
    delete_expired_stories(app)
except Exception:
    app.logger.exception('story_cleanup failed at startup (non-fatal)')

# ANTER: منشور مساعد أنتر اليومي — عند الإقلاع (كحالة أولى).
try:
    with app.app_context():
        ensure_daily_assistant_post()
except Exception:
    app.logger.exception('daily_assistant_post failed at startup (non-fatal)')

# ANTER: فحص ساعي في /health — يضمن النشر اليومي دون إثقال /health.
from datetime import datetime, timedelta, timezone
_last_daily_check = {'at': None}

@app.route('/health')
def health_check():
    global _last_daily_check
    now = datetime.now(timezone.utc)
    last = _last_daily_check.get('at')
    if last is None or (now - last) > timedelta(hours=1):
        _last_daily_check['at'] = now
        try:
            with app.app_context():
                ensure_daily_assistant_post()
        except Exception:
            app.logger.exception('daily_assistant_post failed in /health (non-fatal)')
    return make_response('OK', 200)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=False)
