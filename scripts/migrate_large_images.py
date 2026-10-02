"""معالجة الصور الكبيرة في قاعدة البيانات (migration لمرة واحدة).

- يحوّل كل صورة > 500 KB إلى WebP بحجم أقصى 1600px.
- يعمل على قاعدة الإنتاج Aiven (أو أي قاعدة عبر DATABASE_URL).
- يقبل معامل --dry-run لمعاينة النتائج دون كتابة.

الاستخدام:
    export DATABASE_URL="postgresql://..."
    python3 scripts/migrate_large_images.py --dry-run
    python3 scripts/migrate_large_images.py --apply
"""
import argparse
import os
import sys
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

# الحدود
SIZE_THRESHOLD = 500 * 1024       # 500 KB
MAX_DIM = 1600
WEBP_QUALITY = 85


def _process(data, mime):
    """يُعيد (bytes, mime) للنسخة المصغّرة، أو None إن لم تكن بحاجة."""
    if not data or len(data) < SIZE_THRESHOLD:
        return None
    try:
        img = Image.open(BytesIO(data))
        img.load()
    except Exception:
        return None

    # إذا كانت أصغر من الحد، تجاهل
    if max(img.width, img.height) <= MAX_DIM and len(data) < SIZE_THRESHOLD * 2:
        # صغيرة الحجم والأبعاد — لا حاجة
        if len(data) < SIZE_THRESHOLD:
            return None

    # تصغير
    if max(img.width, img.height) > MAX_DIM:
        ratio = MAX_DIM / max(img.width, img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # تحويل للـ WebP
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    out = BytesIO()
    img.save(out, format="WEBP", quality=WEBP_QUALITY, method=5, optimize=True)
    new_data = out.getvalue()

    if len(new_data) >= len(data):
        return None  # لم نُوفّر
    return new_data, "image/webp"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="طبّق التغييرات")
    parser.add_argument("--dry-run", action="store_true", help="معاينة فقط")
    parser.add_argument("--batch", type=int, default=20, help="حجم الدفعة")
    args = parser.parse_args()

    if not args.apply and not args.dry_run:
        print("استخدم --dry-run أو --apply")
        sys.exit(1)

    # تنظيف الرابط: إزالة التعليقات والمسافات الزائدة
    db_url = (os.environ.get("DATABASE_URL", "") or "").strip()
    # إزالة أي تعليق بعد #
    if "#" in db_url:
        db_url = db_url.split("#", 1)[0].rstrip()
    # إصلاح البادئة القديمة
    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]
        print("صحّحنا الرابط: postgres:// → postgresql://")
    os.environ["DATABASE_URL"] = db_url
    print(f"طول الرابط بعد التنظيف: {len(db_url)}")

    from app import create_app
    from app.extensions import db
    from app.models import Post

    app = create_app()
    with app.app_context():
        db_name = db.engine.dialect.name
        print(f"قاعدة البيانات: {db_name}")

        total = Post.query.filter(Post.image_data.isnot(None)).count()
        print(f"إجمالي المنشورات بصور: {total}")
        print(f"معالجة {'(تجريبية)' if args.dry_run else '(حقيقية)'}...")
        print("=" * 60)

        processed = 0
        skipped = 0
        failed = 0
        saved_bytes = 0

        query = Post.query.filter(Post.image_data.isnot(None)).order_by(Post.id)
        for post in query.yield_per(args.batch):
            orig = post.image_data
            if not orig or len(orig) < SIZE_THRESHOLD:
                skipped += 1
                continue

            result = _process(orig, post.image_mime)
            if result is None:
                skipped += 1
                continue

            new_data, new_mime = result
            old_size = len(orig) / 1024
            new_size = len(new_data) / 1024
            diff = old_size - new_size
            saved_bytes += len(orig) - len(new_data)

            print(f"  post #{post.id}: {old_size:.0f} KB → {new_size:.0f} KB "
                  f"(-{diff:.0f} KB, -{diff/old_size*100:.0f}%)")

            if args.apply:
                post.image_data = new_data
                post.image_mime = new_mime
                processed += 1
                if processed % 10 == 0:
                    db.session.commit()
                    print(f"    [حفظ الدفعة — {processed} معالجة]")

        if args.apply and processed:
            db.session.commit()

        print("=" * 60)
        print(f"معالجة: {processed}")
        print(f"متجاهلة: {skipped}")
        print(f"فاشلة: {failed}")
        print(f"وفّرنا: {saved_bytes / (1024*1024):.2f} MB")


if __name__ == "__main__":
    main()
