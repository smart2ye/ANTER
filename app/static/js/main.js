// ==============================
// تحميل لا نهائي + توصيات داخل الخلاصة
// ==============================
let page = 2;
let loading = false;
let hasMore = true;

let recommendationPool = [];
let recommendationIndex = 0;
let postsSinceRecommendation = 0;
let nextRecommendationAt = 2;

function prepareRecommendationPool() {
    const template = document.getElementById('feed-recommendations-template');
    if (!template) return;

    const cards = template.content.querySelectorAll('.post-card');
    const existingPostIds = new Set(
        Array.from(document.querySelectorAll('#posts-container .post-card'))
            .map(card => card.dataset.postId)
            .filter(Boolean)
    );

    recommendationPool = Array.from(cards).filter(card => {
        const id = card.dataset.postId;
        return id && !existingPostIds.has(id);
    });

    recommendationPool.sort(() => Math.random() - 0.5);
}

function getNextRecommendationCarousel() {
    if (recommendationIndex >= recommendationPool.length) return null;

    const wrapper = document.createElement('div');
    wrapper.className = 'feed-recommendations';
    wrapper.dataset.recommendations = 'true';

    const header = document.createElement('div');
    header.className = 'feed-recommendations-header';
    header.innerHTML = '<h3 class="feed-recommendations-title">✨ قد تعجبك</h3>';

    const track = document.createElement('div');
    track.className = 'feed-recommendations-track';

    const cardsPerCarousel = Math.min(
        2,
        recommendationPool.length - recommendationIndex
    );

    for (let i = 0; i < cardsPerCarousel; i++) {
        track.appendChild(
            recommendationPool[recommendationIndex++].cloneNode(true)
        );
    }

    wrapper.appendChild(header);
    wrapper.appendChild(track);

    return wrapper;
}

function maybeInsertRecommendation(container) {
    if (!container || recommendationIndex >= recommendationPool.length) {
        return;
    }

    if (postsSinceRecommendation < nextRecommendationAt) {
        return;
    }

    const carousel = getNextRecommendationCarousel();
    if (!carousel) return;

    container.appendChild(carousel);

    postsSinceRecommendation = 0;
    nextRecommendationAt = 2 + Math.floor(Math.random() * 3);
}

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

                    postsSinceRecommendation++;
                    maybeInsertRecommendation(container);
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

document.addEventListener('DOMContentLoaded', function() {
    prepareRecommendationPool();

    const container = document.getElementById('posts-container');
    if (!container || recommendationIndex >= recommendationPool.length) return;

    nextRecommendationAt = 2 + Math.floor(Math.random() * 3);

    const initialPosts = container.querySelectorAll(':scope > .post-card');

    initialPosts.forEach((post, index) => {
        postsSinceRecommendation++;

        if (postsSinceRecommendation >= nextRecommendationAt) {
            const carousel = getNextRecommendationCarousel();
            if (!carousel) return;

            container.insertBefore(carousel, post.nextSibling);

            postsSinceRecommendation = 0;
            nextRecommendationAt = 2 + Math.floor(Math.random() * 3);
        }
    });
});

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
}

// ANTER: زر المشاركة الآن يفتح نافذة موحّدة (index.html).
// أُبقي هذا المعالج معطّلًا لتجنّب النسخ المزدوج.
// document.addEventListener("click", function(e) {
//     const btn = e.target.closest(".share-btn");
//     if (!btn) return;
//     const url = btn.dataset.shareUrl;
//     if (url) window.copyLink(url);
// });

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
// تفاعلات المنشورات: فتح سلس وتحديث مرئي فوري
// ==============================
const reactionIcons = { like: '👍', love: '🥰', haha: '🤣', angry: '😡', sad: '😢' };
const reactionNames = { like: 'إعجاب', love: 'حب', haha: 'أضحكني', angry: 'أغضبني', sad: 'أحزنني' };
const reactionRequestsInFlight = new Set();
const reactionLongPressTimers = new WeakMap();
let reactionPickerCloseTimer = null;

function getReactionElements(postId, wrapper) {
    return {
        wrapper,
        toggle: wrapper?.querySelector('.reaction-toggle'),
        picker: wrapper?.querySelector('.reaction-picker'),
        icon: document.getElementById(`reaction-icon-${postId}`),
        label: document.getElementById(`reaction-label-${postId}`),
        count: document.getElementById(`reaction-count-${postId}`),
        summary: document.getElementById(`reaction-summary-${postId}`),
    };
}

function setReactionPickerOpen(wrapper, isOpen) {
    if (!wrapper) return;
    const toggle = wrapper.querySelector('.reaction-toggle');
    wrapper.classList.toggle('reaction-picker-open', isOpen);
    if (toggle) toggle.setAttribute('aria-expanded', String(isOpen));
}

function closeAllReactionPickers(exceptWrapper = null) {
    document.querySelectorAll('.reaction-wrapper.reaction-picker-open').forEach(wrapper => {
        if (wrapper !== exceptWrapper) setReactionPickerOpen(wrapper, false);
    });
}

function scheduleReactionPickerClose(wrapper) {
    clearTimeout(reactionPickerCloseTimer);
    reactionPickerCloseTimer = setTimeout(() => setReactionPickerOpen(wrapper, false), 150);
}

function playReactionSelectionAnimation(icon) {
    if (!icon) return;
    icon.classList.remove('reaction-just-selected');
    void icon.offsetWidth;
    icon.classList.add('reaction-just-selected');
}

function renderReactionSummary(summary, reactionCounts, totalCount, userReaction, recentUsers = []) {
    if (!summary) return;

    const textSpan = summary.querySelector('#reaction-summary-text-' + summary.id.split('-').pop());
    if (!textSpan) return;

    if (totalCount <= 0) {
        textSpan.textContent = '';
        return;
    }

    const users = Array.isArray(recentUsers) ? recentUsers : [];

    if (users.length > 0) {
        const names = users.map(user => {
            return user.is_current_user ? 'أنت' : (user.name || 'مستخدم');
        });

        let text = names.join(' و ');

        const remaining = totalCount - users.length;

        if (remaining > 0) {
            text += ` و ${remaining} آخرين`;
        }

        textSpan.textContent = text;
        return;
    }

    // fallback إذا لم تصل بيانات المستخدمين
    if (userReaction) {
        const emoji = reactionIcons[userReaction] || '👍';
        const others = totalCount - 1;
        textSpan.innerHTML = `${emoji} أنت${others > 0 ? ` و ${others} آخرين` : ''}`;
        return;
    }

    const orderedTypes = ['like', 'love', 'haha', 'angry', 'sad'];

    const content = orderedTypes
        .filter(type => Number(reactionCounts?.[type]) > 0)
        .map(type => `${reactionIcons[type]} ${reactionCounts[type]}`)
        .join(' ');

    textSpan.textContent = content || `👍 ${totalCount}`;
}

function updateReactionUi(postId, reaction, data, elements) {
    const liked = Boolean(data.liked);
    const activeReaction = liked ? (data.reaction || reaction) : null;
    if (elements.count) {
        elements.count.textContent = data.count ?? 0;
        elements.count.classList.remove('reaction-count-updated');
        void elements.count.offsetWidth;
        elements.count.classList.add('reaction-count-updated');
    }
    if (elements.icon) elements.icon.textContent = activeReaction ? (reactionIcons[activeReaction] || '👍') : '👍';
    if (elements.label) elements.label.textContent = activeReaction ? (reactionNames[activeReaction] || 'إعجاب') : 'إعجاب';
    if (elements.toggle) {
        elements.toggle.classList.toggle('reaction-active', liked);
        elements.toggle.dataset.userReaction = activeReaction || '';
        elements.toggle.dataset.reaction = activeReaction || '';
        elements.toggle.setAttribute('aria-label', activeReaction ? `تفاعلت بـ ${reactionNames[activeReaction]}` : 'إضافة تفاعل');
    }
    elements.wrapper?.querySelectorAll('.reaction-option').forEach(option => {
        option.classList.toggle('is-selected', option.dataset.reaction === activeReaction);
    });
    renderReactionSummary(
        elements.summary,
        data.reaction_counts,
        data.count ?? 0,
        activeReaction,
        data.recent_users || []
    );
    playReactionSelectionAnimation(elements.icon);
}

async function submitPostReaction(wrapper, reaction) {
    const postId = wrapper?.querySelector('.reaction-toggle')?.dataset.post;
    if (!postId || reactionRequestsInFlight.has(postId)) return;

    const elements = getReactionElements(postId, wrapper);
    if (!elements.toggle) return;
    const snapshot = {
        icon: elements.icon?.textContent,
        label: elements.label?.textContent,
        count: elements.count?.textContent,
        summary: elements.summary?.innerHTML,
        active: elements.toggle.classList.contains('reaction-active'),
        reaction: elements.toggle.dataset.reaction || '',
    };

    reactionRequestsInFlight.add(postId);
    elements.toggle.classList.add('is-loading');
    elements.wrapper?.classList.add('reaction-request-pending');
    if (elements.icon) elements.icon.textContent = reactionIcons[reaction] || '👍';
    if (elements.label) elements.label.textContent = reactionNames[reaction] || 'إعجاب';
    elements.toggle.classList.add('reaction-active');
    playReactionSelectionAnimation(elements.icon);

    try {
        const response = await fetch(`/like/${postId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'include',
            body: JSON.stringify({ reaction })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'تعذر تسجيل التفاعل');
        updateReactionUi(postId, reaction, data, elements);
    } catch (error) {
        if (elements.icon) elements.icon.textContent = snapshot.icon || '👍';
        if (elements.label) elements.label.textContent = snapshot.label || 'إعجاب';
        if (elements.count) elements.count.textContent = snapshot.count || '0';
        if (elements.summary) elements.summary.innerHTML = snapshot.summary || '';
        elements.toggle.classList.toggle('reaction-active', snapshot.active);
        elements.toggle.dataset.reaction = snapshot.reaction;
        elements.toggle.dataset.userReaction = snapshot.reaction;
        elements.toggle.classList.remove('reaction-error');
        void elements.toggle.offsetWidth;
        elements.toggle.classList.add('reaction-error');
        console.error('Post reaction error:', error);
    } finally {
        reactionRequestsInFlight.delete(postId);
        elements.toggle.classList.remove('is-loading');
        elements.wrapper?.classList.remove('reaction-request-pending');
    }
}

document.addEventListener('pointerenter', function(e) {
    const wrapper = e.target.closest('.reaction-wrapper');
    if (!wrapper || e.pointerType === 'touch') return;
    clearTimeout(reactionPickerCloseTimer);
    closeAllReactionPickers(wrapper);
    setReactionPickerOpen(wrapper, true);
}, true);

document.addEventListener('pointerleave', function(e) {
    const wrapper = e.target.closest('.reaction-wrapper');
    if (!wrapper || e.pointerType === 'touch') return;
    scheduleReactionPickerClose(wrapper);
}, true);

document.addEventListener('focusin', function(e) {
    const wrapper = e.target.closest('.reaction-wrapper');
    if (!wrapper) return;
    clearTimeout(reactionPickerCloseTimer);
    closeAllReactionPickers(wrapper);
    setReactionPickerOpen(wrapper, true);
});

document.addEventListener('focusout', function(e) {
    const wrapper = e.target.closest('.reaction-wrapper');
    if (wrapper && !wrapper.contains(e.relatedTarget)) scheduleReactionPickerClose(wrapper);
});

document.addEventListener('pointerdown', function(e) {
    const toggle = e.target.closest('.reaction-toggle');
    if (!toggle || e.pointerType !== 'touch') return;
    const wrapper = toggle.closest('.reaction-wrapper');
    const timer = setTimeout(() => {
        toggle.dataset.longPressOpen = 'true';
        closeAllReactionPickers(wrapper);
        setReactionPickerOpen(wrapper, true);
        if (navigator.vibrate) navigator.vibrate(12);
    }, 380);
    reactionLongPressTimers.set(toggle, timer);
}, true);

['pointerup', 'pointercancel', 'pointerleave'].forEach(eventName => {
    document.addEventListener(eventName, function(e) {
        const toggle = e.target.closest('.reaction-toggle');
        if (!toggle) return;
        const timer = reactionLongPressTimers.get(toggle);
        if (timer) clearTimeout(timer);
        reactionLongPressTimers.delete(toggle);
    }, true);
});

document.addEventListener('click', function(e) {
    const option = e.target.closest('.reaction-option');
    if (option) {
        e.preventDefault();
        e.stopPropagation();
        const wrapper = option.closest('.reaction-wrapper');
        const picker = option.closest('.reaction-picker');
        picker?.classList.add('selection-complete');
        setReactionPickerOpen(wrapper, false);
        setTimeout(() => picker?.classList.remove('selection-complete'), 180);
        submitPostReaction(wrapper, option.dataset.reaction);
        return;
    }

    const toggle = e.target.closest('.reaction-toggle');
    if (toggle) {
        e.preventDefault();
        e.stopPropagation();
        const wrapper = toggle.closest('.reaction-wrapper');
        if (toggle.dataset.longPressOpen === 'true') {
            delete toggle.dataset.longPressOpen;
            return;
        }
        submitPostReaction(wrapper, toggle.dataset.userReaction || 'like');
        return;
    }

    if (!e.target.closest('.reaction-wrapper')) closeAllReactionPickers();
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

// ==============================================
// تحويل توقيت المنشورات إلى التوقيت المحلي لجوال المستخدم
// ==============================================
document.addEventListener('DOMContentLoaded', function() {
    const timeElements = document.querySelectorAll('.local-time');
    timeElements.forEach(el => {
        const utcStr = el.getAttribute('data-utc');
        if (!utcStr) return;
        try {
            // اعتبار الوقت القادم من الخادم بتوقيت UTC
            const utcDate = new Date(utcStr.replace(' ', 'T') + 'Z');
            if (isNaN(utcDate)) return;

            const now = new Date();
            const diffMs = now - utcDate;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMins / 60);
            const diffDays = Math.floor(diffHours / 24);

            if (diffMins < 1) {
                el.textContent = 'الآن';
            } else if (diffMins < 60) {
                el.textContent = `منذ ${diffMins} دقيقة`;
            } else if (diffHours < 24) {
                el.textContent = `منذ ${diffHours} ساعة`;
            } else if (diffDays === 1) {
                el.textContent = 'أمس في ' + utcDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            } else {
                // عرض التاريخ المحلي بالتنسيق المناسب لجوال المستخدم
                const options = { hour: '2-digit', minute: '2-digit', month: 'numeric', day: 'numeric' };
                el.textContent = utcDate.toLocaleDateString([], options);
            }
        } catch (e) {
            console.error('Error formatting local time:', e);
        }
    });
});

// ==============================================
// وظائف مساعدة عامة
// ==============================================
function copyToClipboard(text) {
    const el = document.createElement('textarea');
    el.value = text;
    document.body.appendChild(el);
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);
}

/* فتح صفحة المنشور عند الضغط على البطاقة */
document.addEventListener('click', function(e) {
    const card = e.target.closest('.post-card');
    if (!card) return;

    /* لا نفتح المنشور عند الضغط على زر أو رابط داخله */
    if (e.target.closest('button, a, input, textarea, select, .reaction-picker')) return;

    const url = card.dataset.postUrl;
    if (url) window.location.href = url;
});

/* ============================================================
   ANTER Image Lightbox — عارض الصور العالمي
   ============================================================ */
(function _anterLightbox() {
    let overlay = null;
    let imgEl = null;
    let captionEl = null;

    function build() {
        if (overlay) return;
        overlay = document.createElement('div');
        overlay.className = 'anter-lightbox';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.innerHTML = `
            <button type="button" class="anter-lightbox__close" aria-label="إغلاق">
                <i class="fas fa-times"></i>
            </button>
            <img class="anter-lightbox__img" alt="">
            <div class="anter-lightbox__caption"></div>
        `;
        document.body.appendChild(overlay);
        imgEl = overlay.querySelector('.anter-lightbox__img');
        captionEl = overlay.querySelector('.anter-lightbox__caption');

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay || e.target.closest('.anter-lightbox__close')) {
                close();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && overlay.classList.contains('is-open')) close();
        });
    }

    function open(src, caption) {
        build();
        imgEl.src = src;
        captionEl.textContent = caption || '';
        overlay.classList.add('is-open');
        document.body.style.overflow = 'hidden';
    }

    function close() {
        if (!overlay) return;
        overlay.classList.remove('is-open');
        document.body.style.overflow = '';
        setTimeout(() => {
            if (imgEl) imgEl.src = '';
        }, 250);
    }

    window.anterOpenImage = open;

    // التقاط الضغط على أي صورة تحمل class js-lightbox أو post-image
    document.addEventListener('click', (e) => {
        const img = e.target.closest('img.js-lightbox, .post-image, .anter-post-image');
        if (!img) return;
        // لا نُفعّل العارض على الأيقونات الصغيرة/الأفاتار (لها معالج مختلف)
        if (img.classList.contains('post-avatar') || img.closest('.anter-avatar') || img.classList.contains('story-avatar')) return;
        e.preventDefault();
        e.stopPropagation();
        const caption = img.alt || '';
        const src = img.dataset.fullsrc || img.src;
        open(src, caption);
    }, true);
})();

/* ============================================================
   ANTER Image Menu — قائمة خيارات الصورة
   ============================================================ */
(function _anterImageMenu() {

    // توست بسيط
    function toast(message, kind) {
        let box = document.getElementById('anterImgToast');
        if (!box) {
            box = document.createElement('div');
            box.id = 'anterImgToast';
            box.className = 'anter-img-toast';
            document.body.appendChild(box);
        }
        box.textContent = message;
        box.className = 'anter-img-toast is-visible ' + (kind || '');
        clearTimeout(box._timer);
        box._timer = setTimeout(() => box.classList.remove('is-visible'), 2400);
    }

    function closeAll() {
        document.querySelectorAll('.anter-img-menu').forEach(m => m.hidden = true);
        document.querySelectorAll('[data-img-menu-toggle]').forEach(b => b.setAttribute('aria-expanded', 'false'));
    }

    // فتح/إغلاق القائمة
    document.addEventListener('click', (e) => {
        const toggle = e.target.closest('[data-img-menu-toggle]');
        if (toggle) {
            e.preventDefault();
            e.stopPropagation();
            const wrapper = toggle.closest('.post-image-wrapper');
            const menu = wrapper?.querySelector('.anter-img-menu');
            if (!menu) return;
            const willOpen = menu.hidden;
            closeAll();
            if (willOpen) {
                menu.hidden = false;
                toggle.setAttribute('aria-expanded', 'true');
            }
            return;
        }

        // إغلاق عند النقر خارج القائمة
        if (!e.target.closest('.anter-img-menu') && !e.target.closest('[data-img-menu-toggle]')) {
            closeAll();
        }
    }, true);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeAll();
    });

    // تنفيذ الأفعال
    document.addEventListener('click', async (e) => {
        const item = e.target.closest('[data-img-action]');
        if (!item) return;
        e.preventDefault();
        e.stopPropagation();

        const wrapper = item.closest('.post-image-wrapper');
        const img = wrapper?.querySelector('img.js-lightbox, img.post-image');
        if (!img) return;

        const action = item.dataset.imgAction;
        const src = img.dataset.fullsrc || img.src;

        closeAll();

        if (action === 'download') {
            try {
                const resp = await fetch(src, { credentials: 'same-origin' });
                const blob = await resp.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'anter-' + Date.now() + '.jpg';
                document.body.appendChild(a);
                a.click();
                a.remove();
                setTimeout(() => URL.revokeObjectURL(url), 3000);
                toast('تم تنزيل الصورة', 'success');
            } catch (_) {
                // fallback
                const a = document.createElement('a');
                a.href = src;
                a.download = 'anter-image.jpg';
                a.target = '_blank';
                document.body.appendChild(a);
                a.click();
                a.remove();
            }
            return;
        }

        if (action === 'copy') {
            const postCard = img.closest('.post-card');
            const url = postCard?.dataset.postUrl || window.location.href;
            try {
                await navigator.clipboard.writeText(url);
                toast('تم نسخ الرابط', 'success');
            } catch (_) {
                const input = document.createElement('input');
                input.value = url;
                document.body.appendChild(input);
                input.select();
                document.execCommand('copy');
                input.remove();
                toast('تم نسخ الرابط', 'success');
            }
            return;
        }

        if (action === 'set-avatar') {
            const postId = wrapper?.dataset.postId;
            if (!postId) return;
            item.disabled = true;
            const label = item.querySelector('span');
            const oldText = label ? label.textContent : '';
            if (label) label.textContent = 'جارٍ التعيين…';
            try {
                const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
                const resp = await fetch('/users/set-avatar-from-post/' + encodeURIComponent(postId), {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrf,
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    credentials: 'same-origin'
                });
                const data = await resp.json().catch(() => ({}));
                if (!resp.ok || data.success === false) {
                    throw new Error(data.message || 'تعذر تعيين الصورة.');
                }
                toast(data.message || 'تم تعيين الصورة كصورة بروفايل', 'success');
                setTimeout(() => window.location.reload(), 900);
            } catch (err) {
                toast(err.message || 'تعذر تعيين الصورة', 'error');
                if (label) label.textContent = oldText;
            } finally {
                item.disabled = false;
            }
            return;
        }

        if (action === 'report') {
            const postId = item.dataset.post;
            if (!postId) return;
            if (!confirm('هل تريد الإبلاغ عن هذه الصورة؟')) return;
            try {
                const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
                const resp = await fetch('/report', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrf,
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({ post_id: postId, reason: 'inappropriate image' })
                });
                const data = await resp.json().catch(() => ({}));
                if (!resp.ok || data.success === false) {
                    throw new Error(data.message || 'تعذر إرسال البلاغ.');
                }
                toast('تم إرسال البلاغ', 'success');
            } catch (err) {
                toast(err.message || 'تعذر إرسال البلاغ', 'error');
            }
            return;
        }
    }, true);
})();
