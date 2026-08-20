//------------------------ Preview ------------------------//

// Show the left preview with the provided image source and frame information
function showLeftPreview(src, frameInfo, positionIndex) {

  const previewImage = document.getElementById('preview-image');
  const leftPreview = document.querySelector('.left-preview');
  const previewInfor = leftPreview.querySelector('.infor');
  const positionIndexElement = leftPreview.querySelector('.positionIndex');
  
  previewImage.src = src;
  previewInfor.textContent = frameInfo;
  positionIndexElement.textContent = positionIndex;
  leftPreview.classList.add('visible');
  updatePreviewFrameVisibility();
}

// Show the current frame preview on the right side
function showCurrentFramePreview() {
  const rightPreview = document.querySelector('.right-preview');
  updateCurrentPreview();
  rightPreview.classList.add('visible');
  updatePreviewFrameVisibility();
}

// Hide the left preview
function hideLeftPreview() {
  const leftPreview = document.querySelector('.left-preview');
  leftPreview.classList.remove('visible');
  updatePreviewFrameVisibility();
}

// Hide the current frame preview on the right side
function hideCurrentFramePreview() {
  const rightPreview = document.querySelector('.right-preview');
  rightPreview.classList.remove('visible');
  updatePreviewFrameVisibility();
}

// Check the visibility of the preview frame and update its display accordingly
function checkPreviewFrameVisibility() {
  const previewFrame = document.getElementById('preview-frame');
  const leftPreview = document.querySelector('.left-preview');
  const rightPreview = document.querySelector('.right-preview');
  
  if (leftPreview.classList.contains('visible') || rightPreview.classList.contains('visible')) {
    previewFrame.style.display = 'flex';
  } else {
    previewFrame.style.display = 'none';
  }
}

// Update the visibility of the preview frame
function updatePreviewFrameVisibility() {
  const previewFrame = document.getElementById('preview-frame');
  const leftPreview = document.querySelector('.left-preview');
  const rightPreview = document.querySelector('.right-preview');
  
  if (leftPreview.classList.contains('visible') || rightPreview.classList.contains('visible')) {
    previewFrame.style.display = 'block';
  } else {
    previewFrame.style.display = 'none';
  }
}

// Hide the entire preview frame and reset visibility of both previews
function hidePreviewFrame() {
  const previewFrame = document.getElementById('preview-frame');
  const leftPreview = document.querySelector('.left-preview');
  const rightPreview = document.querySelector('.right-preview');
  previewFrame.style.display = 'none';
  leftPreview.classList.remove('visible');
  rightPreview.classList.remove('visible');
}


//-----------------------------------------------------------------------//

// Update the current preview on the right side based on the current frame
function updateCurrentPreview() {
  const currentFrame = document.querySelector('.current-frame');
  const currentPreview = document.getElementById('current-preview');
  const currentPreviewInfo = document.querySelector('.right-preview .infor');
  
  if (currentFrame) {
    const frameContainer = currentFrame.closest('.frame-container');
    currentPreview.src = currentFrame.src;
    currentPreviewInfo.textContent = frameContainer.querySelector('.infor').textContent;
  }
}

//-----------------------------------------------------------------------//

// Check if both previews are hidden and update the display of the preview frame accordingly
function checkAndHidePreviewFrame() {
  const leftPreview = document.querySelector('.left-preview');
  const rightPreview = document.querySelector('.right-preview');
  const previewFrame = document.getElementById('preview-frame');
  
  if (!leftPreview.classList.contains('visible') && !rightPreview.classList.contains('visible')) {
    previewFrame.style.display = 'none';
  } else {
    previewFrame.style.display = 'block';
  }
}

// Main event listener to handle various key presses, mouse events, and focus/blur events
document.addEventListener('DOMContentLoaded', () => {

  const previewFrame = document.getElementById('preview-frame');
  let isAltPressed = false;
  let isPreviewModeEnabled = false;

  let escPressCount = 0;
  const escPressResetTime = 500; // time after press reset, ms

  //Reset the preview state when necessary
  function resetPreviewState() {
    isAltPressed = false;
    isPreviewModeEnabled = false;
  }

  // Hide the preview frame when certain keys are pressed
  function hidePreviewFrame() {
    previewFrame.style.display = 'none';
    document.querySelector('.left-preview').classList.remove('visible');
    document.querySelector('.right-preview').classList.remove('visible');
  }

  // Handle the Escape key press and manage the preview frame visibility
  function handleEscPress() {
    escPressCount++;
    if (escPressCount === 2) {
      hidePreviewFrame();
      escPressCount = 0;
    }
    setTimeout(() => {
      escPressCount = 0;
    }, escPressResetTime);

  }

  // Track when the Alt key is pressed down and prevent the default action.
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Alt') {
      isAltPressed = true;
      e.preventDefault();
    } else if (e.altKey && e.key === 'x') {
      isPreviewModeEnabled = !isPreviewModeEnabled;
      e.preventDefault();
    } else if (e.key === 'Escape') {
      handleEscPress();
    }
  });

  // Track when the Alt key is released and prevent the default action.
  document.addEventListener('keyup', (e) => {
    if (e.key === 'Alt') {
      isAltPressed = false;
      e.preventDefault();
    }
  });

  // Show the preview frame with the image when the Alt key is pressed and the mouse is over a result.
  document.addEventListener('mouseover', (e) => {
  if ((isAltPressed || isPreviewModeEnabled) && (e.target.classList.contains('result') || e.target.classList.contains('export-image'))) {
    const imgDis = e.target.closest('.img-dis, .export-image-container');
    const frameInfo = imgDis.querySelector('.infor').textContent;

    const imgElement = imgDis.querySelector('.result, .export-image');
    const positionIndex = imgElement.id;

    showLeftPreview(e.target.src, frameInfo, positionIndex);
    e.preventDefault();
  }
});

  // Reset Alt state when window loses focus
  window.addEventListener('blur', resetPreviewState);

  // Add event listeners for close buttons
  const closeButtons = document.querySelectorAll('.close-preview-button');
  closeButtons.forEach(button => {
    button.addEventListener('click', function() {
      const previewContainer = this.closest('.preview-container');
      if (previewContainer.classList.contains('left-preview')) {
        hideLeftPreview();
      } else {
        hideCurrentFramePreview();
      }
    });
  });

  // Add click event listeners to preview images to play video
  document.getElementById('preview-image')?.addEventListener('click', () => {
    const infoText = document.querySelector('.left-preview .infor')?.textContent;
    if (infoText) {
      const parts = infoText.split('-');
      if (parts.length >= 2) {
        const videoName = parts[0];
        const timeVal = parseFloat(parts[1]);
        if (typeof playVideoAtTime === 'function') {
          playVideoAtTime(videoName, timeVal);
        }
      }
    }
  });

  document.getElementById('current-preview')?.addEventListener('click', () => {
    const infoText = document.querySelector('.right-preview .infor')?.textContent;
    if (infoText) {
      const parts = infoText.split('-');
      if (parts.length >= 2) {
        const videoName = parts[0];
        const timeVal = parseFloat(parts[1]);
        if (typeof playVideoAtTime === 'function') {
          playVideoAtTime(videoName, timeVal);
        }
      }
    }
  });
});

// Observer to watch for changes in the video frames and update the current preview accordingly
const videoFramesObserver = new MutationObserver((mutations) => {
  mutations.forEach((mutation) => {
    if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
      const targetElement = mutation.target;
      if (targetElement.classList.contains('current-frame')) {
        updateCurrentPreview();
      }
    }
  });
});

const videoFrames = document.getElementById('video-frames');
if (videoFrames) {
  videoFramesObserver.observe(videoFrames, { attributes: true, subtree: true, attributeFilter: ['class'] });
}





//------------------------------------------------------------------------------------------//


// Show the image in fullscreen mode with navigation controls
let currentFullscreenContext = {
  type: 'search', // 'search' or 'video'
  currentIndex: 1,
  totalResults: 100,
  currentFrameNumber: 0,
  directory: ''
};

function showFullscreenImage(src, isLeftPreview = false, targetElement = null) {
  const container = document.getElementById('fullscreen-image-container');
  const image = document.getElementById('fullscreen-image');
  const titleEl = document.getElementById('fullscreen-frame-title');
  const ocrBadge = document.getElementById('fullscreen-ocr-badge');
  const ocrTextEl = document.getElementById('fullscreen-ocr-text');
  
  if (!container || !image) return;

  image.src = src;
  container.style.display = 'flex';

  // Determine context
  let imgDis = null;
  if (targetElement) {
    imgDis = targetElement.closest ? targetElement.closest('.img-dis, .frame-container') : null;
  }
  
  if (!imgDis && event && event.target) {
    imgDis = event.target.closest('.img-dis, .frame-container');
  }

  if (imgDis && imgDis.classList.contains('img-dis')) {
    currentFullscreenContext.type = 'search';
    const index = parseInt(imgDis.dataset.index || imgDis.querySelector('.result')?.id || '1');
    currentFullscreenContext.currentIndex = isNaN(index) ? 1 : index;

    const infoText = imgDis.querySelector('.infor')?.textContent || '';
    const ocrText = imgDis.dataset.ocr || imgDis.querySelector('.ocr-text-tag')?.textContent || '';

    if (titleEl) titleEl.textContent = `Kết quả #${currentFullscreenContext.currentIndex} | ${infoText}`;
    if (ocrBadge && ocrTextEl) {
      if (ocrText) {
        ocrTextEl.textContent = ocrText.replace('Văn bản nhận diện (OCR):', '').trim();
        ocrBadge.style.display = 'inline-flex';
      } else {
        ocrBadge.style.display = 'none';
      }
    }
  } else {
    // Video frames strip or Right Preview context
    currentFullscreenContext.type = 'video';
    const framesContainer = document.querySelector('.frames-container');
    currentFullscreenContext.directory = framesContainer ? (framesContainer.dataset.directory || '') : '';
    
    let frameNumber = 0;
    const srcParts = src.split('/');
    const lastPart = srcParts[srcParts.length - 1] || '';
    if (lastPart.includes('_')) {
      frameNumber = parseInt(lastPart.split('_')[1].split('.')[0]) || 0;
    }
    currentFullscreenContext.currentFrameNumber = frameNumber;

    if (titleEl) titleEl.textContent = `Khung hình: ${frameNumber}`;
    if (ocrBadge) ocrBadge.style.display = 'none';
  }

  document.removeEventListener('keydown', handleEscapeKey);
  document.addEventListener('keydown', handleEscapeKey);
}

// Hide the fullscreen image and remove event listeners
function hideFullscreenImage() {
  const container = document.getElementById('fullscreen-image-container');
  if (container) container.style.display = 'none';
  document.removeEventListener('keydown', handleEscapeKey);
}

// Handle Escape key press to exit fullscreen mode
function handleEscapeKey(event) {
  if (event.key === 'Escape') {
    hideFullscreenImage();
  }
}

// Navigate between images in fullscreen mode using direction (-1 for prev, +1 for next)
function navigateFullscreenImage(direction) {
  const container = document.getElementById('fullscreen-image-container');
  const image = document.getElementById('fullscreen-image');
  const titleEl = document.getElementById('fullscreen-frame-title');
  const ocrBadge = document.getElementById('fullscreen-ocr-badge');
  const ocrTextEl = document.getElementById('fullscreen-ocr-text');
  
  if (!container || container.style.display !== 'flex' || !image) return;

  if (currentFullscreenContext.type === 'search') {
    // Navigate along search result list
    const visibleContainer = document.querySelector('.show-image-1').style.display !== 'none' 
      ? document.getElementById('list-photo') 
      : document.getElementById('images-rows');

    const allCards = Array.from(visibleContainer.querySelectorAll('.img-dis'));
    if (!allCards || allCards.length === 0) return;

    let targetIndex = currentFullscreenContext.currentIndex + direction;
    if (targetIndex < 1) targetIndex = allCards.length; // wrap around
    if (targetIndex > allCards.length) targetIndex = 1; // wrap around

    const nextCard = allCards.find(c => parseInt(c.dataset.index) === targetIndex) || allCards[targetIndex - 1];
    if (nextCard) {
      currentFullscreenContext.currentIndex = targetIndex;
      const nextImg = nextCard.querySelector('img');
      const infoText = nextCard.querySelector('.infor')?.textContent || '';
      const ocrText = nextCard.dataset.ocr || nextCard.querySelector('.ocr-text-tag')?.textContent || '';

      if (nextImg) image.src = nextImg.src || nextImg.dataset.src;
      if (titleEl) titleEl.textContent = `Kết quả #${targetIndex} | ${infoText}`;
      
      if (ocrBadge && ocrTextEl) {
        if (ocrText) {
          ocrTextEl.textContent = ocrText.replace('Văn bản nhận diện (OCR):', '').trim();
          ocrBadge.style.display = 'inline-flex';
        } else {
          ocrBadge.style.display = 'none';
        }
      }
    }
  } else {
    // Navigate along video frame strip
    if (globalFrameList && globalFrameList.length > 0) {
      const curIdx = globalFrameList.indexOf(currentFullscreenContext.currentFrameNumber);
      let newIdx = (curIdx !== -1 ? curIdx : 0) + direction;
      if (newIdx < 0) newIdx = globalFrameList.length - 1;
      if (newIdx >= globalFrameList.length) newIdx = 0;

      const newFrameNumber = globalFrameList[newIdx];
      currentFullscreenContext.currentFrameNumber = newFrameNumber;

      const framesContainer = document.querySelector('.frames-container');
      const directory = framesContainer ? framesContainer.dataset.directory : currentFullscreenContext.directory;
      const newSrc = `${directory}keyframe_${newFrameNumber}.webp`;

      image.src = newSrc;
      if (titleEl) titleEl.textContent = `Khung hình: ${newFrameNumber}`;
      if (ocrBadge) ocrBadge.style.display = 'none';

      // Also sync right preview if function exists
      if (typeof updateMainFrame === 'function') {
        const videoName = typeof parseVideoNameFromDirOrInfo === 'function' ? parseVideoNameFromDirOrInfo(directory, '') : 'video';
        updateMainFrame(newFrameNumber, directory, `${videoName}-${newFrameNumber}`);
      }
    }
  }
}

// Event listeners for fullscreen image controls
document.addEventListener('DOMContentLoaded', () => {
  const fullscreenContainer = document.getElementById('fullscreen-image-container');
  const closeFullscreenButton = document.getElementById('close-fullscreen-button');
  const prevFrameButton = document.getElementById('prev-frame-button');
  const nextFrameButton = document.getElementById('next-frame-button');
  const prevArrow = document.getElementById('fullscreen-prev-arrow');
  const nextArrow = document.getElementById('fullscreen-next-arrow');
  const addExportBtn = document.getElementById('fullscreen-add-export-btn');

  if (closeFullscreenButton) closeFullscreenButton.addEventListener('click', hideFullscreenImage);
  if (prevFrameButton) prevFrameButton.addEventListener('click', () => navigateFullscreenImage(-1));
  if (nextFrameButton) nextFrameButton.addEventListener('click', () => navigateFullscreenImage(1));
  if (prevArrow) prevArrow.addEventListener('click', () => navigateFullscreenImage(-1));
  if (nextArrow) nextArrow.addEventListener('click', () => navigateFullscreenImage(1));

  if (addExportBtn) {
    addExportBtn.addEventListener('click', () => {
      const img = document.getElementById('fullscreen-image');
      if (img && img.src) {
        const srcParts = img.src.split('/');
        const lastPart = srcParts[srcParts.length - 1] || '';
        const frameId = lastPart.includes('_') ? lastPart.split('_')[1].split('.')[0] : '0';
        const titleText = document.getElementById('fullscreen-frame-title')?.textContent || '';
        const info = titleText.includes('|') ? titleText.split('|')[1].trim() : `frame-${frameId}`;
        if (typeof addImageToExportArea === 'function') {
          addImageToExportArea(frameId, img.src, info);
          if (typeof showNotification === 'function') {
            showNotification('Đã thêm ảnh vào danh sách xuất / nộp bài!', 'success');
          }
        }
      }
    });
  }

  if (fullscreenContainer) {
    fullscreenContainer.addEventListener('click', (e) => {
      if (e.target === fullscreenContainer) {
        hideFullscreenImage();
      }
    });
  }
});

// Navigate with keyboard arrows in fullscreen mode
function handleFullscreenKeyPress(event) {
  const container = document.getElementById('fullscreen-image-container');
  if (container && container.style.display === 'flex') {
    if (event.key === 'ArrowLeft') {
      navigateFullscreenImage(-1);
      event.preventDefault();
    } else if (event.key === 'ArrowRight') {
      navigateFullscreenImage(1);
      event.preventDefault();
    } else if (event.key === 'Escape') {
      hideFullscreenImage();
      event.preventDefault();
    }
  }
}

document.addEventListener('keydown', handleFullscreenKeyPress);


