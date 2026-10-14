/**
 * AI Shorts Generator - Frontend Application
 * Complete client-side logic for video upload, AI rewriting, and Short generation
 */

// Configuration
const API_BASE = window.location.origin;

// State
const state = {
    selectedFile: null,
    bgFile: null,
    logoFile: null,
    currentHook: null,
    currentNiche: null,
    currentHashtags: null,
    seo: null,
    videoFitMode: 'fit',
    isGenerating: false,
    crop: null,
};

// DOM Elements
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);

// ==========================================
// Session guard
// ==========================================
// If any API call returns 401 (session expired or invalid), send the user to the
// login screen. Wrapping window.fetch once means every call site is covered.
(function () {
    const originalFetch = window.fetch.bind(window);
    window.fetch = async (...args) => {
        const res = await originalFetch(...args);
        const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url) || '';
        if (res.status === 401 && !url.includes('/api/login')) {
            window.location.href = '/login';
        }
        return res;
    };
})();

// ==========================================
// Navigation
// ==========================================
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const targetId = link.getAttribute('href').slice(1);
        
        // Update nav
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');
        
        // Show section
        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
        document.getElementById(targetId).classList.add('active');
        
        // Load section data
        if (targetId === 'history') loadHistory();
        if (targetId === 'niches') loadNiches();
    });
});

// ==========================================
// Status Check
// ==========================================
async function checkStatus() {
    const dot = $('#statusDot');
    const text = $('#statusText');
    
    dot.className = 'status-dot checking';
    text.textContent = 'Checking...';
    
    try {
        const res = await fetch(`${API_BASE}/api/status`);
        if (res.status === 401) { window.location.href = '/login'; return; }
        const data = await res.json();
        
        if (data.status === 'running') {
            dot.className = 'status-dot online';
            const parts = [];
            if (data.ffmpeg) parts.push('🎬');
            if (data.ollama) parts.push('🤖');
            if (data.whisper) parts.push('💬');
            if (data.downloader) parts.push('⬇️');
            text.textContent = parts.length ? `Ready ${parts.join(' ')}` : 'Limited';

            // Paste-a-link needs yt-dlp on the server
            isDownloaderReady = data.downloader !== false;
            fetchUrlBtn.disabled = !isDownloaderReady || isFetchingUrl;
            fetchUrlBtn.title = isDownloaderReady
                ? 'Download this video so you can crop it'
                : 'yt-dlp is not installed on the server — run: pip install yt-dlp';
        } else {
            dot.className = 'status-dot offline';
            text.textContent = 'Offline';
        }
    } catch {
        dot.className = 'status-dot offline';
        text.textContent = 'Disconnected';
    }
}

// Check immediately and every 30s
checkStatus();
setInterval(checkStatus, 30000);


// ==========================================
// Video Upload
// ==========================================
let isDownloaderReady = true;

const uploadZone = $('#uploadZone');
const videoInput = $('#videoInput');
const uploadPlaceholder = $('#uploadPlaceholder');
const uploadPreview = $('#uploadPreview');
const previewVideo = $('#previewVideo');
const fileName = $('#fileName');
const removeVideoBtn = $('#removeVideo');

// Click to upload
uploadZone.addEventListener('click', () => videoInput.click());

// Drag and drop
uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('video/')) {
        handleVideoFile(file);
    } else {
        showToast('Please upload a video file', 'error');
    }
});

videoInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) handleVideoFile(file);
});

function handleVideoFile(file, displayName) {
    state.selectedFile = file;
    
    // A newly loaded video invalidates any crop made on the previous one
    state.crop = null;
    cropToggleBtn.textContent = '✂️ Crop Video';
    cropToggleBtn.classList.remove('has-crop');
    
    // Show preview
    uploadPlaceholder.style.display = 'none';
    uploadPreview.style.display = 'block';
    uploadZone.classList.add('has-video');
    
    previewVideo.src = URL.createObjectURL(file);
    
    // Show file size (displayName lets URL downloads show the real video title)
    const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
    fileName.innerHTML = `${displayName || file.name} <span class="file-size-badge">${sizeMB} MB</span>`;
    
    // Enable generate button and crop button
    updateGenerateButton();
    updateCropButton();
    
    // Auto-ask: open crop modal after a short delay so video preview renders
    setTimeout(() => openCropModal(), 300);
}

// ==========================================
// Paste a video link (YouTube / Shorts / Instagram / TikTok)
// ==========================================
const videoUrlInput = $('#videoUrlInput');
const fetchUrlBtn = $('#fetchUrlBtn');
const fetchUrlLabel = $('#fetchUrlLabel');
const fetchUrlLoader = $('#fetchUrlLoader');
const fetchUrlLoaderText = $('#fetchUrlLoaderText');
const urlClearBtn = $('#urlClearBtn');

// Backend caps downloads at 1080p (best quality for a 1080x1920 Short)
const MAX_DOWNLOAD_HEIGHT = 1080;

let isFetchingUrl = false;

function setFetchLoading(loading, text) {
    isFetchingUrl = loading;
    fetchUrlBtn.disabled = loading || !isDownloaderReady;
    fetchUrlLabel.style.display = loading ? 'none' : 'inline';
    fetchUrlLoader.style.display = loading ? 'inline-flex' : 'none';
    if (text) fetchUrlLoaderText.textContent = text;
    videoUrlInput.disabled = loading;
}

// Turn a title into a safe filename, e.g. "How to code 🔥 | Ep. 2" -> "How to code Ep. 2.mp4"
function toSafeFileName(title, ext) {
    const clean = (title || '')
        .replace(/[^\w\- ]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 60);
    return clean ? `${clean}.${ext}` : null;
}

async function fetchVideoFromUrl() {
    if (isFetchingUrl) return;
    
    const url = videoUrlInput.value.trim();
    if (!url) {
        showToast('Paste a video link first', 'error');
        videoUrlInput.focus();
        return;
    }
    if (!/^https?:\/\//i.test(url)) {
        showToast('Link must start with http:// or https://', 'error');
        return;
    }
    
    setFetchLoading(true, 'Downloading...');
    
    try {
        const formData = new FormData();
        formData.append('url', url);
        formData.append('max_height', String(MAX_DOWNLOAD_HEIGHT));
        
        const res = await fetch(`${API_BASE}/api/fetch-url`, {
            method: 'POST',
            body: formData,
        });
        
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || 'Download failed');
        
        // Pull the downloaded file into the browser as a File object so the preview,
        // crop modal and generate pipeline behave exactly like a normal upload.
        setFetchLoading(true, 'Loading video...');
        const fileRes = await fetch(`${API_BASE}${data.preview_url}`);
        if (!fileRes.ok) throw new Error('Could not load the downloaded video');
        
        const blob = await fileRes.blob();
        const ext = ((data.filename || '').split('.').pop() || 'mp4').toLowerCase();
        const name = toSafeFileName(data.title, ext) || data.filename || 'video.mp4';
        const file = new File([blob], name, { type: blob.type || 'video/mp4' });
        
        handleVideoFile(file, data.title ? `🔗 ${data.title}` : null);
        videoUrlInput.value = '';
        urlClearBtn.style.display = 'none';
        
        const secs = data.duration ? ` • ${Math.round(data.duration)}s` : '';
        showToast(`⬇️ Video downloaded${secs} — crop it below ✂️`, 'success');
    } catch (err) {
        showToast(`❌ ${err.message}`, 'error');
        console.error(err);
    } finally {
        setFetchLoading(false);
    }
}

fetchUrlBtn.addEventListener('click', fetchVideoFromUrl);

// Enter fetches the link instead of submitting the form
videoUrlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        fetchVideoFromUrl();
    }
});

videoUrlInput.addEventListener('input', () => {
    urlClearBtn.style.display = videoUrlInput.value ? 'inline-flex' : 'none';
});

urlClearBtn.addEventListener('click', () => {
    videoUrlInput.value = '';
    urlClearBtn.style.display = 'none';
    videoUrlInput.focus();
});

removeVideoBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    state.selectedFile = null;
    state.crop = null;
    cropState.active = false;
    videoInput.value = '';
    cropToggleBtn.textContent = '✂️ Crop Video';
    cropToggleBtn.classList.remove('has-crop');
    
    uploadPlaceholder.style.display = 'block';
    uploadPreview.style.display = 'none';
    uploadZone.classList.remove('has-video');    previewVideo.src = '';
    updateGenerateButton();
});

// ==========================================
// Video Cropper
// ==========================================
const cropToggleBtn = $('#cropToggleBtn');
const cropModal = $('#cropModal');
const cropVideo = $('#cropVideo');
const cropContainer = $('#cropContainer');
const cropBox = $('#cropBox');
const cropCoords = $('#cropCoords');
const cropApplyBtn = $('#cropApplyBtn');
const cropCancelBtn = $('#cropCancelBtn');

let cropState = {
    active: false,
    x: 0, y: 0, w: 0, h: 0,
    dragging: false,
    resizing: false,
    resizeDir: null,
    startX: 0, startY: 0,
    startBox: null,
};

// Enable crop toggle when video is uploaded
function updateCropButton() {
    cropToggleBtn.disabled = !state.selectedFile;
}

cropToggleBtn.addEventListener('click', () => {
    if (!state.selectedFile) return;
    openCropModal();
});

function openCropModal() {
    cropModal.style.display = 'block';
    cropVideo.src = URL.createObjectURL(state.selectedFile);
    
    // Wait for video metadata to load
    cropVideo.addEventListener('loadedmetadata', () => {
        // Use multiple rAFs to ensure CSS layout has fully settled
        let frames = 0;
        function waitForLayout() {
            requestAnimationFrame(() => {
                frames++;
                if (frames < 5) { waitForLayout(); return; }
                
                // Use actual rendered video dimensions
                const dispW = cropVideo.offsetWidth;
                const dispH = cropVideo.offsetHeight;
                
                if (dispW <= 0 || dispH <= 0) { waitForLayout(); return; }
                
                // Initial crop box: center 80% of video
                const margin = 0.1;
                cropState.w = Math.round(dispW * (1 - margin * 2));
                cropState.h = Math.round(dispH * (1 - margin * 2));
                cropState.x = Math.round((dispW - cropState.w) / 2);
                cropState.y = Math.round((dispH - cropState.h) / 2);
                cropState.active = true;
                
                updateCropBox();
            });
        }
        waitForLayout();
    }, { once: true });
}

function closeCropModal() {
    cropModal.style.display = 'none';
    cropVideo.src = '';
    cropState.active = false;
}

/**
 * Convert crop box display coordinates to cropping coordinates for FFmpeg.
 * 
 * Strategy: The backend uses `autorotate` filter to first rotate the video to
 * its display orientation, THEN applies the crop. So the coordinates must be
 * in the DISPLAY (correctly oriented) coordinate system, NOT the stored system.
 * 
 * For non-rotated videos: Simple uniform scale from CSS pixels to video pixels.
 * For rotated videos (portrait phone videos stored as landscape with metadata):
 *   - Scale from CSS pixels to full rotated resolution
 *   - The coordinates are in the display (portrait) space
 *   - Backend will autorotate first, then crop using these coordinates
 * 
 * @param {object} box - {x, y, w, h} in display CSS pixels
 * @param {number} dispW - video element displayed CSS width
 * @param {number} dispH - video element displayed CSS height
 * @param {number} vw - coded video width
 * @param {number} vh - coded video height
 * @returns {{ x, y, w, h, rotated }} crop coords (in display space) + rotation flag
 */
function computeCropCoords(box, dispW, dispH, vw, vh) {
    dispW = dispW || 1;
    dispH = dispH || 1;
    
    // Detect rotation: display aspect ≈ inverse of coded aspect means 90° rotation.
    // e.g., portrait display (0.56) vs landscape coded (0.56 inverse)
    const isRotated = Math.abs(dispW / dispH - vh / vw) < 0.1;
    
    let x, y, w, h;
    
    if (isRotated) {
        // Scale CSS display coordinates to full rotated resolution.
        // The rotated display dimensions are (vh, vw):
        //   width (visible) = vh (stored height becomes display width)
        //   height (visible) = vw (stored width becomes display height)
        const scaleW = vh / dispW;  // full rotated width / CSS display width
        const scaleH = vw / dispH;  // full rotated height / CSS display height
        
        x = Math.round(box.x * scaleW);
        y = Math.round(box.y * scaleH);
        w = Math.round(box.w * scaleW);
        h = Math.round(box.h * scaleH);
        
        // Clamp to the rotated video dimensions (vh wide, vw tall)
        x = Math.max(0, Math.min(x, vh - 2));
        y = Math.max(0, Math.min(y, vw - 2));
        w = Math.max(4, Math.min(w, vh - x));
        h = Math.max(4, Math.min(h, vw - y));
    } else {
        // Normal (non-rotated) video - uniform scale
        const scaleX = vw / dispW;
        const scaleY = vh / dispH;
        x = Math.round(box.x * scaleX);
        y = Math.round(box.y * scaleY);
        w = Math.round(box.w * scaleX);
        h = Math.round(box.h * scaleY);
        
        // Clamp to video dimensions
        x = Math.max(0, Math.min(x, vw - 2));
        y = Math.max(0, Math.min(y, vh - 2));
        w = Math.max(4, Math.min(w, vw - x));
        h = Math.max(4, Math.min(h, vh - y));
    }
    
    return { x, y, w, h, rotated: isRotated };
}

function updateCropBox() {
    if (!cropState.active) return;
    
    // Clamp crop box to video boundaries before applying
    const videoW = cropVideo.offsetWidth;
    const videoH = cropVideo.offsetHeight;
    
    // Ensure box doesn't go outside video
    cropState.x = Math.max(2, Math.min(cropState.x, videoW - cropState.w - 2));
    cropState.y = Math.max(2, Math.min(cropState.y, videoH - cropState.h - 2));
    
    // Position crop box (overlay covers video wrapper exactly, so coords are video-relative)
    cropBox.style.left = cropState.x + 'px';
    cropBox.style.top = cropState.y + 'px';
    cropBox.style.width = cropState.w + 'px';
    cropBox.style.height = cropState.h + 'px';
    
    // Convert display coords to actual video coords using shared helper
    const vw = cropVideo.videoWidth || 1;
    const vh = cropVideo.videoHeight || 1;
    const result = computeCropCoords(
        { x: cropState.x, y: cropState.y, w: cropState.w, h: cropState.h },
        videoW, videoH,
        vw, vh
    );
    
    cropCoords.textContent = `${result.w}×${result.h}  at (${result.x}, ${result.y})`;
    
    // 🐛 Update debug panel
    updateCropDebug({
        displayW: videoW, displayH: videoH,
        videoW: vw, videoH: vh,
        dispRatio: (videoW/videoH).toFixed(3),
        videoRatioSwapped: (vh/vw).toFixed(3),
        isRotated: result.rotated,
        cropBoxDisplay: `(${cropState.x}, ${cropState.y}) ${cropState.w}×${cropState.h}`,
        cropStored: `(${result.x}, ${result.y}) ${result.w}×${result.h}`,
    });
}

// 🐛 Debug panel updater
function updateCropDebug(info) {
    const el = $('#cropDebugContent');
    if (!el) return;
    el.innerHTML = `
📐 Display: ${info.displayW}×${info.displayH} (ratio: ${info.dispRatio})
🎬 Video:   ${info.videoW}×${info.videoH} (ratio: ${info.videoRatioSwapped} swapped)
🔄 Rotated: ${info.isRotated ? 'YES ✓' : 'NO'}
📦 Box(display): ${info.cropBoxDisplay}
✂️ Crop(stored): ${info.cropStored}
    `.trim().replace(/\n/g, '<br>');
}

// Mouse events for crop box
// Use video element dimensions for clamping since overlay now exactly covers the video
document.addEventListener('mousedown', (e) => {
    if (!cropState.active || !cropModal.style.display || cropModal.style.display === 'none') return;
    
    const handle = e.target.closest('.crop-handle');
    const box = e.target.closest('.crop-box');
    
    if (handle) {
        cropState.resizing = true;
        cropState.resizeDir = handle.className.split(' ').pop().replace('crop-handle-', '');
        cropState.startX = e.clientX;
        cropState.startY = e.clientY;
        cropState.startBox = { ...cropState };
        e.preventDefault();
    } else if (box && !e.target.closest('.crop-handle')) {
        cropState.dragging = true;
        cropState.startX = e.clientX;
        cropState.startY = e.clientY;
        cropState.startBox = { ...cropState };
        e.preventDefault();
    }
});

document.addEventListener('mousemove', (e) => {
    if (!cropState.active) return;
    
    // Use video element dimensions for clamping (not container, which includes border)
    const maxW = cropVideo.offsetWidth;
    const maxH = cropVideo.offsetHeight;
    const minSize = 40;
    
    if (cropState.dragging) {
        const dx = e.clientX - cropState.startX;
        const dy = e.clientY - cropState.startY;
        cropState.x = Math.max(2, Math.min(maxW - cropState.w - 2, cropState.startBox.x + dx));
        cropState.y = Math.max(2, Math.min(maxH - cropState.h - 2, cropState.startBox.y + dy));
        updateCropBox();
    } else if (cropState.resizing) {
        const dx = e.clientX - cropState.startX;
        const dy = e.clientY - cropState.startY;
        let { x, y, w, h } = cropState.startBox;
        const dir = cropState.resizeDir;
        
        if (dir.includes('e')) { w = Math.max(minSize, w + dx); }
        if (dir.includes('w')) { w = Math.max(minSize, w - dx); x = cropState.startBox.x + (cropState.startBox.w - w); }
        if (dir.includes('s')) { h = Math.max(minSize, h + dy); }
        if (dir.includes('n')) { h = Math.max(minSize, h - dy); y = cropState.startBox.y + (cropState.startBox.h - h); }
        
        // Clamp to video boundaries (overlay covers video exactly)
        if (x < 2) { x = 2; w = Math.max(minSize, cropState.startBox.w - (cropState.startBox.x - 2)); }
        if (y < 2) { y = 2; h = Math.max(minSize, cropState.startBox.h - (cropState.startBox.y - 2)); }
        if (x + w > maxW - 2) { w = maxW - x - 2; }
        if (y + h > maxH - 2) { h = maxH - y - 2; }
        
        cropState.x = x; cropState.y = y;
        cropState.w = Math.max(minSize, w); cropState.h = Math.max(minSize, h);
        updateCropBox();
    }
});

document.addEventListener('mouseup', () => {
    cropState.dragging = false;
    cropState.resizing = false;
});

cropApplyBtn.addEventListener('click', () => {
    if (!cropState.active || cropState.w < 20 || cropState.h < 20) {
        showToast('Please select a valid crop area', 'error');
        return;
    }
    
    // Convert display coords to actual video coords using shared helper
    const result = computeCropCoords(
        { x: cropState.x, y: cropState.y, w: cropState.w, h: cropState.h },
        cropVideo.offsetWidth, cropVideo.offsetHeight,
        cropVideo.videoWidth, cropVideo.videoHeight
    );
    
    state.crop = {
        x: result.x,
        y: result.y,
        w: result.w,
        h: result.h,
        rotated: result.rotated,
    };
    
    console.log(`[CROP] Applied: display=${cropState.w}×${cropState.h} at (${cropState.x}, ${cropState.y}) → stored=${result.w}×${result.h} at (${result.x}, ${result.y}) ${result.rotated ? '(rotated 90° ↻)' : ''}`);
    
    // 🚀 Auto-switch to 'cover' mode when crop is applied
    // This ensures the cropped area fills the entire video display area in the template
    setFitMode('cover');
    showToast('🔄 Auto-switched to Cover mode so cropped video fills the frame!', 'info');
    
    cropToggleBtn.textContent = `✂️ Crop: ${result.w}×${result.h}`;    cropToggleBtn.classList.add('has-crop');
    closeCropModal();
    showToast('✂️ Crop area applied!', 'success');
});

cropCancelBtn.addEventListener('click', () => {
    state.crop = null;
    cropToggleBtn.textContent = '✂️ Crop Video';    cropToggleBtn.classList.remove('has-crop');
    closeCropModal();
});

// ==========================================
// Video Fit Mode
// ==========================================
// Mode options:
// "fit"   = preserve aspect ratio, shrink to fit, pad with black bars (CSS contain)
// "cover" = preserve aspect ratio, zoom to fill, crop excess (CSS cover) ← BEST for portrait!

function setFitMode(mode) {
    state.videoFitMode = mode;
    document.querySelectorAll('.fit-mode-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.mode === mode);
    });
}

document.querySelectorAll('.fit-mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        setFitMode(btn.dataset.mode);
    });
});



// ==========================================
// Story Input
// ==========================================
const storyInput = $('#storyInput');
const charCount = $('#charCount');
const rewriteBtn = $('#rewriteBtn');

storyInput.addEventListener('input', () => {
    const len = storyInput.value.length;
    charCount.textContent = `${len}/500`;
    
    // Visual warning states
    charCount.className = '';
    if (len > 450) charCount.classList.add('danger');
    else if (len > 400) charCount.classList.add('warning');
    
    // Enable rewrite button if text is long enough
    rewriteBtn.disabled = len < 10;
    
    updateGenerateButton();
});

// ==========================================
// Background Upload (image or video)
// ==========================================
const bgUploadZone = $('#bgUploadZone');
const bgInput = $('#bgInput');
const bgPlaceholder = $('#bgPlaceholder');
const bgPreview = $('#bgPreview');
const bgPreviewImg = $('#bgPreviewImg');
const bgPreviewVideo = $('#bgPreviewVideo');
const bgFileName = $('#bgFileName');
const removeBgBtn = $('#removeBg');

bgUploadZone.addEventListener('click', () => bgInput.click());

bgInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        state.bgFile = file;
        bgPlaceholder.style.display = 'none';
        bgPreview.style.display = 'block';
        bgFileName.textContent = file.name;
        
        const url = URL.createObjectURL(file);
        if (file.type.startsWith('video/')) {
            bgPreviewImg.style.display = 'none';
            bgPreviewVideo.style.display = 'block';
            bgPreviewVideo.src = url;
            bgPreviewVideo.play();
        } else {
            bgPreviewVideo.style.display = 'none';
            bgPreviewImg.style.display = 'block';
            bgPreviewImg.src = url;
        }
    }
});

removeBgBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    state.bgFile = null;
    bgInput.value = '';
    bgPlaceholder.style.display = 'flex';
    bgPreview.style.display = 'none';
    bgPreviewImg.src = '';
    bgPreviewVideo.src = '';
});

// ==========================================
// Channel Logo Upload
// ==========================================
const logoUploadZone = $('#logoUploadZone');
const logoInput = $('#logoInput');
const logoPlaceholder = $('#logoPlaceholder');
const logoPreview = $('#logoPreview');
const logoPreviewImg = $('#logoPreviewImg');
const removeLogoBtn = $('#removeLogo');

logoUploadZone.addEventListener('click', () => logoInput.click());

logoInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file && file.type.startsWith('image/')) {
        state.logoFile = file;
        logoPlaceholder.style.display = 'none';
        logoPreview.style.display = 'flex';
        logoPreviewImg.src = URL.createObjectURL(file);
        updateGenerateButton();
    }
});

removeLogoBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    state.logoFile = null;
    logoInput.value = '';
    logoPlaceholder.style.display = 'flex';
    logoPreview.style.display = 'none';
    logoPreviewImg.src = '';
});

// ==========================================
// AI Rewrite
// ==========================================
rewriteBtn.addEventListener('click', rewriteStory);

async function rewriteStory() {
    const story = storyInput.value.trim();
    if (story.length < 10) {
        showToast('Please write at least 10 characters', 'error');
        return;
    }
    
    rewriteBtn.disabled = true;
    rewriteBtn.textContent = '⏳ Rewriting...';
    
    try {
        const formData = new FormData();
        formData.append('story', story);
        
        const res = await fetch(`${API_BASE}/api/rewrite`, {
            method: 'POST',
            body: formData,
        });
        
        if (!res.ok) throw new Error('Rewrite failed');
        
        const data = await res.json();
        
        state.currentHook = data.hook;
        state.currentNiche = data.niche;
        state.currentHashtags = data.hashtags;
        
        // Show hook preview
        const hookPreview = $('#hookPreview');
        hookPreview.style.display = 'block';
        
        $('#hookContent').textContent = data.hook;
        $('#nicheBadge').textContent = getNicheIcon(data.niche) + ' ' + capitalize(data.niche);
        $('#hashtags').textContent = data.hashtags;
        
        showToast('✨ Viral hook generated!', 'success');
    } catch (err) {
        showToast('Failed to generate hook. Is Ollama running?', 'error');
        console.error(err);
        
        // Use offline fallback
        const { hook, niche, hashtags } = generateLocalHook(story);
        state.currentHook = hook;
        state.currentNiche = niche;
        state.currentHashtags = hashtags;
        
        $('#hookPreview').style.display = 'block';
        $('#hookContent').textContent = hook;
        $('#nicheBadge').textContent = getNicheIcon(niche) + ' ' + capitalize(niche);
        $('#hashtags').textContent = hashtags;
    } finally {
        rewriteBtn.disabled = false;
        rewriteBtn.textContent = '✨ AI Rewrite';
    }
}

function generateLocalHook(text) {
    // Offline fallback hook generation
    const templates = [
        `Nobody expected this ${text.split(' ').slice(0, 3).join(' ')} twist! 🔥`,
        `The ${text.split(' ').slice(0, 2).join(' ')} story that shocked everyone 😱`,
        `What happened during ${text.split(' ').slice(0, 3).join(' ')} was UNEXPECTED 👀`,
        `This ${text.split(' ').slice(0, 2).join(' ')} moment went viral for a reason 🎬`,
        `You won't believe what ${text.split(' ').slice(0, 3).join(' ')} did next 💀`,
    ];
    
    const niche = detectNiche(text);
    const hook = templates[Math.floor(Math.random() * templates.length)];
    const hashtags = getHashtags(niche);
    
    return { hook, niche, hashtags };
}

function detectNiche(text) {
    const t = text.toLowerCase();
    if (t.match(/(movie|film|actor|actress|scene|director|hollywood|bollywood)/)) return 'movie';
    if (t.match(/(celebrity|famous|star|interview|revealed|confessed)/)) return 'celebrity';
    if (t.match(/(crime|murder|killer|detective|police|case|mystery)/)) return 'crime';
    if (t.match(/(sport|game|player|team|champion|match|win)/)) return 'sports';
    return 'story';
}

function getHashtags(niche) {
    const tags = {
        movie: '#movies #shorts #viral #facts #hollywood #behindthescenes',
        celebrity: '#celebrity #shorts #viral #facts #trending',
        crime: '#truecrime #mystery #shorts #viral #crime',
        sports: '#sports #shorts #viral #athlete #highlights',
        story: '#storytime #shorts #viral #fyp #trending',
    };
    return tags[niche] || '#shorts #viral #fyp #trending';
}

function getNicheIcon(niche) {
    const icons = { movie: '🎬', celebrity: '🌟', crime: '🔍', sports: '🏆', story: '📖' };
    return icons[niche] || '🔥';
}

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// Regenerate hook
$('#regenerateHook').addEventListener('click', rewriteStory);

// ==========================================
// Generate Button
// ==========================================
function updateGenerateButton() {
    const btn = $('#generateBtn');
    btn.disabled = !state.selectedFile || !storyInput.value.trim();
}

$('#generatorForm').addEventListener('submit', generateShort);

async function generateShort(e) {
    e.preventDefault();
    
    if (state.isGenerating) return;
    
    if (!state.selectedFile) {
        showToast('Please upload a video', 'error');
        return;
    }
    
    const story = storyInput.value.trim();
    if (!story) {
        showToast('Please write your story', 'error');
        return;
    }
    
    state.isGenerating = true;
    
    // Show loading state
    const btn = $('#generateBtn');
    const btnContent = btn.querySelector('.btn-content');
    const btnLoader = btn.querySelector('.btn-loader');
    btnContent.style.display = 'none';
    btnLoader.style.display = 'flex';
    btn.disabled = true;
    
    // Show preview loading
    $('#previewEmpty').style.display = 'none';
    $('#previewResult').style.display = 'none';
    $('#previewLoading').style.display = 'block';
    
    // Start loading animation
    startLoadingAnimation();
    
    try {
        const formData = new FormData();
        formData.append('video', state.selectedFile);
        formData.append('story', story);
        formData.append('channel_name', $('#channelName').value || 'YourChannel');
        formData.append('channel_handle', $('#channelHandle').value || '@yourchannel');
        if (state.logoFile) {                        formData.append('logo', state.logoFile);
                    }
                    if (state.bgFile) {
                        formData.append('background', state.bgFile);
                    }
                    formData.append('add_subtitles', $('#addSubtitles').checked)
                    formData.append('video_fit_mode', state.videoFitMode)
                    formData.append('audio_pitch_shift', $('#pitchShift').checked)
        if (state.crop) {
            formData.append('crop_x', state.crop.x);
            formData.append('crop_y', state.crop.y);
            formData.append('crop_w', state.crop.w);
            formData.append('crop_h', state.crop.h);
            formData.append('crop_rotated', state.crop.rotated ? '1' : '0');
        }
        
        const res = await fetch(`${API_BASE}/api/generate`, {
            method: 'POST',
            body: formData,
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Generation failed');
        }
        
        const data = await res.json();
        
        // Show result
        setTimeout(() => {
            $('#previewLoading').style.display = 'none';
            $('#previewResult').style.display = 'block';
            
            const resultVideo = $('#resultVideo');
            resultVideo.src = `${API_BASE}${data.video_url}`;
            
            $('#downloadBtn').href = `${API_BASE}${data.video_url}`;
            $('#downloadBtn').download = data.filename;
            
            // Show details
            const details = $('#resultDetails');
            const sizeMB = (data.file_size / (1024 * 1024)).toFixed(1);
            details.innerHTML = `
                <div><strong>Hook:</strong> ${data.hook}</div>
                <div><strong>Niche:</strong> ${getNicheIcon(data.niche)} ${capitalize(data.niche)}</div>
                <div><strong>Duration:</strong> ${data.duration}s</div>
                <div><strong>Size:</strong> ${sizeMB} MB</div>
            `;
            
            // SEO pack (title / description / hashtags / tags) under the preview
            renderSeoPack(data.seo || {
                title: data.hook,
                description: story,
                hashtags: data.hashtags,
                tags: 'shorts, viral, storytime',
            });
            
            showToast('🎬 Your viral Short is ready!', 'success');
            
            // Scroll to video
            $('#previewResult').scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 500);
        
    } catch (err) {
        $('#previewLoading').style.display = 'none';
        $('#previewEmpty').style.display = 'block';
        showToast(`❌ ${err.message}`, 'error');
        console.error(err);
    } finally {
        state.isGenerating = false;
        btnContent.style.display = 'flex';
        btnLoader.style.display = 'none';
        btn.disabled = false;
    }
}

// ==========================================
// Loading Animation
// ==========================================
function startLoadingAnimation() {
    const steps = document.querySelectorAll('.loading-step');
    const progress = $('#loadingProgress');
    const defaultTexts = ['📝 Analyzing story...', '🤖 Generating viral hook...', '🎬 Processing video...', '💬 Adding subtitles...', '✨ Composing final Short...'];
    let currentStep = 0;
    
    steps.forEach((s, i) => {
        s.className = 'loading-step';
        s.textContent = defaultTexts[i] || s.textContent;
        if (i === 0) s.classList.add('active');
    });
    progress.style.width = '0%';
    
    const stepInterval = setInterval(() => {
        currentStep++;
        
        if (currentStep < steps.length) {
            steps[currentStep - 1].classList.remove('active');
            steps[currentStep - 1].classList.add('completed');
            steps[currentStep].classList.add('active');
            progress.style.width = `${(currentStep / steps.length) * 100}%`;
        } else {
            clearInterval(stepInterval);
            progress.style.width = '90%';
            
            // Wait for actual completion
            const checkDone = setInterval(() => {
                if (!$('#previewLoading').style.display || $('#previewLoading').style.display === 'none') {
                    clearInterval(checkDone);
                }
            }, 100);
        }
    }, 2000);
}

// ==========================================
// Copy Link
// ==========================================
$('#copyLinkBtn').addEventListener('click', async () => {
    const videoUrl = $('#resultVideo').src;
    if (!videoUrl) return;
    
    try {
        await navigator.clipboard.writeText(videoUrl);
        showToast('🔗 Link copied to clipboard!', 'success');
    } catch {
        showToast('Failed to copy link', 'error');
    }
});

// ==========================================
// SEO Pack (shown under the video when it's ready)
// ==========================================
function renderSeoPack(seo) {
    const pack = {
        title: (seo.title || '').trim(),
        description: (seo.description || '').trim(),
        hashtags: (seo.hashtags || '').trim(),
        tags: (seo.tags || '').trim(),
    };
    state.seo = pack;
    
    $('#seoTitleValue').textContent = pack.title;
    $('#seoDescValue').textContent = pack.description;
    
    // Hashtags as chips (#word)
    renderSeoChips(
        $('#seoHashtags'),
        pack.hashtags.split(/\s+/).filter(t => t.startsWith('#'))
    );
    // Tags as chips (comma separated)
    renderSeoChips(
        $('#seoTags'),
        pack.tags.split(',').map(t => t.trim()).filter(Boolean)
    );
    
    updateSeoCounts();
    
    const box = $('#seoBox');
    box.style.display = 'block';
    // Re-trigger the entrance animation on regenerate
    box.style.animation = 'none';
    void box.offsetHeight;
    box.style.animation = '';
}

function renderSeoChips(container, items) {
    container.innerHTML = '';
    items.forEach(item => {
        const chip = document.createElement('span');
        chip.className = 'seo-chip';
        chip.textContent = item;
        chip.title = 'Click to copy';
        chip.addEventListener('click', async () => {
            if (await copyToClipboard(item)) showToast(`📋 Copied ${item}`, 'success');
        });
        container.appendChild(chip);
    });
}

function updateSeoCounts() {
    const seo = state.seo || {};
    setSeoCount('#seoTitleCount', (seo.title || '').length, 100);
    setSeoCount('#seoDescCount', (seo.description || '').length, 5000);
    setSeoCount('#seoTagsCount', (seo.tags || '').length, 500);
}

function setSeoCount(selector, len, max) {
    const el = $(selector);
    if (!el) return;
    el.textContent = `${len}/${max}`;
    el.classList.toggle('over', len > max);
}

async function copyToClipboard(text) {
    if (!text) return false;
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch {
        // Fallback for browsers/contexts without the async clipboard API
        try {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            const ok = document.execCommand('copy');
            ta.remove();
            return ok;
        } catch {
            return false;
        }
    }
}

// Individual field copy buttons (event delegation)
$('#seoBox').addEventListener('click', async (e) => {
    const btn = e.target.closest('.seo-copy-btn');
    if (!btn || !state.seo) return;
    
    const field = btn.dataset.field;
    const labels = { title: 'Title', description: 'Description', hashtags: 'Hashtags', tags: 'Tags' };
    
    if (await copyToClipboard(state.seo[field] || '')) {
        flashCopied(btn);
        showToast(`📋 ${labels[field] || 'Content'} copied!`, 'success');
    } else {
        showToast('Failed to copy', 'error');
    }
});

// Copy everything at once
$('#seoCopyAllBtn').addEventListener('click', async () => {
    const seo = state.seo;
    if (!seo) return;
    
    const all = [
        `TITLE:\n${seo.title}`,
        `\nDESCRIPTION:\n${seo.description}`,
        `\nHASHTAGS:\n${seo.hashtags}`,
        `\nTAGS:\n${seo.tags}`,
    ].join('\n');
    
    if (await copyToClipboard(all)) {
        flashCopied($('#seoCopyAllBtn'), '✓ Copied!');
        showToast('📋 Full SEO pack copied!', 'success');
    } else {
        showToast('Failed to copy', 'error');
    }
});

function flashCopied(btn, doneText = '✓ Copied') {
    if (btn.classList.contains('copied')) return; // ignore rapid double-clicks
    const original = btn.textContent;
    btn.textContent = doneText;
    btn.classList.add('copied');
    setTimeout(() => {
        btn.textContent = original;
        btn.classList.remove('copied');
    }, 1400);
}

// ==========================================
// History
// ==========================================
async function loadHistory() {
    const grid = $('#historyGrid');
    
    try {
        const res = await fetch(`${API_BASE}/api/exports?limit=20`);
        const data = await res.json();
        
        if (!data.exports || data.exports.length === 0) {
            grid.innerHTML = `
                <div class="history-empty">
                    <div class="empty-icon">📂</div>
                    <div class="empty-text">No exports yet</div>
                    <div class="empty-hint">Generate your first Short to see it here</div>
                </div>
            `;
            return;
        }
        
        grid.innerHTML = data.exports.map(exp => {
            const uid = exp.uid || exp.output_path?.split('_').pop()?.split('.').shift() || '';
            return `
                <div class="history-card" onclick="window.open('${API_BASE}/api/download/${uid}', '_blank')">
                    <div class="history-card-header">
                        <div class="history-title">${exp.video_name || 'Unknown'}</div>
                        <span class="history-badge ${exp.status}">${exp.status}</span>
                    </div>
                    <div class="history-meta">
                        <span>${exp.niche || 'General'}</span>
                        <span>${new Date(exp.created_at).toLocaleDateString()}</span>
                        <span>${Math.round(exp.duration || 0)}s</span>
                    </div>
                </div>
            `;
        }).join('');
        
    } catch (err) {
        console.error('Failed to load history:', err);
    }
}

// ==========================================
// Niches
// ==========================================
async function loadNiches() {
    const grid = $('#nichesGrid');
    
    const niches = [
        {
            name: 'Movie Facts 🎬',
            desc: 'Behind-the-scenes movie secrets & actor stories. High RPM, massive reach.',
            viral: '⭐⭐⭐⭐⭐',
            rpm: 'High',
            example: 'Did you know this actor almost quit the movie?'
        },
        {
            name: 'Celebrity Secrets 🌟',
            desc: 'Unknown facts about famous celebrities. People LOVE celebrity content.',
            viral: '⭐⭐⭐⭐⭐',
            rpm: 'High',
            example: 'Nobody expected this celebrity secret...'
        },
        {
            name: 'True Crime 🔍',
            desc: 'Mysterious crime stories. Highest engagement rate on YouTube Shorts.',
            viral: '⭐⭐⭐⭐⭐',
            rpm: 'Very High',
            example: 'The detective noticed ONE thing that broke the case'
        },
        {
            name: 'Sports Facts 🏆',
            desc: 'Incredible sports moments and athlete stories. Great for evergreens.',
            viral: '⭐⭐⭐⭐',
            rpm: 'Medium',
            example: 'This athlete\'s comeback was UNREAL'
        },
        {
            name: 'Reddit Stories 💀',
            desc: 'Viral Reddit stories narrated over gameplay. Easy to produce in bulk.',
            viral: '⭐⭐⭐⭐⭐',
            rpm: 'High',
            example: 'This Reddit story went viral for a reason...'
        },
        {
            name: 'Documentary Facts 📚',
            desc: 'Interesting facts from documentaries. Educational & entertaining.',
            viral: '⭐⭐⭐⭐',
            rpm: 'Medium',
            example: 'Scientists were SHOCKED by this discovery'
        },
    ];
    
    grid.innerHTML = niches.map(n => `
        <div class="niche-card">
            <div class="niche-card-header">
                <div class="niche-name">${n.name}</div>
                <div class="niche-viral">${n.viral}</div>
            </div>
            <div class="niche-desc">${n.desc}</div>
            <div class="niche-stats">
                <span>💰 RPM: ${n.rpm}</span>
            </div>
            <div class="niche-example">"${n.example}"</div>
        </div>
    `).join('');
}

// ==========================================
// Toast Notifications
// ==========================================
function showToast(message, type = 'info') {
    const container = $('#toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100px)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ==========================================
// Keyboard Shortcuts
// ==========================================
document.addEventListener('keydown', (e) => {
    // Ctrl+Enter to generate
    if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault();
        if (!state.isGenerating) {
            $('#generatorForm').dispatchEvent(new Event('submit'));
        }
    }
    
    // Escape to close modals
    if (e.key === 'Escape') {
        // Any cleanup if needed
    }
});

// ==========================================
// Initial Load
// ==========================================
console.log('🎬 AI Shorts Generator loaded');
console.log('📤 Upload a video and write your story to create viral Shorts!');
console.log('⌨️ Ctrl+Enter to generate');

// ==========================================
// Logout
// ==========================================
const logoutBtn = $('#logoutBtn');
if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
        logoutBtn.disabled = true;
        try {
            await fetch(`${API_BASE}/api/logout`, { method: 'POST' });
        } catch (e) {
            // Ignore - we redirect to the login screen regardless
        }
        window.location.href = '/login';
    });
}
