# ANTER — الهوية البصرية الرسمية

## لوحة الألوان

| الاسم | HEX | الاستخدام |
|---|---|---|
| ANTER Navy | #031E64 | خلفيات رئيسية داكنة |
| ANTER Dark | #051B4E | خلفيات داكنة ثانوية |
| ANTER Blue | #003AAB | اللون الأساسي — أزرار وروابط |
| ANTER Blue Dark | #002A7A | حالة hover للأزرار |
| ANTER Electric | #158AEC | حدود، إضاءة، تفاعلات |
| ANTER Cyan | #00C8F8 | الشعار، التوهج، عناصر تفاعلية |
| ANTER Aqua | #78F7FD | لمعان، تدرجات فاتحة |
| ANTER Purple | #160B8E | التدرّج السفلي، التوهج |
| ANTER White | #FFFFFF | النصوص على الداكن |

## التدرّج الرسمي

background: linear-gradient(135deg, #031E64 0%, #003AAB 35%, #00C8F8 65%, #160B8E 100%);

## التوهج الرسمي

box-shadow:
  0 0 20px rgba(0, 58, 171, 0.45),
  0 0 40px rgba(0, 200, 248, 0.25),
  0 0 70px rgba(22, 11, 142, 0.20);

## متغيرات CSS

كل المتغيرات في app/static/css/style.css داخل :root:

- --anter-navy, --anter-dark
- --anter-primary    = #003AAB
- --anter-primary-dark = #002A7A
- --anter-electric, --anter-accent, --anter-aqua, --anter-purple
- --anter-gradient, --anter-glow

للتوافق مع الكود القديم توجد مرادفات --fb-* تشير إلى --anter-*. يمكن حذفها تدريجياً لاحقاً.

## الخط

- Cairo (افتراضي)
- Tajawal (احتياطي)

## الطابع البصري

Navy -> Electric Blue -> Cyan -> Purple

- الأزرق: تقنية وثقة
- السماوي: ذكاء ورقمنة
- البنفسجي: مستقبلية

## قواعد الاستخدام

1. الأزرار الأساسية: --anter-primary أو التدرّج.
2. النصوص على أبيض: --anter-primary (تباين كافٍ).
3. الحدود والتوهج: --anter-accent (سيان نيون) — لا يُستخدم كخلفية نص.
4. الأيقونات النشطة: --anter-accent أو --anter-electric.
5. لا تستخدم ألواناً خارج اللوحة إلا لضرورة وظيفية (نجاح/خطأ/تحذير).

## الأيقونات

- PWA: app/static/icons/icon-192.svg
- شعار التطبيق: من الشعار الرسمي المستخرج.

## تاريخ

- 2026-09-26: توحيد الهوية — استبدال أزرق فيسبوك (#1877f2) بلوحة ANTER الرسمية.
