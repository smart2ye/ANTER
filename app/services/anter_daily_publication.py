"""النشر اليومي الآمن لحساب مساعد أنتر.

لا توجد نقطة نشر عامة ولا يُستقبل محتوى من الطلبات. ينشئ النظام منشوراً
عربياً منظماً مرة واحدة يومياً عند تشغيل فحص صحة موثوق أو عند استدعاء الخدمة.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from flask import current_app

from app.extensions import db
from app.models import AssistantDailyPublication, Post
from app.services.anter_assistant import ensure_anter_assistant_user


ARABIA_TIMEZONE = timezone(timedelta(hours=3))
DAILY_POSTS = (
    "صباح الخير من مساعد أنتر. اجعل حضورك اليوم إيجابياً: شارك فكرة مفيدة، واكتب تعليقاً محترماً، وامنح الآخرين مساحة للتعبير.\n\n#ANTER #مجتمع_أنتر",
    "تذكير من مساعد أنتر: المحتوى الجيد يبدأ بفكرة واضحة وعنوان مختصر ولغة محترمة. اكتب ما يضيف قيمة حقيقية لمجتمع أنتر.\n\n#ANTER #صناعة_المحتوى",
    "في ANTER، الحوار الهادئ أقوى من الرد المتسرع. اقرأ الفكرة كاملة، ثم شارك رأيك بوضوح واحترام.\n\n#ANTER #حوار_راقي",
    "فكرة اليوم من مساعد أنتر: لا تنتظر الكمال لتشارك. ابدأ بمسودة صادقة، ثم حسّنها خطوة خطوة.\n\n#ANTER #تطوير_المحتوى",
    "مجتمع أنتر يبنى بالتفاعل المفيد. ادعم منشوراً أعجبك، أجب عن سؤال، أو رحّب بعضو جديد اليوم.\n\n#ANTER #مجتمع_إيجابي",
    "الخصوصية مسؤولية مشتركة. لا تشارك كلمات المرور أو الرموز أو البيانات الحساسة داخل أي محادثة أو منشور.\n\n#ANTER #الخصوصية_أولاً",
    "ختام الأسبوع فرصة للتأمل: ما الفكرة التي تعلمتها؟ وما المحتوى الذي ترغب في تقديمه لمجتمع ANTER القادم؟\n\n#ANTER #تعلم_وتطور",
)


def anter_today():
    """تاريخ اليوم وفق توقيت ANTER العربي (+03:00)."""
    return datetime.now(ARABIA_TIMEZONE).date()


def ensure_daily_assistant_post() -> Post | None:
    """ينشر منشوراً واحداً فقط لمساعد أنتر في كل يوم.

    يعيد المنشور القائم إن كان منشور اليوم موجوداً، ولا يكشف أخطاء قاعدة
    البيانات إلى مستخدمي الموقع لأن هذه الوظيفة تستدعى من مسار الصحة.
    """
    if not current_app.config.get("ANTER_ASSISTANT_DAILY_POSTS_ENABLED", True):
        return None

    today = anter_today()
    published = AssistantDailyPublication.query.filter_by(published_on=today).first()
    if published is not None:
        return published.post

    assistant = ensure_anter_assistant_user()
    weekday_index = today.weekday() % len(DAILY_POSTS)
    post = Post(
        author_id=assistant.id,
        content=DAILY_POSTS[weekday_index],
        image='',
    )
    db.session.add(post)
    db.session.flush()
    db.session.add(AssistantDailyPublication(published_on=today, post_id=post.id))

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        concurrent_publication = AssistantDailyPublication.query.filter_by(published_on=today).first()
        return concurrent_publication.post if concurrent_publication is not None else None

    return post
