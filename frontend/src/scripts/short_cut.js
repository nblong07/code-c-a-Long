//------------------------ Short cut ---------

document.addEventListener('DOMContentLoaded', function() {
    const originalLeftPanel = document.querySelector('.left-panel').cloneNode(true);

    // Enter: trigger the search button
    // Enter: trigger search
    document.addEventListener('keydown', async function(event) {
        if (event.key === "Enter" && !event.shiftKey) {
            const activeElement = document.activeElement;
            const searchScene = activeElement.closest('.Search_Scene') || activeElement.closest('#Search');
    
            if (searchScene) {
                const isTextInput = activeElement.matches('textarea[name="Text_Query"]') ||
                                    activeElement.matches('textarea[name="Ocr_Query"]') ||
                                    activeElement.matches('textarea[name="Asm_Query"]') ||
                                    activeElement.matches('textarea[name="Asr_Query"]') ||
                                    activeElement.matches('textarea[name="QA_Query"]') ||
                                    activeElement.matches('textarea[name="QunNhiuChien_Query"]') ||
                                    activeElement.matches('#Omni-Query-First') ||
                                    activeElement.matches('#Omni-Query-VQA-First');
                if (isTextInput) {
                    event.preventDefault();
                    if (typeof handleFilterAction === 'function') {
                        handleFilterAction(event);
                    }
                }
            }
        }
    });
    

    // Shift + Enter: trigger the filter button
    document.addEventListener('keydown', function(event) {
        if (event.shiftKey && event.key === 'Enter') {
            const activeElement = document.activeElement;
            const isRelevantInput = 
                activeElement.matches('textarea[name="Text_Query"]') ||
                activeElement.matches('textarea[name="Ocr_Query"]') ||
                activeElement.matches('textarea[name="Asm_Query"]') ||
                activeElement.matches('textarea[name="QunNhiuChien_Query"]') ||
                activeElement.closest('.object-filter');
    
            if (isRelevantInput) {
                event.preventDefault();
                handleFilterAction();
            }
        }
    });

    // Helper function to trigger combined search
    async function triggerSearchExecution() {
        if (typeof handleFilterAction === 'function') {
            handleFilterAction();
        } else if (typeof performCombinedSearch === 'function') {
            await performCombinedSearch();
        }
    }

    // Add event listener for the search button in bottom panel
    const searchButton = document.getElementById('search-button');
    if (searchButton) {
        searchButton.addEventListener('click', function() {
            triggerSearchExecution();
        });
    }

    // Add event listener for the main search button inside search card
    const cardSearchButton = document.getElementById('card-search-button');
    if (cardSearchButton) {
        cardSearchButton.addEventListener('click', function() {
            triggerSearchExecution();
        });
    }

    // Form submit listener to prevent page refresh and trigger search
    const searchForm = document.getElementById('Search');
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            e.preventDefault();
            triggerSearchExecution();
        });
    }

    // Alt + w: Toggle switch view
    const toggleSwitch = document.getElementById('mode-toggle');
    toggleSwitch.addEventListener('change', togglePanelLayout);
    document.addEventListener('keydown', function(event) {
        if (event.altKey && event.key === 'w') {
            event.preventDefault();
            toggleSwitch.checked = !toggleSwitch.checked;
            togglePanelLayout.call(toggleSwitch);
        }
    });

    // Alt + e: Toggle translate
    document.addEventListener('keydown', function(event) {
        if (event.altKey && event.key === 'e') {
            event.preventDefault();
            const translateOptionCheckbox = document.querySelector('.translate-option .toggle-checkbox');
            if (translateOptionCheckbox) {
                translateOptionCheckbox.checked = !translateOptionCheckbox.checked;
            }
        }
    });



    // Ctrl + i: Add search OCR textarea
    document.addEventListener('keydown', function(event) {
        if (event.ctrlKey && event.key === 'i') {
            event.preventDefault();
            insertOcrTextarea();
        }
    });

    // Ctrl + k: Add search ASM textarea
    document.addEventListener('keydown', function(event) {
        if (event.ctrlKey && event.key === 'k') {
            event.preventDefault();
            insertAsmTextarea();
        }
    });

    // Ctrl + l: Add search QunNhiuChien textarea
    document.addEventListener('keydown', function(event) {
        if (event.ctrlKey && event.key === 'l') {
            event.preventDefault();
            insertQunNhiuChienTextarea();
        }
    });

    // Ctrl + j: Add search object element
    document.addEventListener('keydown', function(event) {
        if (event.ctrlKey && event.key === 'j') {
            event.preventDefault();
            insertObjectFilter();
        }
    });

    // Ctrl + h: Add a new search scene
    document.addEventListener('keydown', function(event) {
        if (event.ctrlKey && event.key === 'h') {
            event.preventDefault();
            addNewSearchScene();
        }
    });

    // Ctrl + q: Clear all query text and reset to 1 scene
    document.addEventListener('keydown', function(event) {
        if (event.ctrlKey && event.key === 'q') {
            event.preventDefault();
            if (typeof resetAllQueries === 'function') {
                resetAllQueries();
            } else {
                clearAllTextareas();
                removeAddedScenes();
                focusOnFirstTextbox();
            }
        }
    });
    
    // Event listener for keyboard shortcuts
    document.addEventListener('keydown', function(event) {
        // Slash (/): Focus on the first textbox in search-scene-1
        if (event.key === '/' && !event.shiftKey) {
            event.preventDefault();
            focusOnFirstTextbox();
        }
        
        // Shift + Slash (?): Cycle through Text_Query textboxes
        if (event.key === '?' || (event.key === '/' && event.shiftKey)) {
            event.preventDefault();
            cycleThroughTextboxes();
        }
    });

    // Ctrl + e: Clear all textareas
    document.addEventListener('keydown', function(event) {
        if (event.ctrlKey && event.key === 'e') {
            event.preventDefault();
            clearAllTextareas();
        }
    });



    // Alt + a: Toggle export area
    document.addEventListener('keydown', function(event) {
        if (event.altKey && (event.key === 'a' || event.key === 'A')) {
          event.preventDefault();
          if (typeof toggleExportArea === 'function') toggleExportArea();
        }
    });

    // Alt + p: Open Submission Package Manager Modal
    document.addEventListener('keydown', function(event) {
        if (event.altKey && (event.key === 'p' || event.key === 'P')) {
            event.preventDefault();
            if (typeof openSubmissionPackageModal === 'function') openSubmissionPackageModal();
        }
    });

    // Alt + s: Reset images in export area
    document.addEventListener('keydown', function(event) {
        if (event.altKey && (event.key === 's' || event.key === 'S')) {
            event.preventDefault();
            const resetBtn = document.getElementById('reset-export');
            if (resetBtn) resetBtn.click();
        }
    });

    // Ctrl + s: Trigger Pack & Zip Submission
    document.addEventListener('keydown', function(event) {
        if (event.ctrlKey && (event.key === 's' || event.key === 'S')) {
            event.preventDefault();
            if (typeof packAndZipSubmission === 'function') {
                packAndZipSubmission();
            }
        }
    });
});

