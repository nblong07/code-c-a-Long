//------------------------ Random search ------------------------//

const RANDOM_QUERIES = [
    "tòa nhà cao tầng đô thị",
    "xe ô tô màu đỏ chạy trên đường",
    "người đi bộ trên vỉa hè",
    "công viên cây xanh bãi cỏ",
    "biển hiệu cửa hàng mua sắm",
    "bản tin thời sự truyền hình",
    "quang cảnh đường phố buổi tối đèn xe",
    "sông nước tàu thuyền di chuyển",
    "hoạt động thể thao ngoài trời",
    "đèn giao thông ngã tư phố",
    "bảng hiệu \"CÀ PHÊ\"",
    "phát biểu hội nghị sự kiện"
];

function getRandomQuery() {
    const idx = Math.floor(Math.random() * RANDOM_QUERIES.length);
    return RANDOM_QUERIES[idx];
}

// Handle dice click function
async function handleDiceClick() {
    const diceContainer = document.querySelector(".dice-logo");
    if (diceContainer) {
        diceContainer.classList.add('shake');
        setTimeout(() => {
            diceContainer.classList.remove('shake');
        }, 500);
    }

    const randomQuery = getRandomQuery();
    
    // Switch to Text mode tab on search-scene-1
    const scene1 = document.getElementById("search-scene-1");
    if (scene1 && typeof switchTab === 'function') {
        switchTab(scene1, 'text');
    }

    const textFirst = document.getElementById("Omni-Query-First");
    if (textFirst) {
        textFirst.value = randomQuery;
    }

    const textSecond = document.getElementById("Omni-Query-Second");
    if (textSecond) {
        textSecond.value = "";
    }

    // Also place in details input if requested by user
    const detailsTextArea = document.querySelector('textarea[name="QunNhiuChien_Query"]');
    if (detailsTextArea) {
        detailsTextArea.value = randomQuery;
    }

    if (typeof showNotification === 'function') {
        showNotification(`🎲 Tráo câu truy vấn ngẫu nhiên: "${randomQuery}"`, 'success');
    }

    // Trigger Search Execution
    if (typeof handleFilterAction === 'function') {
        handleFilterAction();
    } else {
        const cardSearchBtn = document.getElementById('card-search-button');
        if (cardSearchBtn) {
            cardSearchBtn.click();
        }
    }
}

function handleKeyboardShortcuts(event) {
    if (event.ctrlKey && event.key.toLowerCase() === 'd') {
        event.preventDefault(); // Prevent the default browser action
        handleDiceClick();
    }
}

// Add event listeners when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    const diceBtn = document.querySelector(".dice-logo");
    if (diceBtn) {
        diceBtn.addEventListener("click", handleDiceClick);
    }
    document.addEventListener('keydown', handleKeyboardShortcuts);
});