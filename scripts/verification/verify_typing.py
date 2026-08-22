from bs4 import BeautifulSoup

from app import create_app
from app.models import User

app = create_app()

with app.app_context():
    users = User.query.order_by(User.id.asc()).limit(2).all()
    if len(users) < 2:
        raise SystemExit('Need at least two local users for typing test')
    sender, receiver = users[0], users[1]


def logged_client(user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True
    return client

sender_client = logged_client(sender.id)
receiver_client = logged_client(receiver.id)

set_response = sender_client.post(
    f'/messages/typing/{receiver.id}',
    json={'typing': True},
)
get_response = receiver_client.get(f'/messages/typing/{sender.id}')
clear_response = sender_client.post(
    f'/messages/typing/{receiver.id}',
    json={'typing': False},
)
after_clear = receiver_client.get(f'/messages/typing/{sender.id}')
chat_response = sender_client.get(f'/messages/{receiver.id}')

print('set:', set_response.status_code, set_response.get_json())
print('get:', get_response.status_code, get_response.get_json())
print('clear:', clear_response.status_code, clear_response.get_json())
print('after_clear:', after_clear.status_code, after_clear.get_json())
print('chat:', chat_response.status_code)

if set_response.status_code != 200 or not set_response.get_json().get('typing'):
    raise SystemExit('typing start failed')
if get_response.status_code != 200 or not get_response.get_json().get('typing'):
    raise SystemExit('typing read failed')
if clear_response.status_code != 200 or after_clear.get_json().get('typing'):
    raise SystemExit('typing clear failed')
if chat_response.status_code != 200:
    raise SystemExit('chat render failed')

soup = BeautifulSoup(chat_response.data, 'html.parser')
script_text = '\n'.join(script.get_text() for script in soup.find_all('script'))
open('/tmp/anter-rendered-chat.js', 'w', encoding='utf-8').write(script_text)
print('rendered_js:', len(script_text))
