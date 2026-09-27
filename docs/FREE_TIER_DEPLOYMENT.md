# إعدادات ANTER للخطة المجانية (Render Free)

**آخر تحديث:** 2026-09-27

## Start Command الحالي

gunicorn --bind 0.0.0.0:$PORT run:app --workers=1 --threads=1 
  --timeout=120 --max-requests=300 --max-requests-jitter=50 --preload

| العلم | القيمة | السبب |
|---|---|---|
| `--workers=1` | عامل واحد | الخطة Free تعطي 512MB فقط |
| `--threads=1` | خيط واحد | يمنع التعارض مع SQLAlchemy |
| `--timeout=120` | 120 ثانية | يستوعب استدعاءات AI الطويلة |
| `--max-requests=300` | 300 طلب | إعادة تدوير دورية للعامل |
| `--max-requests-jitter=50` | ±50 | يمنع التزامن بين العمال |
| `--preload` | مُفعّل | تحميل التطبيق قبل شوكة العمال |

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
