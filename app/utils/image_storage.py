from PIL import Image, UnidentifiedImageError
import os
import uuid
from flask import current_app

def prepare_image_data(image_file, upload_folder='uploads'):
    try:
        img = Image.open(image_file)
        # تقليل الحجم لتوفير الذاكرة
        img.thumbnail((800, 800))
        filename = f"{uuid.uuid4()}.jpg"
        filepath = os.path.join(current_app.root_path, 'static', upload_folder, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        img.save(filepath, 'JPEG', quality=85, optimize=True)
        img.close()  # 🔑 إغلاق الصورة لمنع تسرب الذاكرة
        return filename
    except UnidentifiedImageError:
        return None
    except Exception as e:
        print(f"Error processing image: {e}")
        return None
