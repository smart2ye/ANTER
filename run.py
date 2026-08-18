import os
from flask import make_response
from app import create_app
from app.extensions import db
from app.services.anter_daily_publication import ensure_daily_assistant_post

app = create_app()

@app.route('/health')
def health_check():
    # يعمل بشكل آمن ومحدود: ينشئ منشوراً واحداً فقط في اليوم عند أول فحص صحة.
    ensure_daily_assistant_post()
    response = make_response('OK', 200)
    database_kind = db.engine.dialect.name
    response.headers['X-ANTER-Database'] = database_kind
    response.headers['X-ANTER-Persistent-Database'] = 'true' if database_kind != 'sqlite' else 'false'
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=False)
