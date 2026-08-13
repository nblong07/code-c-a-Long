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
        this.video.addEventListener('loadedmetadata', () => this.onLoadedMetadata());
        this.video.addEventListener('error', (e) => this.onError(e));
        this.video.addEventListener('waiting', () => this.onWaiting());
        this.video.addEventListener('canplay', () => this.onCanPlay());
        this.video.addEventListener('click', () => this.togglePlayPause());
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
        document.getElementById('rewindBtn')?.addEventListener('click', () => this.skip(-10));
        document.getElementById('forwardBtn')?.addEventListener('click', () => this.skip(10));
        document.getElementById('initialTimeBtn')?.addEventListener('click', () => this.goToInitialTime());
    }
    
    skip(seconds) {
        this.video.currentTime += seconds;
    }
    
    goToInitialTime() {
        this.video.currentTime = this.initialTime;
    }
}

async function getVideo(videoName) {
    if (!videoName) return '';
    const videoBase = window.VIDEO_BASE || 'http://localhost:8000/videos';
    return `${videoBase}/${videoName}.mp4`;
}

// Play video starting 3s prior to target keyframe, then FRAME-EXACT AUTO-PAUSE at target time!
async function playVideoAtTime(videoName, timeInSeconds) {
    const detailsDiv = document.getElementById('Details');
    const videoElement = document.getElementById('vid_details');
    let player = null;

    detailsDiv.style.display = 'block';

    const videoSrc = await getVideo(videoName);

    // Target keyframe timestamp (in seconds) from CSV map
    const targetTime = (timeInSeconds !== undefined && !isNaN(timeInSeconds)) ? Math.max(0, timeInSeconds) : 0;
    // Start 3 seconds before target moment for smooth pre-roll
    const startTime = Math.max(0, targetTime - 3.0);

    console.log("Playing video:", videoName, "| Keyframe target:", targetTime + "s", "| Pre-roll start (-3s):", startTime + "s");

    if (!videoElement.playerInstance) {
        videoElement.playerInstance = new VideoPlayer('vid_details', videoSrc);
        player = videoElement.playerInstance;
    } else {
        player = videoElement.playerInstance;
        player.videoSrc = videoSrc;
        player.initPlayer();
    }

    // Hủy bộ giám sát khung hình cũ nếu đang chạy
    if (player.rafAutoPauseId) {
        cancelAnimationFrame(player.rafAutoPauseId);
        player.rafAutoPauseId = null;
    }

    player.initialTime = startTime;

    // Vòng lặp giám sát độ phân giải cao 60fps (16ms precision)
    const monitorAndAutoPause = () => {
        if (!player || !player.video) return;

        if (player.video.currentTime >= targetTime) {
            try {
                player.video.pause();
                player.video.currentTime = targetTime; // Khóa chuẩn xác đúng frame ảnh!
            } catch(e) {}
            player.rafAutoPauseId = null;
        } else {
            if (!player.video.paused) {
                player.rafAutoPauseId = requestAnimationFrame(monitorAndAutoPause);
            }
        }
    };

    const setTimeAndPlay = () => {
        try {
            player.video.currentTime = startTime;
        } catch(e) {}

        if (targetTime > startTime) {
            player.video.play().then(() => {
                player.rafAutoPauseId = requestAnimationFrame(monitorAndAutoPause);
            }).catch(e => console.error('Play failed:', e));
        } else {
            player.play();
        }
    };

    if (player.video.readyState >= 1) {
        setTimeAndPlay();
    } else {
        player.video.addEventListener('loadedmetadata', setTimeAndPlay, { once: true });
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
    const entity = item.entity || {};
    const videoName = entity.video_id || entity.video || '';
    const frameId = entity.frame_id || 0;

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
document.addEventListener("keydown", event => {
    if (event.key === 'Escape') {
        event.preventDefault();
        const detailsDiv = document.getElementById('Details');
        if (detailsDiv.style.display === 'block') {
            detailsDiv.style.display = 'none';
            document.getElementById('vid_details')?.pause(); // Pause video if open
        }
    }
});
  

// Close modal on click of close button or outside of modal
const modal= document.getElementById("Details")
const video= document.getElementById("vid_details")

document.getElementsByClassName("close")[0]?.addEventListener("click", () => {
    modal.style.display = "none";
    video.pause();
});


window.addEventListener("click", function(event){
    if (event.target == modal) {
        modal.style.display = "none";
        video.pause();
    }
});


// Move video
const draggableBar = document.querySelector('.draggable-bar');
const detailsBg = document.querySelector('.details_bg');
const detailsContainer = document.querySelector('#Details');

let isDragging = false;
let startX, startY, startLeft, startTop;

draggableBar.addEventListener('mousedown', (e) => {
    isDragging = true;
    startX = e.clientX;
    startY = e.clientY;
    startLeft = detailsBg.offsetLeft;
    startTop = detailsBg.offsetTop;
    e.preventDefault();
});

document.addEventListener('mouseup', () => {
    isDragging = false;
});

document.addEventListener('mousemove', (e) => {
    if (isDragging) {
        const deltaX = e.clientX - startX;
        const deltaY = e.clientY - startY;

        let newLeft = startLeft + deltaX;
        let newTop = startTop + deltaY;

        // Lấy kích thước của màn hình
        const screenWidth = window.innerWidth;
        const screenHeight = window.innerHeight;

        // Giới hạn newLeft để không di chuyển ra khỏi màn hình bên phải
        newLeft = Math.min(newLeft, screenWidth - detailsBg.offsetWidth);

        // Giới hạn newTop để không di chuyển ra khỏi màn hình phía trên và dưới
        newTop = Math.max(44, Math.min(newTop, screenHeight - detailsBg.offsetHeight));

        detailsBg.style.left = `${newLeft}px`;
        detailsBg.style.top = `${newTop}px`;
    }
});