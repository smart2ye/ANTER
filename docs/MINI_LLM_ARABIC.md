# mini-llm Arabic داخل منظومة ANTER

**آخر تحديث:** 2026-09-27

## التعريف المعتمد

> **mini-llm Arabic هو محرك الذكاء الاصطناعي العربي داخل ANTER. يعتمد في الإنتاج على Groq API (نموذج qwen/qwen3.8-27b)، مع طبقات محلية للمساعدة والسياق.**

## البنية الحالية

### المكوّنات

| المكوّن | الموقع | الدور |
|---|---|---|
| `app/services/anter_assistant.py` | ANTER | منطق مساعد أنتر داخل الدردشة |
| `app/services/anter_memory.py` | ANTER | ذاكرة محلية للمستخدم |
| `app/services/ai_service.py` | ANTER | كتابة المنشورات وتحسينها |
| Groq API | خارجي | النموذج الفعلي (qwen/qwen3.8-27b) |

### الذاكرة والسياق

- **الذاكرة القصيرة:** 24 رسالة × 800 حرف كحد أقصى لكل مستخدم.
- **الفلترة:** تُستبعد الردود < 3 أحرف وردود الفشل المتكررة.
- **السياق المُرسل للـ AI:** ~3000 حرف لكل طلب (لتفادي 413/429).
- **هوية المستخدم:** اسم + username يُرسلان في `system prompt`.

### المحلي مقابل الخارجي

| الميزة | محلي | خارجي |
|---|---|---|
| تحية المستخدم | ✅ | — |
| أوامر الذاكرة ("نادني…") | ✅ | — |
| سؤال عن الاسم/الدور | ✅ | — |
| ردود عامة | — | ✅ Groq |
| تلخيص منشور | — | ✅ Groq |
| اقتراح تعليق | — | ✅ Groq |

## المتغيرات البيئية

- `GROQ_API_KEY` — مفتاح Groq
- `GROQ_MODEL` — النموذج (افتراضي: qwen/qwen3.8-27b)
- `MINI_LLM_ARABIC_API_URL` — عنوان endpoint
- `MINI_LLM_ARABIC_API_KEY` — مفتاح (نفس GROQ_API_KEY)
- `MINI_LLM_ARABIC_MODEL` — نفس GROQ_MODEL
- `MINI_LLM_ARABIC_TIMEOUT_SECONDS` — مهلة الطلب (افتراضي 40)
- `MINI_LLM_ARABIC_MAX_TOKENS` — حد الرد (افتراضي 420)
- `ANTER_ASSISTANT_ENABLED` — تفعيل/تعطيل المساعد
- `ANTER_ASSISTANT_USERNAME` — اسم المستخدم المساعد (anter_assistant)
- `ANTER_ASSISTANT_MAX_QUESTION_CHARACTERS` — 3000
- `ANTER_ASSISTANT_MAX_REPLY_CHARACTERS` — 1200

## مستودع مستقل

- المستودع: [smart2ye/mini-llm-arabic](https://github.com/smart2ye/mini-llm-arabic)
- المستند المعماري: [docs/MINI_LLM_ARABIC_ARCHITECTURE.md](https://github.com/smart2ye/mini-llm-arabic/blob/main/docs/MINI_LLM_ARABIC_ARCHITECTURE.md)

## تاريخ المراجعات

- **2026-09-27:** توثيق التوسيع — ذاكرة موسّعة + تمرير هوية المستخدم + فلترة ضوضاء.
- **2026-08-24:** توثيق أولي (نموذج محلي N-gram + TF-IDF).
