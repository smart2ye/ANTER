/**
 * ANTER Guard — حماية عامة للتفاعلات
 * - مؤشر تحميل مركزي (حلقة تدور + "لحظة...") يظهر أثناء الطلبات
 * - يمنع الإرسال المزدوج للنماذج
 * - يمنع النقر المزدوج على الروابط
 * - يوقف الأزرار المشغولة (is-loading) عن الاستقبال
 */
(function () {
    'use strict';

    if (window.__anterGuardReady) return;
    window.__anterGuardReady = true;

    // ============ مؤشر التحميل المركزي ============
    var activeRequests = 0;
    var spinnerEl = null;
    var showTimer = null;
    var hideTimer = null;
    var SHOW_DELAY = 300;     // لا يظهر لطلبات < 300ms
    var SAFETY_TIMEOUT = 30000; // 30s — يفشل بأمان

    function buildSpinner() {
        if (spinnerEl) return spinnerEl;
        var el = document.createElement('div');
        el.className = 'anter-loading-overlay';
        el.id = 'anter-loading-overlay';
        el.setAttribute('role', 'status');
        el.setAttribute('aria-live', 'polite');
        el.innerHTML =
            '<div class="anter-loading-box">' +
            '  <div class="anter-loading-ring" aria-hidden="true"></div>' +
            '  <div class="anter-loading-text">لحظة…</div>' +
            '</div>';
        document.body.appendChild(el);
        spinnerEl = el;
        return el;
    }

    function showSpinner() {
        if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
        if (showTimer) return;
        showTimer = setTimeout(function () {
            showTimer = null;
            if (activeRequests > 0) {
                var el = buildSpinner();
                el.classList.add('is-open');
            }
        }, SHOW_DELAY);
    }

    function hideSpinner() {
        if (showTimer) { clearTimeout(showTimer); showTimer = null; }
        if (activeRequests > 0) return;
        hideTimer = setTimeout(function () {
            hideTimer = null;
            if (activeRequests > 0) return;
            if (spinnerEl) spinnerEl.classList.remove('is-open');
        }, 1400);  // فترة سماح: لو الصفحة بصدد الانتقال، الحلقة تبقى
    }

    var pinSafetyTimer = null;

    function pin() {
        if (showTimer) { clearTimeout(showTimer); showTimer = null; }
        if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
        if (pinSafetyTimer) { clearTimeout(pinSafetyTimer); }
        activeRequests = 9999;
        buildSpinner().classList.add('is-open');

        // أمان: لو الصفحة لم تنتقل خلال 30 ثانية، ارفع المؤشر
        pinSafetyTimer = setTimeout(function () {
            pinSafetyTimer = null;
            activeRequests = 0;
            if (spinnerEl) spinnerEl.classList.remove('is-open');
        }, 30000);
    }

    function trackStart() {
        activeRequests += 1;
        showSpinner();
        // أمان: لو نسينا إنقاص العداد، نصفّره بعد 30s
        setTimeout(function () {
            if (activeRequests > 0 && !showTimer) {
                // لا نفعل شيئًا عنيفًا — فقط نسمح بالإخفاء
            }
        }, SAFETY_TIMEOUT);
    }

    function trackEnd() {
        if (activeRequests > 0) activeRequests -= 1;
        hideSpinner();
    }

    window.__anterTrack = { start: trackStart, end: trackEnd };
    window.__anterGuard = { pin: pin, unPin: function() { activeRequests = 0; hideSpinner(); } };

    // ============ اعتراض fetch تلقائيًا ============
    // نقاط polling — لا تُظهر المؤشر (تعمل كل 3s في الخلفية)
    var POLL_PATTERNS = [
        /\/unread_count/,
        /\/unread_total/,
        /\/calls\/pending/,
        /\/typing\//,
        /\/poll(\?|$)/,
        /\/stories\/feed/,
        /\/video-thumb\//,
        /\/avatar\//,
        /\/media\//
    ];

    function isPolling(url) {
        if (!url) return false;
        var s = String(url);
        for (var i = 0; i < POLL_PATTERNS.length; i++) {
            if (POLL_PATTERNS[i].test(s)) return true;
        }
        return false;
    }

    var originalFetch = window.fetch;
    if (typeof originalFetch === 'function') {
        window.fetch = function () {
            var args = Array.prototype.slice.call(arguments);
            var url = args[0];
            if (url && typeof url === 'object' && url.url) url = url.url;
            if (isPolling(url)) {
                return originalFetch.apply(this, args);
            }
            trackStart();
            var p = originalFetch.apply(this, args);
            return p.finally(function () {
                trackEnd();
            });
        };
    }

    // ============ منع الإرسال المزدوج للنماذج ============
    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!form || form.tagName !== 'FORM') return;
        if (form.dataset.anterSubmitting === 'true') {
            e.preventDefault();
            e.stopImmediatePropagation();
            return false;
        }

        // إن كان معالج آخر قد اعترض بالفعل، لا نثبّت
        if (e.defaultPrevented) return;

        // التحقق من الصلاحية أولًا — لا نثبّت المؤشر إن كان النموذج غير صالح
        if (form.checkValidity && !form.checkValidity()) {
            return; // نسمح للمتصفح بعرض رسائل التحقق
        }

        form.dataset.anterSubmitting = 'true';

        var btn = form.querySelector('button[type="submit"], input[type="submit"]');
        if (btn) {
            btn.dataset.anterOriginalText = btn.innerHTML;
            btn.disabled = true;
        }

        // تثبيت المؤشر حتى انتقال الصفحة
        pin();

        // إن اعترض معالج آخر الإرسال (AJAX)، ارفع التثبيت فورًا
        setTimeout(function () {
            if (e.defaultPrevented) {
                window.__anterGuard.unPin();
            }
        }, 0);
    }, true);

    // لو رجع المستخدم عبر bfcache، نصفّر الحالة
    window.addEventListener('pageshow', function (e) {
        if (e.persisted) {
            document.querySelectorAll('form[data-anter-submitting="true"]').forEach(function (f) {
                f.dataset.anterSubmitting = 'false';
            });
        }
    });

    // ============ منع النقر المزدوج على الروابط ============
    var lastClick = { href: '', at: 0 };
    document.addEventListener('click', function (e) {
        var link = e.target.closest('a[href]');
        if (!link) return;
        if (link.target === '_blank' || link.hasAttribute('download')) return;
        if (link.dataset.anterNoGuard === 'true') return;
        if (link.classList.contains('js-lightbox') || link.closest('.js-lightbox')) return;

        var href = link.getAttribute('href') || '';
        if (!href || href === '#' || href.startsWith('javascript:')) return;

        var now = Date.now();
        if (lastClick.href === href && (now - lastClick.at) < 900) {
            e.preventDefault();
            e.stopImmediatePropagation();
            return false;
        }
        lastClick.href = href;
        lastClick.at = now;
    }, true);

    // ============ الأزرار المشغولة لا تستقبل نقرات ============
    document.addEventListener('click', function (e) {
        var busy = e.target.closest('.is-loading, [disabled]');
        if (busy && e.detail !== 0) {
            e.preventDefault();
            e.stopImmediatePropagation();
            return false;
        }
    }, true);
})();
