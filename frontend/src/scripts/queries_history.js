//------------------------ Queries History (Lịch Sử Truy Vấn) ------------------------//

const STORAGE_KEY = 'aic_query_history_v1';
const MAX_HISTORY_ITEMS = 60;

/**
 * Load history from localStorage
 */
function getStoredHistory() {
    try {
        const data = localStorage.getItem(STORAGE_KEY);
        return data ? JSON.parse(data) : [];
    } catch (e) {
        console.error("Failed to load history from localStorage:", e);
        return [];
    }
}

/**
 * Save history to localStorage
 */
function saveStoredHistory(historyArray) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(historyArray.slice(0, MAX_HISTORY_ITEMS)));
    } catch (e) {
        console.error("Failed to save history to localStorage:", e);
    }
}

/**
 * Render the full history list in UI
 */
function renderHistoryUI() {
    const listContainer = document.getElementById('queries-history-list') || document.querySelector('#queries-history .query-container');
    if (!listContainer) return;

    const history = getStoredHistory();
    listContainer.innerHTML = '';

    if (history.length === 0) {
        listContainer.innerHTML = `
            <div style="text-align: center; color: #64748B; padding: 30px 10px; font-size: 12px;">
                <i class="fa-solid fa-inbox" style="font-size: 24px; margin-bottom: 8px; opacity: 0.5; display: block;"></i>
                Chưa có lịch sử truy vấn nào
            </div>
        `;
        return;
    }

    history.forEach((queryText, index) => {
        const item = document.createElement('div');
        item.className = 'query-item';
        item.title = 'Click để nạp lại câu truy vấn này vào ô tìm kiếm';

        const textSpan = document.createElement('span');
        textSpan.className = 'query-text';
        textSpan.textContent = queryText;

        // Click to restore query into current search input
        textSpan.addEventListener('click', () => {
            restoreQueryToActiveInput(queryText);
        });

        // Button container
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'query-actions';

        // Copy button
        const copyBtn = document.createElement('button');
        copyBtn.className = 'query-action-btn copy-btn';
        copyBtn.innerHTML = '<i class="fa-solid fa-copy"></i>';
        copyBtn.title = 'Sao chép câu này';
        copyBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            navigator.clipboard.writeText(queryText).then(() => {
                copyBtn.innerHTML = '<i class="fa-solid fa-check" style="color: #00FF66;"></i>';
                setTimeout(() => {
                    copyBtn.innerHTML = '<i class="fa-solid fa-copy"></i>';
                }, 1200);
            });
        });

        // Delete single item button
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'query-action-btn delete-btn';
        deleteBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
        deleteBtn.title = 'Xóa câu này khỏi lịch sử';
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteHistoryItem(index);
        });

        actionsDiv.appendChild(copyBtn);
        actionsDiv.appendChild(deleteBtn);

        item.appendChild(textSpan);
        item.appendChild(actionsDiv);
        listContainer.appendChild(item);
    });
}

/**
 * Restore query into the active search input
 */
function restoreQueryToActiveInput(queryText) {
    // 1. Check if TRAKE mode is active
    const trakeTab = document.getElementById('search-mode-trake');
    if (trakeTab && trakeTab.classList.contains('active')) {
        const firstEventInput = document.querySelector('.event-description-input');
        if (firstEventInput) {
            firstEventInput.value = queryText;
            firstEventInput.focus();
        }
    } else if (document.getElementById('search-mode-vqa') && document.getElementById('search-mode-vqa').classList.contains('active')) {
        // 2. Check if VQA mode is active
        const vqaInput = document.getElementById('Omni-Query-VQA-First');
        if (vqaInput) {
            vqaInput.value = queryText;
            vqaInput.focus();
        }
    } else {
        // 3. Default KIS mode
        const kisInput = document.getElementById('Omni-Query-First') || document.querySelector('textarea[name="Text_Query"]');
        if (kisInput) {
            kisInput.value = queryText;
            kisInput.focus();
        }
    }

    // Optional toast notification
    if (typeof showNotification === 'function') {
        showNotification(`Đã nạp lại: "${queryText.length > 40 ? queryText.substring(0, 40) + '...' : queryText}"`, 'info');
    }

    // Auto-close history popup
    const queriesPopup = document.getElementById('queries-popup');
    const queriesIcon = document.getElementById('queries-icon');
    if (queriesPopup && queriesPopup.classList.contains('active')) {
        queriesPopup.classList.remove('active');
        if (queriesIcon) queriesIcon.classList.remove('active');
    }
}

/**
 * Add a query string to history
 */
function addUniqueQueryToHistory(query) {
    if (!query) return;
    const trimmed = query.trim();
    if (!trimmed) return;

    let history = getStoredHistory();
    // Remove duplicate if already exists
    history = history.filter(item => item !== trimmed);
    // Prepend to top
    history.unshift(trimmed);
    saveStoredHistory(history);
    renderHistoryUI();
}

/**
 * Delete a single history item by index
 */
function deleteHistoryItem(index) {
    let history = getStoredHistory();
    if (index >= 0 && index < history.length) {
        history.splice(index, 1);
        saveStoredHistory(history);
        renderHistoryUI();
    }
}

/**
 * Clear all history
 */
function clearAllHistory() {
    if (confirm("Bạn có chắc chắn muốn xóa toàn bộ lịch sử truy vấn không?")) {
        localStorage.removeItem(STORAGE_KEY);
        renderHistoryUI();
    }
}

/**
 * Collect all queries currently typed in search boxes
 */
function collectCurrentQueries() {
    const textareas = document.querySelectorAll('textarea[name="Text_Query"], #Omni-Query-First, #Omni-Query-VQA-First, .event-description-input');
    textareas.forEach(textarea => {
        if (textarea && textarea.value && textarea.value.trim()) {
            addUniqueQueryToHistory(textarea.value.trim());
        }
    });
}

/**
 * Toggle queries popup
 */
function toggleQueriesPopup() {
    const queriesIcon = document.getElementById('queries-icon');
    const queriesPopup = document.getElementById('queries-popup');
    
    if (queriesIcon && queriesPopup) {
        queriesIcon.classList.toggle('active');
        queriesPopup.classList.toggle('active');
        if (queriesPopup.classList.contains('active')) {
            renderHistoryUI();
        }
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    const queriesIcon = document.getElementById('queries-icon');
    const clearHistoryBtn = document.getElementById('clear-history');
    const cardSearchBtn = document.getElementById('card-search-button');

    if (queriesIcon) {
        queriesIcon.addEventListener('click', toggleQueriesPopup);
    }

    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', clearAllHistory);
    }

    // Auto-record queries whenever user searches
    if (cardSearchBtn) {
        cardSearchBtn.addEventListener('click', collectCurrentQueries);
    }

    // Also record on Enter inside any search textarea
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            const activeElem = document.activeElement;
            if (activeElem && (activeElem.tagName === 'TEXTAREA' || activeElem.tagName === 'INPUT')) {
                if (activeElem.name === 'Text_Query' || activeElem.id === 'Omni-Query-First' || activeElem.id === 'Omni-Query-VQA-First' || activeElem.classList.contains('event-description-input')) {
                    collectCurrentQueries();
                }
            }
        }
    });

    // Initial render
    renderHistoryUI();
});