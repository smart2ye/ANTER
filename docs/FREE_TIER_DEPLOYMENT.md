# إعدادات ANTER للخطة المجانية (Render Free)

**آخر تحديث:** 2026-11-02

## Start Command الحالي

web: gunicorn --bind 0.0.0.0:$PORT run:app --workers=1 --threads=2 \
  --worker-class=gthread --timeout=120 --max-requests=1000 --max-requests-jitter=100

| العلم | القيمة | السبب |
|---|---|---|
| `--workers=1` | عامل واحد | الخطة Free تعطي 512MB فقط |
| `--threads=2` | خيطان | يعالج طلبين متزامنين (polling لا يحجب) |
| `--worker-class=gthread` | gthread | مطلوب لدعم `--threads` |
| `--timeout=120` | 120 ثانية | يستوعب استدعاءات AI الطويلة |
| `--max-requests=1000` | 1000 طلب | إعادة تدوير دورية (تخفيف تسرب الذاكرة) |
| `--max-requests-jitter=100` | ±100 | يمنع التزامن بين العمال |

## Health Check

- **Path:** `/health`
- **تكرار Render:** كل 5 ثوانٍ
- **UptimeRobot:** كل 5 دقائق (خارجي)
- **الرد:** `OK` (2 بايت، لا يكشف تفاصيل)

## قيود Render Free

- **RAM:** 512MB
- **النوم:** بعد 15 دقيقة خمول
- **Cold start:** 30–60 ثانية
- **750 ساعة/شهر**

## للمزيد

- [integrations.md](reference/integrations.md) — كل التكاملات
- [ANTER_REFERENCE.md](reference/ANTER_REFERENCE.md) — نظرة شاملة
