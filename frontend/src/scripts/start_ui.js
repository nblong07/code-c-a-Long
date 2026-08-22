//------------------------ Start UI ------------------------//


// Adjust interval as needed
// Set the Cyber Robot favicon
let data;
const link = document.querySelector("link[rel~='icon']") || (() => {
  const newLink = document.createElement('link');
  newLink.rel = 'icon';
  document.head.appendChild(newLink);
  return newLink;
})();
link.href = './src/Img/favicon-robot.svg?v=5';



//---------------------------------------------------------------------------------------------//
// Translate toggle

// DOMContentLoaded event listener (runs after the HTML document is fully loaded)
document.addEventListener('DOMContentLoaded', function() {
  const translateCheckbox = document.getElementById('translate-checkbox');
  const toggleLabel = document.querySelector('.translate-option');
  
  if (translateCheckbox && toggleLabel) {
    // Disable transition initially
    toggleLabel.style.transition = 'none';

    // Load saved state
    translateCheckbox.checked = localStorage.getItem('translate-checkbox') === 'true';
    
    // Re-enable transition after a short delay
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        toggleLabel.style.transition = '';
      });
    });
    
    // Save state on change and add animation
    translateCheckbox.addEventListener('change', () => {
      localStorage.setItem('translate-checkbox', translateCheckbox.checked);
      
      // Add animation
      toggleLabel.style.transition = 'all 0.3s ease';
    });
  }
});


// Function to toggle loading indicator
function toggleLoadingIndicator(show) {
  const indicator = document.getElementById('loading-indicator');
  if (indicator) {
    indicator.style.display = show ? 'flex' : 'none';
  }
}


// Function to translate text using Google Translate API
async function translateText(text, sourceLang = 'vi', targetLang = 'en') {
  if (!text) return ''; // Return empty string if text is empty
  const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=${sourceLang}&tl=${targetLang}&dt=t&q=${encodeURIComponent(text)}`;

  try {
    const response = await fetch(url);
    const data = await response.json();
    return data[0].map(item => item[0]).join('');
  } catch (error) {
    console.error('Translation error:', error);
    return text; // Return original text if translation fails
  }
}

//---------------------------------------------------------------------------------------------//

// Debounce function (delays function execution for a certain time)
function debounce(func, delay) {
  let timeoutId;
  return function (...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func.apply(this, args), delay);
  };
}


// document.addEventListener('DOMContentLoaded', () => {
//   connectWebSocket();
//   performCombinedSearch();
// });



//---------------------------------------------------------------------------------------------//
// Update UI by toggle effect

document.addEventListener('DOMContentLoaded', function() {
  const toggleSwitch = document.getElementById('mode-toggle');
  toggleSwitch.addEventListener('change', togglePanelLayout);
  
  // Initially hide the new-right-panel (default to Grid View for KIS/QA)
  document.querySelector('.show-image-1').style.display = 'block';
  document.querySelector('.show-image-2').style.display = 'none';
  
  // Add event listener for the new-right-panel (images-rows)
  document.getElementById("images-rows").addEventListener('click', (event) => {
    if (event.target.classList.contains('result')) {
      showVideo(event.target);
      event.stopPropagation();
    } else if (event.target.closest('.fullscreen_zoom')) {
      event.stopPropagation();
      const imgDis = event.target.closest('.img-dis');
      const imgElement = imgDis ? imgDis.querySelector('img') : null;
      if (imgElement && imgElement.src) {
        if (typeof showFullscreenImage === 'function') {
          showFullscreenImage(imgElement.src, false, imgDis);
        }
      }
    } else if (event.target.closest('.similarity_search')) {
      event.stopPropagation();
      const imgDis = event.target.closest('.img-dis');
      const inforElement = imgDis ? imgDis.querySelector('.infor') : null;
      const imgElement = imgDis ? imgDis.querySelector('img') : null;
      const imgSrc = imgElement ? (imgElement.src || imgElement.dataset.src) : '';
      
      let videoName = '';
      let frameId = '';
      if (imgSrc) {
        const match = imgSrc.match(/\/([^\/]+)\/keyframes\/keyframe_(\d+)\./i) || 
                      imgSrc.match(/(L\d+_V\d+).*?keyframe_(\d+)\./i);
        if (match) {
          videoName = match[1];
          frameId = match[2];
        } else {
          const parts = imgSrc.split('/');
          const kfIdx = parts.lastIndexOf('keyframes');
          if (kfIdx > 0 && parts[kfIdx - 1] && !parts[kfIdx - 1].includes(':')) {
            videoName = parts[kfIdx - 1];
            const fn = parts[parts.length - 1];
            frameId = fn.replace('keyframe_', '').replace(/\.[^.]+$/, '');
          }
        }
      }
      if (!videoName && inforElement) {
        const parts = inforElement.textContent.split('-');
        videoName = parts[0].trim();
        if (parts.length > 1) frameId = parts[1].trim();
      }
      videoName = (videoName || 'video').replace(/\.mp4$/i, '').trim();
      const vectorId = `${videoName}_${frameId}`;
      if (typeof performSimilaritySearch === 'function') {
        performSimilaritySearch(vectorId, imgSrc, videoName, frameId);
      }
    }
  });
});

// Set up event listener for the right panel (list-photo)
document.getElementById("list-photo").addEventListener('click', (event) => {
  const resultElement = event.target.closest('.result');
  if (resultElement) {
    const imgElement = resultElement.querySelector('img') || 
                       resultElement.querySelector('.result-image') || 
                       event.target.closest('img');

    if (event.ctrlKey) {
      // Ctrl+click on a result: perform group search
      event.preventDefault();
      event.stopPropagation();
      
      if (imgElement && data.kq) {
        const index = parseInt(imgElement.id) - 1;
        const imageData = data.kq[index];
        if (imageData && imageData.id) {
          performGroupSearch(imageData.id);
        } else {
          console.error("Invalid image data for group search");
        }
      } else {
        console.error("No image found for group search");
      }
    } else {
      // Normal click on a result: show video
      showVideo(resultElement);
      event.stopPropagation();
    }
  } else if (event.target.closest('.fullscreen_zoom')) {
    // Handle Fullscreen Zoom
    event.stopPropagation();
    const imgDis = event.target.closest('.img-dis');
    const imgElement = imgDis ? imgDis.querySelector('img') : null;
    if (imgElement && imgElement.src) {
      if (typeof showFullscreenImage === 'function') {
        showFullscreenImage(imgElement.src, false, imgDis);
      }
    }
  } else if (event.target.closest('.similarity_search')) {
    // Handle Similarity Search
    event.stopPropagation();
    const imgDis = event.target.closest('.img-dis');
    const inforElement = imgDis ? imgDis.querySelector('.infor') : null;
    const imgElement = imgDis ? imgDis.querySelector('img') : null;
    const imgSrc = imgElement ? (imgElement.src || imgElement.dataset.src) : '';
    
    let videoName = '';
    let frameId = '';
    if (imgSrc) {
      const match = imgSrc.match(/\/([^\/]+)\/keyframes\/keyframe_(\d+)\./i) || 
                    imgSrc.match(/(L\d+_V\d+).*?keyframe_(\d+)\./i);
      if (match) {
        videoName = match[1];
        frameId = match[2];
      } else {
        const parts = imgSrc.split('/');
        const kfIdx = parts.lastIndexOf('keyframes');
        if (kfIdx > 0 && parts[kfIdx - 1] && !parts[kfIdx - 1].includes(':')) {
          videoName = parts[kfIdx - 1];
          const fn = parts[parts.length - 1];
          frameId = fn.replace('keyframe_', '').replace(/\.[^.]+$/, '');
        }
      }
    }
    if (!videoName && inforElement) {
      const parts = inforElement.textContent.split('-');
      videoName = parts[0].trim();
      if (parts.length > 1) frameId = parts[1].trim();
    }
    videoName = (videoName || 'video').replace(/\.mp4$/i, '').trim();
    const vectorId = `${videoName}_${frameId}`;
    if (typeof performSimilaritySearch === 'function') {
      performSimilaritySearch(vectorId, imgSrc, videoName, frameId);
    }
  } else if (event.target.closest('.timeline_explorer')) {
    event.stopPropagation();
    const imgDis = event.target.closest('.img-dis');
    if (imgDis && typeof showVideoFrames === 'function') {
      showVideoFrames(imgDis);
    }
  }
});


// Function to toggle the layout of the right panel
function togglePanelLayout() {
  const showImage_1 = document.querySelector('.show-image-1');
  const showImage_2 = document.querySelector('.show-image-2');
  
  if (this.checked) {
    // Switch to row slider view
    showImage_1.style.display = 'none';
    showImage_2.style.display = 'block';
  } else {
    // Switch back to grid view
    showImage_1.style.display = 'block';
    showImage_2.style.display = 'none';
  }
}


// Disable right-click context menu on the entire page
document.addEventListener('contextmenu', function(event) {
  event.preventDefault();
  if (event.target.closest('.img-dis')) {
    showVideoFrames(event.target.closest('.img-dis'));
  }

  if (event.target.closest('.export-image-container')) {
    showVideoFrames(event.target.closest('.export-image-container'));
  }
});







//------------------------ Shortcut card ------------------------//

document.addEventListener('DOMContentLoaded', function() {
  const shortcutIcon = document.getElementById('shortcut-icon');
  const shortcutCard = document.getElementById('shortcut-card');
  const shortcutList = document.getElementById('shortcut-list');

  const shortcuts = [
    { key: 'Enter', description: 'Tìm kiếm ngay (Execute search)' },
    { key: 'Ctrl + S', description: 'Đóng gói & Nén file submission.zip tự động (Auto-Pack Zip)' },
    { key: 'Alt + P', description: 'Mở Gói Quản Lý Bài Thi Sơ Tuyển (Open Submission Package)' },
    { key: 'Alt + A', description: 'Bật/Tắt khay chọn kết quả / Export Area (Toggle Export)' },
    { key: 'Ctrl + I', description: 'Thêm ô tìm kiếm OCR (Add OCR Query box)' },
    { key: 'Ctrl + K', description: 'Thêm ô tìm kiếm ASR/Lời thoại (Add ASR Query box)' },
    { key: 'Ctrl + H', description: 'Thêm phân cảnh thời gian Scene 2 (Add Temporal Scene)' },
    { key: 'Ctrl + Q', description: 'Xóa bộ lọc & quay về mặc định (Reset search panels)' },
    { key: 'Ctrl + E', description: 'Xóa sạch chữ các ô (Clear all textboxes)' },
    { key: 'Alt + R', description: 'Tinh chỉnh vector tự học (Rocchio Refine Search)' },
    { key: 'Alt + S', description: 'Xóa danh sách ảnh trong khay (Reset export area)' },
    { key: 'Alt + W', description: 'Đổi chế độ xem lưới / phân nhóm (Toggle Grid/Row view)' },
    { key: 'Escape', description: 'Đóng cửa sổ phóng to / popup (Close Fullscreen/Modal)' }
  ];

  function populateShortcutList() {
    if (!shortcutList) return;
    shortcutList.innerHTML = '';
    shortcuts.forEach(shortcut => {
      const li = document.createElement('li');
      li.innerHTML = `<span class="shortcut-key">${shortcut.key}:</span> ${shortcut.description}`;
      shortcutList.appendChild(li);
    });
  }

  if (shortcutIcon && shortcutCard) {
    shortcutIcon.addEventListener('click', function() {
      if (shortcutCard.style.display === 'none') {
        populateShortcutList();
        shortcutCard.style.display = 'block';
      } else {
        shortcutCard.style.display = 'none';
      }
    });
  }

  function closeShortcutCard() {
    if (shortcutCard) shortcutCard.style.display = 'none';
  }

  // Close the card when clicking outside of it
  document.addEventListener('click', function(event) {
    if (shortcutCard && !shortcutCard.contains(event.target) && event.target !== shortcutIcon) {
      shortcutCard.style.display = 'none';
    }
  });

  // Close the card when pressing Escape key
  document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
      closeShortcutCard();
    }
  });
});


