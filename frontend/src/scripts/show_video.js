//------------------------ Show video ------------------------//


// VideoPlayer class to handle video playback and HLS streaming
class VideoPlayer {
    constructor(videoElementId, videoSrc) {
        this.video = document.getElementById(videoElementId);
        this.videoSrc = videoSrc;
        this.hls = null;
        this.initPlayer();

        this.initialTime = 0;
        this.addCustomControls();
    }
  
    // Initialize the video player depending on browser support
    initPlayer() {
        if (this.hls) {
            this.hls.destroy();
            this.hls = null;
        }
        if (this.videoSrc && this.videoSrc.endsWith('.m3u8') && typeof Hls !== 'undefined' && Hls.isSupported()) {
            this.initHlsPlayer();
        } else {
            this.initNativePlayer();
        }
        this.addEventListeners();
    }
  
    // Initialize HLS.js player
    initHlsPlayer() {
        this.hls = new Hls({ 
            enableWorker: true,
            lowLatencyMode: true
        });
        this.hls.loadSource(this.videoSrc);
        this.hls.attachMedia(this.video);
        this.hls.on(Hls.Events.MANIFEST_PARSED, () => {
            this.video.play().catch(e => console.error('Auto-play was prevented:', e));
        });
    }
  
    // Initialize native player for HLS/MP4 streams
    initNativePlayer() {
        this.video.src = this.videoSrc;
        this.video.load();
    }

    // Add event listeners to handle video playback events
    addEventListeners() {
        if (this.hasAddedListeners) return;
        this.hasAddedListeners = true;
        this.video.addEventListener('error', (e) => console.error('Video error:', e));
    }
  
    onLoadedMetadata() {
        // console.log('Video metadata loaded');
    }
  
    onError(e) {
        // console.error('Video error:', e);
    }
  
    onWaiting() {
        // console.log('Video is buffering');
    }
  
    onCanPlay() {
        // console.log('Video can play');
    }

    togglePlayPause() {
        if (this.video.paused) {
            this.video.play();
        } else {
            this.video.pause();
        }
    }
  
    play() {
        this.video.play().catch(e => console.error('Play failed:', e));
    }
  
    pause() {
        this.video.pause();
    }
  
    seek(time) {
        if (isNaN(time)) return;
        this.video.currentTime = time;
    }
  
    setQuality(level) {
        if (this.hls) {
            this.hls.currentLevel = level;
        }
    }
  
    // Clean up resources and remove event listeners
    destroy() {
        if (this.hls) {
            this.hls.destroy();
        }
    }
    
    //----------------------------------
    addCustomControls() {
        document.getElementById('rewindBtn')?.addEventListener('click', () => this.skip(-5));
        document.getElementById('forwardBtn')?.addEventListener('click', () => this.skip(5));
        document.getElementById('initialTimeBtn')?.addEventListener('click', () => this.goToInitialTime());
    }
    
    skip(seconds) {
        if (!this.video) return;
        const newTime = Math.max(0, Math.min(this.video.duration || Infinity, this.video.currentTime + seconds));
        this.video.currentTime = newTime;
    }
    
    goToInitialTime() {
        if (!this.video) return;
        this.video.currentTime = this.initialTime;
    }
}

async function getVideo(videoName) {
    if (!videoName) return '';
    const videoBase = window.VIDEO_BASE || 'http://localhost:8000/videos';
    const cleanVid = (videoName || '').split('/').pop().replace(/\.mp4$/i, '').trim();
    return `${videoBase}/${cleanVid}.mp4`;
}

// Bộ nhớ đệm CSV Map (In-Memory Cache) giúp định vị Frame mili-giây với tốc độ 0ms
window._videoCsvMapCache = window._videoCsvMapCache || {};

// Tìm Frame ID chính xác gần nhất trong tệp CSV Map của video theo số giây hiện tại (chính xác từng mili-giây)
async function getNearestKeyframeForVideo(videoName, curSec) {
    let bestFid = Math.round(curSec * 25);
    let bestSec = curSec;
    const cleanVid = (videoName || '').split('/').pop().replace(/\.mp4$/i, '').trim();

    try {
        let mapList = window._videoCsvMapCache[cleanVid];
        if (!mapList) {
            const csvBase = window.CSV_BASE || 'http://localhost:8000/keyframes/maps';
            let resp = await fetch(`${csvBase}/${cleanVid}_map.csv`);
            if (!resp.ok) {
                resp = await fetch(`${csvBase}/${cleanVid}.csv`);
            }
            if (resp.ok) {
                const text = await resp.text();
                const lines = text.trim().split('\n');
                mapList = [];
                for (let line of lines) {
                    if (line.toLowerCase().includes('frameid') || line.toLowerCase().includes('frame_id')) continue;
                    const parts = line.split(',');
                    if (parts.length >= 2) {
                        const fid = parseInt(parts[0].trim(), 10);
                        const sec = parseFloat(parts[1].trim());
                        if (!isNaN(fid) && !isNaN(sec)) {
                            mapList.push({ fid, sec });
                        }
                    }
                }
                window._videoCsvMapCache[cleanVid] = mapList;
            }
        }

        if (mapList && mapList.length > 0) {
            let minDiff = Infinity;
            for (let item of mapList) {
                const diff = Math.abs(item.sec - curSec);
                if (diff < minDiff) {
                    minDiff = diff;
                    bestFid = item.fid;
                    bestSec = item.sec;
                }
            }
        }
    } catch (e) {
        console.warn("Could not fetch CSV map for nearest keyframe:", e);
    }
    return { frameId: bestFid, seconds: bestSec };
}

// Play video smoothly starting at target keyframe / pre-roll without forced auto-pause
async function playVideoAtTime(videoName, timeInSeconds) {
    const detailsDiv = document.getElementById('Details');
    const videoElement = document.getElementById('vid_details');
    const titleElement = document.getElementById('vid-modal-title');
    let player = null;

    detailsDiv.style.display = 'block';

    const cleanVid = (videoName || '').split('/').pop().replace(/\.mp4$/i, '').trim();
    const videoSrc = await getVideo(cleanVid);

    // Target keyframe timestamp (in seconds) from CSV map
    const targetTime = (timeInSeconds !== undefined && !isNaN(timeInSeconds)) ? Math.max(0, timeInSeconds) : 0;
    
    // Quy tắc phát trước 2s: Nếu trước khoảnh khắc đó còn >= 2s thì lùi 2s, nếu < 2s thì phát từ 0s
    const startTime = Math.max(0, targetTime - 2.0);

    const formatTimeDisplay = (sec) => {
        const m = Math.floor(sec / 60);
        const s = (sec % 60).toFixed(2);
        return `${m < 10 ? '0' : ''}${m}:${parseFloat(s) < 10 ? '0' : ''}${s}s`;
    };

    if (titleElement) {
        titleElement.innerHTML = `<i class="fa-solid fa-film"></i> Video: <strong>${cleanVid}</strong> <span id="vid-time-indicator" style="color: #00F2FE; font-weight: 600; margin-left: 8px;">(${formatTimeDisplay(startTime)} / Target: ${formatTimeDisplay(targetTime)})</span>`;
    }

    console.log("Playing video:", cleanVid, "| Keyframe target:", targetTime.toFixed(3) + "s", "| Pre-roll start at:", startTime.toFixed(3) + "s");

    if (!videoElement.playerInstance) {
        videoElement.playerInstance = new VideoPlayer('vid_details', videoSrc);
        player = videoElement.playerInstance;
    } else {
        player = videoElement.playerInstance;
        player.videoSrc = videoSrc;
        player.initPlayer();
    }

    player.initialTime = targetTime;

    const setTimeAndPlay = () => {
        try {
            videoElement.currentTime = startTime;
            videoElement.play().catch(() => {});
        } catch(e) {
            console.warn("Could not seek/play video:", e);
        }
    };

    if (videoElement.readyState >= 1) {
        setTimeAndPlay();
    } else {
        videoElement.addEventListener('loadedmetadata', setTimeAndPlay, { once: true });
    }

    // Cập nhật chỉ số thời gian chính xác từng mili-giây khi video đang phát
    videoElement.ontimeupdate = () => {
        const timeInd = document.getElementById('vid-time-indicator');
        if (timeInd) {
            const cur = videoElement.currentTime || 0;
            timeInd.textContent = `(${formatTimeDisplay(cur)} / Target: ${formatTimeDisplay(targetTime)})`;
        }
    };

    // Đảm bảo nhấn vào màn hình video (Overlay) hoặc nút điều khiển để Tạm dừng / Phát tiếp video tức thì không bị double-click
    let lastToggleTime = 0;
    const handlePlayPauseToggle = (e) => {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        const now = Date.now();
        if (now - lastToggleTime < 350) return; // Debounce 350ms chống kích hoạt đúp
        lastToggleTime = now;

        if (videoElement.paused) {
            videoElement.play().catch(() => {});
        } else {
            videoElement.pause();
        }
    };

    const clickOverlay = document.getElementById('vid-click-overlay');
    if (clickOverlay) {
        clickOverlay.onclick = handlePlayPauseToggle;
    }

    const togglePlayBtn = document.getElementById('togglePlayPauseBtn');
    if (togglePlayBtn) {
        togglePlayBtn.onclick = handlePlayPauseToggle;
    }

    // Tự động cập nhật icon & nhãn nút Tạm Dừng / Phát Tiếp
    videoElement.onplay = () => {
        const icon = document.getElementById('playPauseIcon');
        const text = document.getElementById('playPauseText');
        if (icon) icon.className = 'fa-solid fa-pause';
        if (text) text.textContent = 'Tạm Dừng';
    };
    videoElement.onpause = () => {
        const icon = document.getElementById('playPauseIcon');
        const text = document.getElementById('playPauseText');
        if (icon) icon.className = 'fa-solid fa-play';
        if (text) text.textContent = 'Phát Tiếp';
    };

    // 1. Nút "Chọn Frame Này": Lấy đúng Keyframe ID gần nhất và thêm vào danh sách xuất file
    const addBtn = document.getElementById('addCurrentMomentBtn');
    if (addBtn) {
        addBtn.onclick = async () => {
            const curSec = videoElement.currentTime || targetTime;
            const { frameId, seconds } = await getNearestKeyframeForVideo(videoName, curSec);
            const keyframeBase = window.KEYFRAME_BASE || 'http://localhost:8000/keyframes';
            const imgSrc = `${keyframeBase}/${videoName}/keyframes/keyframe_${frameId}.webp`;
            const frameInfo = `${videoName}-${seconds.toFixed(2)}`;
            const tsMs = Math.round(seconds * 1000);

            if (typeof addImageToExportArea === 'function') {
                addImageToExportArea(frameId, imgSrc, frameInfo, true, tsMs);
            }
        };
    }

    // 2. Nút "Duyệt Frame Tại Đây": Tự động mở thanh Timeline tại Frame gần nhất với khoảnh khắc đang xem
    const jumpBtn = document.getElementById('jumpToKeyframeBtn');
    if (jumpBtn) {
        jumpBtn.onclick = async () => {
            const curSec = videoElement.currentTime || targetTime;
            const { frameId, seconds } = await getNearestKeyframeForVideo(videoName, curSec);
            const keyframeBase = window.KEYFRAME_BASE || 'http://localhost:8000/keyframes';
            const imgSrc = `${keyframeBase}/${videoName}/keyframes/keyframe_${frameId}.webp`;
            const frameInfo = `${videoName}-${seconds.toFixed(2)}`;

            if (typeof showVideoFramesByInfo === 'function') {
                await showVideoFramesByInfo(videoName, frameId, imgSrc, frameInfo);
            } else if (typeof showVideoFrames === 'function') {
                const fakeDiv = document.createElement('div');
                fakeDiv.innerHTML = `<img src="${imgSrc}"><div class="infor">${frameInfo}</div>`;
                await showVideoFrames(fakeDiv);
            }
            if (typeof showNotification === 'function') {
                showNotification(`🎯 Đã định vị Frame ${frameId} (${seconds.toFixed(2)}s) trên thanh Timeline!`, 'info');
            }
        };
    }

    // 3. Nút "Đưa Lên Top Đầu": Lấy đúng Keyframe ID và đưa ngay lên TOP 1 bằng GPU Refine
    const refineBtn = document.getElementById('refineFromCurrentVideoBtn');
    if (refineBtn) {
        refineBtn.onclick = async () => {
            const curSec = videoElement.currentTime || targetTime;
            const { frameId, seconds } = await getNearestKeyframeForVideo(videoName, curSec);
            const vectorId = `${videoName}_${frameId}`;
            const keyframeBase = window.KEYFRAME_BASE || 'http://localhost:8000/keyframes';
            const imgSrc = `${keyframeBase}/${videoName}/keyframes/keyframe_${frameId}.webp`;
            const frameInfo = `${videoName}-${seconds.toFixed(2)}`;
            const tsMs = Math.round(seconds * 1000);

            // Thêm vào khay chọn
            if (typeof addImageToExportArea === 'function') {
                addImageToExportArea(frameId, imgSrc, frameInfo, true, tsMs);
            }

            // Gọi Refine Search để đưa video và khoảnh khắc này lên đầu
            if (typeof performRefineSearch === 'function') {
                performRefineSearch([vectorId]);
                if (typeof showNotification === 'function') {
                    showNotification(`✨ Đang đưa khoảnh khắc ${frameInfo} (Frame ${frameId}) lên TOP 1!`, 'success');
                }
            } else if (typeof performSimilaritySearch === 'function') {
                performSimilaritySearch(vectorId, imgSrc, videoName, frameId);
            }
        };
    }

    // 3. Xử lý Truy Vấn Sâu Trong Video Này (Video-Scoped Q&A Inspector)
    const qaInput = document.getElementById('vid-qa-input');
    const qaSubmitBtn = document.getElementById('vid-qa-submit-btn');
    const qaResultBox = document.getElementById('vid-qa-result-box');
    const qaResultText = document.getElementById('vid-qa-result-text');
    const qaResultSub = document.getElementById('vid-qa-result-sub');

    if (qaResultBox) qaResultBox.style.display = 'none';
    if (qaInput) qaInput.value = '';

    const executeVideoQA = async () => {
        const queryText = (qaInput ? qaInput.value : '').trim();
        if (!queryText) return;

        if (qaResultBox) {
            qaResultBox.style.display = 'block';
            if (qaResultText) qaResultText.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang phân tích âm thanh và hình ảnh trong video...';
            if (qaResultSub) qaResultSub.textContent = '';
        }

        try {
            const apiBase = window.API_BASE || 'http://localhost:8000';
            const cleanVideoId = (videoName || '').split('/').pop().replace(/\.mp4$/i, '').trim();
            const resp = await fetch(`${apiBase}/api/video_qa`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ video_id: cleanVideoId || videoName, query: queryText, top_k: 50 })
            });

            if (resp.ok) {
                const resData = await resp.json();
                const ans = resData.qa_answer || 'Không tìm thấy đáp án rõ ràng trong video';
                const src = resData.qa_source || 'Phân tích tổng hợp SigLIP & OCR/ASR';
                
                if (qaResultText) qaResultText.innerHTML = `💡 <strong>Đáp án:</strong> "${ans}"`;
                if (qaResultSub) qaResultSub.innerHTML = `<i class="fa-solid fa-circle-info"></i> Nguồn: ${src}`;

                // Tự động điền vào ô nộp bài Q&A của từng frame
                if (typeof toggleTask === 'function') toggleTask('vqa');
                if (typeof applyVqaAnswerToCards === 'function') {
                    applyVqaAnswerToCards(ans);
                } else {
                    const commonInput = document.getElementById('vqa-common-answer');
                    if (commonInput) commonInput.value = ans;
                }

                // Tự động tua video đến đúng khoảnh khắc có câu trả lời (kèm bộ đệm phát trước 2s)
                if (resData.results && resData.results.length > 0) {
                    const bestFrame = resData.results[0];
                    const bestTime = bestFrame.entity?.time;
                    const frameId = bestFrame.entity?.frame_id || 0;
                    if (bestTime !== undefined && !isNaN(bestTime)) {
                        const startTime = Math.max(0, bestTime - 2.0);
                        videoElement.currentTime = startTime;
                        videoElement.play().catch(() => {});

                        const titleEl = document.getElementById('vid-modal-title');
                        if (titleEl) {
                            const formatTime = (sec) => {
                                const m = Math.floor(sec / 60);
                                const s = (sec % 60).toFixed(2);
                                return `${m < 10 ? '0' : ''}${m}:${parseFloat(s) < 10 ? '0' : ''}${s}s`;
                            };
                            titleEl.innerHTML = `<i class="fa-solid fa-film"></i> Video: <strong>${cleanVideoId || videoName}</strong> <span id="vid-time-indicator" style="color: #10B981; font-weight: 600; margin-left: 8px;">(🎯 Đáp án tại Frame ${frameId} - ${formatTime(bestTime)})</span>`;
                        }
                    }
                }

                if (typeof showNotification === 'function') {
                    showNotification(`🎯 Đã tìm thấy đáp án: "${ans}" & tự động phát tại đoạn video tương ứng!`, 'success');
                }
            } else {
                const errDetail = await resp.text();
                console.error("Video QA error:", resp.status, errDetail);
                if (qaResultText) qaResultText.textContent = 'Lỗi truy vấn Q&A trong video (Máy chủ trả về mã ' + resp.status + ')';
            }
        } catch (e) {
            console.error("Lỗi Video QA:", e);
            if (qaResultText) qaResultText.textContent = 'Lỗi kết nối máy chủ Q&A';
        }
    };

    if (qaSubmitBtn) qaSubmitBtn.onclick = executeVideoQA;
    if (qaInput) {
        qaInput.onkeydown = (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                executeVideoQA();
            }
        };
    }



    const divVideoFrames = document.getElementById('video-frames');
    if (divVideoFrames && divVideoFrames.style.display === 'flex') {
        if (typeof setupNavigationButtons === 'function') {
            setupNavigationButtons();
        }
        if (typeof handleKeyPress === 'function') {
            document.addEventListener('keydown', handleKeyPress);
        }
    }
}

// Show video details & lookup exact timestamp from CSV map
async function showVideo(img) {
    if (!data || !data.kq || !data.kq[img.id - 1]) return;

    const item = data.kq[img.id - 1];
    const entity = (item && item.entity) ? item.entity : (item || {});
    const videoName = entity.video_id || entity.video || '';
    const frameId = entity.frame_id !== undefined ? entity.frame_id : 0;

    let exactTime = entity.time;

    // 1. Kiểm tra trong globalSecondList đã nạp sẵn từ CSV map chưa
    if (exactTime === undefined && typeof globalSecondList !== 'undefined' && globalSecondList && globalSecondList[frameId] !== undefined) {
        exactTime = globalSecondList[frameId];
    }

    // 2. Nếu chưa có, tải trực tiếp file CSV map để tra cứu giây chính xác theo FrameID
    if (exactTime === undefined) {
        try {
            const csvBase = window.CSV_BASE || 'http://localhost:8000/keyframes/maps';
            const res = await fetch(`${csvBase}/${videoName}_map.csv`);
            if (res.ok) {
                const text = await res.text();
                const lines = text.trim().split('\n');
                for (let line of lines) {
                    const parts = line.split(',');
                    if (parts.length >= 2) {
                        const fid = parseInt(parts[0].trim(), 10);
                        const sec = parseFloat(parts[1].trim());
                        if (fid === parseInt(frameId, 10) && !isNaN(sec)) {
                            exactTime = sec;
                            break;
                        }
                    }
                }
            }
        } catch (e) {
            console.warn("Could not load CSV map for exact timestamp:", videoName, e);
        }
    }

    // 3. Fallback nếu không thấy CSV
    if (exactTime === undefined || isNaN(exactTime)) {
        exactTime = frameId / 25.0;
    }

    await playVideoAtTime(videoName, exactTime);
}
  

// Close video details when Escape key is pressed
// Keyboard shortcuts for video player: Escape (Close), +/A (Add to Export), R (Top 1 Refine), ArrowLeft/J (-5s), ArrowRight/L (+5s), ,/< (-1 Frame), ./> (+1 Frame), Space/K (Play/Pause)
document.addEventListener("keydown", event => {
    const activeEl = document.activeElement;
    if (activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA' || activeEl.isContentEditable)) {
        return; // Đang gõ chữ / câu trả lời, không bao giờ chặn phím
    }
    const detailsDiv = document.getElementById('Details');
    if (detailsDiv && detailsDiv.style.display === 'block') {
        if (event.key === 'Escape') {
            detailsDiv.style.display = 'none';
            document.getElementById('vid_details')?.pause();
        } else if (event.key === '+' || event.key === '=' || event.key === 'a' || event.key === 'A') {
            event.preventDefault();
            document.getElementById('addCurrentMomentBtn')?.click();
        } else if (event.key === 'r' || event.key === 'R') {
            event.preventDefault();
            document.getElementById('refineFromCurrentVideoBtn')?.click();
        } else if (event.key === 'ArrowLeft' || event.key === 'j' || event.key === 'J') {
            event.preventDefault();
            document.getElementById('rewindBtn')?.click();
        } else if (event.key === 'ArrowRight' || event.key === 'l' || event.key === 'L') {
            event.preventDefault();
            document.getElementById('forwardBtn')?.click();
        } else if (event.key === ',' || event.key === '<') {
            // Lùi 1 Frame chính xác (0.04s)
            event.preventDefault();
            const v = document.getElementById('vid_details');
            if (v) v.currentTime = Math.max(0, v.currentTime - 0.04);
        } else if (event.key === '.' || event.key === '>') {
            // Tới 1 Frame chính xác (0.04s)
            event.preventDefault();
            const v = document.getElementById('vid_details');
            if (v) v.currentTime = Math.min(v.duration || Infinity, v.currentTime + 0.04);
        } else if (event.key === 'k' || event.key === 'K' || event.key === ' ') {
            event.preventDefault();
            document.getElementById('togglePlayPauseBtn')?.click();
        }
    }
});

// Close modal on click of close button
const modal = document.getElementById("Details");
const video = document.getElementById("vid_details");

document.getElementById("close-vid-modal")?.addEventListener("click", (e) => {
    e.stopPropagation();
    if (modal) modal.style.display = "none";
    if (video) video.pause();
});

// Move floating video modal freely across the whole screen
const draggableBar = document.querySelector('.draggable-bar');

let isDragging = false;
let startX, startY, startLeft, startTop;

if (draggableBar && modal) {
    draggableBar.addEventListener('mousedown', (e) => {
        if (e.target.closest('.close') || e.target.closest('button')) return;
        
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;

        const rect = modal.getBoundingClientRect();
        startLeft = rect.left;
        startTop = rect.top;

        modal.style.right = 'auto';
        modal.style.bottom = 'auto';
        modal.style.left = `${startLeft}px`;
        modal.style.top = `${startTop}px`;

        e.preventDefault();
    });

    document.addEventListener('mouseup', () => {
        isDragging = false;
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;

        const deltaX = e.clientX - startX;
        const deltaY = e.clientY - startY;

        let newLeft = startLeft + deltaX;
        let newTop = startTop + deltaY;

        const screenWidth = window.innerWidth;
        const screenHeight = window.innerHeight;
        const modalWidth = modal.offsetWidth;
        const modalHeight = modal.offsetHeight;

        newLeft = Math.max(0, Math.min(newLeft, screenWidth - modalWidth));
        newTop = Math.max(0, Math.min(newTop, screenHeight - modalHeight));

        modal.style.left = `${newLeft}px`;
        modal.style.top = `${newTop}px`;
    });
}