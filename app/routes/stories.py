import os
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db, csrf
from app.models.story import Story, StoryView, StoryReaction
from app.models.user import User
from app.utils.media_urls import avatar_url
from app.utils.helpers import log_user_activity

stories_bp = Blueprint('stories', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'mov'}

@stories_bp.route('/stories', methods=['POST'])
@csrf.exempt
@login_required
def create_story():
    # تحقق من عدد القصص النشطة للمستخدم (حد أقصى 5 قصص نشطة لمنع الضغط)
    now = datetime.utcnow()
    active_count = Story.query.filter_by(user_id=current_user.id, is_active=True).filter(Story.expires_at > now).count()
    if active_count >= 5:
        return jsonify({'error': 'لقد وصلت إلى الحد الأقصى للقصص النشطة (5 قصص). انتظر حتى تنتهي صلاحية إحداها.'}), 400

    media = request.files.get('media')
    caption = request.form.get('caption', '').strip()

    if not media or media.filename == '':
        return jsonify({'error': 'يرجى إرفاق صورة أو فيديو للقصة'}), 400

    if not allowed_file(media.filename):
        return jsonify({'error': 'صيغة الملف غير مدعومة'}), 400

    ext = media.filename.rsplit('.', 1)[1].lower()
    is_video = ext in {'mp4', 'webm', 'mov'}
    media_type = 'video' if is_video else 'image'

    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'stories')
    os.makedirs(upload_folder, exist_ok=True)

    if is_video:
        # ANTER: فحص magic bytes للفيديو + حد الحجم.
        head = media.stream.read(16)
        media.stream.seek(0)
        VIDEO_SIGS = (b'\x00\x00\x00', b'\x1aE\xdf\xa3')
        if not any(head.startswith(sig) for sig in VIDEO_SIGS):
            return jsonify({'error': 'ملف الفيديو غير صالح'}), 400
        max_bytes = current_app.config.get('MAX_VIDEO_UPLOAD_BYTES', 50 * 1024 * 1024)
        media.stream.seek(0, os.SEEK_END)
        size = media.stream.tell()
        media.stream.seek(0)
        if size > max_bytes:
            return jsonify({'error': f'حجم الفيديو أكبر من {max_bytes // (1024*1024)} MB'}), 400
        filename = f"story_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(upload_folder, filename)
        media.save(filepath)
        media_url = f"/static/uploads/stories/{filename}"
    else:
        # ANTER: للصور — التحقق الكامل عبر prepare_image_data.
        from app.utils.image_storage import prepare_image_data
        image_bytes, image_mime = prepare_image_data(media)
        if not image_bytes:
            return jsonify({'error': 'ملف الصورة غير صالح'}), 400
        ext_out = 'webp' if image_mime == 'image/webp' else 'png'
        filename = f"story_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext_out}"
        filepath = os.path.join(upload_folder, filename)
        with open(filepath, 'wb') as fh:
            fh.write(image_bytes)
        media_url = f"/static/uploads/stories/{filename}"

    story = Story(
        user_id=current_user.id,
        media_url=media_url,
        media_type=media_type,
        caption=caption,
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )
    db.session.add(story)
    db.session.commit()
    log_user_activity(current_user.id, 'story_create', {'story_id': story.id, 'attachment': media_type})

    return jsonify({'message': 'تم نشر القصة بنجاح', 'story': story.to_dict(current_user.id)}), 201

@stories_bp.route('/stories/feed', methods=['GET'])
@login_required
def get_stories_feed():
    now = datetime.utcnow()
    
    # جلب المستخدمين الذين يتابعهم المستخدم الحالي + المستخدم نفسه
    # ANTER: current_user.following يُرجع علاقات Follow، ونحتاج IDs المستخدمين المتابَعين
    following_ids = [f.followed_id for f in current_user.following]
    following_ids.append(current_user.id)

    # جلب القصص النشطة التي لم تنتهِ صلاحيتها
    stories = Story.query.filter(
        Story.user_id.in_(following_ids),
        Story.expires_at > now,
        Story.is_active == True
    ).order_by(Story.created_at.desc()).all()

    # تجميع القصص حسب المستخدم
    users_dict = {}
    for story in stories:
        user = story.user
        if not user:
            continue
        if user.id not in users_dict:
            # التحقق مما إذا كانت جميع قصص هذا المستخدم مشاهدة
            users_dict[user.id] = {
                'user_id': user.id,
                'username': user.username,
                'name': user.name or user.username,
                'avatar': avatar_url(user),
                'stories': [],
                'all_viewed': True
            }
        
        story_dict = story.to_dict(current_user.id)
        if not story_dict['viewed'] and story.user_id != current_user.id:
            users_dict[user.id]['all_viewed'] = False
        
        users_dict[user.id]['stories'].append(story_dict)

    # ترتيب المستخدمين: غير المشاهدة أولاً ثم المشاهدة
    sorted_users = sorted(users_dict.values(), key=lambda x: (x['all_viewed'], -len(x['stories'])))

    return jsonify(sorted_users), 200

@stories_bp.route('/user-stories/<int:user_id>', methods=['GET'])
@login_required
def get_user_stories(user_id):
    now = datetime.utcnow()
    stories = Story.query.filter(
        Story.user_id == user_id,
        Story.expires_at > now,
        Story.is_active == True
    ).order_by(Story.created_at.asc()).all()

    user = User.query.get_or_404(user_id)
    if getattr(user, 'is_deleted', False):
        return jsonify({'error': 'not found'}), 404

    return jsonify({
        'user': {
            'id': user.id,
            'username': user.username,
            'name': user.name or user.username,
            'avatar': avatar_url(user)
        },
        'stories': [s.to_dict(current_user.id) for s in stories]
    }), 200

@stories_bp.route('/stories/<int:story_id>/view', methods=['POST'])
@csrf.exempt
@login_required
def view_story(story_id):
    story = Story.query.get_or_404(story_id)
    if not story.is_active or story.expires_at <= datetime.utcnow():
        return jsonify({'error': 'هذه القصة لم تعد متاحة'}), 410
    
    if story.user_id == current_user.id:
        return jsonify({'message': 'لا يمكن تسجيل مشاهدة قصتك الخاصة', 'story': story.to_dict(current_user.id)}), 200

    existing_view = StoryView.query.filter_by(story_id=story_id, viewer_id=current_user.id).first()
    if not existing_view:
        view = StoryView(story_id=story_id, viewer_id=current_user.id)
        db.session.add(view)
        db.session.commit()
        log_user_activity(current_user.id, 'story_view', {'story_id': story_id})

    return jsonify({'message': 'تم تسجيل المشاهدة', 'story': story.to_dict(current_user.id)}), 200


@stories_bp.route('/stories/<int:story_id>/react', methods=['POST'])
@csrf.exempt
@login_required
def react_story(story_id):
    story = Story.query.get_or_404(story_id)
    if not story.is_active or story.expires_at <= datetime.utcnow():
        return jsonify({'error': 'هذه القصة لم تعد متاحة'}), 410
    data = request.get_json() or {}
    reaction_type = data.get('reaction_type')

    valid_reactions = {'like', 'love', 'haha', 'wow', 'sad', 'fire'}
    if reaction_type not in valid_reactions:
        return jsonify({'error': 'نوع التفاعل غير صالح'}), 400

    existing = StoryReaction.query.filter_by(story_id=story_id, user_id=current_user.id).first()
    if existing:
        if existing.reaction_type == reaction_type:
            # إلغاء التفاعل إذا تم النقر عليه مرة أخرى
            db.session.delete(existing)
            db.session.commit()
            action = 'removed'
        else:
            existing.reaction_type = reaction_type
            db.session.commit()
            action = 'updated'
    else:
        reaction = StoryReaction(story_id=story_id, user_id=current_user.id, reaction_type=reaction_type)
        db.session.add(reaction)
        db.session.commit()
        action = 'added'

    log_user_activity(
        current_user.id,
        'story_reaction_remove' if action == 'removed' else 'story_reaction_add',
        {'story_id': story_id, 'reaction': reaction_type},
    )

    return jsonify({
        'success': True,
        'action': action,
        'story': story.to_dict(current_user.id)
    }), 200


@stories_bp.route('/stories/<int:story_id>/viewers', methods=['GET'])
@login_required
def get_story_viewers(story_id):
    story = Story.query.get_or_404(story_id)
    if story.user_id != current_user.id:
        return jsonify({'error': 'قائمة المشاهدين متاحة لصاحب القصة فقط'}), 403

    return jsonify({
        'story_id': story.id,
        'views_count': story.views.count(),
        'viewers': story.to_dict(current_user.id)['viewers']
    }), 200


@stories_bp.route('/stories/<int:story_id>', methods=['DELETE'])
@csrf.exempt
@login_required
def delete_story(story_id):
    story = Story.query.get_or_404(story_id)
    if story.user_id != current_user.id:
        return jsonify({'error': 'غير مسموح لك بحذف هذه القصة'}), 403

    # حذف الملف الفعلي إن وجد
    try:
        if story.media_url and story.media_url.startswith('/static/uploads/'):
            filepath = os.path.join(current_app.root_path, story.media_url.lstrip('/'))
            if os.path.exists(filepath):
                os.remove(filepath)
    except Exception:
        pass

    deleted_story_id = story.id
    db.session.delete(story)
    db.session.commit()
    log_user_activity(current_user.id, 'story_delete', {'story_id': deleted_story_id})
    return jsonify({'message': 'تم حذف القصة بنجاح'}), 200
