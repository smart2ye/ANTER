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

    # Normalize the file while preserving transparency for PNG/GIF images.
    output = BytesIO()
    if image_format == 'JPEG' and image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')
    save_kwargs = {'optimize': True}
    if image_format == 'JPEG':
        save_kwargs['quality'] = 88
    image.save(output, format=image_format, **save_kwargs)
    return output.getvalue(), mime_type
