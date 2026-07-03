
# 🤝 دليل المساهمة في مشروع ANTER

شكراً لاهتمامك بالمساهمة في تطوير ANTER! هذا الدليل يوضح الخطوات اللازمة للمساهمة بفعالية.

## 🧭 **كيف تبدأ؟**

1. **استنساخ المشروع**:
   ```bash
   git clone https://github.com/smart2ye/ANTER.git
   cd ANTER
```

2. تثبيت المتطلبات:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. تشغيل التطبيق محلياً:
   ```bash
   python run.py
   ```

---

🌿 استراتيجية الفروع (Git Branching)

الفرع الاستخدام
main النسخة المستقرة (الإنتاج). لا نعدل عليه مباشرة.
develop فرع التطوير الرئيسي (دمج الميزات).
feature/* فرع لميزة جديدة (مثل feature/trending).
fix/* فرع لإصلاح خطأ (مثل fix/login-error).

---

📝 خطوات المساهمة

1. أنشئ فرعاً للميزة الجديدة:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. أضف تعديلاتك مع اختبارها محلياً.
3. التزم بالتغييرات:
   ```bash
   git add .
   git commit -m "وصف واضح للتغيير"
   ```
4. ارفع الفرع إلى GitHub:
   ```bash
   git push origin feature/your-feature-name
   ```
5. أنشئ طلب دمج (Pull Request):
   · اذهب إلى صفحة المشروع على GitHub.
   · اضغط "New Pull Request".
   · اختر الفرع develop كقاعدة وفرعك كمصدر.
   · اكتب وصفاً واضحاً للتغييرات.

---

🧪 معايير الكود

· Python: اتبع PEP 8 (4 مسافات للتبويب).
· HTML/CSS: استخدم Bootstrap 5 وتجنب CSS المكرر.
· JavaScript: استخدم fetch بدلاً من XMLHttpRequest.
· التعليقات: اشرح "لماذا" وليس "ماذا".

---

📌 قبل رفع الطلب

· ✅ تأكد من أن التطبيق يعمل محلياً.
· ✅ تأكد من عدم وجود أخطاء في السجلات.
· ✅ اختبر على متصفحات مختلفة (Chrome, Firefox).
· ✅ أضف اختبارات (إن أمكن).

---

📞 الدعم

إذا واجهت أي مشكلة، تواصل مع المطور:

· فيسبوك: abdulqader.mahdly
· واتساب: +967737254619

شكراً لمساهمتك! 🌟
