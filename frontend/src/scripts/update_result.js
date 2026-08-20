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

  let ocrHtml = '';
  if (info.ocrText) {
    ocrHtml = `<div class="ocr-text-tag" title="Văn bản nhận diện (OCR): ${info.ocrText}"><i class="fa-solid fa-font"></i> ${info.ocrText}</div>`;
  }

  let asrHtml = '';
  if (info.asrText) {
    asrHtml = `<div class="ocr-text-tag" style="background: rgba(14, 165, 233, 0.4); border-color: rgba(56, 189, 248, 0.5); color: #bae6fd;" title="Giọng nói nhận diện (ASR): ${info.asrText}"><i class="fa-solid fa-microphone"></i> ${info.asrText}</div>`;
  }

  const div = document.createElement('div');
  div.className = 'img-dis';
  div.dataset.index = index;
  div.dataset.ocr = info.ocrText;
  div.dataset.asr = info.asrText;
  div.dataset.timestampMs = info.timestampMs;
  div.innerHTML = `
    <span class="rank-badge ${topClass}" title="Thứ tự ưu tiên #${index}">#${index}</span>
    ${scoreHtml}
    ${ocrHtml}
    ${asrHtml}
    <img alt="${info.frameInfo}" class="result" loading="lazy" id="${index}"
      src="${info.imgSrc}" data-src="${info.imgSrc}">
    <div class="infor">${info.frameInfo}</div>
    <div class="export_icon" title="Thêm vào danh sách xuất file / Nộp bài (+)" style="display: flex; justify-content: center; align-items: center; width: 24px; height: 24px; position: absolute; right: 5px; top: 5px; cursor: pointer; z-index: 10; background-color: rgba(16, 185, 129, 0.85); border: 1px solid rgba(255,255,255,0.25); border-radius: 4px; color: white;"><i class="fa-solid fa-plus" style="font-size: 13px;"></i></div>
    <div name="similarity_search" class="similarity_search" title="Tìm kiếm tương tự (Similarity Search)" style="display: flex; justify-content: center; align-items: center; width: 24px; height: 24px; position: absolute; right: 5px; top: 33px; cursor: pointer; z-index: 10; background-color: rgba(30, 41, 59, 0.85); border: 1px solid rgba(255,255,255,0.25); border-radius: 4px; color: white;"><i class="fa-solid fa-camera" style="font-size: 12px;"></i></div>
    <div name="fullscreen_zoom" class="fullscreen_zoom" title="Phóng to hình ảnh (Xem chi tiết)" style="display: flex; justify-content: center; align-items: center; width: 24px; height: 24px; position: absolute; right: 5px; top: 61px; cursor: pointer; z-index: 10; background-color: rgba(30, 41, 59, 0.85); border: 1px solid rgba(255,255,255,0.25); border-radius: 4px; color: white;"><i class="fa-solid fa-expand" style="font-size: 12px;"></i></div>
  `;

  const img = div.querySelector('img');
  img.setAttribute('draggable', 'true');
  img.addEventListener('dragstart', drag);
  
  const exportIcon = div.querySelector('.export_icon');
  if (exportIcon) {
    exportIcon.addEventListener('click', (e) => {
      e.stopPropagation();
      const imagePath = img.src || img.dataset.src;
      addImageToExportArea(info.frameId, imagePath, info.frameInfo, true, info.timestampMs);
      if (typeof showNotification === 'function') {
        showNotification(`Đã thêm #${index} (${info.frameInfo}) vào danh sách xuất!`, 'success');
      }
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
  return Array.from(document.querySelectorAll('.img-dis')).map(div => ({
    entity: {
      path: div.querySelector('img').dataset.src,
      video: div.querySelector('.infor').textContent.split('-')[0],
      frame_id: div.querySelector('.infor').textContent.split('-')[1]
    },
    id: div.querySelector('img').id
  }));
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

// Update both panels (hiển thị Top 100 kết quả tìm kiếm có độ chính xác cao nhất khớp với file nộp)
function updateUIWithSearchResults(results) {
  const top100Results = Array.isArray(results) ? results.slice(0, 100) : [];
  updateRightPanel_list(top100Results);
  updateRightPanel_rows(top100Results);


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