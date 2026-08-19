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
  const timeVal = entity.time !== undefined ? parseFloat(Number(entity.time).toFixed(2)) : frameId;
  const keyframeBase = window.KEYFRAME_BASE || 'http://localhost:8000/keyframes';
  const imgSrc = `${keyframeBase}/${video}/keyframes/keyframe_${frameId}.webp`;

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

  return { video, frameId, timeVal, imgSrc, frameInfo: `${video}-${timeVal}`, scoreVal };
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

  const div = document.createElement('div');
  div.className = 'img-dis';
  div.dataset.index = index;
  div.innerHTML = `
    <span class="rank-badge ${topClass}" title="Thứ tự ưu tiên #${index}">#${index}</span>
    ${scoreHtml}
    <img alt="${info.frameInfo}" class="result" loading="lazy" id="${index}"
      src="${info.imgSrc}" data-src="${info.imgSrc}">
    <div class="infor">${info.frameInfo}</div>
    <div name="similarity_search" class="similarity_search" title="Tìm kiếm tương tự (Similarity Search)" style="display: flex; justify-content: center; align-items: center; width: 22px; height: 22px; position: absolute; right: 5px; top: 5px; cursor: pointer; z-index: 10; background-color: rgba(0,0,0,0.5); border-radius: 4px;"><i class="fa-solid fa-camera" style="color: white; font-size: 12px;"></i></div>
    <div name="fullscreen_zoom" class="fullscreen_zoom" title="Phóng to hình ảnh" style="display: flex; justify-content: center; align-items: center; width: 22px; height: 22px; position: absolute; right: 5px; top: 32px; cursor: pointer; z-index: 10; background-color: rgba(0,0,0,0.5); border-radius: 4px;"><i class="fa-solid fa-expand" style="color: white; font-size: 12px;"></i></div>
    <div class="export_icon" title="Thêm vào danh sách xuất"></div>
  `;

  const img = div.querySelector('img');
  img.setAttribute('draggable', 'true');
  img.addEventListener('dragstart', drag);
  
  const exportIcon = div.querySelector('.export_icon');
  if (exportIcon) {
    exportIcon.addEventListener('click', () => {
      const imagePath = img.src || img.dataset.src;
      addImageToExportArea(info.frameId, imagePath, info.frameInfo);
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

// Update both panels (hiển thị 100 kết quả tìm kiếm)
function updateUIWithSearchResults(results) {
  const top100Results = Array.isArray(results) ? results.slice(0, 100) : [];
  updateRightPanel_list(top100Results);
  updateRightPanel_rows(top100Results);
  updateObjectList(top100Results);
  
  // If the object list is visible, update its content
  if (isObjectListVisible) {
    renderObjectList();
    // Ensure the object list content remains visible
    const objectListContent = document.querySelector('.object-list-content');
    if (objectListContent) {
      objectListContent.classList.add('show');
    }
  }


  document.querySelector('.show-image-1').scrollTop = 0;
  document.querySelector('.show-image-2').scrollTop = 0;
  
  addImageEventListeners();
}


function addImageEventListeners() {
  document.querySelectorAll('.img-dis img').forEach(img => {
    img.addEventListener('dragstart', drag);
  });

  document.querySelectorAll('.export_icon').forEach(icon => {
    icon.addEventListener('click', (event) => {
      const container = event.target.closest('.img-dis');
      const img = container.querySelector('img');
      const infor = container.querySelector('.infor');
      const frameId = infor.textContent.split('-')[1];
      const imageSrc = img.src;
      addImageToExportArea(frameId, imageSrc, infor.textContent);
    });
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
      // Remove all observers and event listeners
      element.querySelectorAll('img').forEach(img => imageObserver.unobserve(img));
      element.innerHTML = '';
    }
  });

  // Clear object list if exists
  const objectList = document.querySelector('.object-list-content');
  if (objectList) {
    objectList.innerHTML = '';
    objectList.classList.remove('show');
  }

  // Reset scroll positions
  ['show-image-1', 'show-image-2'].forEach(className => {
    const element = document.querySelector(`.${className}`);
    if (element) element.scrollTop = 0;
  });
}