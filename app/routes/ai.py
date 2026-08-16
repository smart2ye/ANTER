from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.services.ai_service import AIService
from app.models.post import Post

ai_bp = Blueprint('ai', __name__)
ai_service = AIService()

@ai_bp.route('/api/ai/complete', methods=['POST'])
@login_required
def ai_complete():
    data = request.get_json() or {}
    prompt = data.get('prompt')
    if not prompt:
        return jsonify({'error': 'النص المطللوب (prompt) مفقود'}), 400
    
    response = ai_service.generate_response(prompt)
    return jsonify({'response': response})

@ai_bp.route('/api/ai/summarize/<int:post_id>', methods=['GET'])
@login_required
def summarize_post(post_id):
    post = Post.query.get_or_404(post_id)
    if not post.content:
        return jsonify({'summary': 'المنشور لا يحتوي على نص للتلخيص.'})
    
    summary = ai_service.summarize_text(post.content)
    return jsonify({'summary': summary})
