import re


BIO_MAX_LENGTH = 200


def normalize_bio(value):
    """يعيد سيرة ذاتية قصيرة قابلة للعرض مع الحفاظ على فواصل الأسطر المفيدة."""
    text = (value or '').replace('\r\n', '\n').replace('\r', '\n')
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    return re.sub(r'\n{3,}', '\n\n', text).strip()
