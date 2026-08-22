//------------------------ Show videoframe & Timeline Explorer ------------------------//

let globalFrameList = [];
let globalSecondList = {};
let currentVideoName = '';
let currentActiveFrame = 0;

function parseVideoNameFromDirOrInfo(directory, frameInfo) {
  if (frameInfo && frameInfo.includes('-')) {
    const vName = frameInfo.split('-')[0].trim();
    if (vName && !vName.includes(':') && vName.toLowerCase() !== 'video' && !vName.toLowerCase().includes('localhost')) {
      return vName.replace(/\.mp4$/i, '');
    }
  }
  if (directory) {
    const match = directory.match(/\/([^\/]+)\/keyframes/i) || directory.match(/(L\d+_V\d+)/i);
    if (match && match[1] && !match[1].includes(':') && match[1].toLowerCase() !== 'keyframes') {
      return match[1].replace(/\.mp4$/i, '');
    }
    const parts = directory.split('/').filter(Boolean);
    const kfIdx = parts.lastIndexOf('keyframes');
    if (kfIdx > 0 && parts[kfIdx - 1] && !parts[kfIdx - 1].includes(':') && parts[kfIdx - 1].toLowerCase() !== 'keyframes') {
      return parts[kfIdx - 1].replace(/\.mp4$/i, '');
    }
    const lvPart = parts.find(part => part.startsWith('L') && part.includes('V'));
    if (lvPart) return lvPart.replace(/\.mp4$/i, '');
  }
  return 'video';
}

// Display video frames timeline explorer
async function showVideoFrames(imgDiv) {
  const divVideoFrames = document.getElementById('video-frames');
  if (!divVideoFrames) return;

  divVideoFrames.style.display = 'flex';

  // Render top toolbar and container
  divVideoFrames.innerHTML = `
    <div class="vf-header-bar">
      <div class="vf-header-title">
        <i class="fa-solid fa-film" style="color: #00F2FE;"></i>
        <span>Video: <strong id="vf-cur-vid">Loading...</strong></span>
        <span class="vf-header-badge" id="vf-cur-badge">Frame: ...</span>
      </div>
      <div class="vf-toolbar">
        <button class="vf-tool-btn" id="vf-btn-prev" title="Frame kề trước (Phím ←)"><i class="fa-solid fa-chevron-left"></i> Trước</button>
        <button class="vf-tool-btn" id="vf-btn-next" title="Frame kề sau (Phím →)">Sau <i class="fa-solid fa-chevron-right"></i></button>
        <button class="vf-tool-btn primary-btn" id="vf-btn-add-cur" title="Thêm frame đang chọn vào bài thi (Phím Space hoặc +)"><i class="fa-solid fa-plus"></i> Chọn Frame Này</button>
        <button class="vf-tool-btn refine-btn" id="vf-btn-refine-cur" title="Đưa frame đang chọn lên TOP 1 và tìm các ảnh tương tự (Phím R)"><i class="fa-solid fa-wand-magic-sparkles"></i> Đưa Lên Top 1</button>
        <button class="vf-tool-btn" id="vf-btn-play-cur" title="Phát video từ khoảnh khắc này"><i class="fa-solid fa-play"></i> Xem Video</button>
        <button class="vf-close-btn" id="vf-btn-close" title="Đóng thanh duyệt frame (Phím Esc)">×</button>
      </div>
    </div>
    <div class="frames-container"></div>
  `;

  const framesContainer = divVideoFrames.querySelector('.frames-container');

  const img = imgDiv.querySelector ? imgDiv.querySelector('img') : imgDiv;
  if (img) {
    const imgPath = img.src || img.dataset.src || '';
    const infoDiv = imgDiv.querySelector ? imgDiv.querySelector('.infor') : null;
    const imageInfo = infoDiv ? infoDiv.textContent : '';

    const lastSlashIndex = imgPath.lastIndexOf('/');
    const directory = imgPath.substring(0, lastSlashIndex + 1);
    const originalFrameName = imgPath.substring(lastSlashIndex + 1).split('.')[0];
    const currentFrame = parseInt(originalFrameName.replace('keyframe_', '').replace(/\.[^.]+$/, ''), 10) || 0;

    currentActiveFrame = currentFrame;
    currentVideoName = parseVideoNameFromDirOrInfo(directory, imageInfo);

    framesContainer.dataset.currentFrame = currentFrame;
    framesContainer.dataset.directory = directory;

    await loadFrameListFromCSV(directory, imageInfo);
    updateHeaderInfo(currentActiveFrame);
    await updateFrames(framesContainer, directory, currentFrame, imageInfo);
  }

  setupNavigationButtons();
  document.removeEventListener('keydown', handleKeyPress);
  document.addEventListener('keydown', handleKeyPress);
  document.removeEventListener('keydown', escapeHandler);
  document.addEventListener('keydown', escapeHandler);
}

function updateHeaderInfo(frameNumber) {
  const vidEl = document.getElementById('vf-cur-vid');
  const badgeEl = document.getElementById('vf-cur-badge');
  if (vidEl) vidEl.textContent = currentVideoName;
  if (badgeEl) {
    const sec = globalSecondList[frameNumber] !== undefined ? globalSecondList[frameNumber] : (frameNumber / 25.0);
    const curIdx = globalFrameList.indexOf(parseInt(frameNumber, 10));
    const totalCount = globalFrameList.length;
    const posStr = curIdx !== -1 ? `[${curIdx + 1}/${totalCount}]` : '';
    badgeEl.textContent = `Frame: ${frameNumber} (${sec.toFixed(2)}s) ${posStr}`;
  }
}

function setupNavigationButtons() {
  document.getElementById('vf-btn-prev')?.addEventListener('click', () => navigateFrames(-1));
  document.getElementById('vf-btn-next')?.addEventListener('click', () => navigateFrames(1));
  document.getElementById('vf-btn-add-cur')?.addEventListener('click', exportCurrentFrame);
  document.getElementById('vf-btn-refine-cur')?.addEventListener('click', refineCurrentFrame);
  document.getElementById('vf-btn-play-cur')?.addEventListener('click', () => {
    const sec = globalSecondList[currentActiveFrame] !== undefined ? globalSecondList[currentActiveFrame] : (currentActiveFrame / 25.0);
    if (typeof playVideoAtTime === 'function') {
      playVideoAtTime(currentVideoName, sec);
    }
  });
  document.getElementById('vf-btn-close')?.addEventListener('click', closeVideoFrames);
}

async function loadFrameListFromCSV(directory, imageInfo) {
  let videoName = currentVideoName || parseVideoNameFromDirOrInfo(directory, imageInfo);
  const csvBase = window.CSV_BASE || 'http://localhost:8000/keyframes/maps';
  let csvFilePath = `${csvBase}/${videoName}_map.csv`;

  try {
    let response = await fetch(csvFilePath);
    if (!response.ok) {
      csvFilePath = `${csvBase}/${videoName}.csv`;
      response = await fetch(csvFilePath);
    }
    if (response.ok) {
      const csvData = await response.text();
      const lines = csvData.trim().split('\n');
      globalSecondList = {};
      globalFrameList = [];
      lines.forEach((line, idx) => {
        if (idx === 0 && line.toLowerCase().includes('frameid')) return;
        const parts = line.split(',');
        if (parts.length >= 2) {
          const fid = parseInt(parts[0].trim(), 10);
          const sec = parseFloat(parts[1].trim());
          if (!isNaN(fid)) {
            globalFrameList.push(fid);
            globalSecondList[fid] = isNaN(sec) ? fid / 25.0 : sec;
          }
        }
      });
    }
  } catch (e) {
    console.warn("Could not load CSV mapping for", videoName, e);
  }
}

async function updateMainFrame(newFrameNumber, directory, frameInfo) {
  const framesContainer = document.querySelector('.frames-container');
  if (!framesContainer) return;

  currentActiveFrame = parseInt(newFrameNumber, 10);
  framesContainer.dataset.currentFrame = currentActiveFrame;
  framesContainer.dataset.directory = directory;

  updateHeaderInfo(currentActiveFrame);
  await updateFrames(framesContainer, directory, currentActiveFrame, frameInfo);
}

async function updateFrames(container, directory, currentFrame, currentFrameInfo) {
  if (globalFrameList.length === 0) return;

  const curFid = parseInt(currentFrame, 10);
  const currentIndex = globalFrameList.indexOf(curFid);
  const nearestIndex = currentIndex !== -1 ? currentIndex : globalFrameList.reduce((prev, curr, idx) => 
    Math.abs(curr - curFid) < Math.abs(globalFrameList[prev] - curFid) ? idx : prev, 0);

  // Show a generous sliding window of surrounding frames (±35 frames)
  const start = Math.max(0, nearestIndex - 35);
  const end = Math.min(globalFrameList.length, nearestIndex + 36);
  const framesToShow = globalFrameList.slice(start, end);

  await updateFramesSmooth(container, directory, curFid, framesToShow);
}

async function updateFramesSmooth(container, directory, currentFrame, framesToShow) {
  const fragment = document.createDocumentFragment();

  for (let frameNumber of framesToShow) {
    const isCurrent = frameNumber.toString() === currentFrame.toString();
    const frameContainer = document.createElement('div');
    frameContainer.className = 'frame-container' + (isCurrent ? ' current-frame-container' : '');
    frameContainer.dataset.frameNumber = frameNumber;

    const sec = globalSecondList[frameNumber] !== undefined ? globalSecondList[frameNumber] : (frameNumber / 25.0);
    const frameInfo = `${currentVideoName}-${sec.toFixed(2)}`;
    const keyframeBase = window.KEYFRAME_BASE || 'http://localhost:8000/keyframes';
    const framePath = `${keyframeBase}/${currentVideoName}/keyframes/keyframe_${frameNumber}.webp`;

    frameContainer.innerHTML = `
      <div class="frame-actions-overlay">
        <button class="vf-action-btn add" title="Thêm frame này vào bài thi (+)"><i class="fa-solid fa-plus"></i></button>
        <button class="vf-action-btn refine" title="Đưa frame này lên TOP 1 & Tìm tương tự"><i class="fa-solid fa-wand-magic-sparkles"></i></button>
      </div>
      <img class="video-frame ${isCurrent ? 'current-frame' : ''}" src="${framePath}" data-frame-number="${frameNumber}" alt="Video Frame">
      <div class="infor">${frameInfo}</div>
      ${isCurrent ? '<span class="current-indicator-badge">ĐANG CHỌN</span>' : ''}
    `;

    // Click frame to select / focus
    frameContainer.addEventListener('click', (e) => {
      if (e.target.closest('.vf-action-btn')) return; // handled separately
      updateMainFrame(frameNumber, directory, frameInfo);
    });

    // Button: Add to Export
    const addBtn = frameContainer.querySelector('.vf-action-btn.add');
    if (addBtn) {
      addBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const tsMs = Math.round(sec * 1000);
        if (typeof addImageToExportArea === 'function') {
          addImageToExportArea(frameNumber, framePath, frameInfo, true, tsMs);
          if (typeof showNotification === 'function') {
            showNotification(`Đã thêm ${frameInfo} vào danh sách nộp!`, 'success');
          }
        }
      });
    }

    // Button: Refine / Bring to Top 1
    const refineBtn = frameContainer.querySelector('.vf-action-btn.refine');
    if (refineBtn) {
      refineBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const vectorId = `${currentVideoName}_${frameNumber}`;
        const tsMs = Math.round(sec * 1000);
        if (typeof addImageToExportArea === 'function') {
          addImageToExportArea(frameNumber, framePath, frameInfo, true, tsMs);
        }
        if (typeof performRefineSearch === 'function') {
          performRefineSearch([vectorId]);
          if (typeof showNotification === 'function') {
            showNotification(`✨ Đang đưa ${frameInfo} lên TOP 1 và tìm các cảnh liên quan!`, 'success');
          }
        } else if (typeof performSimilaritySearch === 'function') {
          performSimilaritySearch(vectorId, framePath, currentVideoName, frameNumber);
        }
      });
    }

    fragment.appendChild(frameContainer);
  }

  container.innerHTML = '';
  container.appendChild(fragment);

  const currentFrameElement = container.querySelector('.current-frame-container');
  if (currentFrameElement) {
    currentFrameElement.scrollIntoView({ behavior: 'auto', block: 'nearest', inline: 'center' });
  }
}

// Navigate between frames with direction
function navigateFrames(direction) {
  if (globalFrameList.length === 0) return;

  const currentIndex = globalFrameList.indexOf(currentActiveFrame);
  let newIndex = (currentIndex !== -1 ? currentIndex : 0) + direction;
  if (newIndex < 0) newIndex = 0;
  if (newIndex >= globalFrameList.length) newIndex = globalFrameList.length - 1;

  const newFrame = globalFrameList[newIndex];
  const sec = globalSecondList[newFrame] !== undefined ? globalSecondList[newFrame] : (newFrame / 25.0);
  const frameInfo = `${currentVideoName}-${sec.toFixed(2)}`;
  const keyframeBase = window.KEYFRAME_BASE || 'http://localhost:8000/keyframes';
  const directory = `${keyframeBase}/${currentVideoName}/keyframes/`;

  updateMainFrame(newFrame, directory, frameInfo);
}

// Export current active frame
function exportCurrentFrame() {
  if (!currentActiveFrame || !currentVideoName) return;
  const sec = globalSecondList[currentActiveFrame] !== undefined ? globalSecondList[currentActiveFrame] : (currentActiveFrame / 25.0);
  const frameInfo = `${currentVideoName}-${sec.toFixed(2)}`;
  const keyframeBase = window.KEYFRAME_BASE || 'http://localhost:8000/keyframes';
  const framePath = `${keyframeBase}/${currentVideoName}/keyframes/keyframe_${currentActiveFrame}.webp`;
  const tsMs = Math.round(sec * 1000);

  if (typeof addImageToExportArea === 'function') {
    addImageToExportArea(currentActiveFrame, framePath, frameInfo, true, tsMs);
    if (typeof showNotification === 'function') {
      showNotification(`Đã thêm ${frameInfo} vào danh sách nộp!`, 'success');
    }
  }
}

// Refine search: Bring current active frame to Top 1
function refineCurrentFrame() {
  if (!currentActiveFrame || !currentVideoName) return;
  const sec = globalSecondList[currentActiveFrame] !== undefined ? globalSecondList[currentActiveFrame] : (currentActiveFrame / 25.0);
  const frameInfo = `${currentVideoName}-${sec.toFixed(2)}`;
  const vectorId = `${currentVideoName}_${currentActiveFrame}`;
  const keyframeBase = window.KEYFRAME_BASE || 'http://localhost:8000/keyframes';
  const framePath = `${keyframeBase}/${currentVideoName}/keyframes/keyframe_${currentActiveFrame}.webp`;
  const tsMs = Math.round(sec * 1000);

  if (typeof addImageToExportArea === 'function') {
    addImageToExportArea(currentActiveFrame, framePath, frameInfo, true, tsMs);
  }

  if (typeof performRefineSearch === 'function') {
    performRefineSearch([vectorId]);
    if (typeof showNotification === 'function') {
      showNotification(`✨ Đang đưa ${frameInfo} lên TOP 1 và tìm các cảnh liên quan!`, 'success');
    }
  } else if (typeof performSimilaritySearch === 'function') {
    performSimilaritySearch(vectorId, framePath, currentVideoName, currentActiveFrame);
  }
}

function handleKeyPress(event) {
  const activeEl = document.activeElement;
  const target = event.target;
  const isInput = (el) => el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable || el.closest?.('input') || el.closest?.('textarea'));

  if (isInput(activeEl) || isInput(target)) {
    return; // Đang gõ chữ trong ô tìm kiếm / Q&A, không bao giờ can thiệp phím
  }

  // Khi cửa sổ xem Video đang mở, nhường quyền hoàn toàn cho trình phát video
  const detailsDiv = document.getElementById('Details');
  if (detailsDiv && detailsDiv.style.display !== 'none') {
    return;
  }

  const divVideoFrames = document.getElementById('video-frames');
  if (!divVideoFrames || divVideoFrames.style.display === 'none') return;

  if (event.key === 'ArrowLeft') {
    event.preventDefault();
    navigateFrames(event.shiftKey ? -10 : -1);
  } else if (event.key === 'ArrowRight') {
    event.preventDefault();
    navigateFrames(event.shiftKey ? 10 : 1);
  } else if (event.key === '+' || event.key === '=' || event.key === 'a' || event.key === 'A') {
    event.preventDefault();
    exportCurrentFrame();
  } else if (event.key === 'r' || event.key === 'R') {
    event.preventDefault();
    refineCurrentFrame();
  } else if (event.key === 'Escape') {
    event.preventDefault();
    closeVideoFrames();
  }
}

function closeVideoFrames() {
  const divVideoFrames = document.getElementById('video-frames');
  if (divVideoFrames) divVideoFrames.style.display = 'none';
  document.removeEventListener('keydown', handleKeyPress);
  document.removeEventListener('keydown', escapeHandler);
}

const escapeHandler = (event) => {
  const activeEl = document.activeElement;
  const target = event.target;
  const isInput = (el) => el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable || el.closest?.('input') || el.closest?.('textarea'));

  if (isInput(activeEl) || isInput(target)) {
    return;
  }
  if (event.key === 'Escape') {
    closeVideoFrames();
  }
};

async function showVideoFramesByInfo(videoName, frameId, imgSrc, frameInfo) {
  const divVideoFrames = document.getElementById('video-frames');
  if (!divVideoFrames) return;

  divVideoFrames.style.display = 'flex';

  divVideoFrames.innerHTML = `
    <div class="vf-header-bar">
      <div class="vf-header-title">
        <i class="fa-solid fa-film" style="color: #00F2FE;"></i>
        <span>Video: <strong id="vf-cur-vid">Loading...</strong></span>
        <span class="vf-header-badge" id="vf-cur-badge">Frame: ...</span>
      </div>
      <div class="vf-toolbar">
        <button class="vf-tool-btn" id="vf-btn-prev" title="Frame kề trước (Phím ←)"><i class="fa-solid fa-chevron-left"></i> Trước</button>
        <button class="vf-tool-btn" id="vf-btn-next" title="Frame kề sau (Phím →)">Sau <i class="fa-solid fa-chevron-right"></i></button>
        <button class="vf-tool-btn primary-btn" id="vf-btn-add-cur" title="Thêm frame đang chọn vào bài thi (Phím Space hoặc +)"><i class="fa-solid fa-plus"></i> Chọn Frame Này</button>
        <button class="vf-tool-btn refine-btn" id="vf-btn-refine-cur" title="Đưa frame đang chọn lên TOP 1 và tìm các ảnh tương tự (Phím R)"><i class="fa-solid fa-wand-magic-sparkles"></i> Đưa Lên Top 1</button>
        <button class="vf-tool-btn" id="vf-btn-play-cur" title="Phát video từ khoảnh khắc này"><i class="fa-solid fa-play"></i> Xem Video</button>
        <button class="vf-close-btn" id="vf-btn-close" title="Đóng thanh duyệt frame (Phím Esc)">×</button>
      </div>
    </div>
    <div class="frames-container"></div>
  `;

  const framesContainer = divVideoFrames.querySelector('.frames-container');
  const currentFrame = parseInt(frameId, 10) || 0;
  currentActiveFrame = currentFrame;
  currentVideoName = videoName;

  const keyframeBase = window.KEYFRAME_BASE || 'http://localhost:8000/keyframes';
  const directory = imgSrc ? imgSrc.substring(0, imgSrc.lastIndexOf('/') + 1) : `${keyframeBase}/${videoName}/keyframes/`;

  framesContainer.dataset.currentFrame = currentFrame;
  framesContainer.dataset.directory = directory;

  await loadFrameListFromCSV(directory, frameInfo);
  updateHeaderInfo(currentActiveFrame);
  await updateFrames(framesContainer, directory, currentFrame, frameInfo);

  setupNavigationButtons();
  document.removeEventListener('keydown', handleKeyPress);
  document.addEventListener('keydown', handleKeyPress);
  document.removeEventListener('keydown', escapeHandler);
  document.addEventListener('keydown', escapeHandler);
}
