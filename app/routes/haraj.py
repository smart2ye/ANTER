"""ANTER Haraj — سوق الأثاث والأجهزة المنزلية."""

from datetime import datetime

from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, abort, current_app,
)
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.extensions import db
from app.models import User
from app.models.listing import (
    Listing, ListingImage, LISTING_CATEGORIES, LISTING_TYPES,
    LISTING_CONDITIONS, LISTING_STATUSES, default_expires_at,
)
from app.models.haraj_message import HarajMessage
from app.models.listing_reaction import ListingReaction
from app.models.listing_comment import ListingComment
from app.models.seller_rating import SellerRating, seller_rating_stats
from app.forms.haraj import ListingForm
from app.constants.saudi_locations import (
    SAUDI_REGIONS, all_regions, cities_for_region, region_of_city,
)
from app.utils.image_storage import prepare_image_data

haraj_bp = Blueprint('haraj', __name__, url_prefix='/haraj')


# محافظات السعودية (للتوافق مع أي استيراد سابق)
SAUDI_REGIONS_LIST = all_regions()


# ============================================================
# الصفحة الرئيسية
# ============================================================
@haraj_bp.route('/')
def index():
    category = request.args.get('category', '').strip()
    region = request.args.get('region', '').strip()
    city = request.args.get('city', '').strip()
    q = request.args.get('q', '').strip()
    listing_type = request.args.get('type', '').strip()

    query = Listing.query.filter(Listing.status == 'active')

    if category and category in LISTING_CATEGORIES:
        query = query.filter(Listing.category == category)
    if region and region in SAUDI_REGIONS:
        query = query.filter(Listing.region == region)
    if city and region:
        query = query.filter(Listing.city == city)
    if listing_type and listing_type in LISTING_TYPES:
        query = query.filter(Listing.listing_type == listing_type)
    if q:
        like = f'%{q}%'
        query = query.filter(or_(Listing.title.ilike(like), Listing.description.ilike(like)))

    listings = query.order_by(Listing.created_at.desc()).limit(100).all()

    # جمع الإعجابات/الحفظ لكل إعلان
    listing_ids = [l.id for l in listings]
    reactions_by_listing = {}
    user_liked = set()
    user_saved = set()
    if listing_ids:
        from sqlalchemy import func
        rows = db.session.query(
            ListingReaction.listing_id,
            ListingReaction.reaction_type,
            func.count(ListingReaction.id),
        ).filter(ListingReaction.listing_id.in_(listing_ids)) \
         .group_by(ListingReaction.listing_id, ListingReaction.reaction_type).all()
        for lid, rtype, cnt in rows:
            reactions_by_listing.setdefault(lid, {})[rtype] = cnt
        if current_user.is_authenticated:
            u = ListingReaction.query.filter(
                ListingReaction.listing_id.in_(listing_ids),
                ListingReaction.user_id == current_user.id,
            ).all()
            for r in u:
                if r.reaction_type == 'like':
                    user_liked.add(r.listing_id)
                elif r.reaction_type == 'save':
                    user_saved.add(r.listing_id)

    return render_template(
        'haraj/index.html',
        listings=listings,
        reactions_by_listing=reactions_by_listing,
        user_liked=user_liked,
        user_saved=user_saved,
        regions=all_regions(),
        categories=LISTING_CATEGORIES,
        listing_types=LISTING_TYPES,
        current_category=category,
        current_region=region,
        current_city=city,
        current_type=listing_type,
        current_q=q,
        cities=cities_for_region(region) if region else [],
    )


# ============================================================
# API: مدن منطقة
# ============================================================
@haraj_bp.route('/api/cities')
def api_cities():
    from flask import jsonify
    region = request.args.get('region', '').strip()
    return jsonify({'cities': cities_for_region(region)})


# ============================================================
# صفحة إعلان مفرد
# ============================================================
@haraj_bp.route('/listing/<public_id>')
def listing_detail(public_id):
    listing = Listing.query.filter_by(public_id=public_id).first_or_404()

    if listing.status == 'expired':
        abort(404)

    # زيادة العداد
    try:
        listing.views_count = (listing.views_count or 0) + 1
        db.session.commit()
    except Exception:
        db.session.rollback()

    is_owner = current_user.is_authenticated and current_user.id == listing.user_id

    likes_count = ListingReaction.query.filter_by(
        listing_id=listing.id, reaction_type='like',
    ).count()
    saves_count = ListingReaction.query.filter_by(
        listing_id=listing.id, reaction_type='save',
    ).count()

    user_liked = False
    user_saved = False
    if current_user.is_authenticated:
        user_liked = ListingReaction.query.filter_by(
            listing_id=listing.id, user_id=current_user.id, reaction_type='like',
        ).first() is not None
        user_saved = ListingReaction.query.filter_by(
            listing_id=listing.id, user_id=current_user.id, reaction_type='save',
        ).first() is not None

    # التعليقات (الرئيسية فقط، والردود تُحمّل عبر relationship)
    comments = (ListingComment.query
                .filter_by(listing_id=listing.id, parent_id=None, is_deleted=False)
                .order_by(ListingComment.created_at.desc()).all())

    # إحصاءات تقييم البائع
    seller_avg, seller_count = seller_rating_stats(listing.user_id)

    # هل قيّم المستخدم الحالي هذا الإعلان؟
    user_rated = False
    can_rate = False
    if current_user.is_authenticated and not is_owner and listing.status == 'sold':
        user_rated = SellerRating.query.filter_by(
            listing_id=listing.id, rater_id=current_user.id,
        ).first() is not None
        can_rate = not user_rated

    return render_template(
        'haraj/listing.html',
        listing=listing,
        is_owner=is_owner,
        categories=LISTING_CATEGORIES,
        types=LISTING_TYPES,
        conditions=LISTING_CONDITIONS,
        statuses=LISTING_STATUSES,
        likes_count=likes_count,
        saves_count=saves_count,
        user_liked=user_liked,
        user_saved=user_saved,
        comments=comments,
        seller_avg=seller_avg,
        seller_count=seller_count,
        user_rated=user_rated,
        can_rate=can_rate,
    )


# ============================================================
# صورة إعلان
# ============================================================
@haraj_bp.route('/media/listing/<int:image_id>')
def listing_image(image_id):
    img = ListingImage.query.get_or_404(image_id)
    from flask import Response
    resp = Response(img.image_data, mimetype=img.image_mime or 'image/jpeg')
    resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return resp


# ============================================================
# نشر إعلان جديد
# ============================================================
@haraj_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_listing():
    form = ListingForm()

    if request.method == 'GET':
        return render_template(
            'haraj/new.html',
            form=form,
            categories=LISTING_CATEGORIES,
            types=LISTING_TYPES,
            conditions=LISTING_CONDITIONS,
            regions=all_regions(),
            saudi_regions=SAUDI_REGIONS,
        )

    if form.validate_on_submit():
        # المدن تحتاج ملء قبل التحقق
        if form.region.data and form.region.data in SAUDI_REGIONS:
            form.city.choices = [('', 'اختر المدينة')] + [
                (c, c) for c in SAUDI_REGIONS[form.region.data]
            ]

        if not form.city.data:
            flash('اختر المدينة.', 'danger')
            return render_template(
                'haraj/new.html', form=form,
                categories=LISTING_CATEGORIES, types=LISTING_TYPES,
                conditions=LISTING_CONDITIONS, regions=all_regions(),
                saudi_regions=SAUDI_REGIONS,
            )

        if not form.pledge_accepted.data:
            flash('يجب الموافقة على التعهد بدفع 1% للنشر.', 'danger')
            return render_template(
                'haraj/new.html', form=form,
                categories=LISTING_CATEGORIES, types=LISTING_TYPES,
                conditions=LISTING_CONDITIONS, regions=all_regions(),
                saudi_regions=SAUDI_REGIONS,
            )

        # معالجة الصور
        uploaded = [f for f in request.files.getlist('images') if f and f.filename]
        if len(uploaded) > 3:
            flash('3 صور كحد أقصى.', 'danger')
            return render_template(
                'haraj/new.html', form=form,
                categories=LISTING_CATEGORIES, types=LISTING_TYPES,
                conditions=LISTING_CONDITIONS, regions=all_regions(),
                saudi_regions=SAUDI_REGIONS,
            )

        prepared_images = []
        for f in uploaded:
            data, mime = prepare_image_data(f)
            if data and mime:
                prepared_images.append((data, mime))

        if not prepared_images:
            flash('أضف صورة واحدة على الأقل.', 'danger')
            return render_template(
                'haraj/new.html', form=form,
                categories=LISTING_CATEGORIES, types=LISTING_TYPES,
                conditions=LISTING_CONDITIONS, regions=all_regions(),
                saudi_regions=SAUDI_REGIONS,
            )

        # خصم صورة
        listing = Listing(
            user_id=current_user.id,
            category=form.category.data,
            listing_type=form.listing_type.data,
            condition=form.condition.data,
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            price=form.price.data,
            negotiable=bool(form.negotiable.data),
            region=form.region.data,
            city=form.city.data,
            show_whatsapp=bool(form.show_whatsapp.data),
            whatsapp_number=(current_user.haraj_whatsapp_number or '').strip() or None,
            pledge_accepted=True,
            pledge_at=datetime.utcnow(),
            status='active',
            expires_at=default_expires_at(),
        )
        db.session.add(listing)
        db.session.flush()

        for i, (data, mime) in enumerate(prepared_images, 1):
            db.session.add(ListingImage(
                listing_id=listing.id,
                image_data=data,
                image_mime=mime,
                position=i,
            ))

        db.session.commit()

        flash('✅ تم نشر إعلانك.', 'success')
        return redirect(url_for('haraj.listing_detail', public_id=listing.public_id))

    # فشل التحقق
    return render_template(
        'haraj/new.html', form=form,
        categories=LISTING_CATEGORIES, types=LISTING_TYPES,
        conditions=LISTING_CONDITIONS, regions=all_regions(),
        saudi_regions=SAUDI_REGIONS,
    )


# ============================================================
# تعليم الإعلان كمباع
# ============================================================
@haraj_bp.route('/listing/<public_id>/sold', methods=['POST'])
@login_required
def mark_sold(public_id):
    listing = Listing.query.filter_by(public_id=public_id).first_or_404()
    if listing.user_id != current_user.id:
        abort(403)
    if listing.status == 'sold':
        flash('هذا الإعلان مُعلَّم كمباع مسبقًا.', 'info')
        return redirect(url_for('haraj.listing_detail', public_id=public_id))
    listing.status = 'sold'
    db.session.commit()
    flash('✅ تم تعليم الإعلان كمباع. تذكّر تعهدك بدفع 1% من قيمة البيع.', 'success')
    return redirect(url_for('haraj.listing_detail', public_id=public_id))


# ============================================================
# حذف الإعلان
# ============================================================
@haraj_bp.route('/listing/<public_id>/delete', methods=['POST'])
@login_required
def delete_listing(public_id):
    listing = Listing.query.filter_by(public_id=public_id).first_or_404()
    if listing.user_id != current_user.id and not getattr(current_user, 'is_admin', False):
        abort(403)
    db.session.delete(listing)
    db.session.commit()
    flash('تم حذف الإعلان.', 'success')
    return redirect(url_for('haraj.index'))


# ============================================================
# تعديل الإعلان
# ============================================================
@haraj_bp.route('/listing/<public_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_listing(public_id):
    listing = Listing.query.filter_by(public_id=public_id).first_or_404()
    if listing.user_id != current_user.id:
        abort(403)

    form = ListingForm(obj=listing)

    if request.method == 'GET':
        form.category.data = listing.category
        form.listing_type.data = listing.listing_type
        form.condition.data = listing.condition
        form.title.data = listing.title
        form.description.data = listing.description
        form.price.data = listing.price
        form.negotiable.data = listing.negotiable
        form.region.data = listing.region
        form.show_whatsapp.data = listing.show_whatsapp
        form.pledge_accepted.data = listing.pledge_accepted
        if listing.region in SAUDI_REGIONS:
            form.city.choices = [('', 'اختر المدينة')] + [(c, c) for c in SAUDI_REGIONS[listing.region]]
        form.city.data = listing.city
        return render_template(
            'haraj/new.html',
            form=form,
            listing=listing,
            categories=LISTING_CATEGORIES, types=LISTING_TYPES,
            conditions=LISTING_CONDITIONS, regions=all_regions(),
            saudi_regions=SAUDI_REGIONS,
            is_edit=True,
        )

    # POST
    if form.region.data and form.region.data in SAUDI_REGIONS:
        form.city.choices = [('', 'اختر المدينة')] + [(c, c) for c in SAUDI_REGIONS[form.region.data]]

    if form.validate_on_submit() and form.city.data and form.pledge_accepted.data:
        listing.category = form.category.data
        listing.listing_type = form.listing_type.data
        listing.condition = form.condition.data
        listing.title = form.title.data.strip()
        listing.description = form.description.data.strip()
        listing.price = form.price.data
        listing.negotiable = bool(form.negotiable.data)
        listing.region = form.region.data
        listing.city = form.city.data
        listing.show_whatsapp = bool(form.show_whatsapp.data)
        if not listing.pledge_accepted:
            listing.pledge_accepted = True
            listing.pledge_at = datetime.utcnow()

        uploaded = [f for f in request.files.getlist('images') if f and f.filename]
        if uploaded:
            prepared = []
            for f in uploaded[:3]:
                data, mime = prepare_image_data(f)
                if data and mime:
                    prepared.append((data, mime))
            if prepared:
                for old in listing.images.all():
                    db.session.delete(old)
                db.session.flush()
                for i, (data, mime) in enumerate(prepared, 1):
                    db.session.add(ListingImage(
                        listing_id=listing.id,
                        image_data=data, image_mime=mime, position=i,
                    ))

        db.session.commit()
        flash('✅ تم تحديث الإعلان.', 'success')
        return redirect(url_for('haraj.listing_detail', public_id=listing.public_id))

    flash('تحقق من الحقول المطلوبة.', 'danger')
    return render_template(
        'haraj/new.html',
        form=form, listing=listing,
        categories=LISTING_CATEGORIES, types=LISTING_TYPES,
        conditions=LISTING_CONDITIONS, regions=all_regions(),
        saudi_regions=SAUDI_REGIONS,
        is_edit=True,
    )



# ============================================================
# الرسائل — بدء محادثة بخصوص إعلان
# ============================================================
@haraj_bp.route('/listing/<public_id>/contact', methods=['POST'])
@login_required
def contact_seller(public_id):
    listing = Listing.query.filter_by(public_id=public_id).first_or_404()
    if listing.user_id == current_user.id:
        flash('لا يمكنك مراسلة نفسك.', 'info')
        return redirect(url_for('haraj.listing_detail', public_id=public_id))
    return redirect(url_for(
        'haraj.chat',
        listing_public_id=public_id,
        other_username=listing.seller.username,
    ))


# ============================================================
# قائمة المحادثات
# ============================================================
@haraj_bp.route('/messages')
@login_required
def messages():
    from sqlalchemy import and_, or_, func
    # نستخرج المحادثات الفريدة (listing_id + الطرف الآخر)
    sub = db.session.query(
        HarajMessage.listing_id,
        func.max(HarajMessage.id).label('last_id'),
    ).filter(
        or_(HarajMessage.sender_id == current_user.id,
            HarajMessage.receiver_id == current_user.id)
    ).group_by(HarajMessage.listing_id).subquery()

    last_msgs = (HarajMessage.query
                 .join(sub, HarajMessage.id == sub.c.last_id)
                 .order_by(HarajMessage.created_at.desc()).all())

    threads = []
    for m in last_msgs:
        other_id = m.receiver_id if m.sender_id == current_user.id else m.sender_id
        other = db.session.get(User, other_id)
        listing = m.listing
        unread = HarajMessage.query.filter_by(
            listing_id=m.listing_id,
            sender_id=other_id,
            receiver_id=current_user.id,
            is_read=False,
        ).count()
        threads.append({
            'listing': listing,
            'other': other,
            'last_message': m,
            'unread': unread,
        })

    return render_template('haraj/messages.html', threads=threads)


# ============================================================
# محادثة حول إعلان
# ============================================================
@haraj_bp.route('/messages/<listing_public_id>/<other_username>', methods=['GET', 'POST'])
@login_required
def chat(listing_public_id, other_username):
    listing = Listing.query.filter_by(public_id=listing_public_id).first_or_404()
    other = User.query.filter_by(username=other_username).first_or_404()

    if other.id == current_user.id:
        abort(400)

    # يجب أن يكون أحدهما صاحب الإعلان
    if current_user.id != listing.user_id and other.id != listing.user_id:
        abort(403)

    # تحقق أن الطرفين مرتبطان بالإعلان
    if not (
        (current_user.id == listing.user_id and other.id != listing.user_id)
        or (current_user.id != listing.user_id and other.id == listing.user_id)
    ):
        abort(403)

    if request.method == 'POST':
        content = (request.form.get('content') or '').strip()
        if content and len(content) <= 2000:
            db.session.add(HarajMessage(
                listing_id=listing.id,
                sender_id=current_user.id,
                receiver_id=other.id,
                content=content,
            ))
            db.session.commit()
        return redirect(url_for(
            'haraj.chat',
            listing_public_id=listing_public_id,
            other_username=other_username,
        ))

    msgs = (HarajMessage.query
            .filter_by(listing_id=listing.id)
            .filter(
                or_(
                    (HarajMessage.sender_id == current_user.id) & (HarajMessage.receiver_id == other.id),
                    (HarajMessage.sender_id == other.id) & (HarajMessage.receiver_id == current_user.id),
                )
            )
            .order_by(HarajMessage.created_at.asc()).all())

    # تعليم الرسائل الواردة كمقروءة
    unread_q = HarajMessage.query.filter_by(
        listing_id=listing.id,
        sender_id=other.id,
        receiver_id=current_user.id,
        is_read=False,
    )
    unread_count = unread_q.count()
    if unread_count:
        unread_q.update({'is_read': True}, synchronize_session=False)
        db.session.commit()

    return render_template(
        'haraj/chat.html',
        listing=listing, other=other, messages=msgs,
    )


# ============================================================
# عدد الرسائل غير المقروءة (للـ navbar)
# ============================================================
@haraj_bp.route('/messages/unread_count')
@login_required
def messages_unread_count():
    from flask import jsonify
    n = HarajMessage.query.filter_by(
        receiver_id=current_user.id, is_read=False,
    ).count()
    return jsonify({'count': n})



# ============================================================
# إعجاب / حفظ إعلان
# ============================================================
@haraj_bp.route('/listing/<public_id>/react', methods=['POST'])
@login_required
def react_listing(public_id):
    from flask import jsonify
    listing = Listing.query.filter_by(public_id=public_id).first_or_404()
    reaction_type = (request.form.get('type') or '').strip().lower()

    if reaction_type not in {'like', 'save'}:
        return jsonify({'ok': False, 'error': 'نوع غير صالح'}), 400

    existing = ListingReaction.query.filter_by(
        listing_id=listing.id,
        user_id=current_user.id,
        reaction_type=reaction_type,
    ).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        active = False
    else:
        db.session.add(ListingReaction(
            listing_id=listing.id,
            user_id=current_user.id,
            reaction_type=reaction_type,
        ))
        db.session.commit()
        active = True

    count = ListingReaction.query.filter_by(
        listing_id=listing.id, reaction_type=reaction_type,
    ).count()

    return jsonify({'ok': True, 'active': active, 'count': count})



# ============================================================
# إضافة تعليق
# ============================================================
@haraj_bp.route('/listing/<public_id>/comment', methods=['POST'])
@login_required
def add_comment(public_id):
    listing = Listing.query.filter_by(public_id=public_id).first_or_404()

    content = (request.form.get('content') or '').strip()
    parent_id = request.form.get('parent_id', type=int)

    if not content or len(content) > 1000:
        flash('تعليق فارغ أو طويل جدًا.', 'danger')
        return redirect(url_for('haraj.listing_detail', public_id=public_id) + '#comments')

    if parent_id:
        parent = ListingComment.query.filter_by(
            id=parent_id, listing_id=listing.id, parent_id=None,
        ).first()
        if not parent:
            parent_id = None

    db.session.add(ListingComment(
        listing_id=listing.id,
        author_id=current_user.id,
        parent_id=parent_id,
        content=content,
    ))
    db.session.commit()
    flash('✅ تم إضافة تعليقك.', 'success')
    return redirect(url_for('haraj.listing_detail', public_id=public_id) + '#comments')


# ============================================================
# حذف تعليق (صاحبه فقط أو الأدمن)
# ============================================================
@haraj_bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = ListingComment.query.get_or_404(comment_id)
    listing = comment.listing
    if comment.author_id != current_user.id and not getattr(current_user, 'is_admin', False):
        abort(403)
    comment.is_deleted = True
    db.session.commit()
    flash('تم حذف التعليق.', 'success')
    return redirect(url_for('haraj.listing_detail', public_id=listing.public_id) + '#comments')



# ============================================================
# تقييم البائع (بعد البيع)
# ============================================================
@haraj_bp.route('/listing/<public_id>/rate', methods=['POST'])
@login_required
def rate_seller(public_id):
    listing = Listing.query.filter_by(public_id=public_id).first_or_404()

    # لا يمكن تقييم إعلانك
    if listing.user_id == current_user.id:
        flash('لا يمكنك تقييم نفسك.', 'info')
        return redirect(url_for('haraj.listing_detail', public_id=public_id))

    # لا تقييم إلا بعد البيع
    if listing.status != 'sold':
        flash('يمكن التقييم بعد إتمام البيع فقط.', 'info')
        return redirect(url_for('haraj.listing_detail', public_id=public_id))

    # تقييم واحد فقط لكل مستخدم
    existing = SellerRating.query.filter_by(
        listing_id=listing.id, rater_id=current_user.id,
    ).first()
    if existing:
        flash('لقد قمت بتقييم هذا البائع مسبقًا.', 'info')
        return redirect(url_for('haraj.listing_detail', public_id=public_id))

    try:
        rating = int(request.form.get('rating', 0))
    except (ValueError, TypeError):
        rating = 0
    if not 1 <= rating <= 5:
        flash('اختر تقييمًا من 1 إلى 5.', 'danger')
        return redirect(url_for('haraj.listing_detail', public_id=public_id))

    comment = (request.form.get('comment') or '').strip()[:1000] or None

    db.session.add(SellerRating(
        listing_id=listing.id,
        rater_id=current_user.id,
        seller_id=listing.user_id,
        rating=rating,
        comment=comment,
    ))
    db.session.commit()
    flash('✅ تم حفظ تقييمك. شكرًا لك.', 'success')
    return redirect(url_for('haraj.listing_detail', public_id=public_id))



# ============================================================
# إعدادات الحراج (رقم الواتساب)
# ============================================================
@haraj_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        number = (request.form.get('whatsapp_number') or '').strip()
        show = bool(request.form.get('show_whatsapp'))

        # تحقق من الصيغة (يسمح بـ + و أرقام فقط، 6-20 حرفًا)
        import re
        cleaned = re.sub(r'[^0-9+]', '', number)
        if cleaned and (len(cleaned) < 6 or len(cleaned) > 20):
            flash('رقم الواتساب غير صالح. أمثلة: +966501234567', 'danger')
        else:
            current_user.haraj_whatsapp_number = cleaned or None
            current_user.haraj_show_whatsapp = show
            db.session.commit()
            flash('✅ تم تحديث إعدادات الحراج.', 'success')
        return redirect(url_for('haraj.settings'))

    return render_template('haraj/settings.html')
