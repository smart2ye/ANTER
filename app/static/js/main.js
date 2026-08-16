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
    return post.html || '';
}

window.addEventListener('scroll', function() {
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 200) {
        loadMorePosts();
    }
});

// ==============================
// تأثير الإعجاب (like-btn)
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
// تبديل التعليقات
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
// تفعيل قائمة المشاركة
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
// تفعيل قائمة التفاعلات
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

const reactionIcons = { 'like': '👍', 'love': '🥰', 'haha': '🤣', 'angry': '😡', 'sad': '😢' };
const reactionNames = { 'like': 'إعجاب', 'love': 'حب', 'haha': 'أضحكني', 'angry': 'أغضبني', 'sad': 'أحزنني' };

document.addEventListener('click', function(e) {
    const option = e.target.closest('.reaction-option');
    if (!option) return;
    e.stopPropagation();

    const postId = option.dataset.post;
    const reaction = option.dataset.reaction;
    const toggle = option.closest('.reaction-wrapper')?.querySelector('.reaction-toggle');
    const iconEl = document.getElementById(`reaction-icon-${postId}`);
    const labelEl = document.getElementById(`reaction-label-${postId}`);
    const countEl = document.getElementById(`reaction-count-${postId}`);
    const summary = document.getElementById(`reaction-summary-${postId}`);

    fetch(`/like/${postId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'include',
        body: JSON.stringify({ reaction: reaction })
    })
    .then(res => res.json())
    .then(data => {
        const liked = Boolean(data.liked);
        if (countEl) countEl.textContent = data.count ?? 0;
        if (iconEl) iconEl.textContent = liked ? (reactionIcons[reaction] || '👍') : '👍';
        if (labelEl) labelEl.textContent = liked ? (reactionNames[reaction] || 'إعجاب') : 'إعجاب';
        toggle?.classList.toggle('reaction-active', liked);
        if (summary) summary.innerHTML = `<span class="reaction-item">${iconEl?.textContent || '👍'} ${data.count ?? 0}</span>`;
    });
});

document.addEventListener('click', function(e) {
    if (!e.target.closest('.reaction-wrapper')) {
        document.querySelectorAll('.reaction-picker').forEach(picker => picker.style.display = '');
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
                    postElement.style.opacity = '0';
                    setTimeout(() => postElement.remove(), 350);
                }
            }
        });
    }
});

// ==============================
// نظام الأصوات
// ==============================
class SoundManager {
    constructor() {
        this.enabled = localStorage.getItem('soundEnabled') !== 'false';
        this.ctx = null;
    }
    _getContext() {
        if (!this.ctx) this.ctx = new (window.AudioContext || window.webkitAudioContext)();
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
}
const sounds = new SoundManager();

document.addEventListener('click', function(e) {
    if (e.target.closest('.like-btn, .reaction-option, .comment-like-btn')) sounds.like();
});

let previousNotificationCount = null;
document.addEventListener('anter:notification-count', function(event) {
    const count = Number(event.detail && event.detail.count);
    if (Number.isFinite(count) && previousNotificationCount !== null && count > previousNotificationCount) {
        sounds.notification();
    }
    previousNotificationCount = count;
});

// ==============================================
// نظام الإكمال التلقائي للإشارات (@mention Autocomplete)
// ==============================================
document.addEventListener('DOMContentLoaded', function() {
    const dropdown = document.createElement('div');
    dropdown.className = 'mention-autocomplete-dropdown';
    document.body.appendChild(dropdown);

    let activeInput = null;
    let mentionStartIndex = -1;
    let selectedIndex = -1;
    let usersList = [];

    function updateDropdown() {
        if (usersList.length === 0) {
            dropdown.style.display = 'none';
            return;
        }

        dropdown.innerHTML = usersList.map((u, i) => `
            <div class="mention-item ${i === selectedIndex ? 'active' : ''}" data-index="${i}">
                <img src="${u.avatar}" alt="${u.name}">
                <div class="mention-info">
                    <div class="mention-name">${u.name}</div>
                    <div class="mention-username">@${u.username}</div>
                </div>
            </div>
        `).join('');

        const rect = activeInput.getBoundingClientRect();
        dropdown.style.top = `${window.scrollY + rect.bottom + 5}px`;
        dropdown.style.left = `${window.scrollX + rect.left}px`;
        dropdown.style.display = 'block';
    }

    function selectUser(index) {
        if (index < 0 || index >= usersList.length) return;
        const user = usersList[index];
        const before = activeInput.value.substring(0, mentionStartIndex);
        const after = activeInput.value.substring(activeInput.selectionStart);
        activeInput.value = before + `@${user.username} ` + after;
        dropdown.style.display = 'none';
        usersList = [];
        activeInput.focus();
    }

    document.addEventListener('input', function(e) {
        if (!e.target.matches('input[type="text"], textarea')) return;
        
        // منع الإكمال التلقائي في حقول الرسائل الخاصة
        if (e.target.closest('.chat-composer') || e.target.id === 'messageInput') return;
        
        activeInput = e.target;
        const val = activeInput.value;
        const cursorPos = activeInput.selectionStart;
        const textBeforeCursor = val.substring(0, cursorPos);
        const match = textBeforeCursor.match(/@([\w\u0600-\u06FF]*)$/);

        if (match) {
            const query = match[1];
            mentionStartIndex = cursorPos - match[0].length;
            fetch(`/users/api/search?q=${encodeURIComponent(query)}`)
                .then(res => res.json())
                .then(users => {
                    usersList = users;
                    selectedIndex = users.length > 0 ? 0 : -1;
                    updateDropdown();
                });
        } else {
            dropdown.style.display = 'none';
            usersList = [];
        }
    });

    document.addEventListener('keydown', function(e) {
        if (dropdown.style.display !== 'block') return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedIndex = (selectedIndex + 1) % usersList.length;
            updateDropdown();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = (selectedIndex - 1 + usersList.length) % usersList.length;
            updateDropdown();
        } else if (e.key === 'Enter' || e.key === 'Tab') {
            if (selectedIndex >= 0) {
                e.preventDefault();
                selectUser(selectedIndex);
            }
        } else if (e.key === 'Escape') {
            dropdown.style.display = 'none';
        }
    });

    dropdown.addEventListener('mousedown', function(e) {
        const item = e.target.closest('.mention-item');
        if (item) {
            e.preventDefault();
            selectUser(parseInt(item.dataset.index));
        }
    });

    document.addEventListener('click', function(e) {
        if (!dropdown.contains(e.target) && e.target !== activeInput) {
            dropdown.style.display = 'none';
        }
    });
});

// عميل موحد لواجهات Hybrid AI مع تمرير رمز CSRF في طلبات POST.
async function anterAiRequest(url, method = 'GET', payload = null) {
    const headers = { 'Accept': 'application/json' };
    if (payload) {
        headers['Content-Type'] = 'application/json';
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        if (csrfToken) headers['X-CSRFToken'] = csrfToken;
    }

    const response = await fetch(url, {
        method,
        headers,
        credentials: 'same-origin',
        body: payload ? JSON.stringify(payload) : null,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.ok === false) {
        throw new Error(data.error || 'تعذر إتمام طلب الذكاء الاصطناعي.');
    }
    return data;
}

function setAiStatus(button, message, isError = false) {
    const status = document.querySelector(button.dataset.status || '');
    if (!status) return;
    status.textContent = message;
    status.classList.toggle('text-danger', isError);
    status.classList.toggle('text-muted', !isError);
}

// معالج زر تلخيص المنشورات بالذكاء الاصطناعي.
document.addEventListener('click', async function(e) {
    const aiBtn = e.target.closest('.ai-summarize-btn');
    if (!aiBtn) return;

    const postId = aiBtn.getAttribute('data-post');
    const summaryBox = document.getElementById(`ai-summary-box-${postId}`);
    const summaryText = document.getElementById(`ai-summary-text-${postId}`);
    if (!summaryBox || !summaryText) return;

    if (summaryBox.style.display !== 'none') {
        summaryBox.style.display = 'none';
        return;
    }

    summaryBox.style.display = 'block';
    summaryText.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> جاري توليد الملخص الذكي...';
    try {
        const data = await anterAiRequest(`/api/ai/summarize/${postId}`);
        summaryText.textContent = data.summary || 'تعذر إنشاء الملخص.';
    } catch (error) {
        summaryText.textContent = error.message || 'حدث خطأ أثناء الاتصال بخدمة الذكاء الاصطناعي.';
    }
});

// اقتراح أو تحسين نص منشور؛ يضع النتيجة في الحقل فقط ولا ينشرها تلقائياً.
document.addEventListener('click', async function(e) {
    const button = e.target.closest('.ai-composer-btn');
    if (!button) return;

    const target = document.querySelector(button.dataset.target || '');
    if (!target) return;
    const action = button.dataset.action;
    const previousIcon = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    setAiStatus(button, 'جاري إعداد اقتراح ذكي…');

    try {
        const data = await anterAiRequest('/api/ai/assist', 'POST', {
            action,
            text: target.value,
        });
        target.value = data.text || target.value;
        target.dispatchEvent(new Event('input', { bubbles: true }));
        target.focus();
        setAiStatus(button, 'تمت إضافة الاقتراح إلى المسودة. راجعه ثم انشره متى أردت.');
    } catch (error) {
        setAiStatus(button, error.message || 'تعذر إنشاء الاقتراح.', true);
    } finally {
        button.disabled = false;
        button.innerHTML = previousIcon;
    }
});

// اقتراح تعليق على المنشور أو رد؛ لا يُرسل التعليق قبل موافقة المستخدم.
document.addEventListener('click', async function(e) {
    const button = e.target.closest('.ai-comment-suggest-btn');
    if (!button) return;

    const target = document.querySelector(button.dataset.target || '');
    const postId = button.dataset.postId;
    if (!target || !postId) return;

    const previousIcon = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    setAiStatus(button, 'جاري اقتراح تعليق…');

    try {
        const data = await anterAiRequest('/api/ai/assist', 'POST', {
            action: 'suggest_comment',
            post_id: Number(postId),
        });
        target.value = data.text || '';
        target.dispatchEvent(new Event('input', { bubbles: true }));
        target.focus();
        setAiStatus(button, 'تمت إضافة تعليق مقترح؛ يمكنك تعديله قبل الإرسال.');
    } catch (error) {
        setAiStatus(button, error.message || 'تعذر اقتراح تعليق.', true);
    } finally {
        button.disabled = false;
        button.innerHTML = previousIcon;
    }
});
