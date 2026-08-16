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

        <!-- نافذة إضافة قصة -->
        <div id="createStoryModal" class="modal fade" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content rounded-4 border-0 shadow">
                    <div class="modal-header border-0 pb-0">
                        <h5 class="fw-bold">إضافة قصة جديدة</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="createStoryForm" onsubmit="submitStory(event)">
                            <div class="mb-3">
                                اختر صورة أو فيديو للقصة:
                                <input type="file" class="form-control mt-2" id="storyMediaInput" accept="image/*,video/*" required>
                            </div>
                            <div class="mb-3">
                                تعليق أو نص اختياري:
                                <input type="text" class="form-control mt-2" id="storyCaptionInput" placeholder="اكتب تعليقاً..." maxlength="200">
                            </div>
                            <button type="submit" class="btn btn-primary w-100 rounded-pill py-2 fw-bold">نشر القصة</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    `;

    container.innerHTML = html;
    window._cachedUsersStories = users;
}

function openCreateStoryModal() {
    const modal = new bootstrap.Modal(document.getElementById('createStoryModal'));
    modal.show();
}

function submitStory(e) {
    e.preventDefault();
    const fileInput = document.getElementById('storyMediaInput');
    const captionInput = document.getElementById('storyCaptionInput');

    if (!fileInput.files[0]) return;

    const formData = new FormData();
    formData.append('media', fileInput.files[0]);
    formData.append('caption', captionInput.value);

    const submitBtn = e.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = 'جاري النشر...';

    fetch('/api/stories', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
        }
    })
    .then(res => res.json().then(data => ({status: res.status, body: data})))
    .then(res => {
        if (res.status === 201) {
            bootstrap.Modal.getInstance(document.getElementById('createStoryModal')).hide();
            fileInput.value = '';
            captionInput.value = '';
            loadStoriesFeed();
        } else {
            alert(res.body.error || 'حدث خطأ أثناء نشر القصة');
        }
    })
    .finally(() => {
        submitBtn.disabled = false;
        submitBtn.textContent = 'نشر القصة';
    });
}

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

    // عرض الوسائط
    const mediaContainer = document.getElementById('storyMediaContainer');
    if (story.media_type === 'video') {
        mediaContainer.innerHTML = `<video src="${story.media_url}" autoplay playsinline onended="nextStoryItem()"></video>`;
    } else {
        mediaContainer.innerHTML = `<img src="${story.media_url}" alt="Story">`;
    }

    updateStoryInteractions(story);

    // تسجيل المشاهدة وتحديث العدد بعد نجاح الطلب
    fetch(`/api/stories/${story.id}/view`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
        }
    })
    .then(res => res.json().then(data => ({ok: res.ok, data})))
    .then(result => {
        if (result.ok && result.data.story) {
            Object.assign(story, result.data.story);
            updateStoryInteractions(story);
        }
    })
    .catch(() => {});

    // تشغيل العداد التلقائي
    let startTime = Date.now();
    const fillBar = document.getElementById(`progressFill_${currentStoryIndex}`);
    
    progressTimer = setInterval(() => {
        let elapsed = Date.now() - startTime;
        let pct = Math.min(100, (elapsed / STORY_DURATION) * 100);
        if (fillBar) fillBar.style.width = pct + '%';
    }, 50);

    storyTimer = setTimeout(() => {
        nextStoryItem();
    }, STORY_DURATION);
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
            updateStoryInteractions(story);
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
