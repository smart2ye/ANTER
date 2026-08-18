from flask import Blueprint, request, jsonify
from flask_login import login_required
from app.models.post import Post
from app.services.ai_service import AIService

ai_bp = Blueprint('ai', __name__)
ai_service = AIService()

VALID_ASSIST_ACTIONS = {'suggest_comment', 'suggest_post', 'improve_text'}
MAX_INPUT_LENGTH = 2000


def _json_error(message, status=400):
    return jsonify({'ok': False, 'error': message}), status


@ai_bp.route('/api/ai/complete', methods=['POST'])
@login_required
def ai_complete():
    """واجهة توافق قديمة لتوليد نص عام؛ لا تستخدم لعرض مفاتيح أو إعدادات."""
    data = request.get_json(silent=True) or {}
    prompt = str(data.get('prompt') or '').strip()
    if not prompt:
        return _json_error('النص المطلوب مفقود.')
    if len(prompt) > MAX_INPUT_LENGTH:
        return _json_error(f'النص طويل جداً؛ الحد الأقصى {MAX_INPUT_LENGTH} حرفاً.')

    response, error = ai_service.generate_response(prompt)
    if error:
        return _json_error(error, 503)
    return jsonify({'ok': True, 'response': response, 'engine': AIService.DISPLAY_NAME})


@ai_bp.route('/api/ai/summarize/<int:post_id>', methods=['GET'])
@login_required
def summarize_post(post_id):
    post = Post.query.get_or_404(post_id)
    summary, error = ai_service.summarize_text(post.content)
    if error:
        return _json_error(error, 503)
    return jsonify({'ok': True, 'summary': summary, 'engine': AIService.DISPLAY_NAME})


@ai_bp.route('/api/ai/assist', methods=['POST'])
@login_required
def assist_writing():
    """ينفذ أدوات الكتابة الذكية دون حفظ أي نص نيابة عن المستخدم."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _json_error('أرسل طلباً صالحاً بصيغة JSON.')

    action = str(data.get('action') or '').strip()
    if action not in VALID_ASSIST_ACTIONS:
        return _json_error('نوع المساعدة المطلوب غير مدعوم.')

    if action == 'suggest_comment':
        try:
            post_id = int(data.get('post_id'))
        except (TypeError, ValueError):
            return _json_error('معرّف المنشور مطلوب لاقتراح تعليق.')
        post = Post.query.get_or_404(post_id)
        result, error = ai_service.suggest_comment(post.content)
    else:
        source_text = str(data.get('text') or '').strip()
        if len(source_text) > MAX_INPUT_LENGTH:
            return _json_error(f'النص طويل جداً؛ الحد الأقصى {MAX_INPUT_LENGTH} حرفاً.')
        if action == 'suggest_post':
            result, error = ai_service.suggest_post(source_text)
        else:
            result, error = ai_service.improve_text(source_text)

    if error:
        return _json_error(error, 503)
    return jsonify({'ok': True, 'action': action, 'text': result, 'engine': AIService.DISPLAY_NAME})
