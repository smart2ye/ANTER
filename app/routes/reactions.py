from flask import Blueprint, render_template, request, abort
from app.extensions import db
from app.models import Post, User, Like

reactions_bp = Blueprint('reactions', __name__)

@reactions_bp.route('/post/<int:post_id>/reactions')
def post_reactions(post_id):
    post = Post.query.get_or_404(post_id)
    reaction_type = request.args.get('type')
    
    # استعلام أساسي
    query = db.session.query(User).join(Like, Like.user_id == User.id).filter(Like.post_id == post_id)
    
    # تطبيق الفلتر إذا كان موجوداً
    if reaction_type and reaction_type in ['like', 'love', 'haha', 'angry', 'sad']:
        query = query.filter(Like.reaction_type == reaction_type)
    
    users = query.all()
    
    # إحصائيات لكل نوع
    stats = {}
    for rt in ['like', 'love', 'haha', 'angry', 'sad']:
        stats[rt] = db.session.query(Like).filter(Like.post_id == post_id, Like.reaction_type == rt).count()
    
    return render_template('post_reactions.html', post=post, users=users, reaction_type=reaction_type, stats=stats)
