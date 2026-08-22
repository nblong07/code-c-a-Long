//------------------------ Update result ------------------------//

// Cache for storing search results
const searchCache = new Map();

// AbortController for cancelling ongoing requests
let currentAbortController = null;

/**
 * Tạo một div chứa hình ảnh kết quả tìm kiếm.
 * @param {Object} result - Đối tượng kết quả từ Milvus (có entity: {video, frame_id, time, ...})
 * @param {number} index  - Vị trí hiển thị (1-indexed)
 * @returns {HTMLElement}  - phần tử div có thể append vào DOM
 */
function getEntityInfo(result) {
  const entity = (result && result.entity) ? result.entity : (result || {});
  const video = entity.video_id || entity.video || 'video';
  const frameId = entity.frame_id !== undefined ? entity.frame_id : 0;
  
  // Tính toán thời gian thực chuẩn xác (Seconds & Milliseconds)
  let timestampMs = 0;
  if (entity.timestamp_ms !== undefined && entity.timestamp_ms !== null) {
    timestampMs = parseInt(entity.timestamp_ms);
  } else if (entity.time !== undefined && entity.time !== null) {
    timestampMs = Math.round(parseFloat(entity.time) * 1000.0);
  } else {
    timestampMs = Math.round((parseInt(frameId) / 25.0) * 1000.0);
  }
  
  const timeVal = (timestampMs / 1000.0).toFixed(2);
  const keyframeBase = window.KEYFRAME_BASE || 'http://localhost:8000/keyframes';
  const imgSrc = `${keyframeBase}/${video}/keyframes/keyframe_${frameId}.webp`;
  const ocrText = entity.ocr_text || result.ocr_text || '';
  const asrText = entity.asr_text || result.asr_text || '';

  let scoreVal = null;
  if (result && result.rerank_score !== undefined && result.rerank_score !== null) {
    scoreVal = parseFloat(result.rerank_score);
  } else if (result && result.distance !== undefined && result.distance !== null) {
    scoreVal = parseFloat(result.distance);
  } else if (result && result.score !== undefined && result.score !== null) {
    scoreVal = parseFloat(result.score);
  } else if (entity && entity.distance !== undefined && entity.distance !== null) {
    scoreVal = parseFloat(entity.distance);
  } else if (entity && entity.score !== undefined && entity.score !== null) {
    scoreVal = parseFloat(entity.score);
  }

  return { video, frameId, timeVal, timestampMs, imgSrc, frameInfo: `${video}-${timeVal}`, scoreVal, ocrText, asrText };
}

// Video frame list cache for instant stepping
const videoMapCache = new Map();

async function getVideoFrameMap(videoName) {
  if (!videoName) return { frames: [], times: {} };
  if (videoMapCache.has(videoName)) {
    return videoMapCache.get(videoName);
  }
  const csvBase = window.CSV_BASE || 'http://localhost:8000/keyframes/maps';
  const frames = [];
  const times = {};
  try {
    let res = await fetch(`${csvBase}/${videoName}_map.csv`);
    if (!res.ok) {
      res = await fetch(`${csvBase}/${videoName}.csv`);
    }
    if (res.ok) {
      const text = await res.text();
      const lines = text.trim().split('\n');
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (i === 0 && line.toLowerCase().includes('frameid')) continue;
        const parts = line.split(',');
        if (parts.length >= 2) {
          const fid = parseInt(parts[0].trim(), 10);
          const sec = parseFloat(parts[1].trim());
          if (!isNaN(fid)) {
            frames.push(fid);
            times[fid] = isNaN(sec) ? fid / 25.0 : sec;
          }
        }
      }
    }
  } catch (e) {
    console.warn("Could not load video map:", videoName, e);
  }
  const result = { frames, times };
  videoMapCache.set(videoName, result);
  return result;
}

async function stepCardFrame(imgDis, direction, event) {
  if (event) event.stopPropagation();
  const img = imgDis.querySelector('img');
  const inforEl = imgDis.querySelector('.infor');
  if (!img) return;

  const currentSrc = img.src || img.dataset.src;
  let videoName = '';
  let currentFid = 0;
  
  if (currentSrc) {
    const match = currentSrc.match(/\/([^\/]+)\/keyframes\/keyframe_(\d+)\./i) || 
                  currentSrc.match(/(L\d+_V\d+).*?keyframe_(\d+)\./i);
    if (match) {
      videoName = match[1];
      currentFid = parseInt(match[2], 10) || 0;
    } else {
      const parts = currentSrc.split('/');
      const kfIdx = parts.lastIndexOf('keyframes');
      if (kfIdx > 0 && parts[kfIdx - 1] && !parts[kfIdx - 1].includes(':')) {
        videoName = parts[kfIdx - 1];
        const fn = parts[parts.length - 1];
        currentFid = parseInt(fn.replace('keyframe_', '').replace(/\.[^.]+$/, ''), 10) || 0;
      }
    }
  }
  if (!videoName && inforEl) {
    videoName = inforEl.textContent.split('-')[0].trim();
  }
  videoName = (videoName || 'video').replace(/\.mp4$/i, '').trim();

  const mapData = await getVideoFrameMap(videoName);
  if (!mapData.frames || mapData.frames.length === 0) return;

  const curIdx = mapData.frames.indexOf(currentFid);
  let newIdx = (curIdx !== -1 ? curIdx : 0) + direction;
  if (newIdx < 0) newIdx = 0;
  if (newIdx >= mapData.frames.length) newIdx = mapData.frames.length - 1;

  const newFid = mapData.frames[newIdx];
  const newSec = mapData.times[newFid] !== undefined ? mapData.times[newFid] : (newFid / 25.0);
  const keyframeBase = window.KEYFRAME_BASE || 'http://localhost:8000/keyframes';
  const newSrc = `${keyframeBase}/${videoName}/keyframes/keyframe_${newFid}.webp`;
  const newFrameInfo = `${videoName}-${newSec.toFixed(2)}`;

  img.src = newSrc;
  img.dataset.src = newSrc;
  if (inforEl) inforEl.textContent = newFrameInfo;
  imgDis.dataset.timestampMs = Math.round(newSec * 1000);
  imgDis.dataset.frameId = newFid;

  imgDis.style.boxShadow = '0 0 16px #00F2FE';
  setTimeout(() => {
    imgDis.style.boxShadow = '';
  }, 220);
}

function formatTimeHMS(secondsFloat) {
  const totalSec = Math.max(0, Math.floor(parseFloat(secondsFloat) || 0));
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function createImageDiv(result, index) {
  const info = getEntityInfo(result);

  let topClass = '';
  if (index === 1) topClass = 'top-1';
  else if (index === 2) topClass = 'top-2';
  else if (index === 3) topClass = 'top-3';

  let scoreHtml = '';
  if (info.scoreVal !== null && !isNaN(info.scoreVal)) {
    const formattedScore = Math.abs(info.scoreVal) > 1 ? info.scoreVal.toFixed(1) : info.scoreVal.toFixed(3);
    scoreHtml = `<span class="score-badge" title="Score / Distance"><i class="fa-solid fa-chart-simple"></i> ${formattedScore}</span>`;
  }

  const timeFormatted = formatTimeHMS(info.timeVal);
  const timeBadgeHtml = `<span class="time-badge" style="position: absolute; top: 6px; left: 45px; background: rgba(15, 23, 42, 0.85); color: #38bdf8; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 700; border: 1px solid rgba(56, 189, 248, 0.4); z-index: 10;" title="Mốc thời gian video: ${timeFormatted} (${info.timeVal}s)"><i class="fa-regular fa-clock"></i> ${timeFormatted}</span>`;

  let ocrHtml = '';
  if (info.ocrText) {
    ocrHtml = `<div class="ocr-text-tag" title="Văn bản nhận diện (OCR): ${info.ocrText}"><i class="fa-solid fa-font"></i> ${info.ocrText}</div>`;
  }

  let asrHtml = '';
  if (info.asrText) {
    asrHtml = `<div class="ocr-text-tag" style="background: rgba(14, 165, 233, 0.4); border-color: rgba(56, 189, 248, 0.5); color: #bae6fd;" title="Giọng nói nhận diện (ASR): ${info.asrText}"><i class="fa-solid fa-microphone"></i> ${info.asrText}</div>`;
  }

  let trakeHtml = '';
  if (result.trake_stage) {
    const stageColors = ['#8B5CF6', '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#EC4899'];
    const color = stageColors[(result.trake_stage - 1) % stageColors.length];
    trakeHtml = `<div class="trake-stage-badge" title="Sự kiện ${result.trake_stage}" style="position: absolute; top: 30px; left: 6px; background: ${color}; color: white; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 800; z-index: 10; border: 1px solid rgba(255, 255, 255, 0.4); box-shadow: 0 2px 6px rgba(0,0,0,0.4);"><i class="fa-solid fa-clock"></i> Sự kiện ${result.trake_stage}</div>`;
  }

  const div = document.createElement('div');
  div.className = 'img-dis';
  div.dataset.index = index;
  div.dataset.video = info.video;
  div.dataset.frameId = info.frameId;
  div.dataset.timeSec = info.timeVal;
  div.dataset.timestampMs = info.timestampMs;
  div.dataset.ocr = info.ocrText;
  div.dataset.asr = info.asrText;
  const isTopView = index <= 30;
  div.innerHTML = `
    <span class="rank-badge ${topClass}" title="Thứ tự ưu tiên #${index}">#${index}</span>
    ${timeBadgeHtml}
    ${scoreHtml}
    ${ocrHtml}
    ${asrHtml}
    ${trakeHtml}
    <img alt="${info.frameInfo}" class="result" loading="${isTopView ? 'eager' : 'lazy'}" decoding="async" id="${index}"
      src="${info.imgSrc}" data-src="${info.imgSrc}">
    <div class="infor">${info.frameInfo}</div>
    <div class="card-step-btn prev-step" title="Frame kề trước trong video (←)" style="position: absolute; left: 4px; top: 50%; transform: translateY(-50%); width: 22px; height: 28px; background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(0, 242, 254, 0.4); border-radius: 4px; color: #00F2FE; display: flex; justify-content: center; align-items: center; cursor: pointer; z-index: 10; font-size: 11px; opacity: 0.85; transition: all 0.2s ease;"><i class="fa-solid fa-chevron-left"></i></div>
    <div class="card-step-btn next-step" title="Frame kề sau trong video (→)" style="position: absolute; right: 4px; top: 50%; transform: translateY(-50%); width: 22px; height: 28px; background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(0, 242, 254, 0.4); border-radius: 4px; color: #00F2FE; display: flex; justify-content: center; align-items: center; cursor: pointer; z-index: 10; font-size: 11px; opacity: 0.85; transition: all 0.2s ease;"><i class="fa-solid fa-chevron-right"></i></div>
    <div class="export_icon" title="Thêm vào danh sách xuất file / Nộp bài (+)" style="display: flex; justify-content: center; align-items: center; width: 24px; height: 24px; position: absolute; right: 5px; top: 5px; cursor: pointer; z-index: 10; background-color: rgba(16, 185, 129, 0.85); border: 1px solid rgba(255,255,255,0.25); border-radius: 4px; color: white;"><i class="fa-solid fa-plus" style="font-size: 13px;"></i></div>
    <div name="similarity_search" class="similarity_search" title="Tìm kiếm tương tự (Similarity Search)" style="display: flex; justify-content: center; align-items: center; width: 24px; height: 24px; position: absolute; right: 5px; top: 33px; cursor: pointer; z-index: 10; background-color: rgba(30, 41, 59, 0.85); border: 1px solid rgba(255,255,255,0.25); border-radius: 4px; color: white;"><i class="fa-solid fa-camera" style="font-size: 12px;"></i></div>
    <div name="fullscreen_zoom" class="fullscreen_zoom" title="Phóng to hình ảnh (Xem chi tiết)" style="display: flex; justify-content: center; align-items: center; width: 24px; height: 24px; position: absolute; right: 5px; top: 61px; cursor: pointer; z-index: 10; background-color: rgba(30, 41, 59, 0.85); border: 1px solid rgba(255,255,255,0.25); border-radius: 4px; color: white;"><i class="fa-solid fa-expand" style="font-size: 12px;"></i></div>
    <div name="timeline_explorer" class="timeline_explorer" title="Mở toàn bộ chuỗi frame của video này (Timeline Explorer)" style="display: flex; justify-content: center; align-items: center; width: 24px; height: 24px; position: absolute; right: 5px; top: 89px; cursor: pointer; z-index: 10; background-color: rgba(30, 41, 59, 0.85); border: 1px solid rgba(0, 242, 254, 0.5); border-radius: 4px; color: #00F2FE;"><i class="fa-solid fa-film" style="font-size: 11px;"></i></div>
  `;

  const img = div.querySelector('img');
  img.setAttribute('draggable', 'true');
  img.addEventListener('dragstart', drag);
  
  const prevStepBtn = div.querySelector('.prev-step');
  const nextStepBtn = div.querySelector('.next-step');
  if (prevStepBtn) prevStepBtn.addEventListener('click', (e) => stepCardFrame(div, -1, e));
  if (nextStepBtn) nextStepBtn.addEventListener('click', (e) => stepCardFrame(div, 1, e));

  const timelineBtn = div.querySelector('.timeline_explorer');
  if (timelineBtn) {
    timelineBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (typeof showVideoFrames === 'function') {
        showVideoFrames(div);
      }
    });
  }

  const exportIcon = div.querySelector('.export_icon');
  if (exportIcon) {
    exportIcon.addEventListener('click', (e) => {
      e.stopPropagation();
      const imagePath = img.src || img.dataset.src;
      const inforText = div.querySelector('.infor')?.textContent || info.frameInfo;
      const currentFid = div.dataset.frameId || info.frameId;
      const currentMs = div.dataset.timestampMs || info.timestampMs;
      addImageToExportArea(currentFid, imagePath, inforText, true, currentMs);
    });
  }

  return div;
}


// Update UI with search results
function updateRightPanel_list(results) {
  const listPhoto = document.getElementById("list-photo");
  if (!listPhoto) return [];

  const fragment = document.createDocumentFragment();
  const existingDivs = Array.from(listPhoto.children);

  const updatedDivs = results.map((result, index) => {
      const rankIndex = index + 1;
      const info = getEntityInfo(result);
      let div;

      if (index < existingDivs.length) {
          div = existingDivs[index];
          div.style.display = 'block';
          div.dataset.index = rankIndex;
          div.dataset.video = info.video;
          div.dataset.frameId = info.frameId;
          div.dataset.timeSec = info.timeVal;
          div.dataset.timestampMs = info.timestampMs;
          div.dataset.ocr = info.ocrText;
          div.dataset.asr = info.asrText;

          // Update rank badge
          let rankBadge = div.querySelector('.rank-badge');
          if (!rankBadge) {
              rankBadge = document.createElement('span');
              div.insertBefore(rankBadge, div.firstChild);
          }
          let topClass = 'rank-badge';
          if (rankIndex === 1) topClass += ' top-1';
          else if (rankIndex === 2) topClass += ' top-2';
          else if (rankIndex === 3) topClass += ' top-3';
          rankBadge.className = topClass;
          rankBadge.textContent = `#${rankIndex}`;
          rankBadge.title = `Thứ tự ưu tiên #${rankIndex}`;

          // Update score badge
          let scoreBadge = div.querySelector('.score-badge');
          if (info.scoreVal !== null && !isNaN(info.scoreVal)) {
              const formattedScore = Math.abs(info.scoreVal) > 1 ? info.scoreVal.toFixed(1) : info.scoreVal.toFixed(3);
              if (!scoreBadge) {
                  scoreBadge = document.createElement('span');
                  scoreBadge.className = 'score-badge';
                  scoreBadge.title = 'Score / Distance';
                  const firstImg = div.querySelector('img');
                  if (firstImg) {
                      div.insertBefore(scoreBadge, firstImg);
                  } else {
                      div.appendChild(scoreBadge);
                  }
              }
              scoreBadge.innerHTML = `<i class="fa-solid fa-chart-simple"></i> ${formattedScore}`;
              scoreBadge.style.display = 'flex';
          } else if (scoreBadge) {
              scoreBadge.style.display = 'none';
          }

          const img = div.querySelector('img');
          const infor = div.querySelector('.infor');
          if (img) {
              img.id = rankIndex;
              img.loading = rankIndex <= 30 ? 'eager' : 'lazy';
              img.decoding = 'async';
              img.dataset.src = info.imgSrc;
              img.src = info.imgSrc;
          }
          if (infor) {
              infor.textContent = info.frameInfo;
          }
      } else {
          div = createImageDiv(result, rankIndex);
          fragment.appendChild(div);
      }

      return div;
  });

  // Remove excess divs
  existingDivs.slice(results.length).forEach(div => div.remove());

  // Append new divs if any
  if (fragment.children.length > 0) {
      listPhoto.appendChild(fragment);
  }

  return updatedDivs;
}



//-----------------------------------------------------------------------------------------------------//

// Get current results from the right panel
function getCurrentResults() {
  return Array.from(document.querySelectorAll('.img-dis')).map(div => {
    const img = div.querySelector('img');
    const imgSrc = img ? (img.dataset.src || img.src || '') : '';
    
    // 1. Trích xuất Frame ID chuẩn xác từ dataset hoặc tên file keyframe_X.webp
    let frameId = 0;
    if (div.dataset.frameId !== undefined && div.dataset.frameId !== '') {
      frameId = parseInt(div.dataset.frameId, 10);
    } else if (imgSrc) {
      const match = imgSrc.match(/keyframe_(\d+)\./);
      if (match) frameId = parseInt(match[1], 10);
    }

    // 2. Trích xuất Video ID chuẩn xác
    let video = div.dataset.video || '';
    if (video && (video.includes(':') || video.toLowerCase() === 'keyframes')) video = '';
    if (!video && imgSrc) {
      const match = imgSrc.match(/\/([^\/]+)\/keyframes\/keyframe_\d+/i) || imgSrc.match(/(L\d+_V\d+)/i);
      if (match) video = match[1];
      else {
        const parts = imgSrc.split('/');
        const kfIdx = parts.lastIndexOf('keyframes');
        if (kfIdx > 0 && parts[kfIdx - 1] && !parts[kfIdx - 1].includes(':')) video = parts[kfIdx - 1];
      }
    }
    if (!video) {
      const inforText = div.querySelector('.infor')?.textContent || '';
      video = inforText.split('-')[0] || 'video';
    }
    video = video.replace(/\.mp4$/i, '').trim();

    return {
      entity: {
        path: imgSrc,
        video: video,
        video_id: video,
        frame_id: frameId,
        time: parseFloat(div.dataset.timeSec || 0)
      },
      frameId: frameId,
      videoName: video,
      src: imgSrc,
      score: parseFloat(div.querySelector('.score-badge')?.textContent || 0),
      id: img ? img.id : ''
    };
  });
}


// Group the results by video
function groupResultsByVideo(results) {
  return results.reduce((groups, result) => {
      const videoName = (result && result.entity) ? (result.entity.video_id || result.entity.video || 'video') : 'video';
      (groups[videoName] = groups[videoName] || []).push(result);
      return groups;
  }, {});
}

// Update the new right panel
function updateRightPanel_rows(results) {
  const imagesRows = document.getElementById('images-rows');
  imagesRows.innerHTML = ''; // Clear existing content

  const videoGroups = groupResultsByVideo(results);
  
  const fragment = document.createDocumentFragment();

  Object.entries(videoGroups).forEach(([videoName, videoResults], index) => {
      const videoSection = document.createElement('div');
      videoSection.className = 'group-frame';

      if (index > 0) {
          videoSection.appendChild(document.createElement('hr'));
      }

      const videoTitle = document.createElement('h3');
      videoTitle.textContent = videoName;
      videoSection.appendChild(videoTitle);

      const resultFragment = document.createDocumentFragment();
      videoResults.forEach((result) => {
          let originalIndex = results.findIndex(r => r === result || (r.id && r.id === result.id));
          if (originalIndex === -1) originalIndex = 0;
          const imgDiv = createImageDiv(result, originalIndex + 1);
          resultFragment.appendChild(imgDiv);
      });

      videoSection.appendChild(resultFragment);
      fragment.appendChild(videoSection);
  });

  imagesRows.appendChild(fragment);

  imagesRows.scrollTop = 0;
}

// Update both panels (hiển thị kết quả tìm kiếm)
function updateUIWithSearchResults(results) {
  if (!Array.isArray(results)) return;
  
  // Phát hiện xem đây có phải là kết quả của thuật toán TRAKE không
  const isTrake = results.length > 0 && results[0].trake_stage;
  
  // KIS & Q&A lay 80 frame. TRAKE lay 200 frame theo dung yeu cau
  const limit = isTrake ? 200 : 80;
  
  const slicedResults = results.slice(0, limit);
  updateRightPanel_list(slicedResults);
  updateRightPanel_rows(slicedResults);


  document.querySelector('.show-image-1').scrollTop = 0;
  document.querySelector('.show-image-2').scrollTop = 0;
  
  addImageEventListeners();
}


function addImageEventListeners() {
  document.querySelectorAll('.img-dis img').forEach(img => {
    img.addEventListener('dragstart', drag);
  });

  // Add middle-click event listener to all relevant containers
  document.querySelectorAll('.img-dis, .frame-container, .preview-image-wrapper, .current-preview-wrapper').forEach(container => {
    container.addEventListener('mousedown', handleMiddleClick);
  });
}





  
function cleanupSearchResults() {
  // Clear main content areas
  ['list-photo', 'images-rows'].forEach(id => {
    const element = document.getElementById(id);
    if (element) {
      if (typeof imageObserver !== 'undefined' && imageObserver) {
        element.querySelectorAll('img').forEach(img => imageObserver.unobserve(img));
      }
      element.innerHTML = '';
    }
  });

  // Reset scroll positions
  ['show-image-1', 'show-image-2'].forEach(className => {
    const element = document.querySelector(`.${className}`);
    if (element) element.scrollTop = 0;
  });
}