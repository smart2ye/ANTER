import os
from flask import make_response
from app import create_app
from app.extensions import db

app = create_app()

@app.route('/health')
def health_check():
    response = make_response('OK', 200)
    database_kind = db.engine.dialect.name
    response.headers['X-ANTER-Database'] = database_kind
    response.headers['X-ANTER-Persistent-Database'] = 'true' if database_kind != 'sqlite' else 'false'
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=False)
