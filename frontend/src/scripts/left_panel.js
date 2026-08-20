//------------------------ Left Panel ------------------------//

function clearAllTextareas() {
    const textareas = document.querySelectorAll('textarea');
    textareas.forEach(textarea => {
        textarea.value = '';
    });
}

function resetAllQueries() {
    clearAllTextareas();
    if (typeof resetTrakeScenes === 'function') {
        resetTrakeScenes();
    }
    // Clear any extra dynamic containers
    const ocrContainers = document.querySelectorAll('.ocr-container, .asm-container, .asr-container, .object-filter');
    ocrContainers.forEach(el => el.remove());
    // Clear quick answer bar if exists
    const commonInput = document.getElementById('vqa-common-answer');
    if (commonInput) commonInput.value = '';
    focusOnFirstTextbox();
}

// Function to focus on the first textbox in search-scene-1
function focusOnFirstTextbox() {
    const firstScene = document.querySelector('#search-scene-1');
    if (firstScene) {
        const textbox = firstScene.querySelector('textarea[name="Text_Query"]');
        if (textbox) {
            textbox.focus();
        }
    }
}

// Function to cycle through Text_Query textboxes
function cycleThroughTextboxes() {
    const scenes = document.querySelectorAll('.Search_Scene');
    if (scenes.length === 0) return;

    const activeElement = document.activeElement;
    let currentSceneIndex = -1;

    for (let i = 0; i < scenes.length; i++) {
        if (scenes[i].contains(activeElement)) {
            currentSceneIndex = i;
            break;
        }
    }

    const nextSceneIndex = (currentSceneIndex + 1) % scenes.length;
    const nextScene = scenes[nextSceneIndex];

    const nextTextQuery = nextScene.querySelector('textarea[name="Text_Query"]');
    if (nextTextQuery) {
        nextTextQuery.focus();
    }
}

//------------------------------------------------------------------------//


// AI Engine Status Bar: Both SigLIP and LLM Omni-Parser are always active in parallel
function switchModel(model) {
    console.log(`Active model engine: Google SigLIP SO400M + LLM Omni-Parser`);
}

//------------------------------------------------------------------------//
// Insert elements

// Insert a textarea for entering OCR (Optical Character Recognition) query
function insertOcrTextarea() {
    const activeElement = document.activeElement;
    const queryGroup = activeElement.closest('.query-group');
    
    if (queryGroup) {
        const textQuery = queryGroup.querySelector('textarea[name="Text_Query"]');
        if (textQuery && textQuery.style.display !== 'none') {
            const queryImageArea = queryGroup.querySelector('.query-content-area');
            
            const existingOcr = queryGroup.querySelector('textarea[name="Ocr_Query"]');
            if (!existingOcr) {
                const ocrContainer = document.createElement('div');
                ocrContainer.className = 'ocr-container';
                
                const newOcrTextarea = document.createElement('textarea');
                newOcrTextarea.name = 'Ocr_Query';
                newOcrTextarea.rows = '2';
                newOcrTextarea.placeholder = '🔤 Nhập văn bản cần tìm trên ảnh (OCR - Biển tên đường, biển số xe, cổng chùa)...';
                newOcrTextarea.title = 'Tìm kiếm chữ viết xuất hiện trên video (OCR)';
                
                const closeButton = document.createElement('button');
                closeButton.innerHTML = '&times;';
                closeButton.className = 'close-ocr-button';
                closeButton.title = 'Đóng ô tìm kiếm OCR';
                closeButton.addEventListener('click', function() {
                    ocrContainer.remove();
                });
                
                ocrContainer.appendChild(newOcrTextarea);
                ocrContainer.appendChild(closeButton);
                
                queryImageArea.after(ocrContainer);

                // Focus on the newly created OCR textarea
                newOcrTextarea.focus();
            }
        }
    }
}

// Insert a textarea for entering ASM
function insertAsmTextarea() {
    const activeElement = document.activeElement;
    const queryGroup = activeElement.closest('.query-group');
    
    if (queryGroup) {
        const textQuery = queryGroup.querySelector('textarea[name="Text_Query"]');
        if (textQuery && textQuery.style.display !== 'none') {
            const queryImageArea = queryGroup.querySelector('.query-content-area');
            
            const existingAsm = queryGroup.querySelector('textarea[name="Asm_Query"]');
            if (!existingAsm) {
                const asmContainer = document.createElement('div');
                asmContainer.className = 'asm-container';
                
                const newAsmTextarea = document.createElement('textarea');
                newAsmTextarea.name = 'Asm_Query';
                newAsmTextarea.rows = '2';
                newAsmTextarea.placeholder = '🎙️ Nhập lời thoại / giọng nói cần tìm (ASR)...';
                newAsmTextarea.title = 'Tìm kiếm lời thoại / âm thanh phát ra trong video (ASR)';
                
                const closeButton = document.createElement('button');
                closeButton.innerHTML = '&times;';
                closeButton.className = 'close-asm-button';
                closeButton.title = 'Đóng ô tìm kiếm ASR';
                closeButton.addEventListener('click', function() {
                    asmContainer.remove();
                });
                
                asmContainer.appendChild(newAsmTextarea);
                asmContainer.appendChild(closeButton);
                
                queryImageArea.after(asmContainer);

                // Focus on the newly created ASM textarea
                newAsmTextarea.focus();
            }
        }
    }
}


//---------------------------------------------------------------------------------------------------
//---------------------------------------------------------------------------------------------------
//---------------------------------------------------------------------------------------------------

function insertQunNhiuChienTextarea() {
    const activeElement = document.activeElement;
    const queryGroup = activeElement.closest('.query-group');
    
    if (queryGroup) {
        const textQuery = queryGroup.querySelector('textarea[name="Text_Query"]');
        if (textQuery && textQuery.style.display !== 'none') {
            const queryImageArea = queryGroup.querySelector('.query-content-area');
            
            const existingQunNhiuChien = queryGroup.querySelector('textarea[name="QunNhiuChien_Query"]');
            if (!existingQunNhiuChien) {
                const QunNhiuChienContainer = document.createElement('div');
                QunNhiuChienContainer.className = 'QunNhiuChien-container';
                
                const newQunNhiuChienTextarea = document.createElement('textarea');
                newQunNhiuChienTextarea.name = 'QunNhiuChien_Query';
                newQunNhiuChienTextarea.rows = '2';
                newQunNhiuChienTextarea.placeholder = '🛡️ Nhập từ khóa quân nhu / phương tiện chiến thuật...';
                newQunNhiuChienTextarea.title = 'Tìm kiếm quân nhu / phương tiện chiến đấu';
                
                const closeButton = document.createElement('button');
                closeButton.innerHTML = '&times;';
                closeButton.className = 'close-QunNhiuChien-button';
                closeButton.title = 'Đóng ô tìm kiếm quân nhu';
                closeButton.addEventListener('click', function() {
                    QunNhiuChienContainer.remove();
                });
                
                QunNhiuChienContainer.appendChild(newQunNhiuChienTextarea);
                QunNhiuChienContainer.appendChild(closeButton);
                
                queryImageArea.after(QunNhiuChienContainer);

                // Focus on the newly created QunNhiuChien textarea
                newQunNhiuChienTextarea.focus();
            }
        }
    }
}


//---------------------------------------------------------------------------------------------------
//---------------------------------------------------------------------------------------------------
//---------------------------------------------------------------------------------------------------


// Insert an object filter
function insertObjectFilter() {
    const activeElement = document.activeElement;
    const searchScene = activeElement.closest('.Search_Scene');
    
    if (searchScene) {
        const queryGroup = searchScene.querySelector('.query-group');
        const textQuery = queryGroup.querySelector('textarea[name="Text_Query"]');
        if (textQuery && textQuery.style.display !== 'none') {
            const objectFilterHTML = `
                <div class="object-filter">
                    <label class="object_label">Obj: </label>
                    <input type="text" class="objectInput" list="suggestions">
                    <input type="text" class="valueInput" data-type="text">
                    <button class="close-filter-button">&times;</button>
                </div>
            `;
            
            const lastElement = queryGroup.querySelector('.object-filter:last-of-type') || 
                                queryGroup.querySelector('.ocr-container') || 
                                queryGroup.querySelector('.query-content-area');
            
            lastElement.insertAdjacentHTML('afterend', objectFilterHTML);
            
            const newObjectFilter = queryGroup.querySelector('.object-filter:last-of-type');
            const newObjectInput = newObjectFilter.querySelector('.objectInput');
            const closeButton = newObjectFilter.querySelector('.close-filter-button');
            
            closeButton.addEventListener('click', function() {
                newObjectFilter.remove();
            });
            
            if (newObjectInput) {
                newObjectInput.focus();
            }
        }
    }
}





// Reset the content of the left panel to its original state
function resetLeftPanel(originalLeftPanel) {
    const searchForm = document.getElementById('Search');
    const scenes = searchForm.querySelectorAll('.Search_Scene');

    scenes.forEach(scene => {
        // Remove all divs with class="object-filter"
        const objectFilters = scene.querySelectorAll('.object-filter');
        objectFilters.forEach(filter => filter.remove());

        // Clear textareas
        const textareas = scene.querySelectorAll('textarea');
        textareas.forEach(ta => ta.value = '');

        // Remove image in image-drop-area
        const imageDropAreas = scene.querySelectorAll('.image-drop-area');
        imageDropAreas.forEach(dropArea => {
            const previewContainer = dropArea.querySelector('.preview-upload-container');
            const fileInput = dropArea.querySelector('input[type="file"]');
            if (previewContainer && dropArea.querySelector('.drop-instruction') && fileInput) {
                clearImage(previewContainer, dropArea.querySelector('.drop-instruction'), fileInput);
            }
        });

        // Reset mode to temporal
        switchMode(scene, 'temporal-search');
    });
}


// Function to set up the search scene tabs (DEPRECATED IN OMNI-SEARCH)
function setupSearchScene(scene) {
    // No-op for Omni-Search UI since tabs are removed
}


//------------------------------------------------------------------------//
// Change tab

// Event listener change tab text, image, ocr, asr (DEPRECATED IN OMNI-SEARCH, setup images only)
document.addEventListener('DOMContentLoaded', function() {
    const searchScenes = document.querySelectorAll('.Search_Scene');

    searchScenes.forEach(scene => {
        const queryContentArea = scene.querySelector('.query-content-area');
        const imageDropArea = queryContentArea ? queryContentArea.querySelector('.image-drop-area') : null;

        if (imageDropArea) {
            const fileInput = imageDropArea.querySelector('input[type="file"]');
            const previewContainer = imageDropArea.querySelector('.preview-upload-container');
            setupImageUpload(imageDropArea, fileInput, previewContainer);
        }
    });

    // Toggle Scene 2 logic
    const toggleScene2Btn = document.getElementById('toggle-scene2-btn');
    const closeScene2Btn = document.getElementById('close-scene2-btn');
    const scene2 = document.getElementById('search-scene-2');

    if (toggleScene2Btn && scene2) {
        toggleScene2Btn.addEventListener('click', (e) => {
            e.preventDefault();
            if (scene2.style.display === 'none' || !scene2.style.display) {
                scene2.style.display = 'flex';
                toggleScene2Btn.classList.add('active');
                toggleScene2Btn.innerHTML = '<i class="fa-solid fa-timeline"></i> Đang bật Cảnh 2';
            } else {
                scene2.style.display = 'none';
                toggleScene2Btn.classList.remove('active');
                toggleScene2Btn.innerHTML = '<i class="fa-solid fa-timeline"></i> + Thêm Cảnh 2';
            }
        });
    }

    if (closeScene2Btn && scene2) {
        closeScene2Btn.addEventListener('click', (e) => {
            e.preventDefault();
            scene2.style.display = 'none';
            if (toggleScene2Btn) {
                toggleScene2Btn.classList.remove('active');
                toggleScene2Btn.innerHTML = '<i class="fa-solid fa-timeline"></i> + Thêm Cảnh 2';
            }
        });
    }
});


// Switch between tabs (Text, Image, OCR, ASR) (DEPRECATED IN OMNI-SEARCH)
function switchTab(scene, tabName) {
    // No-op for Omni-Search
}


//------------------------------------------------------------------------//

// Function to switch between modes
function switchMode(scene, modeName) {
    const modeButtons = scene.querySelectorAll('.mode-button button');
    modeButtons.forEach(button => button.classList.remove('active'));
    
    const activeButton = scene.querySelector(`.${modeName}`);
    if (activeButton) {
        activeButton.classList.add('active');
    }
}

// Function to set up mode buttons for a search scene
function setupModeButtons(scene) {
    const temporalButton = scene.querySelector('.temporal-search');
    const expansionButton = scene.querySelector('.query-expansion');

    temporalButton.addEventListener('click', (e) => {
        e.preventDefault();
        switchMode(scene, 'temporal-search');
    });

    expansionButton.addEventListener('click', (e) => {
        e.preventDefault();
        switchMode(scene, 'query-expansion');
    });

    // Set temporal as active by default
    switchMode(scene, 'temporal-search');
}



//------------------------------------------------------------------------//
// Upload image

// Set up image upload functionality
function setupImageUpload(dropZone, fileInput, previewContainer) {
    const dropInstruction = dropZone.querySelector('.drop-instruction');
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        handleImageUpload(file, previewContainer, dropInstruction);
    });

    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        handleImageUpload(file, previewContainer, dropInstruction);
    });
}


// Handle the image upload and display the image
function handleImageUpload(file, previewContainer, dropInstruction) {
    if (file && file.type.startsWith('image/')) {
        const reader = new FileReader();
        
        reader.onload = (e) => {
            const imgContainer = document.createElement('div');
            imgContainer.className = 'image-preview-container';
            
            const img = document.createElement('img');
            img.src = e.target.result;
            img.id = 'Img-review';
            
            const removeButton = document.createElement('button');
            removeButton.innerHTML = '&times;';
            removeButton.className = 'remove-image-button';
            removeButton.addEventListener('click', (event) => {
                event.stopPropagation(); // Prevent triggering the dropZone click event
                clearImage(previewContainer, dropInstruction, imgContainer.closest('.image-drop-area').querySelector('input[type="file"]'));
            });
            
            imgContainer.appendChild(img);
            imgContainer.appendChild(removeButton);
            
            previewContainer.innerHTML = '';
            previewContainer.appendChild(imgContainer);
            dropInstruction.style.display = 'none';
        };
        reader.readAsDataURL(file);
    }
}

// Clear the image from the preview container and reset the file input
function clearImage(previewContainer, dropInstruction, fileInput) {
    previewContainer.innerHTML = '';
    dropInstruction.style.display = 'block';
    fileInput.value = ''; // Clear the file input value
}






//------------------------------------------------------------------------//
// Add new search scene for multi-event TRAKE (Always appends above the bottom button)

function addNewSearchScene() {
    const scenesContainer = document.getElementById('dynamic-scenes-container') || document.getElementById('Search');
    if (!scenesContainer) return;

    const existingScenes = scenesContainer.querySelectorAll('.Search_Scene');
    const newSceneNumber = existingScenes.length + 1;

    // Create a streamlined new search scene for multi-event TRAKE
    const newSceneElement = document.createElement('div');
    newSceneElement.className = 'Search_Scene';
    newSceneElement.id = `search-scene-${newSceneNumber}`;
    newSceneElement.style.cssText = 'margin-top: 10px; border: 1px solid #334155; border-radius: 8px; padding: 10px; background: #0F172A; transition: all 0.2s ease;';

    newSceneElement.innerHTML = `
        <div class="scene-header-title" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span class="scene-title-text" style="font-size: 12px; font-weight: 700; color: #00F2FE;">
                <i class="fa-solid fa-clock-rotate-left"></i> Sự kiện ${newSceneNumber}
            </span>
            <button type="button" class="close-scene2-btn" style="background: none; border: none; color: #EF4444; font-size: 18px; font-weight: 700; cursor: pointer; padding: 0 4px; line-height: 1;" title="Xóa Sự kiện ${newSceneNumber}">&times;</button>
        </div>
        <div class="query-group">
            <div class="query-content-area">
                <textarea name="Text_Query" id="Omni-Query-${newSceneNumber}" rows="3" placeholder="🔍 Nhập mô tả sự kiện ${newSceneNumber}..." style="width: 100%; box-sizing: border-box;"></textarea>
            </div>
        </div>
    `;

    // Set up close button with automatic sequential reindexing
    const closeButton = newSceneElement.querySelector('.close-scene2-btn');
    if (closeButton) {
        closeButton.addEventListener('click', function() {
            newSceneElement.remove();
            reindexScenes();
        });
    }

    scenesContainer.appendChild(newSceneElement);

    // Auto-focus into the newly created event textarea
    const newTextarea = newSceneElement.querySelector('textarea');
    if (newTextarea) {
        newTextarea.focus();
    }
}

// Re-indexes all scenes sequentially (Sự kiện 2, 3, 4...) when any scene is removed
function reindexScenes() {
    const scenesContainer = document.getElementById('dynamic-scenes-container') || document.getElementById('Search');
    if (!scenesContainer) return;

    const allScenes = scenesContainer.querySelectorAll('.Search_Scene');
    allScenes.forEach((scene, idx) => {
        const num = idx + 1;
        scene.id = `search-scene-${num}`;
        if (num > 1) {
            const titleSpan = scene.querySelector('.scene-title-text');
            if (titleSpan) {
                titleSpan.innerHTML = `<i class="fa-solid fa-clock-rotate-left"></i> Sự kiện ${num}`;
            }
            const ta = scene.querySelector('textarea[name="Text_Query"]');
            if (ta) {
                ta.id = `Omni-Query-${num}`;
                ta.placeholder = `🔍 Nhập mô tả sự kiện ${num}...`;
            }
        }
    });
}

function resetTrakeScenes() {
    const scenesContainer = document.getElementById('dynamic-scenes-container') || document.getElementById('Search');
    if (!scenesContainer) return;

    const scenes = scenesContainer.querySelectorAll('.Search_Scene');
    scenes.forEach((scene, index) => {
        if (index >= 1) { // Keep only Scene 1
            scene.remove();
        }
    });
}

function removeAddedScenes() {
    resetTrakeScenes();
}