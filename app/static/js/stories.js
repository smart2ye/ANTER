document.addEventListener('DOMContentLoaded', function() {
    loadStoriesFeed();
});

let currentUsersStories = [];
let currentUserIndex = 0;
let currentStoryIndex = 0;
let storyTimer = null;
let progressTimer = null;
const STORY_DURATION = 5000; // 5 ثوانٍ لكل قصة

function loadStoriesFeed() {
    const container = document.getElementById('storiesFeedContainer');
    if (!container) return;

    fetch('/api/stories/feed')
        .then(res => res.json())
        .then(users => {
            renderStoriesBar(users);
        })
        .catch(err => console.error('Error loading stories:', err));
}

function renderStoriesBar(users) {
    const container = document.getElementById('storiesFeedContainer');
    if (!container) return;

    let html = `
        <div class="stories-container-wrapper">
            <div class="stories-scroll">
                <!-- إضافة قصة جديدة -->
                <div class="story-item" onclick="openCreateStoryModal()">
                    <div class="story-ring add-story">
                        <div class="story-avatar d-flex align-items-center justify-content:center bg-light text-primary fs-4 fw-bold">
                            <i class="fas fa-plus"></i>
                        </div>
                    </div>
                    <span class="story-username">قصتك</span>
                </div>
    `;

    users.forEach((userObj, uIdx) => {
        const ringClass = userObj.all_viewed ? 'viewed' : 'unviewed';
        html += `
            <div class="story-item" onclick="openUserStories(${uIdx})">
                <div class="story-ring ${ringClass}">
                    <img src="${userObj.avatar}" class="story-avatar" alt="${userObj.username}">
                </div>
                <span class="story-username">${userObj.name}</span>
            </div>
        `;
    });

    html += `
            </div>
        </div>
        
        <!-- نافذة عرض القصص -->
        <div id="storyModalOverlay" class="story-modal-overlay" onclick="handleOverlayClick(event)">
            <div class="story-modal-box">
                <div class="story-progress-container" id="storyProgressBars"></div>
                
                <div class="story-header-info">
                    <div class="story-user-meta">
                        <img id="modalUserAvatar" src="" alt="">
                        <div class="name-time">
                            <span class="username" id="modalUsername"></span>
                            <span class="time" id="modalStoryTime"></span>
                        </div>
                    </div>
                    <div class="story-header-actions">
                        <button class="story-viewers-btn" id="storyViewersToggle" onclick="toggleStoryViewers(event)" style="display: none;" title="من شاهد قصتك">
                            <i class="fas fa-eye"></i>
                            <span id="storyViewsCount">0</span>
                        </button>
                        <button class="story-close-btn" onclick="closeStoryModal()"><i class="fas fa-times"></i></button>
                    </div>
                </div>

                <div class="story-media-container" id="storyMediaContainer">
                    <!-- الوسائط هنا -->
                </div>

                <div class="story-caption-box" id="storyCaptionBox" style="display: none;"></div>

                <div class="story-reaction-bar" id="storyReactionBar">
                    <div class="story-reaction-summary" id="storyReactionSummary"></div>
                    <div class="story-reaction-buttons" role="group" aria-label="التفاعل مع القصة">
                        <button type="button" class="story-reaction-btn" data-reaction="like" onclick="sendStoryReaction('like', event)" title="إعجاب">👍</button>
                        <button type="button" class="story-reaction-btn" data-reaction="love" onclick="sendStoryReaction('love', event)" title="حب">❤️</button>
                        <button type="button" class="story-reaction-btn" data-reaction="haha" onclick="sendStoryReaction('haha', event)" title="مضحك">😂</button>
                        <button type="button" class="story-reaction-btn" data-reaction="wow" onclick="sendStoryReaction('wow', event)" title="مندهش">😮</button>
                        <button type="button" class="story-reaction-btn" data-reaction="fire" onclick="sendStoryReaction('fire', event)" title="رائع">🔥</button>
                    </div>
                </div>

                <div class="story-viewers-panel" id="storyViewersPanel" style="display: none;">
                    <div class="story-viewers-panel-header">
                        <strong>مشاهدو القصة</strong>
                        <button type="button" onclick="toggleStoryViewers(event)" aria-label="إغلاق قائمة المشاهدين"><i class="fas fa-times"></i></button>
                    </div>
                    <div id="storyViewersList" class="story-viewers-list"></div>
                </div>

                <button class="story-nav-btn story-prev-btn" onclick="prevStoryItem(event)"><i class="fas fa-chevron-right"></i></button>
                <button class="story-nav-btn story-next-btn" onclick="nextStoryItem(event)"><i class="fas fa-chevron-left"></i></button>
            </div>
        </div>

        <!-- ANTER: نافذة إضافة قصة (تصميم جديد) -->
        <div id="anterStoryComposer" class="anter-story-composer" aria-hidden="true">
            <div class="anter-story-composer__backdrop" data-close-story-composer></div>
            <div class="anter-story-composer__dialog" role="dialog" aria-modal="true">
                <header class="anter-story-composer__header">
                    <button type="button" class="anter-story-composer__close" data-close-story-composer aria-label="إغلاق">
                        <i class="fas fa-times"></i>
                    </button>
                    <h3>قصة جديدة</h3>
                    <span class="anter-story-composer__spacer"></span>
                </header>

                <div class="anter-story-composer__stage" id="storyStage">
                    <!-- منطقة السحب والإفلات (تظهر عند عدم اختيار ملف) -->
                    <label class="anter-story-dropzone" id="storyDropzone" for="storyMediaInput">
                        <div class="anter-story-dropzone__ring">
                            <i class="fas fa-image"></i>
                        </div>
                        <strong>أضف صورة</strong>
                        <small>اسحب الملف هنا أو اضغط للاختيار</small>
                        <span class="anter-story-dropzone__hint">JPG · PNG · WebP — حتى 5MB</span>
                    </label>

                    <!-- معاينة الملف (تظهر بعد الاختيار) -->
                    <div class="anter-story-preview" id="storyPreview" hidden>
                        <img id="storyPreviewImg" alt="معاينة القصة" hidden>
                        <video id="storyPreviewVideo" playsinline muted loop hidden></video>

                        <button type="button" class="anter-story-preview__remove" data-remove-media aria-label="إزالة الملف">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>

                    <input type="file" id="storyMediaInput" accept="image/*" hidden>

                    <!-- حقل التعليق يطفو فوق المعاينة -->
                    <div class="anter-story-caption-wrap" id="storyCaptionWrap">
                        <input type="text" id="storyCaptionInput" placeholder="أضف تعليقاً..." maxlength="200" autocomplete="off">
                        <span class="anter-story-caption-count" id="storyCaptionCount">0/200</span>
                    </div>
                </div>

                <footer class="anter-story-composer__footer">
                    <div class="anter-story-composer__progress" id="storyProgress" hidden>
                        <div class="anter-story-composer__progress-bar">
                            <div class="anter-story-composer__progress-fill" id="storyProgressFill"></div>
                        </div>
                        <span id="storyProgressLabel">جارٍ النشر…</span>
                    </div>
                    <button type="button" class="anter-story-composer__publish" id="storyPublishBtn" disabled>
                        <i class="fas fa-arrow-up"></i>
                        <span>نشر القصة</span>
                    </button>
                </footer>
            </div>
        </div>
    `;

    container.innerHTML = html;
    window._cachedUsersStories = users;
    if (typeof window._anterBindStoryComposer === 'function') window._anterBindStoryComposer();
}

/* ============================================================
   ANTER Story Composer — تصميم جديد
   ============================================================ */
let _anterStoryObjectUrl = null;

function _resetStoryComposer() {
    const composer = document.getElementById('anterStoryComposer');
    if (!composer) return;
    const fileInput = document.getElementById('storyMediaInput');
    const preview = document.getElementById('storyPreview');
    const previewImg = document.getElementById('storyPreviewImg');
    const previewVideo = document.getElementById('storyPreviewVideo');
    const dropzone = document.getElementById('storyDropzone');
    const caption = document.getElementById('storyCaptionInput');
    const counter = document.getElementById('storyCaptionCount');
    const publishBtn = document.getElementById('storyPublishBtn');
    const progress = document.getElementById('storyProgress');
    const progressFill = document.getElementById('storyProgressFill');
    const progressLabel = document.getElementById('storyProgressLabel');

    if (_anterStoryObjectUrl) {
        URL.revokeObjectURL(_anterStoryObjectUrl);
        _anterStoryObjectUrl = null;
    }
    if (fileInput) fileInput.value = '';
    if (previewImg) { previewImg.src = ''; previewImg.hidden = true; }
    if (previewVideo) { previewVideo.pause(); previewVideo.src = ''; previewVideo.hidden = true; }
    if (preview) preview.hidden = true;
    if (dropzone) dropzone.hidden = false;
    if (caption) caption.value = '';
    if (counter) counter.textContent = '0/200';
    if (publishBtn) { publishBtn.disabled = true; publishBtn.classList.remove('is-loading'); }
    if (progress) progress.hidden = true;
    if (progressFill) progressFill.style.width = '0%';
    if (progressLabel) progressLabel.textContent = 'جارٍ النشر…';
}

function openCreateStoryModal() {
    const composer = document.getElementById('anterStoryComposer');
    if (!composer) return;
    _resetStoryComposer();
    composer.classList.add('is-open');
    composer.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
}

function _closeStoryComposer() {
    const composer = document.getElementById('anterStoryComposer');
    if (!composer) return;
    composer.classList.remove('is-open');
    composer.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    _resetStoryComposer();
}

function _handleStoryFile(file) {
    if (!file) return;
    const preview = document.getElementById('storyPreview');
    const previewImg = document.getElementById('storyPreviewImg');
    const previewVideo = document.getElementById('storyPreviewVideo');
    const dropzone = document.getElementById('storyDropzone');
    const publishBtn = document.getElementById('storyPublishBtn');

    if (_anterStoryObjectUrl) URL.revokeObjectURL(_anterStoryObjectUrl);
    _anterStoryObjectUrl = URL.createObjectURL(file);

    // ANTER: القصص صور فقط.
    if (file.type.startsWith('video/')) {
        alert('القصص تقبل الصور فقط حاليًا. الفيديو غير مدعوم.');
        return;
    }
    previewVideo.pause();
    previewVideo.hidden = true;
    previewImg.src = _anterStoryObjectUrl;
    previewImg.hidden = false;
    dropzone.hidden = true;
    preview.hidden = false;
    publishBtn.disabled = false;
}

function submitStory(e) {
    if (e) e.preventDefault();
    const fileInput = document.getElementById('storyMediaInput');
    const captionInput = document.getElementById('storyCaptionInput');
    const publishBtn = document.getElementById('storyPublishBtn');
    const progress = document.getElementById('storyProgress');
    const progressFill = document.getElementById('storyProgressFill');
    const progressLabel = document.getElementById('storyProgressLabel');

    if (!fileInput || !fileInput.files[0]) return;

    const formData = new FormData();
    formData.append('media', fileInput.files[0]);
    formData.append('caption', captionInput ? captionInput.value : '');

    if (publishBtn) { publishBtn.disabled = true; publishBtn.classList.add('is-loading'); }
    if (progress) progress.hidden = false;
    if (progressFill) progressFill.style.width = '8%';
    if (progressLabel) progressLabel.textContent = 'جارٍ الرفع…';

    // محاكاة تقدّم حقيقي عبر XHR (fetch لا يدعم progress)
    const xhr = new XMLHttpRequest();
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

    xhr.upload.onprogress = (event) => {
        if (!event.lengthComputable) return;
        const percent = Math.min(95, Math.round((event.loaded / event.total) * 100));
        if (progressFill) progressFill.style.width = percent + '%';
        if (progressLabel) progressLabel.textContent = 'جارٍ الرفع… ' + percent + '%';
    };

    xhr.onload = () => {
        if (progressFill) progressFill.style.width = '100%';
        let data = {};
        try { data = JSON.parse(xhr.responseText || '{}'); } catch (_) {}

        if (xhr.status === 201) {
            if (progressLabel) progressLabel.textContent = 'تم النشر ✓';
            setTimeout(() => {
                _closeStoryComposer();
                loadStoriesFeed();
            }, 500);
        } else {
            if (progress) progress.hidden = true;
            if (publishBtn) { publishBtn.disabled = false; publishBtn.classList.remove('is-loading'); }
            alert(data.error || 'حدث خطأ أثناء نشر القصة');
        }
    };

    xhr.onerror = () => {
        if (progress) progress.hidden = true;
        if (publishBtn) { publishBtn.disabled = false; publishBtn.classList.remove('is-loading'); }
        alert('تعذر الاتصال بالخادم.');
    };

    xhr.open('POST', '/api/stories');
    xhr.setRequestHeader('X-CSRFToken', csrfToken);
    xhr.send(formData);
}

/* ربط الأحداث (يُنفَّذ مرة واحدة عند أول تحميل) */
(function _setupStoryComposer() {
    const bind = () => {
        const fileInput = document.getElementById('storyMediaInput');
        const caption = document.getElementById('storyCaptionInput');
        const counter = document.getElementById('storyCaptionCount');
        const publishBtn = document.getElementById('storyPublishBtn');
        const dropzone = document.getElementById('storyDropzone');
        const stage = document.getElementById('storyStage');

        if (!fileInput || fileInput.dataset.bound === 'true') return;
        fileInput.dataset.bound = 'true';

        fileInput.addEventListener('change', (e) => {
            const file = e.target.files && e.target.files[0];
            if (file) _handleStoryFile(file);
        });

        if (publishBtn) {
            publishBtn.addEventListener('click', submitStory);
        }

        if (caption && counter) {
            caption.addEventListener('input', () => {
                counter.textContent = caption.value.length + '/200';
            });
        }

        // سحب وإفلات
        if (stage) {
            ['dragenter', 'dragover'].forEach(evt => {
                stage.addEventListener(evt, (e) => {
                    e.preventDefault();
                    stage.classList.add('is-dragover');
                });
            });
            ['dragleave', 'drop'].forEach(evt => {
                stage.addEventListener(evt, (e) => {
                    e.preventDefault();
                    stage.classList.remove('is-dragover');
                });
            });
            stage.addEventListener('drop', (e) => {
                const file = e.dataTransfer?.files?.[0];
                if (!file) return;
                if (!file.type.startsWith('image/')) {
                    alert('القصص تقبل الصور فقط حاليًا.');
                    return;
                }
                // استخدم DataTransfer لتحديد الملف في input
                const dt = new DataTransfer();
                dt.items.add(file);
                fileInput.files = dt.files;
                _handleStoryFile(file);
            });
        }

        // إزالة الملف
        document.querySelectorAll('[data-remove-media]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                _resetStoryComposer();
            });
        });

        // إغلاق
        document.querySelectorAll('[data-close-story-composer]').forEach(el => {
            el.addEventListener('click', (e) => {
                e.preventDefault();
                _closeStoryComposer();
            });
        });
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bind);
    } else {
        bind();
    }
    // أعِد الربط بعد كل render للشريط
    window._anterBindStoryComposer = bind;
})();

window._closeStoryComposer = _closeStoryComposer;

function openUserStories(uIdx) {
    currentUserIndex = uIdx;
    currentStoryIndex = 0;
    currentUsersStories = window._cachedUsersStories || [];
    
    if (!currentUsersStories[currentUserIndex] || !currentUsersStories[currentUserIndex].stories.length) return;

    document.getElementById('storyModalOverlay').style.display = 'flex';
    playCurrentStory();
}

function closeStoryModal() {
    clearTimeout(storyTimer);
    clearInterval(progressTimer);
    document.getElementById('storyModalOverlay').style.display = 'none';
    loadStoriesFeed(); // تحديث الحلقات عند الإغلاق
}

function handleOverlayClick(e) {
    if (e.target.id === 'storyModalOverlay') {
        closeStoryModal();
    }
}

function playCurrentStory() {
    clearTimeout(storyTimer);
    clearInterval(progressTimer);

    const userObj = currentUsersStories[currentUserIndex];
    if (!userObj) {
        closeStoryModal();
        return;
    }

    const story = userObj.stories[currentStoryIndex];
    if (!story) {
        closeStoryModal();
        return;
    }

    // تحديث الهيدر
    document.getElementById('modalUserAvatar').src = userObj.avatar;
    document.getElementById('modalUsername').textContent = userObj.name;
    document.getElementById('modalStoryTime').textContent = formatTimeAgo(story.created_at);

    // تحديث التسمية
    const captionBox = document.getElementById('storyCaptionBox');
    if (story.caption) {
        captionBox.textContent = story.caption;
        captionBox.style.display = 'block';
    } else {
        captionBox.style.display = 'none';
    }

    // تحديث أشرطة التقدم
    renderProgressBars(userObj.stories.length, currentStoryIndex);

    // ANTER: ابدأ المؤقّت فقط بعد تحميل الوسائط (كان يبدأ قبل التحميل → الصورة تُتخطى).
    const mediaContainer = document.getElementById('storyMediaContainer');
    const fillBar = document.getElementById('progressFill_' + currentStoryIndex);

    function startStoryTimer(durationMs) {
        clearInterval(progressTimer);
        clearTimeout(storyTimer);
        const dur = durationMs || STORY_DURATION;
        const startTime = Date.now();
        progressTimer = setInterval(function() {
            const elapsed = Date.now() - startTime;
            const pct = Math.min(100, (elapsed / dur) * 100);
            if (fillBar) fillBar.style.width = pct + '%';
        }, 50);
        storyTimer = setTimeout(function() {
            nextStoryItem();
        }, dur);
    }

    // عرض الوسائط
    mediaContainer.innerHTML = '';

    if (story.media_type === 'video') {
        const video = document.createElement('video');
        video.src = story.media_url;
        video.autoplay = true;
        video.playsInline = true;
        video.muted = false;
        mediaContainer.appendChild(video);

        // ابدأ المؤقّت عند بدء التشغيل الفعلي
        video.addEventListener('playing', function() {
            const dur = Math.max(STORY_DURATION, (video.duration || 5) * 1000);
            startStoryTimer(dur);
        }, { once: true });
        video.addEventListener('ended', nextStoryItem, { once: true });
        video.addEventListener('error', function() { startStoryTimer(); }, { once: true });

        // احتياطي: لو لم يبدأ خلال 4 ثوانٍ
        setTimeout(function() {
            if (!progressTimer) startStoryTimer();
        }, 4000);
    } else {
        const img = document.createElement('img');
        img.alt = 'Story';
        img.onload = function() { startStoryTimer(); };
        img.onerror = function() { startStoryTimer(); };
        img.src = story.media_url;
        mediaContainer.appendChild(img);

        // احتياطي: لو تأخر التحميل أكثر من 8 ثوانٍ
        setTimeout(function() {
            if (!progressTimer) startStoryTimer();
        }, 8000);
    }

    updateStoryInteractions(story);

    // تسجيل المشاهدة
    fetch('/api/stories/' + story.id + '/view', {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
        }
    })
    .then(function(res) { return res.json().then(function(data) { return {ok: res.ok, data: data}; }); })
    .then(function(result) {
        if (result.ok && result.data.story) {
            Object.assign(story, result.data.story);
        }
    })
    .catch(function() {});
}

function getCurrentStory() {
    const userObj = currentUsersStories[currentUserIndex];
    return userObj ? userObj.stories[currentStoryIndex] : null;
}

function escapeStoryHtml(value) {
    return String(value ?? '').replace(/[&<>\"']/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;', "'": '&#039;'
    }[char]));
}

const storyReactionEmojis = {
    like: '👍',
    love: '❤️',
    haha: '😂',
    wow: '😮',
    sad: '😢',
    fire: '🔥'
};

function updateStoryInteractions(story) {
    const viewersButton = document.getElementById('storyViewersToggle');
    const viewersCount = document.getElementById('storyViewsCount');
    const reactionSummary = document.getElementById('storyReactionSummary');
    const viewersPanel = document.getElementById('storyViewersPanel');

    if (!viewersButton || !viewersCount || !reactionSummary) return;

    const isOwner = Boolean(story.is_owner);
    viewersButton.style.display = isOwner ? 'inline-flex' : 'none';
    viewersCount.textContent = story.views_count || 0;
    if (!isOwner && viewersPanel) viewersPanel.style.display = 'none';

    const reactions = story.reactions || {};
    reactionSummary.innerHTML = Object.entries(reactions)
        .filter(([, count]) => count > 0)
        .map(([type, count]) => `<span>${storyReactionEmojis[type] || '✨'} ${count}</span>`)
        .join('');

    document.querySelectorAll('.story-reaction-btn').forEach(button => {
        button.classList.toggle('active', button.dataset.reaction === story.user_reaction);
    });

    renderStoryViewers(story.viewers || []);
}

function renderStoryViewers(viewers) {
    const list = document.getElementById('storyViewersList');
    if (!list) return;
    if (!viewers.length) {
        list.innerHTML = '<div class="story-no-viewers">لم يشاهد أحد قصتك بعد</div>';
        return;
    }
    list.innerHTML = viewers.map(viewer => `
        <div class="story-viewer-row">
            <img src="${escapeStoryHtml(viewer.avatar || '/static/uploads/default.png')}" alt="${escapeStoryHtml(viewer.name || viewer.username)}" loading="lazy">
            <div class="story-viewer-info">
                <strong>${escapeStoryHtml(viewer.name || viewer.username)}</strong>
                <small>@${escapeStoryHtml(viewer.username || '')} · ${escapeStoryHtml(viewer.viewed_at || '')}</small>
            </div>
        </div>
    `).join('');
}

function toggleStoryViewers(e) {
    if (e) e.stopPropagation();
    const panel = document.getElementById('storyViewersPanel');
    const button = document.getElementById('storyViewersToggle');
    if (!panel || !button || button.style.display === 'none') return;
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

function sendStoryReaction(reactionType, e) {
    if (e) e.stopPropagation();
    const story = getCurrentStory();
    if (!story) return;

    fetch(`/api/stories/${story.id}/react`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
        },
        body: JSON.stringify({reaction_type: reactionType})
    })
    .then(res => res.json().then(data => ({ok: res.ok, data})))
    .then(result => {
        if (!result.ok) throw new Error(result.data.error || 'تعذر إرسال التفاعل');
        if (result.data.story) {
            Object.assign(story, result.data.story);
        }
    })
    .catch(err => console.error('Story reaction error:', err));
}

function renderProgressBars(total, activeIdx) {
    const container = document.getElementById('storyProgressBars');
    let html = '';
    for (let i = 0; i < total; i++) {
        let width = i < activeIdx ? '100%' : (i === activeIdx ? '0%' : '0%');
        html += `
            <div class="story-progress-bar">
                <div class="story-progress-fill" id="progressFill_${i}" style="width: ${width};"></div>
            </div>
        `;
    }
    container.innerHTML = html;
}

function nextStoryItem(e) {
    if (e) e.stopPropagation();
    clearTimeout(storyTimer);
    clearInterval(progressTimer);

    const userObj = currentUsersStories[currentUserIndex];
    if (currentStoryIndex < userObj.stories.length - 1) {
        currentStoryIndex++;
        playCurrentStory();
    } else {
        // الانتقال للمستخدم التالي
        if (currentUserIndex < currentUsersStories.length - 1) {
            currentUserIndex++;
            currentStoryIndex = 0;
            playCurrentStory();
        } else {
            closeStoryModal();
        }
    }
}

function prevStoryItem(e) {
    if (e) e.stopPropagation();
    clearTimeout(storyTimer);
    clearInterval(progressTimer);

    if (currentStoryIndex > 0) {
        currentStoryIndex--;
        playCurrentStory();
    } else {
        if (currentUserIndex > 0) {
            currentUserIndex--;
            const prevUser = currentUsersStories[currentUserIndex];
            currentStoryIndex = prevUser.stories.length - 1;
            playCurrentStory();
        } else {
            closeStoryModal();
        }
    }
}

function formatTimeAgo(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    
    if (seconds < 0) return 'الآن';
    if (seconds < 60) return `منذ ${seconds}ث`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `منذ ${minutes}د`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `منذ ${hours}س`;
    return 'منذ يوم';
}
