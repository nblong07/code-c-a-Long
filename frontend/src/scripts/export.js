//---------------------------------------------------------------------------------------------//
// AIC 2026 SUBMISSION PACKAGE & CSV EXPORT MANAGER
// Hỗ trợ đầy đủ 3 dạng: Textual KIS, Visual Q&A, và TRAKE
// Tự động kiểm tra định dạng và đóng gói submission.zip tại D:\code-c-a-Long
//---------------------------------------------------------------------------------------------//

let activeTask = 'kis';
let vqaInputs = {};
let exportedImages = [];

// LocalStorage key cho gói nộp bài
const SUBMISSION_PKG_KEY = 'aic_submission_package_v1';

/**
 * Lấy danh sách các câu query đã lưu trong gói
 */
function getStoredSubmissionPackage() {
  try {
    const raw = localStorage.getItem(SUBMISSION_PKG_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (e) {
    console.error("Failed to load submission package from storage:", e);
    return {};
  }
}

/**
 * Lưu danh sách các câu query vào localStorage và cập nhật badge
 */
function saveStoredSubmissionPackage(pkg) {
  try {
    localStorage.setItem(SUBMISSION_PKG_KEY, JSON.stringify(pkg));
    updateSubmissionBadge();
  } catch (e) {
    console.error("Failed to save submission package to storage:", e);
  }
}

/**
 * Cập nhật số lượng query trên Badge ở Header
 */
function updateSubmissionBadge() {
  const badge = document.getElementById('package-badge');
  if (!badge) return;
  const pkg = getStoredSubmissionPackage();
  const count = Object.keys(pkg).length;
  badge.textContent = count;
  badge.style.display = count > 0 ? 'inline-block' : 'none';
}

// Toggle visibility của Export Area bên phải
function toggleExportArea() {
  const exportArea = document.getElementById('export-area');
  const contentWrapper = document.querySelector('.content-wrapper');
  if (!exportArea || !contentWrapper) return;
  
  const isOpening = !exportArea.classList.contains('show');
  if (isOpening) {
    exportArea.classList.add('show');
    contentWrapper.classList.add('export-active');
    contentWrapper.style.width = '80%';
  } else {
    exportArea.classList.remove('show');
    contentWrapper.classList.remove('export-active');
    contentWrapper.style.width = '';
  }
}

function openExportAreaIfClosed() {
  const exportArea = document.getElementById('export-area');
  const contentWrapper = document.querySelector('.content-wrapper');
  if (exportArea && contentWrapper && !exportArea.classList.contains('show')) {
    exportArea.classList.add('show');
    contentWrapper.classList.add('export-active');
    contentWrapper.style.width = '80%';
  }
}

// Chuyển đổi giữa 3 Task: KIS, VQA (Q&A), TRAKE
function toggleTask(task) {
  activeTask = task;
  const kisBtn = document.getElementById('kis');
  const vqaBtn = document.getElementById('vqa');
  const trakeBtn = document.getElementById('trake-task-btn');
  const exportImages = document.getElementById('export-images');
  const vqaQuickBar = document.getElementById('vqa-quick-answer-bar');

  [kisBtn, vqaBtn, trakeBtn].forEach(b => { if (b) b.classList.remove('active'); });

  if (task === 'kis') {
    if (kisBtn) kisBtn.classList.add('active');
    if (exportImages) exportImages.classList.remove('vqa-mode');
    if (vqaQuickBar) vqaQuickBar.style.display = 'none';
  } else if (task === 'vqa' || task === 'qa') {
    activeTask = 'vqa';
    if (vqaBtn) vqaBtn.classList.add('active');
    if (exportImages) exportImages.classList.add('vqa-mode');
    if (vqaQuickBar) {
      vqaQuickBar.style.display = 'block';
      const commonInput = document.getElementById('vqa-common-answer');
      if (commonInput) setTimeout(() => commonInput.focus(), 100);
    }
  } else if (task === 'trake') {
    if (trakeBtn) trakeBtn.classList.add('active');
    if (exportImages) exportImages.classList.remove('vqa-mode');
    if (vqaQuickBar) vqaQuickBar.style.display = 'none';
  }

  // Tự động chuyển đổi layout tương ứng với Task
  const toggleSwitch = document.getElementById('mode-toggle');
  if (toggleSwitch) {
    if (task === 'trake') {
      if (!toggleSwitch.checked) {
        toggleSwitch.checked = true;
        toggleSwitch.dispatchEvent(new Event('change'));
      }
    } else {
      if (toggleSwitch.checked) {
        toggleSwitch.checked = false;
        toggleSwitch.dispatchEvent(new Event('change'));
      }
    }
  }

  updateExportArea();
}

// Xóa danh sách ảnh trong khay
function resetExportArea() {
  exportedImages = [];
  vqaInputs = {};
  activeTrakeCandidate = 1;
  trakeCandidateTabs = [1];
  const commonInput = document.getElementById('vqa-common-answer');
  if (commonInput) commonInput.value = '';
  updateExportArea();
}

function allowDrop(ev) {
  ev.preventDefault();
}

let activeTrakeCandidate = 1;
let trakeCandidateTabs = [1];

function selectTrakeCandidate(cId) {
  activeTrakeCandidate = cId;
  if (!trakeCandidateTabs.includes(cId)) {
    trakeCandidateTabs.push(cId);
    trakeCandidateTabs.sort((a, b) => a - b);
  }
  updateExportArea();
  if (typeof showNotification === 'function') {
    showNotification(`🎯 Đang chọn: Phương Án ${cId}. Bấm [+] để thêm sự kiện vào Phương Án ${cId}!`, 'info');
  }
}

function addNewTrakeCandidate() {
  const nextCId = trakeCandidateTabs.length > 0 ? Math.max(...trakeCandidateTabs) + 1 : 1;
  trakeCandidateTabs.push(nextCId);
  trakeCandidateTabs.sort((a, b) => a - b);
  activeTrakeCandidate = nextCId;
  updateExportArea();
  if (typeof showNotification === 'function') {
    showNotification(`✨ Đã mở Phương Án ${nextCId}! Bấm dấu [+] trên kết quả tìm kiếm để thêm sự kiện.`, 'success');
  }
}

function deleteTrakeCandidate(cId) {
  // 1. Xóa tất cả ảnh thuộc candidate này
  exportedImages = exportedImages.filter(img => (img.candidateId || 1) !== cId);
  
  // 2. Lấy danh sách các candidate ID còn lại theo thứ tự tăng dần
  const remainingTabs = trakeCandidateTabs.filter(id => id !== cId).sort((a, b) => a - b);
  
  // 3. Tự động đánh số lại liên tục (Renumber: 2 -> 1, 3 -> 2...)
  if (remainingTabs.length > 0) {
    const idMapping = {};
    const newTabs = [];
    remainingTabs.forEach((oldId, idx) => {
      const newId = idx + 1;
      idMapping[oldId] = newId;
      newTabs.push(newId);
    });

    // Cập nhật lại candidateId cho tất cả các ảnh còn lại trong khay
    exportedImages.forEach(img => {
      const oldCandId = img.candidateId || 1;
      if (idMapping[oldCandId]) {
        img.candidateId = idMapping[oldCandId];
      }
    });

    // Cập nhật lại danh sách tabs
    trakeCandidateTabs = newTabs;

    // Cập nhật lại tab đang chọn
    if (activeTrakeCandidate === cId) {
      activeTrakeCandidate = 1;
    } else if (idMapping[activeTrakeCandidate]) {
      activeTrakeCandidate = idMapping[activeTrakeCandidate];
    } else {
      activeTrakeCandidate = 1;
    }
  } else {
    trakeCandidateTabs = [1];
    activeTrakeCandidate = 1;
  }

  updateExportArea();
  if (typeof showNotification === 'function') {
    showNotification(`🗑️ Đã xóa Phương Án ${cId} & tự động đánh số lại danh sách (1, 2...)!`, 'info');
  }
}

// Render các thẻ ảnh trong Export Area và cập nhật thanh thống kê
function updateExportArea() {
  const exportImages = document.getElementById('export-images');
  const selectedCountEl = document.getElementById('export-selected-count');
  const targetCountEl = document.getElementById('export-target-count');

  if (selectedCountEl) selectedCountEl.textContent = exportedImages.length;
  if (targetCountEl) {
    const count = exportedImages.length;
    if (activeTask === 'trake') {
      targetCountEl.textContent = count > 0 ? `${count} frame` : 'Chưa có';
      targetCountEl.style.color = '#94A3B8';
    } else if (count === 0) {
      targetCountEl.textContent = 'Chưa có';
      targetCountEl.style.color = '#475569';
    } else if (count === 1) {
      targetCountEl.textContent = `${count} frame ✓ Tốt nhất`;
      targetCountEl.style.color = '#10B981';
    } else if (count <= 3) {
      targetCountEl.textContent = `${count} frame — OK`;
      targetCountEl.style.color = '#F59E0B';
    } else if (count <= 5) {
      targetCountEl.textContent = `${count} frame ⚠ Nhiều`;
      targetCountEl.style.color = '#F97316';
    } else {
      targetCountEl.textContent = `${count} frame ⛔ Quá nhiều`;
      targetCountEl.style.color = '#EF4444';
    }
  }

  if (!exportImages) return;

  // CHẾ ĐỘ TRAKE: HIỂN THỊ CÁC PHƯƠNG ÁN DỰ PHÒNG RÕ RÀNG VỚI NÚT THÊM PHƯƠNG ÁN 1, 2, 3...
  if (activeTask === 'trake') {
    // Đảm bảo các candidateId trong exportedImages có trong trakeCandidateTabs
    exportedImages.forEach(img => {
      const cId = img.candidateId || 1;
      if (!trakeCandidateTabs.includes(cId)) {
        trakeCandidateTabs.push(cId);
      }
    });
    trakeCandidateTabs.sort((a, b) => a - b);
    if (trakeCandidateTabs.length === 0) trakeCandidateTabs = [1];

    const tabsHtml = `
      <div class="trake-candidate-selector-bar" style="background: rgba(15, 23, 42, 0.95); border: 1.5px solid #38BDF8; border-radius: 8px; padding: 8px 10px; margin-bottom: 10px; box-shadow: 0 0 12px rgba(56, 189, 248, 0.15);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <span style="font-size: 11.5px; font-weight: 700; color: #38BDF8; display: flex; align-items: center; gap: 5px;">
            <i class="fa-solid fa-layer-group"></i> CÁC PHƯƠNG ÁN (TRAKE):
          </span>
          <button type="button" onclick="addNewTrakeCandidate()" style="background: linear-gradient(135deg, #00F2FE, #4FACFE); border: none; color: #0F172A; font-weight: 800; font-size: 10.5px; padding: 4px 10px; border-radius: 6px; cursor: pointer; display: flex; align-items: center; gap: 4px;">
            <i class="fa-solid fa-plus"></i> Thêm Phương Án
          </button>
        </div>
        <div style="display: flex; gap: 5px; flex-wrap: wrap;">
          ${trakeCandidateTabs.map(cId => {
            const count = exportedImages.filter(img => (img.candidateId || 1) === cId).length;
            const isActive = (cId === activeTrakeCandidate);
            const bg = isActive ? 'linear-gradient(135deg, rgba(0,242,254,0.35), rgba(168,85,247,0.35))' : 'rgba(30,41,59,0.8)';
            const border = isActive ? '1.5px solid #00F2FE' : '1px solid #475569';
            const color = isActive ? '#00F2FE' : '#94A3B8';
            return `
              <button type="button" onclick="selectTrakeCandidate(${cId})" style="background: ${bg}; border: ${border}; color: ${color}; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 5px; cursor: pointer; display: flex; align-items: center; gap: 4px;">
                ${isActive ? '🟢' : '⚪'} PA ${cId} <span style="font-size: 10px; opacity: 0.85;">(${count})</span>
              </button>
            `;
          }).join('')}
        </div>
      </div>
    `;

    const candidateCardsHtml = trakeCandidateTabs.map(cId => {
      const cFrames = exportedImages.map((img, origIdx) => ({ ...img, origIdx })).filter(img => (img.candidateId || 1) === cId);
      cFrames.sort((a, b) => a.frameId - b.frameId);
      const isActive = (cId === activeTrakeCandidate);
      const vName = cFrames.length > 0 ? (cFrames[0].videoName || 'Video') : '';

      const framesHtml = cFrames.length > 0 ? cFrames.map((fItem, seqIdx) => `
        <div class="export-image-container" style="position: relative; flex: 0 0 100px; margin: 0;">
          <div style="position: absolute; top: 3px; left: 3px; z-index: 2; background: rgba(0, 242, 254, 0.95); color: #0F172A; font-weight: 800; font-size: 9.5px; padding: 1px 5px; border-radius: 4px;">
            #${seqIdx + 1}
          </div>
          <img src="${fItem.src}" class="export-image" title="PA ${cId} - Sự kiện ${seqIdx + 1} (Frame ${fItem.frameId})" style="height: 70px; object-fit: cover;">
          <button class="delete-button" title="Xóa" onclick="deleteExportImage(${fItem.origIdx})">×</button>
          <div class="infor" style="font-size: 9.5px; padding: 2px 4px;">Frame ${fItem.frameId}</div>
        </div>
      `).join('') : `
        <div style="padding: 10px; text-align: center; color: #64748B; font-size: 11px; width: 100%; border: 1px dashed #334155; border-radius: 6px;">
          Phương Án ${cId} đang trống. Nhấp <strong>[+]</strong> trên kết quả tìm kiếm để thêm sự kiện vào đây.
        </div>
      `;

      return `
        <div class="trake-candidate-card" style="background: rgba(15, 23, 42, 0.9); border: ${isActive ? '2px solid #00F2FE' : '1.5px solid #475569'}; border-radius: 8px; padding: 8px 10px; margin-bottom: 10px; width: 100%; box-sizing: border-box;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 4px;">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 11.5px; font-weight: 700; color: ${isActive ? '#00F2FE' : '#C084FC'};">
                🎯 Phương Án ${cId}: <strong>${vName || '(Chưa chọn)'}</strong> <span style="font-size: 10.5px; color: #94A3B8; font-weight: normal;">(${cFrames.length} frame)</span>
              </span>
              ${isActive ? '<span style="background: rgba(16, 185, 129, 0.2); border: 1px solid #10B981; color: #34D399; font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 3px;">🟢 ĐANG CHỌN</span>' : ''}
            </div>
            <div style="display: flex; gap: 4px; align-items: center;">
              ${!isActive ? `
                <button type="button" onclick="selectTrakeCandidate(${cId})" style="background: rgba(56, 189, 248, 0.15); border: 1px solid #38BDF8; color: #38BDF8; font-size: 9.5px; font-weight: 700; padding: 2px 6px; border-radius: 4px; cursor: pointer;">
                  👉 Chọn
                </button>
              ` : ''}
              <button type="button" onclick="deleteTrakeCandidate(${cId})" title="Xóa Phương Án ${cId}" style="background: rgba(239, 68, 68, 0.2); border: 1px solid #EF4444; color: #FCA5A5; font-size: 9.5px; font-weight: 700; padding: 2px 6px; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center; gap: 3px;">
                <i class="fa-solid fa-trash"></i> Xóa
              </button>
            </div>
          </div>
          <div class="trake-frames-row" style="display: flex; gap: 6px; overflow-x: auto; padding-bottom: 2px;">
            ${framesHtml}
          </div>
        </div>
      `;
    }).join('');

    exportImages.innerHTML = `
      ${tabsHtml}
      ${candidateCardsHtml}
    `;
    return;
  }

  if (exportedImages.length === 0) {
    exportImages.innerHTML = `
      <div style="text-align: center; color: #64748B; padding: 32px 10px; font-size: 11.5px;">
        <i class="fa-solid fa-photo-film" style="font-size: 24px; margin-bottom: 8px; opacity: 0.35; display: block;"></i>
        Chưa có ảnh nào. Bấm <strong>[+]</strong> trên kết quả để thêm vào khay.
      </div>
    `;
    return;
  }

  const htmlContent = exportedImages.map((img, index) => {
    const frameAns = vqaInputs[img.frameId] || '';
    return `
    <div class="export-image-container">
      <img src="${img.src}" class="export-image" title="${img.frameInfo || img.frameId}">
      <button class="delete-button" title="Xóa" onclick="deleteExportImage(${index})">×</button>
      <div class="infor">${img.frameInfo}</div>
      ${activeTask === 'vqa' ? `
        <div class="vqa-card-box" style="margin-top: 5px; display: flex; flex-direction: column; gap: 3px; width: 100%;">
          <textarea 
            class="vqa-input" 
            id="vqa-input-${img.frameId}"
            placeholder="Đáp án 1 | Đáp án 2 | ..." 
            title="Nhập đáp án, cách nhau bởi dấu |"
            oninput="handleVqaCardInput(${img.frameId}, this.value, this)"
            rows="2"
            style="width: 100%; box-sizing: border-box; font-size: 12px; line-height: 1.45; padding: 6px 8px; background: #0B1120; border: 1.5px solid #38BDF8; border-radius: 6px; color: #FFFFFF; font-weight: 600; resize: vertical; min-height: 48px; word-wrap: break-word; white-space: pre-wrap;"
          >${frameAns}</textarea>
          <div id="vqa-chips-${img.frameId}" class="vqa-chips-container" style="display: flex; flex-wrap: wrap; gap: 3px; margin-top: 2px;">
            ${renderVqaChipsHtml(img.frameId, frameAns)}
          </div>
        </div>
      ` : ''}
    </div>
  `;
  }).join('');
  
  exportImages.innerHTML = htmlContent;
}

function renderVqaChipsHtml(frameId, rawText) {
  if (!rawText || !rawText.trim()) return '';
  const parts = rawText.split(/[|;\n]/).map(s => s.trim()).filter(Boolean);
  if (parts.length === 0) return '';
  
  return parts.map((ans, idx) => {
    const isTop1 = (idx === 0);
    const bg = isTop1 ? 'linear-gradient(135deg, rgba(0,242,254,0.3), rgba(16,185,129,0.3))' : 'rgba(30,41,59,0.8)';
    const border = isTop1 ? '1px solid #00F2FE' : '1px solid #475569';
    const color = isTop1 ? '#00F2FE' : '#94A3B8';
    const star = isTop1 ? '★ #1' : `#${idx + 1}`;
    
    return `
      <span 
        class="vqa-priority-chip" 
        title="Đặt '${ans}' làm đáp án #1"
        onclick="setVqaTopPriority(${frameId}, ${idx})"
        style="display: inline-flex; align-items: center; gap: 3px; font-size: 9.5px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background: ${bg}; border: ${border}; color: ${color}; cursor: pointer; transition: all 0.2s ease;"
      >
        <span>${star}:</span> <strong>${ans}</strong>
      </span>
    `;
  }).join('');
}

function setVqaTopPriority(frameId, clickedIdx) {
  const currentVal = vqaInputs[frameId] || (document.getElementById('vqa-common-answer')?.value || '');
  const parts = currentVal.split(/[|;\n]/).map(s => s.trim()).filter(Boolean);
  if (clickedIdx >= 0 && clickedIdx < parts.length) {
    const selected = parts.splice(clickedIdx, 1)[0];
    parts.unshift(selected); // Đưa lên đầu làm Ưu tiên 1
    const newVal = parts.join(' | ');
    vqaInputs[frameId] = newVal;
    
    const inp = document.getElementById(`vqa-input-${frameId}`);
    if (inp) {
      inp.value = newVal;
      inp.style.height = 'auto';
      inp.style.height = Math.max(48, inp.scrollHeight) + 'px';
    }
    
    const chipsDiv = document.getElementById(`vqa-chips-${frameId}`);
    if (chipsDiv) chipsDiv.innerHTML = renderVqaChipsHtml(frameId, newVal);

    if (typeof showNotification === 'function') {
      showNotification(`🎯 Đã chọn '${selected}' làm Ưu Tiên 1 cho Frame ${frameId}!`, 'success');
    }
  }
}

function handleVqaCardInput(frameId, val, textareaEl) {
  vqaInputs[frameId] = val;
  if (textareaEl) {
    textareaEl.style.height = 'auto';
    textareaEl.style.height = Math.max(48, textareaEl.scrollHeight) + 'px';
  }
  const chipsDiv = document.getElementById(`vqa-chips-${frameId}`);
  if (chipsDiv) {
    chipsDiv.innerHTML = renderVqaChipsHtml(frameId, val);
  }
}

function applyVqaAnswerToCards(ans) {
  if (!ans) return;
  exportedImages.forEach(img => {
    vqaInputs[img.frameId] = ans;
    const inp = document.getElementById(`vqa-input-${img.frameId}`);
    if (inp) {
      inp.value = ans;
      inp.style.height = 'auto';
      inp.style.height = Math.max(48, inp.scrollHeight) + 'px';
    }
    const chipsDiv = document.getElementById(`vqa-chips-${img.frameId}`);
    if (chipsDiv) chipsDiv.innerHTML = renderVqaChipsHtml(img.frameId, ans);
  });
  const commonInput = document.getElementById('vqa-common-answer');
  if (commonInput) commonInput.value = ans;
}

function updateVqaInput(frameId, vqaInput) {
  vqaInputs[frameId] = vqaInput;
}

function deleteExportImage(index) {
  exportedImages.splice(index, 1);
  updateExportArea();
}

function deleteTrakeVideoGroup(videoName) {
  exportedImages = exportedImages.filter(img => {
    const { videoName: vName } = extractVideoAndFrameId(img);
    return (vName || '').toLowerCase() !== (videoName || '').toLowerCase();
  });
  updateExportArea();
}

function addImageToExportArea(frameId, imageSrc, frameInfo, shouldBroadcast = true, timestampMs = null) {
  let fid = parseInt(frameId, 10);
  if (isNaN(fid) || fid <= 0) {
    if (imageSrc) {
      const match = imageSrc.match(/keyframe_(\d+)\./);
      if (match) fid = parseInt(match[1], 10);
    }
  }
  if (isNaN(fid)) fid = 0;

  let videoName = '';
  if (frameInfo && typeof frameInfo === 'string') {
    const v = frameInfo.split('-')[0].trim();
    if (v && !v.includes(':') && v.toLowerCase() !== 'video' && !v.toLowerCase().includes('localhost')) {
      videoName = v;
    }
  }
  if (!videoName && imageSrc) {
    const match = imageSrc.match(/\/([^\/]+)\/keyframes\/keyframe_\d+/i) || 
                  imageSrc.match(/(L\d+_V\d+)/i) || 
                  imageSrc.match(/\/([^\/]+)\/keyframe_\d+/i);
    if (match && match[1] && !match[1].includes(':') && match[1].toLowerCase() !== 'keyframes') {
      videoName = match[1];
    } else {
      const parts = imageSrc.split('/');
      const kfIdx = parts.lastIndexOf('keyframes');
      if (kfIdx > 0 && parts[kfIdx - 1] && !parts[kfIdx - 1].includes(':') && parts[kfIdx - 1].toLowerCase() !== 'keyframes') {
        videoName = parts[kfIdx - 1];
      } else {
        videoName = parts[parts.length - 3] || '';
      }
    }
  }
  videoName = (videoName || 'video').replace(new RegExp('\\.mp4$', 'i'), '').trim();

  const pathParts = (imageSrc || '').split('/');
  const videoFramePart = pathParts.length >= 2
    ? `${pathParts[pathParts.length - 2]}/${pathParts[pathParts.length - 1].split('.')[0]}`
    : `${videoName}/keyframe_${fid}`;

  const candidateId = (activeTask === 'trake') ? (activeTrakeCandidate || 1) : 1;

  // --- Giới hạn số frame cho KIS / Q&A (không áp dụng cho TRAKE) ---
  if (activeTask !== 'trake') {
    const currentCount = exportedImages.filter(img => (img.candidateId || 1) === 1).length;
    const KIS_WARN_LIMIT = 5;   // Cảnh báo khi > 5 frame
    const KIS_HARD_LIMIT = 10;  // Chặn cứng khi > 10 frame

    if (currentCount >= KIS_HARD_LIMIT) {
      if (typeof showNotification === 'function') {
        showNotification(`🚫 Giới hạn ${KIS_HARD_LIMIT} frame cho KIS/Q&A! Xóa bớt frame trước khi thêm mới.`, 'error');
      }
      return false;
    }

    if (currentCount >= KIS_WARN_LIMIT) {
      if (typeof showNotification === 'function') {
        showNotification(`⚠️ Đã có ${currentCount} frame — điểm cao nhất khi chỉ chọn frame đúng nhất!`, 'info');
      }
    }
  }

  // Kiểm tra xem frame này của cùng video đã có trong danh sách/candidate này chưa
  const existingImageIndex = exportedImages.findIndex(img => {
    const imgVid = (img.videoName || (img.frameInfo || '').split('-')[0]).replace(new RegExp('\\.mp4$', 'i'), '').trim();
    const imgCand = img.candidateId || 1;
    if (activeTask === 'trake') {
      return imgCand === candidateId && img.frameId === fid && (imgVid.toLowerCase() === videoName.toLowerCase());
    }
    return img.frameId === fid && (imgVid.toLowerCase() === videoName.toLowerCase());
  });

  if (existingImageIndex === -1) {
    if (timestampMs === null || timestampMs === undefined) {
      const timeParts = (frameInfo || '').split('-');
      if (timeParts.length > 1 && !isNaN(parseFloat(timeParts[1])) && parseFloat(timeParts[1]) > 0) {
        timestampMs = Math.round(parseFloat(timeParts[1]) * 1000.0);
      } else {
        timestampMs = Math.round((fid / 25.0) * 1000.0);
      }
    }
    exportedImages.push({ frameId: fid, videoFramePart, videoName, src: imageSrc, frameInfo, timestampMs, candidateId });
    openExportAreaIfClosed();
    updateExportArea();
    if (typeof showNotification === 'function') {
      const totalNow = exportedImages.filter(img => (img.candidateId || 1) === candidateId).length;
      const candMsg = (activeTask === 'trake') ? ` [PA ${candidateId}]` : ` (${totalNow} frame trong khay)`;
      showNotification(`✅ Đã thêm ${videoName} / Frame ${fid}${candMsg}`, 'success');
    }
    return true;
  } else {
    if (typeof showNotification === 'function') {
      showNotification(`Frame ${fid} (${videoName}) đã có trong khay rồi!`, 'info');
    }
    return false;
  }
}

//---------------------------------------------------------------------------------------------//
// CSV GENERATION ENGINES (CHỈ XUẤT CÁC ẢNH & ĐÁP ÁN NGƯỜI DÙNG ĐÃ CHỌN)
//---------------------------------------------------------------------------------------------//

/**
 * Helper: Trích xuất chuẩn xác VideoName và FrameID từ bất kỳ item (result hoặc exportImage)
 */
function extractVideoAndFrameId(item) {
  let videoName = item.videoName || (item.entity ? (item.entity.video_id || item.entity.video) : '');
  if (videoName && (videoName.includes(':') || videoName.toLowerCase() === 'keyframes' || videoName.toLowerCase().includes('localhost'))) {
    videoName = '';
  }

  let frameId = item.frameId !== undefined ? parseInt(item.frameId, 10) : (item.entity ? parseInt(item.entity.frame_id, 10) : 0);

  // Fallback nếu frameId là NaN hoặc <= 0
  if ((isNaN(frameId) || frameId <= 0) && item.src) {
    const match = item.src.match(/keyframe_(\d+)\./);
    if (match) frameId = parseInt(match[1], 10);
  }
  if ((isNaN(frameId) || frameId <= 0) && item.entity && item.entity.path) {
    const match = item.entity.path.match(/keyframe_(\d+)\./);
    if (match) frameId = parseInt(match[1], 10);
  }

  // Fallback videoName
  if (!videoName && item.frameInfo) {
    const v = item.frameInfo.split('-')[0].trim();
    if (v && !v.includes(':') && v.toLowerCase() !== 'video' && !v.toLowerCase().includes('localhost')) {
      videoName = v;
    }
  }
  if (!videoName && item.src) {
    const match = item.src.match(/\/([^\/]+)\/keyframes\/keyframe_\d+/i) || 
                  item.src.match(/(L\d+_V\d+)/i) || 
                  item.src.match(/\/([^\/]+)\/keyframe_\d+/i);
    if (match && match[1] && !match[1].includes(':') && match[1].toLowerCase() !== 'keyframes') {
      videoName = match[1];
    } else {
      const parts = item.src.split('/');
      const kfIdx = parts.lastIndexOf('keyframes');
      if (kfIdx > 0 && parts[kfIdx - 1] && !parts[kfIdx - 1].includes(':') && parts[kfIdx - 1].toLowerCase() !== 'keyframes') {
        videoName = parts[kfIdx - 1];
      } else {
        videoName = parts[parts.length - 3] || '';
      }
    }
  }
  if (!videoName && item.entity && item.entity.path) {
    const match = item.entity.path.match(/\/([^\/]+)\/keyframes\/keyframe_\d+/i) || 
                  item.entity.path.match(/(L\d+_V\d+)/i);
    if (match && match[1]) {
      videoName = match[1];
    }
  }

  videoName = (videoName || 'video').replace(new RegExp('\\.mp4$', 'i'), '').trim();
  if (isNaN(frameId)) frameId = 0;

  return { videoName, frameId };
}

/**
 * 1. Sinh nội dung CSV cho Textual KIS:
 * Format: <video_name>,<frame_id> (Chỉ xuất các ảnh người dùng đã chọn bằng tay)
 */
function generateKisCSV() {
  if (exportedImages.length === 0) {
    alert("⚠️ Bạn chưa chọn ảnh nào trong khay nộp bài! Hãy bấm dấu [+] trên các ảnh kết quả để chọn.");
    return "";
  }

  const seen = new Set();
  const uniqueRows = [];

  function parseItemToRow(item) {
    const { videoName, frameId } = extractVideoAndFrameId(item);
    const key = `${videoName.toLowerCase()}_${frameId}`;
    return { key, row: `${videoName},${frameId}` };
  }

  // CHỈ NỘP CÁC ẢNH NGƯỜI DÙNG ĐÃ CHỌN
  for (const img of exportedImages) {
    const { key, row } = parseItemToRow(img);
    if (!seen.has(key)) {
      seen.add(key);
      uniqueRows.push(row);
    }
  }

  return uniqueRows.join('\n');
}

/**
 * 2. Sinh nội dung CSV cho Visual Q&A:
 * Format: <video_name>,<frame_id>,"<answer>" (Chỉ xuất các ảnh người dùng đã chọn kết hợp với các biến thể đáp án)
 */
function generateVqaCSV() {
  if (exportedImages.length === 0) {
    alert("⚠️ Bạn chưa chọn frame nào để xuất Q&A! Hãy bấm dấu [+] trên ảnh kết quả.");
    return "";
  }

  const commonAnswerRaw = (document.getElementById('vqa-common-answer')?.value || '').trim();
  const seen = new Set();
  const uniqueRows = [];

  function splitAnswers(rawText) {
    if (!rawText) return [];
    return rawText.split(/[|;\n]/).map(s => s.trim()).filter(Boolean);
  }

  function getCommonAnswers() {
    const arr = splitAnswers(commonAnswerRaw);
    return arr.length > 0 ? arr : ["0"];
  }

  function getItemAnswers(item) {
    const perFrameRaw = (item.frameId !== undefined ? vqaInputs[item.frameId] : '') || '';
    const perFrameArr = splitAnswers(perFrameRaw);
    if (perFrameArr.length > 0) return perFrameArr;
    return getCommonAnswers();
  }

  // XUẤT TUẦN TỰ THEO TỪNG FRAME: XONG HẾT ĐÁP ÁN FRAME 1 RỒI MỚI TỚI FRAME 2
  for (const img of exportedImages) {
    const { videoName, frameId } = extractVideoAndFrameId(img);
    const candidateAnswers = getItemAnswers(img);

    for (let ans of candidateAnswers) {
      ans = ans.substring(0, 100).replaceAll('"', '""');
      const key = `${videoName.toLowerCase()}_${frameId}_${ans.toLowerCase()}`;
      if (!seen.has(key)) {
        seen.add(key);
        uniqueRows.push(`${videoName},${frameId},"${ans}"`);
      }
    }
  }

  return uniqueRows.join('\n');
}

/**
 * 3. Sinh nội dung CSV cho TRAKE:
 * Format: <video_name>,<frame_1>,<frame_2>,...,<frame_N> (Chỉ xuất các chuỗi frame thuộc các video mà người dùng đã chọn)
 */
function generateTrakeCSV() {
  if (exportedImages.length === 0) {
    alert("⚠️ Bạn chưa chọn chuỗi frame nào cho TRAKE! Hãy chọn các frame theo thứ tự thời gian.");
    return "";
  }

  const rows = [];
  const processedCIds = Array.from(new Set(exportedImages.map(img => img.candidateId || 1))).sort((a, b) => a - b);
  
  processedCIds.forEach(cId => {
    const cFrames = exportedImages.filter(img => (img.candidateId || 1) === cId);
    if (cFrames.length > 0) {
      const { videoName } = extractVideoAndFrameId(cFrames[0]);
      const frames = Array.from(new Set(cFrames.map(f => extractVideoAndFrameId(f).frameId).filter(f => f > 0))).sort((a, b) => a - b);
      if (videoName && frames.length > 0) {
        if (frames.length < 2) {
          alert(`⚠️ Cảnh báo: Video ${videoName} chỉ có ${frames.length} frame được chọn! TRAKE yêu cầu số frame bằng ĐÚNG số sự kiện (ví dụ 4 sự kiện cần đúng 4 frame). Vui lòng chọn thêm ảnh!`);
        }
        rows.push(videoName + ',' + frames.join(','));
      }
    }
  });

  if (rows.length === 0) {
    return generateKisCSV();
  }

  return rows.join('\n');
}

//---------------------------------------------------------------------------------------------//
// GỢI Ý TÊN FILE & LƯU VÀO GÓI
//---------------------------------------------------------------------------------------------//

function getSuggestedFileName() {
  const pkg = getStoredSubmissionPackage();
  const count = Object.keys(pkg).length + 1;
  
  if (activeTask === 'kis') {
    return `query-${count}-kis.csv`;
  } else if (activeTask === 'vqa' || activeTask === 'qa') {
    return `query-${count}-qa.csv`;
  } else if (activeTask === 'trake') {
    return `query-${count}-trake.csv`;
  }
  return `query-${count}-kis.csv`;
}

/**
 * Mở modal xác nhận lưu query / xuất file
 */
function openExportConfirmModal() {
  const modal = document.getElementById('exportModal');
  const filenameInput = document.getElementById('filenameInput');
  if (modal && filenameInput) {
    filenameInput.value = getSuggestedFileName();
    modal.style.display = 'block';
    filenameInput.focus();
  }
}

/**
 * Lưu câu truy vấn hiện tại vào Gói Nộp Bài (Submission Package)
 */
function saveCurrentQueryToPackage(fileName) {
  if (!fileName) fileName = getSuggestedFileName();
  if (!fileName.endsWith('.csv')) fileName += '.csv';

  let csvContent = "";
  let taskType = activeTask;

  if (activeTask === 'kis') {
    csvContent = generateKisCSV();
  } else if (activeTask === 'vqa' || activeTask === 'qa') {
    csvContent = generateVqaCSV();
    taskType = 'qa';
  } else if (activeTask === 'trake') {
    csvContent = generateTrakeCSV();
    taskType = 'trake';
  }

  if (!csvContent) return;

  const lines = csvContent.split('\n').filter(l => l.trim());
  const pkg = getStoredSubmissionPackage();
  
  pkg[fileName] = {
    filename: fileName,
    type: taskType,
    content: csvContent,
    rowCount: lines.length,
    savedAt: new Date().toLocaleTimeString('vi-VN')
  };

  saveStoredSubmissionPackage(pkg);

  if (typeof showNotification === 'function') {
    showNotification(`✅ Đã lưu ${fileName} (${lines.length} dòng) vào Gói nộp bài!`, 'success');
  }

  // Tự động dọn dẹp khay xuất để sẵn sàng làm câu tiếp theo
  resetExportArea();
  
  // Đóng modal
  const modal = document.getElementById('exportModal');
  if (modal) modal.style.display = 'none';
}

function downloadCSV(csvContent, fileName) {
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

//---------------------------------------------------------------------------------------------//
// SUBMISSION PACKAGE MODAL UI & AUTO-ZIP PACKING
//---------------------------------------------------------------------------------------------//

function openSubmissionPackageModal() {
  const modal = document.getElementById('submissionPackageModal');
  if (!modal) return;
  renderSubmissionPackageUI();
  modal.style.display = 'flex';
}

function closeSubmissionPackageModal() {
  const modal = document.getElementById('submissionPackageModal');
  if (modal) modal.style.display = 'none';
}

function renderSubmissionPackageUI() {
  const container = document.getElementById('pkg-query-list');
  const countEl = document.getElementById('pkg-total-count');
  if (!container) return;

  const pkg = getStoredSubmissionPackage();
  const queryKeys = Object.keys(pkg);

  if (countEl) countEl.textContent = `${queryKeys.length} câu truy vấn`;

  if (queryKeys.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; color: #64748B; padding: 35px 15px; font-size: 13px;">
        <i class="fa-solid fa-folder-open" style="font-size: 32px; margin-bottom: 12px; opacity: 0.4; display: block;"></i>
        Chưa có câu truy vấn nào được lưu vào gói.<br>
        Sau khi tìm kiếm mỗi query, hãy bấm <strong>"➕ Lưu Query"</strong> ở khay bên phải để thêm vào đây!
      </div>
    `;
    return;
  }

  container.innerHTML = queryKeys.map(key => {
    const item = pkg[key];
    const typeClass = (item.type || 'kis').toLowerCase();
    const typeLabel = typeClass.toUpperCase();

    return `
      <div class="pkg-query-item">
        <div class="pkg-query-left">
          <span class="pkg-type-badge ${typeClass}">${typeLabel}</span>
          <div>
            <span class="pkg-query-name">${item.filename}</span>
            <span class="pkg-query-meta">(${item.rowCount} dòng • Lúc ${item.savedAt || 'vừa xong'})</span>
          </div>
        </div>
        <div class="pkg-query-actions">
          <button class="pkg-action-btn edit" title="Đổi tên câu truy vấn này" onclick="renameQueryInPackage('${item.filename}')">
            <i class="fa-solid fa-pen-to-square"></i> Đổi tên
          </button>
          <button class="pkg-action-btn" title="Xem trước file CSV" onclick="previewQueryCSV('${item.filename}')">
            <i class="fa-solid fa-eye"></i> Xem
          </button>
          <button class="pkg-action-btn" title="Tải file CSV này về máy" onclick="downloadSingleQueryCSV('${item.filename}')">
            <i class="fa-solid fa-download"></i> Tải
          </button>
          <button class="pkg-action-btn delete" title="Xóa câu này khỏi gói" onclick="deleteQueryFromPackage('${item.filename}')">
            <i class="fa-solid fa-trash-can"></i>
          </button>
        </div>
      </div>
    `;
  }).join('');
}

/**
 * Đổi tên câu truy vấn đã lưu trong Gói Nộp Bài
 */
function renameQueryInPackage(oldFilename) {
  const pkg = getStoredSubmissionPackage();
  const item = pkg[oldFilename];
  if (!item) return;

  const currentBaseName = oldFilename.replace(new RegExp('\\.csv$', 'i'), '');
  const newNameRaw = prompt(`Nhập tên mới cho file truy vấn (Hiện tại: ${currentBaseName}):\nVí dụ: query-p1-1-kis`, currentBaseName);
  
  if (!newNameRaw || !newNameRaw.trim()) return;

  let newFilename = newNameRaw.trim();
  if (!newFilename.toLowerCase().endsWith('.csv')) {
    newFilename += '.csv';
  }

  if (newFilename === oldFilename) return;

  if (pkg[newFilename]) {
    if (!confirm(`⚠️ File "${newFilename}" đã tồn tại trong gói nộp bài. Bạn có muốn ghi đè lên file đó không?`)) {
      return;
    }
  }

  // Cập nhật thuộc tính
  delete pkg[oldFilename];
  item.filename = newFilename;
  
  // Tự động nhận diện loại task theo hậu tố tên file
  const lowerName = newFilename.toLowerCase();
  if (lowerName.includes('-kis')) item.type = 'kis';
  else if (lowerName.includes('-qa') || lowerName.includes('-vqa')) item.type = 'qa';
  else if (lowerName.includes('-trake')) item.type = 'trake';

  pkg[newFilename] = item;
  saveStoredSubmissionPackage(pkg);
  renderSubmissionPackageUI();

  if (typeof showNotification === 'function') {
    showNotification(`✏️ Đã đổi tên thành công: ${oldFilename} ➔ ${newFilename}`, 'success');
  }
}

function previewQueryCSV(filename) {
  const pkg = getStoredSubmissionPackage();
  const item = pkg[filename];
  if (!item) return;

  const previewModal = document.getElementById('csvPreviewModal');
  const previewTitle = document.getElementById('csvPreviewTitle');
  const previewContent = document.getElementById('csvPreviewContent');

  if (previewModal && previewTitle && previewContent) {
    previewTitle.textContent = `Nội dung file: ${filename} (${item.rowCount} dòng)`;
    previewContent.textContent = item.content;
    previewModal.style.display = 'flex';
  }
}

function closeCsvPreviewModal() {
  const previewModal = document.getElementById('csvPreviewModal');
  if (previewModal) previewModal.style.display = 'none';
}

function downloadSingleQueryCSV(filename) {
  const pkg = getStoredSubmissionPackage();
  const item = pkg[filename];
  if (item && item.content) {
    downloadCSV(item.content, filename);
  }
}

function deleteQueryFromPackage(filename) {
  const pkg = getStoredSubmissionPackage();
  delete pkg[filename];
  saveStoredSubmissionPackage(pkg);
  renderSubmissionPackageUI();
  if (typeof showNotification === 'function') {
    showNotification(`Đã xóa ${filename} khỏi gói nộp bài!`, 'info');
  }
}

function clearSubmissionPackage() {
  if (confirm("Bạn có chắc chắn muốn xóa toàn bộ các câu truy vấn trong gói nộp bài không?")) {
    localStorage.removeItem(SUBMISSION_PKG_KEY);
    updateSubmissionBadge();
    renderSubmissionPackageUI();
    // Gửi lệnh xóa phía backend
    fetch('http://localhost:8000/api/submission/clear', { method: 'POST' }).catch(() => {});
    if (typeof showNotification === 'function') {
      showNotification("Đã làm sạch toàn bộ gói nộp bài!", 'success');
    }
  }
}

/**
 * ĐÓNG GÓI SUBMISSION.ZIP QUA BACKEND (Tự động nén vào D:\code-c-a-Long\submission.zip)
 */
async function packAndZipSubmission() {
  const pkg = getStoredSubmissionPackage();
  const queryKeys = Object.keys(pkg);

  if (queryKeys.length === 0) {
    alert("⚠️ Gói nộp bài đang trống! Hãy tìm kiếm và lưu ít nhất 1 câu truy vấn trước khi nén zip.");
    return;
  }

  const queriesPayload = queryKeys.map(k => ({
    filename: pkg[k].filename,
    content: pkg[k].content,
    query_type: pkg[k].type
  }));

  const packBtn = document.getElementById('btn-pack-zip-modal');
  if (packBtn) {
    packBtn.disabled = true;
    packBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang nén file zip...';
  }

  try {
    const response = await fetch('http://localhost:8000/api/submission/pack', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        queries: queriesPayload,
        zip_filename: 'submission.zip'
      })
    });

    if (response.ok) {
      const data = await response.json();
      const zipPath = data.zip_path || 'D:\\code-c-a-Long\\submission.zip';
      
      alert(`🎉 ĐÃ ĐÓNG GÓI THÀNH CÔNG ${data.total_queries} QUERIES!\n\n📁 File ZIP đã sẵn sàng tại:\n${zipPath}\n\n👉 Cấu trúc hợp lệ 100%: Có thư mục con "submission/" chứa đầy đủ các file CSV. Bạn chỉ cần vào thư mục này để nộp lên Web BTC!`);
      
      if (typeof showNotification === 'function') {
        showNotification(`🎉 Đã nén thành công submission.zip tại D:\\code-c-a-Long!`, 'success');
      }

      closeSubmissionPackageModal();
    } else {
      const errText = await response.text();
      alert(`❌ Lỗi đóng gói zip từ máy chủ: ${errText}`);
    }
  } catch (error) {
    console.error("Pack zip failed:", error);
    alert(`❌ Không thể kết nối tới Backend để nén zip: ${error.message}`);
  } finally {
    if (packBtn) {
      packBtn.disabled = false;
      packBtn.innerHTML = '<i class="fa-solid fa-file-zipper"></i> NÉN & TẠO FILE SUBMISSION.ZIP (Tự động nén vào D:\\code-c-a-Long)';
    }
  }
}

//---------------------------------------------------------------------------------------------//
// EVENT LISTENERS & INITIALIZATION
//---------------------------------------------------------------------------------------------//

document.addEventListener('DOMContentLoaded', function() {
  // 1. Header Buttons
  const exportBtn = document.getElementById('export-button');
  const packageBtn = document.getElementById('package-button');

  if (exportBtn) exportBtn.addEventListener('click', toggleExportArea);
  if (packageBtn) packageBtn.addEventListener('click', openSubmissionPackageModal);

  // 2. Export Area Buttons
  const kisBtn = document.getElementById('kis');
  const vqaBtn = document.getElementById('vqa');
  const trakeBtn = document.getElementById('trake-task-btn');
  const resetExportBtn = document.getElementById('reset-export');
  const saveQueryBtn = document.getElementById('add-to-package-btn');
  const exportCsvBtn = document.getElementById('export-csv-btn');
  const refineSearchBtn = document.getElementById('refine-search');

  if (kisBtn) kisBtn.addEventListener('click', () => toggleTask('kis'));
  if (vqaBtn) vqaBtn.addEventListener('click', () => toggleTask('vqa'));
  if (trakeBtn) trakeBtn.addEventListener('click', () => toggleTask('trake'));
  if (resetExportBtn) resetExportBtn.addEventListener('click', resetExportArea);
  
  if (saveQueryBtn) saveQueryBtn.addEventListener('click', openExportConfirmModal);
  if (exportCsvBtn) exportCsvBtn.addEventListener('click', openExportConfirmModal);

  if (refineSearchBtn) {
    refineSearchBtn.addEventListener('click', () => {
      const relevantIds = exportedImages.map(img => {
        if (img.src) return img.src;
        if (img.frameInfo && img.frameInfo.includes('-')) {
          return `${img.frameInfo.split('-')[0]}_${img.frameId}`;
        }
        return `${img.frameId}`;
      });
      if (relevantIds.length > 0) {
        if (typeof performRefineSearch === 'function') {
          performRefineSearch(relevantIds);
          if (typeof showNotification === 'function') {
            showNotification(`Đang tinh chỉnh tìm kiếm (Refine Search) theo ${relevantIds.length} ảnh...`, 'success');
          }
        }
      } else {
        alert("Vui lòng thêm ít nhất 1 ảnh vào danh sách để sử dụng tính năng Refine Search!");
      }
    });
  }

  // 3. Export Confirm Modal Buttons
  const confirmBtn = document.querySelector('.export-modal-btn.confirm');
  const cancelBtn = document.querySelector('.export-modal-btn.cancel');
  if (confirmBtn) {
    confirmBtn.addEventListener('click', () => {
      const fileName = document.getElementById('filenameInput')?.value || getSuggestedFileName();
      saveCurrentQueryToPackage(fileName);
    });
  }
  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => {
      const modal = document.getElementById('exportModal');
      if (modal) modal.style.display = 'none';
    });
  }

  // 4. Submission Package Modal Action Buttons
  const packZipModalBtn = document.getElementById('btn-pack-zip-modal');
  const clearPkgBtn = document.getElementById('btn-clear-package');
  const closePkgBtn = document.getElementById('close-pkg-modal');
  const closeCsvPrevBtn = document.getElementById('close-csv-preview-btn');

  if (packZipModalBtn) packZipModalBtn.addEventListener('click', packAndZipSubmission);
  if (clearPkgBtn) clearPkgBtn.addEventListener('click', clearSubmissionPackage);
  if (closePkgBtn) closePkgBtn.addEventListener('click', closeSubmissionPackageModal);
  if (closeCsvPrevBtn) closeCsvPrevBtn.addEventListener('click', closeCsvPreviewModal);

  // 5. Drag & Drop
  const exportArea = document.getElementById('export-area');
  if (exportArea) {
    exportArea.addEventListener('dragover', allowDrop);
    exportArea.addEventListener('drop', drop);
  }

  // 6. Update badge initial state
  updateSubmissionBadge();
});

// Drag and drop helper
function drop(ev) {
  ev.preventDefault();
  const data = ev.dataTransfer.getData("text");
  const imgElement = document.getElementById(data);
  if (imgElement) {
    const imgDis = imgElement.closest('.img-dis, .frame-container');
    const infor = imgDis ? imgDis.querySelector('.infor')?.textContent : '';
    let frameId = imgDis?.dataset?.frameId || '';
    if (!frameId && imgElement.src) {
      const match = imgElement.src.match(/keyframe_(\d+)\./);
      if (match) frameId = match[1];
    }
    const tsMs = imgDis?.dataset?.timestampMs || null;
    addImageToExportArea(frameId, imgElement.src, infor, true, tsMs);
  }
}

function drag(ev) {
  ev.dataTransfer.setData("text", ev.target.id);
}

function handleMiddleClick(event) {
  if (event.button === 1) { // Middle click
    event.preventDefault();
    const target = event.currentTarget;
    const img = target.querySelector('img');
    const infor = target.querySelector('.infor')?.textContent;
    let frameId = target.dataset?.frameId || '';
    if (!frameId && img?.src) {
      const match = img.src.match(/keyframe_(\d+)\./);
      if (match) frameId = match[1];
    }
    const tsMs = target.dataset?.timestampMs || null;
    if (img && infor) {
      addImageToExportArea(frameId, img.src, infor, true, tsMs);
      if (typeof showNotification === 'function') {
        showNotification(`Đã thêm ${infor} (Frame ${frameId}) vào danh sách xuất!`, 'success');
      }
    }
  }
}
