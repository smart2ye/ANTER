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
                    <button class="story-close-btn" onclick="closeStoryModal()"><i class="fas fa-times"></i></button>
                </div>

                <div class="story-media-container" id="storyMediaContainer">
                    <!-- الوسائط هنا -->
                </div>

                <div class="story-caption-box" id="storyCaptionBox" style="display: none;"></div>

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

    // تسجيل المشاهدة
    fetch(`/api/stories/${story.id}/view`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
        }
    }).catch(() => {});

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
