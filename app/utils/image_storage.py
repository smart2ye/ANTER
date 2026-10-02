from io import BytesIO

from flask import current_app
from PIL import Image, UnidentifiedImageError


IMAGE_MIME_BY_FORMAT = {
    'JPEG': 'image/jpeg',
    'PNG': 'image/png',
    'GIF': 'image/gif',
    'WEBP': 'image/webp',
}


def prepare_image_data(uploaded_file):
    """Validate and normalize an uploaded image for database storage."""
    if not uploaded_file or not getattr(uploaded_file, 'filename', ''):
        return None, None

    max_bytes = current_app.config['MAX_IMAGE_BYTES']
    raw_data = uploaded_file.read(max_bytes + 1)
    if not raw_data or len(raw_data) > max_bytes:
        return None, None

    try:
        image = Image.open(BytesIO(raw_data))
        image.verify()
        image = Image.open(BytesIO(raw_data))
        if image.width * image.height > current_app.config['MAX_IMAGE_PIXELS']:
            return None, None
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        return None, None

    image_format = (image.format or '').upper()
    mime_type = IMAGE_MIME_BY_FORMAT.get(image_format)
    if not mime_type:
        return None, None

    # ANTER (2026-10-02): تصغير تلقائي — يمنع تخزين صور 4000px بحجم 2.5MB.
    # الحد الأقصى: 1600×1600 (يكفي للعرض الكامل على الجوال والشاشات العادية).
    MAX_DIM = 1600
    if max(image.width, image.height) > MAX_DIM:
        ratio = MAX_DIM / max(image.width, image.height)
        new_size = (int(image.width * ratio), int(image.height * ratio))
        image = image.resize(new_size, Image.LANCZOS)

    # Normalize the file while preserving transparency for PNG/GIF images.
    output = BytesIO()

    # تحويل إلى WebP: أصغر بـ 25-35% من JPEG/PNG، مدعوم في كل المتصفحات الحديثة.
    # نحافظ على الشفافية (RGBA) إن وُجدت.
    if image_format in ('JPEG', 'PNG', 'WEBP'):
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGBA')
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(output, format='WEBP', quality=85, method=5, optimize=True)
        return output.getvalue(), 'image/webp'

    # GIF: نحتفظ بالصيغة (فقدان حركة/شفافية معقد).
    save_kwargs = {'optimize': True}
    if image_format == 'JPEG':
        save_kwargs['quality'] = 88
    image.save(output, format=image_format, **save_kwargs)
    return output.getvalue(), mime_type
