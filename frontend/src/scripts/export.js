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

  updateExportArea();
}

// Xóa danh sách ảnh trong khay
function resetExportArea() {
  exportedImages = [];
  vqaInputs = {};
  const commonInput = document.getElementById('vqa-common-answer');
  if (commonInput) commonInput.value = '';
  updateExportArea();
}

function allowDrop(ev) {
  ev.preventDefault();
}

// Render các thẻ ảnh trong Export Area và cập nhật thanh thống kê
function updateExportArea() {
  const exportImages = document.getElementById('export-images');
  const selectedCountEl = document.getElementById('export-selected-count');
  const targetCountEl = document.getElementById('export-target-count');

  if (selectedCountEl) selectedCountEl.textContent = exportedImages.length;
  if (targetCountEl) {
    if (activeTask === 'kis') {
      targetCountEl.textContent = '100 dòng (Top AI)';
    } else {
      targetCountEl.textContent = `${exportedImages.length} dòng`;
    }
  }

  if (!exportImages) return;
  
  if (exportedImages.length === 0) {
    exportImages.innerHTML = `
      <div style="text-align: center; color: #64748B; padding: 40px 10px; font-size: 12px;">
        <i class="fa-solid fa-cloud-arrow-up" style="font-size: 28px; margin-bottom: 10px; opacity: 0.4; display: block;"></i>
        Chưa có ảnh nào được chọn.<br>Bấm dấu <strong>[+]</strong> trên kết quả tìm kiếm hoặc kéo thả vào đây!
      </div>
    `;
    return;
  }

  const htmlContent = exportedImages.map((img, index) => `
    <div class="export-image-container">
      <img src="${img.src}" class="export-image" title="Frame ID: ${img.frameId}">
      <button class="delete-button" title="Xóa ảnh này khỏi danh sách" onclick="deleteExportImage(${index})">×</button>
      <div class="infor">${img.frameInfo}</div>
      ${activeTask === 'vqa' ? `
        <input 
          type="text" 
          class="vqa-input" 
          value="${vqaInputs[img.frameId] || ''}" 
          placeholder="Đáp án Q&A..." 
          title="Nhập đáp án cho frame này"
          oninput="updateVqaInput(${img.frameId}, this.value)"
        >
      ` : ''}
    </div>
  `).join('');
  
  exportImages.innerHTML = htmlContent;
}

function updateVqaInput(frameId, vqaInput) {
  vqaInputs[frameId] = vqaInput;
}

function deleteExportImage(index) {
  exportedImages.splice(index, 1);
  updateExportArea();
}

function addImageToExportArea(frameId, imageSrc, frameInfo, shouldBroadcast = true, timestampMs = null) {
  frameId = parseInt(frameId, 10);

  const pathParts = imageSrc.split('/');
  const videoFramePart = `${pathParts[pathParts.length - 2]}/${pathParts[pathParts.length - 1].split('.')[0]}`;

  const existingImageIndex = exportedImages.findIndex(img => img.frameId === frameId && img.videoFramePart === videoFramePart);

  if (existingImageIndex === -1) {
    if (timestampMs === null || timestampMs === undefined) {
      const timeParts = (frameInfo || '').split('-');
      if (timeParts.length > 1 && !isNaN(parseFloat(timeParts[1])) && parseFloat(timeParts[1]) > 0) {
        timestampMs = Math.round(parseFloat(timeParts[1]) * 1000.0);
      } else {
        timestampMs = Math.round((frameId / 25.0) * 1000.0);
      }
    }
    exportedImages.push({ frameId, videoFramePart, src: imageSrc, frameInfo, timestampMs });
    openExportAreaIfClosed();
    updateExportArea();
  }
}

//---------------------------------------------------------------------------------------------//
// CSV GENERATION ENGINES (CHUẨN QUY ĐỊNH BTC AIC 2026)
//---------------------------------------------------------------------------------------------//

/**
 * 1. Sinh nội dung CSV cho Textual KIS:
 * Format: <video_name>,<frame_id> (tối đa 100 dòng, không header)
 */
function generateKisCSV() {
  const currentResults = typeof getCurrentResults === 'function' ? getCurrentResults() : [];
  const sortedResults = [...currentResults].sort((a, b) => (b.score || 0) - (a.score || 0));
  
  const exportData = [...exportedImages];
  
  // Nếu người dùng chọn chưa đủ 100 ảnh, tự động bổ sung từ top kết quả tìm kiếm hiện tại
  if (exportData.length < 100 && sortedResults.length > 0) {
    const remainingCount = 100 - exportData.length;
    const additionalImages = sortedResults
      .filter(res => {
        const fid = parseInt(res.entity.frame_id);
        return !exportData.some(img => img.frameId === fid);
      })
      .slice(0, remainingCount)
      .map(res => ({
        frameId: parseInt(res.entity.frame_id),
        src: res.entity.path || '',
        frameInfo: `${res.entity.video || 'video'}-${res.entity.frame_id}`
      }));
    exportData.push(...additionalImages);
  }

  const cleanData = exportData.slice(0, 100);
  const rows = cleanData.map(item => {
    let videoName = (item.frameInfo || '').split('-')[0];
    if (!videoName && item.src) {
      const parts = item.src.split('/');
      videoName = parts[parts.length - 3] || 'video';
    }
    videoName = videoName.replace(new RegExp('\\.mp4$', 'i'), '').trim();
    const frameId = parseInt(item.frameId, 10) || 0;
    return videoName + ',' + frameId;
  });

  return rows.join('\n');
}

/**
 * 2. Sinh nội dung CSV cho Visual Q&A:
 * Format: <video_name>,<frame_id>,"<answer>"
 */
function generateVqaCSV() {
  const commonAnswer = (document.getElementById('vqa-common-answer')?.value || '').trim();
  const limitChoice = document.getElementById('vqa-row-limit')?.value || '100';
  let targetLimit = 100;
  if (limitChoice === '30') targetLimit = 30;
  else if (limitChoice === 'selected') targetLimit = Math.max(1, exportedImages.length);

  const currentResults = typeof getCurrentResults === 'function' ? getCurrentResults() : [];
  const sortedResults = [...currentResults].sort((a, b) => (b.score || 0) - (a.score || 0));
  
  const exportData = [...exportedImages];
  
  // Tự động bổ sung đủ số dòng ứng viên (30 hoặc 100 dòng) với đáp án chung
  if (exportData.length < targetLimit && sortedResults.length > 0 && commonAnswer) {
    const remainingCount = targetLimit - exportData.length;
    const additionalImages = sortedResults
      .filter(res => {
        const fid = parseInt(res.entity.frame_id);
        return !exportData.some(img => img.frameId === fid);
      })
      .slice(0, remainingCount)
      .map(res => ({
        frameId: parseInt(res.entity.frame_id),
        src: res.entity.path || '',
        frameInfo: `${res.entity.video || 'video'}-${res.entity.frame_id}`
      }));
    exportData.push(...additionalImages);
  }

  if (exportData.length === 0) {
    alert("⚠️ Bạn chưa chọn frame nào để xuất Q&A! Hãy bấm dấu [+] trên ảnh kết quả hoặc nhập đáp án chung.");
    return "";
  }

  const cleanData = exportData.slice(0, targetLimit);
  const rows = cleanData.map(item => {
    let videoName = (item.frameInfo || '').split('-')[0];
    if (!videoName && item.src) {
      const parts = item.src.split('/');
      videoName = parts[parts.length - 3] || 'video';
    }
    videoName = videoName.replace(new RegExp('\\.mp4$', 'i'), '').trim();
    const frameId = parseInt(item.frameId, 10) || 0;
    
    let ans = vqaInputs[item.frameId] || commonAnswer || "0";
    ans = ans.substring(0, 100).replaceAll('"', '""');
    
    return videoName + ',' + frameId + ',"' + ans + '"';
  });

  return rows.join('\n');
}

/**
 * 3. Sinh nội dung CSV cho TRAKE:
 * Format: <video_name>,<frame_1>,<frame_2>,...,<frame_N>
 */
function generateTrakeCSV() {
  if (exportedImages.length === 0) {
    alert("⚠️ Bạn chưa chọn chuỗi frame nào cho TRAKE! Hãy chọn các frame theo thứ tự thời gian.");
    return "";
  }

  // Nhóm các frame theo video và sắp xếp thứ tự thời gian
  const videoGroups = {};
  exportedImages.forEach(item => {
    let videoName = (item.frameInfo || '').split('-')[0];
    if (!videoName && item.src) {
      const parts = item.src.split('/');
      videoName = parts[parts.length - 3] || 'video';
    }
    videoName = videoName.replace(new RegExp('\\.mp4$', 'i'), '').trim();
    const frameId = parseInt(item.frameId, 10) || 0;
    
    if (!videoGroups[videoName]) {
      videoGroups[videoName] = [];
    }
    videoGroups[videoName].push(frameId);
  });

  const rows = [];
  Object.entries(videoGroups).forEach(([videoName, frames]) => {
    frames.sort((a, b) => a - b); // Đảm bảo đúng thứ tự thời gian Frame 1 < Frame 2 < Frame N
    rows.push(videoName + ',' + frames.join(','));
  });

  return rows.slice(0, 100).join('\n');
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
    const frameId = infor ? infor.split('-')[1] : imgElement.id;
    addImageToExportArea(frameId, imgElement.src, infor);
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
    if (img && infor) {
      const frameId = infor.split('-')[1];
      addImageToExportArea(frameId, img.src, infor);
      if (typeof showNotification === 'function') {
        showNotification(`Đã thêm ${infor} vào danh sách xuất!`, 'success');
      }
    }
  }
}
