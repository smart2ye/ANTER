// ==============================
// تحميل لا نهائي (Infinite Scroll)
// ==============================
let page = 2;
let loading = false;
let hasMore = true;

function loadMorePosts() {
    if (loading || !hasMore) return;
    loading = true;

    const spinner = document.getElementById('loading-spinner');
    if (spinner) spinner.style.display = 'block';

    fetch(`/api/posts?page=${page}`)
        .then(res => res.json())
        .then(data => {
            if (data.posts && data.posts.length > 0) {
                const container = document.getElementById('posts-container');
                data.posts.forEach(post => {
                    const postHtml = post.html || createPostHtml(post);
                    container.insertAdjacentHTML('beforeend', postHtml);
                });
                hasMore = data.has_next;
                page++;
            } else {
                hasMore = false;
            }
            loading = false;
            if (spinner) spinner.style.display = 'none';
        })
        .catch(() => {
            loading = false;
            if (spinner) spinner.style.display = 'none';
        });
}

function createPostHtml(post) {
    // يجب أن تأتي البطاقات الديناميكية من نفس القالب المشترك المستخدم في بقية المسارات.
    return post.html || '';
}

// اكتشاف التمرير للأسفل
window.addEventListener('scroll', function() {
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 200) {
        loadMorePosts();
    }
});

// ==============================
// تأثير الإعجاب (like-btn) - يعمل مع الأزرار الديناميكية
// ==============================
document.addEventListener('click', function(e) {
    const btn = e.target.closest('.like-btn');
    if (!btn) return;
    const postId = btn.dataset.post;
    fetch(`/like/${postId}`, {
        method: 'POST',
        credentials: 'include'
    })
    .then(res => res.json())
    .then(data => {
        btn.querySelector('.like-count').textContent = data.count;
        btn.classList.toggle('btn-primary');
        btn.classList.toggle('btn-outline-primary');
        btn.classList.toggle('liked');
    });
});

// ==============================
// تبديل التعليقات - يعمل مع الأزرار الديناميكية
// ==============================
document.addEventListener('click', function(e) {
    const btn = e.target.closest('.toggle-comments-btn, .comment-toggle');
    if (!btn) return;

    const postId = btn.dataset.post;
    const commentsDiv = document.getElementById('comments-' + postId);
    if (!commentsDiv) return;

    const isOpen = commentsDiv.classList.contains('open');
    if (!isOpen) {
        commentsDiv.style.display = 'block';
        requestAnimationFrame(() => commentsDiv.classList.add('open'));

        // تُجلب التعليقات مرة واحدة فقط عند فتح النقاش، لتبقى الخلاصة خفيفة.
        if (commentsDiv.dataset.loaded !== 'true') {
            fetch(`/comments/${postId}/fragment`, {credentials: 'include'})
                .then(res => {
                    if (!res.ok) throw new Error('تعذر تحميل التعليقات');
                    return res.text();
                })
                .then(html => {
                    commentsDiv.innerHTML = html;
                    commentsDiv.dataset.loaded = 'true';
                })
                .catch(() => {
                    commentsDiv.innerHTML = '<p class="text-muted small p-3 mb-0">تعذر تحميل التعليقات الآن.</p>';
                });
        }

        if (btn.classList.contains('toggle-comments-btn')) {
            btn.innerHTML = '<i class="fas fa-comment"></i> إخفاء التعليقات';
        }
    } else {
        commentsDiv.classList.remove('open');
        window.setTimeout(() => {
            if (!commentsDiv.classList.contains('open')) commentsDiv.style.display = 'none';
        }, 280);

        if (btn.classList.contains('toggle-comments-btn')) {
            const count = commentsDiv.querySelectorAll('.comment-item').length;
            btn.innerHTML = `<i class="fas fa-comment"></i> (${count})`;
        }
    }
});

// ==============================
// تفاعل الإعجاب على التعليقات
// ==============================
function updateCommentLikeState(btn, liked, countValue, animate = false) {
    const count = btn.querySelector('.comment-like-count');
    const icon = btn.querySelector('i');
    if (count) count.textContent = countValue > 0 ? countValue : '';
    btn.classList.toggle('liked', liked);
    btn.setAttribute('aria-pressed', liked ? 'true' : 'false');
    if (icon) icon.className = `${liked ? 'fas' : 'far'} fa-heart`;
    if (animate) {
        btn.classList.remove('just-liked');
        requestAnimationFrame(() => btn.classList.add('just-liked'));
    }
}

document.addEventListener('click', function(e) {
    const btn = e.target.closest('.comment-like-btn');
    if (!btn) return;

    const commentId = btn.dataset.comment;
    if (!commentId || btn.dataset.loading === 'true') return;

    const countEl = btn.querySelector('.comment-like-count');
    const wasLiked = btn.classList.contains('liked');
    const previousCount = Number.parseInt(countEl?.textContent || '0', 10) || 0;
    const optimisticLiked = !wasLiked;
    const optimisticCount = Math.max(0, previousCount + (optimisticLiked ? 1 : -1));

    btn.dataset.loading = 'true';
    btn.classList.add('is-loading');
    updateCommentLikeState(btn, optimisticLiked, optimisticCount, optimisticLiked);

    fetch(`/like_comment/${commentId}`, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'include'
    })
        .then(res => {
            if (!res.ok) throw new Error('comment like request failed');
            return res.json();
        })
        .then(data => updateCommentLikeState(btn, Boolean(data.liked), Number(data.count) || 0, Boolean(data.liked)))
        .catch(() => updateCommentLikeState(btn, wasLiked, previousCount, false))
        .finally(() => {
            btn.dataset.loading = 'false';
            btn.classList.remove('is-loading');
        });
});

// ==============================
// نسخ الرابط
// ==============================
window.copyLink = function(url) {
    navigator.clipboard.writeText(url).then(() => {
        alert('✅ تم نسخ الرابط!');
    }).catch(() => {
        const input = document.createElement('input');
        input.value = url;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
        alert('✅ تم نسخ الرابط!');
    });
};

// ==============================
// تفعيل قائمة المشاركة (Dropdown)
// ==============================
document.addEventListener('mouseenter', function(e) {
    const el = e.target.closest('.share-dropdown');
    if (el) {
        const options = el.querySelector('.share-options');
        if (options) options.style.display = 'block';
    }
}, true);
document.addEventListener('mouseleave', function(e) {
    const el = e.target.closest('.share-dropdown');
    if (el) {
        const options = el.querySelector('.share-options');
        if (options) options.style.display = 'none';
    }
}, true);

// ==============================
// تفعيل قائمة التفاعلات (reaction-picker) - يعمل مع الأزرار الديناميكية
// ==============================
document.addEventListener('mouseenter', function(e) {
    const toggle = e.target.closest('.reaction-toggle');
    if (toggle) {
        const picker = toggle.querySelector('.reaction-picker');
        if (picker) picker.style.display = 'flex';
    }
}, true);
document.addEventListener('mouseleave', function(e) {
    const toggle = e.target.closest('.reaction-toggle');
    if (toggle) {
        const picker = toggle.querySelector('.reaction-picker');
        if (picker) picker.style.display = 'none';
    }
}, true);

// ==============================
// معالجة اختيار التفاعل (reaction-option) - يعمل مع الأزرار الديناميكية
// ==============================
const reactionNames = {
    'like': 'إعجاب',
    'love': 'حب',
    'haha': 'أضحكني',
    'angry': 'أغضبني',
    'sad': 'أحزنني'
};
const reactionIcons = {
    'like': '👍',
    'love': '🥰',
    'haha': '🤣',
    'angry': '😡',
    'sad': '😢'
};

document.addEventListener('click', function(e) {
    const option = e.target.closest('.reaction-option');
    if (!option) return;
    e.stopPropagation();

    const postId = option.dataset.post;
    const reaction = option.dataset.reaction;
    if (!postId || option.dataset.loading === 'true') return;

    const wrapper = option.closest('.reaction-wrapper');
    const toggle = wrapper?.querySelector('.reaction-toggle');
    const iconEl = document.getElementById(`reaction-icon-${postId}`);
    const labelEl = document.getElementById(`reaction-label-${postId}`);
    const countEl = document.getElementById(`reaction-count-${postId}`);
    const summary = document.getElementById(`reaction-summary-${postId}`);
    const picker = option.closest('.reaction-picker');

    option.dataset.loading = 'true';
    toggle?.classList.add('is-loading');

    fetch(`/like/${postId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'include',
        body: JSON.stringify({ reaction: reaction })
    })
        .then(res => {
            if (!res.ok) throw new Error('reaction request failed');
            return res.json();
        })
        .then(data => {
            const liked = Boolean(data.liked);
            if (countEl) countEl.textContent = data.count ?? 0;
            if (iconEl) iconEl.textContent = liked ? (reactionIcons[reaction] || '👍') : '👍';
            if (labelEl) labelEl.textContent = liked ? (reactionNames[reaction] || 'إعجاب') : 'إعجاب';
            toggle?.classList.toggle('reaction-active', liked);

            if (summary) {
                summary.innerHTML = `<span class="reaction-item">${iconEl ? iconEl.textContent : '👍'} ${data.count ?? 0}</span>`;
            }

            if (iconEl) {
                iconEl.classList.remove('reaction-just-selected');
                requestAnimationFrame(() => iconEl.classList.add('reaction-just-selected'));
            }

            if (picker) {
                picker.classList.add('selection-complete');
                window.setTimeout(() => picker.classList.remove('selection-complete'), 220);
            }
        })
        .catch(() => {
            toggle?.classList.add('reaction-error');
            window.setTimeout(() => toggle?.classList.remove('reaction-error'), 500);
        })
        .finally(() => {
            option.dataset.loading = 'false';
            toggle?.classList.remove('is-loading');
        });
});

// ==============================
// إغلاق قائمة التفاعلات عند النقر خارجها
// ==============================
document.addEventListener('click', function(e) {
    if (!e.target.closest('.reaction-wrapper')) {
        document.querySelectorAll('.reaction-picker').forEach(picker => {
            picker.style.display = '';
        });
    }
});

// ==============================
// إخفاء المنشور
// ==============================
document.addEventListener('click', function(e) {
    const btn = e.target.closest('.hide-post-btn');
    if (!btn) return;
    const postId = btn.dataset.post;
    if (confirm('هل أنت متأكد من إخفاء هذا المنشور؟')) {
        fetch(`/posts/hide/${postId}`, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'include'
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                const postElement = document.getElementById(`post-${postId}`);
                if (postElement) {
                    postElement.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                    postElement.style.opacity = '0';
                    postElement.style.transform = 'scale(0.9)';
                    setTimeout(() => {
                        postElement.remove();
                        const remainingPosts = document.querySelectorAll('.fb-post');
                        if (remainingPosts.length === 0) location.reload();
                    }, 350);
                }
            } else {
                alert('❌ ' + (data.message || 'حدث خطأ أثناء إخفاء المنشور'));
            }
        })
        .catch(() => alert('❌ حدث خطأ غير متوقع'));
    }
});

// ==============================
// نظام الأصوات (SoundManager)
// ==============================
class SoundManager {
    constructor() {
        this.enabled = localStorage.getItem('soundEnabled') !== 'false';
        this.ctx = null;
    }
    _getContext() {
        if (!this.ctx) {
            this.ctx = new (window.AudioContext || window.webkitAudioContext)();
        }
        return this.ctx;
    }
    _playTone(frequency, duration, type = 'sine', volume = 0.3) {
        if (!this.enabled) return;
        try {
            const ctx = this._getContext();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = type;
            osc.frequency.value = frequency;
            gain.gain.value = volume;
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + duration);
        } catch (e) {}
    }
    notification() { this._playTone(800, 0.15, 'sine', 0.3); setTimeout(() => this._playTone(1000, 0.15, 'sine', 0.25), 150); }
    like() { this._playTone(1200, 0.1, 'sine', 0.2); }
    publish() { this._playTone(600, 0.1, 'sine', 0.2); setTimeout(() => this._playTone(800, 0.1, 'sine', 0.2), 100); setTimeout(() => this._playTone(1000, 0.15, 'sine', 0.25), 200); }
    follow() { this._playTone(700, 0.12, 'sine', 0.2); setTimeout(() => this._playTone(900, 0.12, 'sine', 0.2), 120); }
    toggle() { this.enabled = !this.enabled; localStorage.setItem('soundEnabled', this.enabled); return this.enabled; }
}
const sounds = new SoundManager();

// ربط الأصوات بالأحداث
document.addEventListener('click', function(e) {
    if (e.target.closest('.like-btn, .reaction-option, .comment-like-btn')) sounds.like();
});

// ==============================
// صوت الإشعارات من التحديث الدوري الموحد في القالب العام
// ==============================
let previousNotificationCount = null;
document.addEventListener('anter:notification-count', function(event) {
    const count = Number(event.detail && event.detail.count);
    if (!Number.isFinite(count)) return;

    if (previousNotificationCount !== null && count > previousNotificationCount) {
        sounds.notification();
    }
    previousNotificationCount = count;
});
