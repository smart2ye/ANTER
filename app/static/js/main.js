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
                    const postHtml = createPostHtml(post);
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
    return `
        <div class="fb-post">
            <div class="card-body">
                <div class="d-flex align-items-center mb-1">
                    <a href="/users/${post.author.username}">
                        <img src="/static/uploads/${post.author.avatar}" class="post-avatar me-2" width="32" height="32" style="border-radius: 50%; object-fit: cover;">
                    </a>
                    <div>
                        <a href="/users/${post.author.username}" class="text-decoration-none">
                            <strong class="post-author-name" style="font-size: 0.9rem;">
                                ${post.author.name}
                                ${post.author.is_verified ? '<i class="fas fa-check-circle text-primary" style="font-size: 0.6rem;" title="حساب موثق"></i>' : ''}
                            </strong>
                        </a>
                        <small class="post-username d-block" style="font-size: 0.65rem;">@${post.author.username}</small>
                    </div>
                    <small class="text-muted ms-auto" style="font-size: 0.6rem;">${post.created_at}</small>
                </div>
                <p class="post-content" style="font-size: 0.9rem;">${post.content}</p>
                ${post.image ? `<img src="/static/uploads/${post.image}" class="post-image" style="max-height: 200px; width: 100%; object-fit: cover; border-radius: 8px;">` : ''}
                <div class="post-actions mt-1 pt-1">
                    <div class="d-flex gap-2">
                        <button class="btn btn-sm btn-outline-primary like-btn py-0 px-2" style="font-size: 0.7rem;" data-post="${post.id}">
                            <i class="fas fa-thumbs-up"></i> <span class="like-count">${post.like_count}</span>
                        </button>
                        <button class="btn btn-sm btn-outline-secondary toggle-comments-btn py-0 px-2" style="font-size: 0.7rem;" data-post="${post.id}">
                            <i class="fas fa-comment"></i> (${post.comment_count})
                        </button>
                        <div class="dropdown d-inline-block">
                            <button class="btn btn-sm btn-outline-secondary dropdown-toggle py-0 px-2" style="font-size: 0.7rem;" type="button" data-bs-toggle="dropdown">
                                <i class="fas fa-share"></i>
                            </button>
                            <ul class="dropdown-menu">
                                <li><a class="dropdown-item small" href="#" onclick="copyLink('${post_url}')"><i class="fas fa-copy"></i> نسخ الرابط</a></li>
                                <li><a class="dropdown-item small" href="https://wa.me/?text=${post_url}" target="_blank"><i class="fab fa-whatsapp"></i> واتساب</a></li>
                                <li><a class="dropdown-item small" href="https://twitter.com/intent/tweet?url=${post_url}" target="_blank"><i class="fab fa-twitter"></i> تويتر</a></li>
                                <li><a class="dropdown-item small" href="https://www.facebook.com/sharer/sharer.php?u=${post_url}" target="_blank"><i class="fab fa-facebook"></i> فيسبوك</a></li>
                            </ul>
                        </div>
                        <a href="/posts/post/${post.id}" class="btn btn-sm btn-outline-info py-0 px-2" style="font-size: 0.7rem;">
                            <i class="fas fa-external-link-alt"></i>
                        </a>
                        <button class="btn btn-sm btn-outline-danger report-btn py-0 px-2" style="font-size: 0.7rem;" data-post="${post.id}" data-bs-toggle="modal" data-bs-target="#reportModal">
                            <i class="fas fa-flag"></i>
                        </button>
                    </div>
                    ${post.is_author ? `
                        <div class="d-flex gap-1">
                            <a href="/posts/edit/${post.id}" class="btn btn-sm btn-warning py-0 px-2" style="font-size: 0.7rem;"><i class="fas fa-edit"></i></a>
                            <button class="btn btn-sm btn-danger delete-post py-0 px-2" style="font-size: 0.7rem;" data-post="${post.id}"><i class="fas fa-trash"></i></button>
                        </div>
                    ` : ''}
                </div>
                <div id="comments-${post.id}" class="mt-2 comment-section" style="display: none;"></div>
            </div>
        </div>
    `;
}

// اكتشاف التمرير للأسفل
window.addEventListener('scroll', function() {
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 200) {
        loadMorePosts();
    }
});

// ==============================
// تأثير الإعجاب
// ==============================
document.addEventListener('click', function(e) {
    if (e.target.closest('.like-btn')) {
        const btn = e.target.closest('.like-btn');
        const postId = btn.dataset.post;
        fetch(`/posts/like/${postId}`, { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                btn.querySelector('.like-count').textContent = data.count;
                btn.classList.toggle('btn-primary');
                btn.classList.toggle('btn-outline-primary');
                btn.classList.toggle('liked');
            });
    }
});

// ==============================
// تبديل التعليقات
// ==============================
document.addEventListener('click', function(e) {
    if (e.target.closest('.toggle-comments-btn')) {
        const btn = e.target.closest('.toggle-comments-btn');
        const postId = btn.dataset.post;
        const commentsDiv = document.getElementById('comments-' + postId);
        if (commentsDiv) {
            if (commentsDiv.style.display === 'none' || commentsDiv.style.display === '') {
                commentsDiv.style.display = 'block';
                // تحميل التعليقات إذا كانت فارغة
                if (commentsDiv.innerHTML.trim() === '') {
                    fetch(`/posts/post/${postId}`)
                        .then(res => res.text())
                        .then(html => {
                            const temp = document.createElement('div');
                            temp.innerHTML = html;
                            const comments = temp.querySelector('.comment-section');
                            if (comments) {
                                commentsDiv.innerHTML = comments.innerHTML;
                            }
                        });
                }
                btn.innerHTML = '<i class="fas fa-comment"></i> إخفاء التعليقات';
            } else {
                commentsDiv.style.display = 'none';
                const count = commentsDiv.querySelectorAll('.comment-item').length;
                btn.innerHTML = `<i class="fas fa-comment"></i> (${count})`;
            }
        }
    }
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
// معالجة التفاعلات المتعددة
// ==============================
document.addEventListener('click', function(e) {
    if (e.target.closest('.reaction-option')) {
        e.preventDefault();
        const option = e.target.closest('.reaction-option');
        const postId = option.dataset.post;
        const reaction = option.dataset.reaction;
        
        fetch(`/posts/react/${postId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ reaction: reaction })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                // تحديث أيقونة التفاعل
                const reactionIcon = document.getElementById(`reaction-icon-${postId}`);
                const reactionCount = document.getElementById(`reaction-count-${postId}`);
                const summary = document.getElementById(`reaction-summary-${postId}`);
                
                // تحديث الأيقونة
                const icons = {
                    'like': '👍',
                    'love': '🥰',
                    'haha': '🤣',
                    'angry': '😡',
                    'sad': '😢'
                };
                
                if (data.action === 'removed') {
                    reactionIcon.textContent = '👍'; // أيقونة افتراضية
                } else {
                    reactionIcon.textContent = icons[data.reaction] || '👍';
                }
                
                // تحديث العدد الإجمالي
                const total = Object.values(data.counts).reduce((a, b) => a + b, 0);
                reactionCount.textContent = total;
                
                // تحديث ملخص التفاعلات
                if (summary) {
                    let html = '';
                    for (const [key, count] of Object.entries(data.counts)) {
                        if (count > 0) {
                            html += `<span>${icons[key] || '👍'} ${count}</span>`;
                        }
                    }
                    summary.innerHTML = html;
                }
                
                // تحديث لون الزر (إذا كان هناك تفاعل)
                const btn = option.closest('.dropdown').querySelector('.reaction-btn');
                if (data.action !== 'removed') {
                    btn.classList.add('btn-primary');
                    btn.classList.remove('btn-outline-secondary');
                } else {
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-outline-secondary');
                }
            }
        });
    }
});

// ==============================
// إخفاء المنشور
// ==============================
document.addEventListener('click', function(e) {
    if (e.target.closest('.hide-post-btn')) {
        const btn = e.target.closest('.hide-post-btn');
        const postId = btn.dataset.post;
        
        if (confirm('هل أنت متأكد من إخفاء هذا المنشور؟')) {
            fetch(`/posts/hide/${postId}`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    // إزالة المنشور من الواجهة
                    const postElement = document.getElementById(`post-${postId}`);
                    if (postElement) {
                        postElement.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                        postElement.style.opacity = '0';
                        postElement.style.transform = 'scale(0.9)';
                        setTimeout(() => {
                            postElement.remove();
                            // إعادة تحميل الصفحة إذا لم يتبق منشورات
                            const remainingPosts = document.querySelectorAll('.fb-post');
                            if (remainingPosts.length === 0) {
                                location.reload();
                            }
                        }, 350);
                    }
                } else {
                    alert('❌ ' + (data.message || 'حدث خطأ أثناء إخفاء المنشور'));
                }
            })
            .catch(() => {
                alert('❌ حدث خطأ غير متوقع');
            });
        }
    }
});

// ==============================
// تفعيل قائمة المشاركة
// ==============================
document.querySelectorAll('.share-dropdown').forEach(el => {
    el.addEventListener('mouseenter', function() {
        this.querySelector('.share-options').style.display = 'block';
    });
    el.addEventListener('mouseleave', function() {
        this.querySelector('.share-options').style.display = 'none';
    });
});

// ==============================
// تفعيل قائمة التفاعلات
// ==============================
document.querySelectorAll('.reaction-toggle').forEach(el => {
    el.addEventListener('mouseenter', function() {
        this.querySelector('.reaction-dropdown').style.display = 'flex';
    });
    el.addEventListener('mouseleave', function() {
        this.querySelector('.reaction-dropdown').style.display = 'none';
    });
});

// ==============================
// تفعيل التعليقات (toggle)
// ==============================
document.querySelectorAll('.comment-toggle').forEach(btn => {
    btn.addEventListener('click', function() {
        const postId = this.dataset.post;
        const section = document.getElementById('comments-' + postId);
        if (section) {
            section.classList.toggle('open');
        }
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
// معالجة اختيار التفاعل
// ==============================
document.addEventListener('click', function(e) {
    const option = e.target.closest('.reaction-option');
    if (!option) return;

    e.stopPropagation();
    const postId = option.dataset.post;
    const reaction = option.dataset.reaction;

    // أسماء التفاعلات
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

    fetch(`/posts/react/${postId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ reaction: reaction })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // تحديث الأيقونة والاسم
            const iconEl = document.getElementById(`reaction-icon-${postId}`);
            const labelEl = document.getElementById(`reaction-label-${postId}`);
            const countEl = document.getElementById(`reaction-count-${postId}`);
            const displayEl = document.getElementById(`reaction-display-${postId}`);
            const picker = document.getElementById(`reaction-picker-${postId}`);
            const summary = document.getElementById(`reaction-summary-${postId}`);

            if (data.action === 'removed') {
                iconEl.textContent = '👍';
                labelEl.textContent = 'إعجاب';
                if (displayEl) displayEl.parentElement.classList.remove('reaction-active');
            } else {
                iconEl.textContent = reactionIcons[data.reaction] || '👍';
                labelEl.textContent = reactionNames[data.reaction] || 'إعجاب';
                if (displayEl) displayEl.parentElement.classList.add('reaction-active');
            }

            // تحديث العدد الإجمالي
            const total = Object.values(data.counts).reduce((a, b) => a + b, 0);
            countEl.textContent = total;

            // تحديث ملخص التفاعلات
            if (summary) {
                let html = '';
                const icons = {
                    'like': '👍',
                    'love': '🥰',
                    'haha': '🤣',
                    'angry': '😡',
                    'sad': '😢'
                };
                for (const [key, count] of Object.entries(data.counts)) {
                    if (count > 0) {
                        html += `<span class="reaction-item">${icons[key]} ${count}</span>`;
                    }
                }
                summary.innerHTML = html;
            }

            // إغلاق القائمة بعد الاختيار
            if (picker) {
                picker.style.display = 'none';
                setTimeout(() => { picker.style.display = ''; }, 100);
            }

            // تأثير صوتي أو بصري
            const icon = document.getElementById(`reaction-icon-${postId}`);
            if (icon) {
                icon.style.animation = 'none';
                setTimeout(() => {
                    icon.style.animation = 'reactionPop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)';
                }, 10);
            }
        }
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
// نظام الأصوات (Web Audio)
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
        } catch (e) {
            // تجاهل الأخطاء
        }
    }

    // صوت الإشعار (نغمة مزدوجة)
    notification() {
        this._playTone(800, 0.15, 'sine', 0.3);
        setTimeout(() => this._playTone(1000, 0.15, 'sine', 0.25), 150);
    }

    // صوت الإعجاب (نغمة قصيرة)
    like() {
        this._playTone(1200, 0.1, 'sine', 0.2);
    }

    // صوت النشر (نغمة تصاعدية)
    publish() {
        this._playTone(600, 0.1, 'sine', 0.2);
        setTimeout(() => this._playTone(800, 0.1, 'sine', 0.2), 100);
        setTimeout(() => this._playTone(1000, 0.15, 'sine', 0.25), 200);
    }

    // صوت المتابعة
    follow() {
        this._playTone(700, 0.12, 'sine', 0.2);
        setTimeout(() => this._playTone(900, 0.12, 'sine', 0.2), 120);
    }

    toggle() {
        this.enabled = !this.enabled;
        localStorage.setItem('soundEnabled', this.enabled);
        return this.enabled;
    }
}

const sounds = new SoundManager();

// ==============================
// ربط الأصوات بالأحداث
// ==============================

// عند الإعجاب
document.addEventListener('click', function(e) {
    if (e.target.closest('.like-btn, .reaction-option')) {
        sounds.like();
    }
});

// عند النشر (مراقبة نجاح النشر)
document.addEventListener('DOMContentLoaded', function() {
    const quickForm = document.getElementById('quickPostForm');
    if (quickForm) {
        const originalSubmit = quickForm.submit;
        quickForm.addEventListener('submit', function() {
            setTimeout(() => sounds.publish(), 300);
        });
    }
});

// عند متابعة
document.addEventListener('click', function(e) {
    if (e.target.closest('.follow-btn')) {
        setTimeout(() => sounds.follow(), 300);
    }
});

// عند وصول إشعار (SSE)
if (typeof EventSource !== 'undefined') {
    const eventSource = new EventSource('/sse/notifications');
    eventSource.onmessage = function(e) {
        try {
            const data = JSON.parse(e.data);
            if (data.count > 0) {
                sounds.notification();
            }
        } catch (err) {}
    };
}

// تبديل الصوت (زر مخفي في الإعدادات)
// يمكن إضافة زر في settings.html

// ============================================
// نظام الأصوات (Sound Effects)
// ============================================
const SoundManager = {
    sounds: {},
    isMuted: localStorage.getItem('sound_muted') === 'true',

    init() {
        // تحميل الأصوات
        this.sounds = {
            notification: new Audio('/static/sounds/notification.mp3'),
            like: new Audio('/static/sounds/like.mp3'),
            comment: new Audio('/static/sounds/comment.mp3'),
            post: new Audio('/static/sounds/post.mp3')
        };

        // زر التحكم بالصوت
        this.createToggleButton();
    },

    createToggleButton() {
        const btn = document.createElement('button');
        btn.className = 'sound-toggle';
        btn.innerHTML = this.isMuted ? '<i class="fas fa-volume-mute"></i>' : '<i class="fas fa-volume-up"></i>';
        btn.title = 'تشغيل/إيقاف الأصوات';
        document.body.appendChild(btn);

        btn.addEventListener('click', () => {
            this.isMuted = !this.isMuted;
            localStorage.setItem('sound_muted', this.isMuted);
            btn.innerHTML = this.isMuted ? '<i class="fas fa-volume-mute"></i>' : '<i class="fas fa-volume-up"></i>';
            if (!this.isMuted) {
                this.play('notification'); // اختبار الصوت
            }
        });
    },

    play(soundName) {
        if (this.isMuted) return;
        const sound = this.sounds[soundName];
        if (sound) {
            sound.currentTime = 0;
            sound.play().catch(() => {});
        }
    }
};

// ==============================
// تشغيل الأصوات عند الأحداث
// ==============================
document.addEventListener('DOMContentLoaded', () => {
    SoundManager.init();

    // صوت عند الإعجاب
    document.addEventListener('click', function(e) {
        if (e.target.closest('.reaction-option') || e.target.closest('.like-btn')) {
            SoundManager.play('like');
        }
    });

    // صوت عند التعليق
    document.addEventListener('submit', function(e) {
        if (e.target.closest('.comment-form')) {
            setTimeout(() => SoundManager.play('comment'), 200);
        }
    });

    // صوت عند النشر
    document.addEventListener('submit', function(e) {
        if (e.target.closest('#quickPostForm') || e.target.closest('form[action*="/posts/create"]')) {
            setTimeout(() => SoundManager.play('post'), 300);
        }
    });
});

// ==============================
// استقبال الإشعارات عبر SSE
// ==============================
if (document.getElementById('notif-badge')) {
    const eventSource = new EventSource('/sse/notifications');
    eventSource.onmessage = function(e) {
        try {
            const data = JSON.parse(e.data);
            const badge = document.getElementById('notif-badge');
            if (badge) {
                badge.textContent = data.count;
                badge.style.display = data.count > 0 ? 'block' : 'none';
            }
            // تشغيل صوت الإشعار
            if (data.count > 0) {
                SoundManager.play('notification');
            }
        } catch(err) {}
    };
    eventSource.onerror = function() {
        setTimeout(() => {
            const newSource = new EventSource('/sse/notifications');
            eventSource.close();
        }, 5000);
    };
}
