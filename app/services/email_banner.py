"""ANTER: حالة شريط تأكيد البريد (للإشعار الإجباري)."""


def email_banner_state(user):
    """يعيد dict: {show, state, email}.

    - state = 'verified'     → لا شريط
    - state = 'no_email'     → لا شريط (سيرى الإعدادات لإضافة بريد)
    - state = 'pending'      → "طلبك قيد المعالجة"
    - state = 'unverified'   → "أكد بريدك" + زر
    """
    try:
        if not user or not getattr(user, 'is_authenticated', False):
            return {'show': False, 'state': 'anonymous', 'email': ''}

        # البوتات لا تحتاج تأكيد بريد — إلا لو بريدها غير مؤكد (للاختبار)
        email_check = (getattr(user, 'email', '') or '').strip().lower()
        verified_check = bool(getattr(user, 'email_verified', False))
        if getattr(user, 'is_bot', False) and verified_check:
            return {'show': False, 'state': 'bot', 'email': ''}

        email = (getattr(user, 'email', '') or '').strip().lower()
        verified = bool(getattr(user, 'email_verified', False))

        if verified:
            return {'show': False, 'state': 'verified', 'email': email}

        # بريد داخلي (phone-only) → لا شريط (لا يوجد بريد حقيقي)
        if not email or email.endswith('@phone-only.anter.local') or email.endswith('@merged.anter.local'):
            return {'show': False, 'state': 'no_email', 'email': email}

        # هل يوجد Report معلق؟
        from app.models import Report
        pending = Report.query.filter_by(
            reporter_id=user.id,
            reason='verification:email',
            status='pending',
        ).first()
        if pending:
            return {'show': True, 'state': 'pending', 'email': email}

        return {'show': True, 'state': 'unverified', 'email': email}
    except Exception:
        return {'show': False, 'state': 'error', 'email': ''}
