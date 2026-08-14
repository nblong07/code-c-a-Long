//------------------------------------------------------------------------//
function showNotification(message, type = 'success') {
    const container = document.getElementById('notification-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `notification ${type}`;
    toast.innerHTML = `
        <span class="close-btn" onclick="this.parentElement.remove()">&times;</span>
        <span>${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 600);
    }, 3000);
}
// Helper function to extract query content from a search scene
async function getFilterQueryContent(scene) {
    if (!scene) return { text: '', image: '', qa: '' };

    const textInput = scene.querySelector('textarea[name="Text_Query"]');
    const qaInput = scene.querySelector('textarea[name="QA_Query"]');
    const previewImg = scene.querySelector('.preview-upload-container img');

    let textContent = textInput ? textInput.value.trim() : '';
    let qaContent = (qaInput && qaInput.parentElement.style.display !== 'none') ? qaInput.value.trim() : '';
    let imageContent = (previewImg && previewImg.src) ? previewImg.src : '';

    return { text: textContent, image: imageContent, qa: qaContent };
}

// Common function for handling filter functionality
async function handleFilterAction(event) {
    if (event) {
        event.preventDefault();
    }

    // Select all elements with the class 'Search_Scene'
    const scenes = document.querySelectorAll('.Search_Scene');
    const allFilters = [];
    const allTextQueries = [];
    const allImageQueries = [];
    const allQaQueries = [];

    // Extract queries from each search scene
    for (let scene of scenes) {
        // skip hidden scenes (like Scene 2 if TRAKE is off)
        if (scene.style.display === 'none') continue;
        
        const content = await getFilterQueryContent(scene);
        
        if (content.image) {
            allImageQueries.push({ type: 'image', content: content.image });
        }
        if (content.text) {
            allTextQueries.push({ type: 'text', content: content.text });
        }
        if (content.qa) {
            allQaQueries.push(content.qa);
        }

        // Filters if they exist
        const filters = Array.from(scene.querySelectorAll(".object-filter")).map(section => ({
            name: section.querySelector("input[type='text']")?.value || '',
            number: section.querySelector("input[data-type='text']")?.value || ''
        }));
        allFilters.push(filters);
    }

    try {
        requestTime = performance.now();
        toggleLoadingIndicator(true);

        // Fetch selected model if available
        const activeModelBtn = document.querySelector('.model-option button.active');
        // Đọc model key từ className (vd: "clip", "blip", "mix") chứ KHÔNG phải innerText (vd: "DINOv2")
        // vì className mới là key thực sự được backend nhận diện
        const activeModel = activeModelBtn
            ? activeModelBtn.className.split(' ').find(c => !['active', 'btn'].includes(c)) || 'clip'
            : 'clip';

        jsonString = JSON.stringify({
            model: activeModel,
            qaQueries: allQaQueries,
            filters: allFilters,
            textQueries: allTextQueries,
            imageQueries: allImageQueries
        });

        console.log("🚀 Sending search request:", jsonString);

        if (typeof filterSocket !== 'undefined' && filterSocket && filterSocket.readyState === WebSocket.OPEN) {
            filterSocket.send(jsonString);
        } else if (typeof socket !== 'undefined' && socket && socket.readyState === WebSocket.OPEN) {
            const firstQueryStr = (allTextQueries[0]?.content) || "";
            const secondQueryStr = (allTextQueries[1]?.content) || "";
            socket.send(JSON.stringify({
                type: "text_query",
                firstQuery: firstQueryStr,
                secondQuery: secondQueryStr,
                qaQuery: allQaQueries[0] || "",
                model: activeModel
            }));
        } else {
            console.warn("⚠️ WebSocket chưa kết nối. Đang khởi tạo lại kết nối...");
            if (typeof connectWebSocket === 'function') connectWebSocket();
            if (typeof connectFilterWebSocket === 'function') connectFilterWebSocket();
            setTimeout(() => {
                if (typeof filterSocket !== 'undefined' && filterSocket && filterSocket.readyState === WebSocket.OPEN) {
                    filterSocket.send(jsonString);
                } else {
                    toggleLoadingIndicator(false);
                }
            }, 800);
        }

    } catch (error) {
        console.error('Filter query error:', error);
        toggleLoadingIndicator(false);
    }
}

// Event listeners for search execution
document.addEventListener('DOMContentLoaded', function() {
    const cardSearchBtn = document.getElementById("card-search-button");
    if (cardSearchBtn) {
        cardSearchBtn.addEventListener("click", handleFilterAction);
    }
    const filterBtn = document.getElementById("filter-button");
    if (filterBtn) {
        filterBtn.addEventListener("click", handleFilterAction);
    }
});
