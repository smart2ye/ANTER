"""خدمة الترتيب الجغرافي — نفس الدولة + الدول العربية القريبة.

ANTER: ترتيب لا يعتمد على GPS ولا إحداثيات، بل على country_code الموجود.
الخصوصية: لا نجمع مواقع جديدة، نستخدم ما أدخله المستخدم عند التسجيل.
"""

# الدول العربية + الأكثر صلة جغرافيًا
ARAB_COUNTRIES = {
    '+967',  # اليمن
    '+966',  # السعودية
    '+968',  # عمان
    '+971',  # الإمارات
    '+974',  # قطر
    '+973',  # البحرين
    '+965',  # الكويت
    '+962',  # الأردن
    '+961',  # لبنان
    '+963',  # سوريا
    '+964',  # العراق
    '+970',  # فلسطين
    '+20',   # مصر
    '+218',  # ليبيا
    '+216',  # تونس
    '+213',  # الجزائر
    '+212',  # المغرب
    '+222',  # موريتانيا
    '+249',  # السودان
    '+252',  # الصومال
    '+253',  # جيبوتي
    '+269',  # جزر القمر
}

# جيران جغرافيون (نقاط أعلى)
NEIGHBORS = {
    '+967': {'+966', '+968', '+971'},  # اليمن ← السعودية/عمان/الإمارات
    '+966': {'+967', '+968', '+971', '+974', '+973', '+965', '+962', '+964'},
    '+968': {'+967', '+966', '+971'},
    '+971': {'+967', '+966', '+968', '+974', '+973'},
    '+974': {'+966', '+971', '+973'},
    '+973': {'+966', '+971', '+974'},
    '+965': {'+966', '+971', '+964'},
    '+962': {'+966', '+970', '+963', '+964'},
    '+961': {'+963', '+962', '+970'},
    '+963': {'+962', '+961', '+970', '+964'},
    '+964': {'+966', '+962', '+963', '+965'},
    '+970': {'+962', '+961', '+963'},
    '+20':  {'+218', '+249', '+970'},
    '+218': {'+20', '+216', '+249'},
    '+216': {'+218', '+213'},
    '+213': {'+216', '+212'},
    '+212': {'+213', '+222'},
    '+222': {'+212'},
    '+249': {'+20', '+218', '+253'},
    '+252': {'+253', '+967'},
    '+253': {'+252', '+249'},
}


def normalize_country_code(code):
    """يوحّد صيغة رمز الدولة (+967، 967، +00967 → +967)."""
    if not code:
        return ''
    code = str(code).strip()
    if code.startswith('+00967'):
        code = code[3:]
    if not code.startswith('+'):
        code = '+' + code.lstrip('0')
    # تصحيح الحالات الشاذة (966 بدل +966)
    return code


def country_score(viewer_country, author_country):
    """
    يعيد نقاط الترتيب الجغرافي.
    
    - +30: نفس الدولة
    - +15: دولة مجاورة
    - +8: دولة عربية
    - 0: دولة أجنبية أو بيانات ناقصة
    """
    vc = normalize_country_code(viewer_country)
    ac = normalize_country_code(author_country)
    
    if not vc or not ac:
        return 0.0
    
    if vc == ac:
        return 30.0
    
    # جيران مباشرون
    neighbors_of_viewer = NEIGHBORS.get(vc, set())
    if ac in neighbors_of_viewer:
        return 15.0
    
    # كلاهما عربي
    if vc in ARAB_COUNTRIES and ac in ARAB_COUNTRIES:
        return 8.0
    
    return 0.0


def geo_score_for_post(post, viewer):
    """يحسب النقاط الجغرافية لمنشور (بناءً على author.country_code)."""
    if not post or not viewer:
        return 0.0
    author = getattr(post, 'author', None)
    if not author or author.id == viewer.id:
        return 0.0
    return country_score(viewer.country_code, author.country_code)


def geo_score_for_user(target, viewer):
    """يحسب النقاط الجغرافية لمستخدم آخر."""
    if not target or not viewer:
        return 0.0
    if target.id == viewer.id:
        return 0.0
    return country_score(viewer.country_code, target.country_code)
