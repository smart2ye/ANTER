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

@app.route('/health')
def health_check():
    # يعمل بشكل آمن ومحدود: ينشئ منشوراً واحداً فقط في اليوم عند أول فحص صحة.
    ensure_daily_assistant_post()
    response = make_response('OK', 200)
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=False)
