from PIL import Image, ImageDraw, ImageFont
import os

# تأكد من وجود المجلد
os.makedirs('app/static/icons', exist_ok=True)

# أنشئ صورة مربعة 512x512 باللون الأزرق
img = Image.new('RGB', (512, 512), color='#1877f2')
draw = ImageDraw.Draw(img)

# حط حرف "A" باللون الأبيض في النص
try:
    font = ImageFont.truetype('/system/fonts/NotoSansCJK-Regular.ttc', 350)  # خط الجوال
except:
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 350)
    except:
        font = ImageFont.load_default()

# احسب الموقع عشان يكون في النص
draw.text((256, 256), 'A', fill='white', anchor='mm', font=font)

# احفظ الصورة
img.save('app/static/icons/anter-icon-512.png')
print('✅ تم إنشاء الأيقونة المربعة 512x512 في app/static/icons/')
