
/**
 * pagination.js - Quản lý phân trang và tải thêm kết quả tìm kiếm (Infinite Scroll / Batch Pagination).
 */

let isQuickSearch = false;

// Hàm chuyển đổi chế độ tìm kiếm nhanh
function toggleQuickSearchMode() {
    const lightingQuickSearchButton = document.getElementById('quick-search');
    if (!lightingQuickSearchButton) return;
    
    isQuickSearch = !isQuickSearch;
    
    if (isQuickSearch) {
        lightingQuickSearchButton.innerHTML = '<i class="fa-solid fa-bolt" style="color: #FACC15; font-size: 16px;"></i>';
        lightingQuickSearchButton.title = 'Chế độ tìm kiếm nhanh (Đang bật)';
        cleanupSearchResults();
    } else {
        lightingQuickSearchButton.innerHTML = '<i class="fa-solid fa-bolt" style="color: #94A3B8; font-size: 16px;"></i>';
        lightingQuickSearchButton.title = 'Chế độ tìm kiếm tiêu chuẩn';
        resetSearch();
    }
}

// Đăng ký sự kiện sau khi tải xong DOM
document.addEventListener('DOMContentLoaded', function() {
    const openExportSocketButton = document.getElementById('quick-search');
    if (openExportSocketButton) {
        openExportSocketButton.addEventListener('click', toggleQuickSearchMode);
    }
});

// Quản lý IntersectionObserver lazy-loading cho hình ảnh
const imageObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const img = entry.target;
            if (img.dataset && img.dataset.src && img.src !== img.dataset.src) {
                img.src = img.dataset.src;
            }
            observer.unobserve(img);
        }
    });
}, { rootMargin: '200px' });

let paginationSocket = null;
let Pagnitionsocket = null; // Alias tương thích ngược
let currentPage = 0;
let currentModelType = 'ViT-gopt-16-SigLIP2-384';
let currentModeType = 'search';

// Observer nhận diện ảnh cuối cùng trong danh sách để tải trang tiếp theo
const batchObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
        if (entry.isIntersecting && entry.target.id && entry.target.id.startsWith('page-end-')) {
            currentPage++;
            requestNextBatch(currentPage);
            observer.unobserve(entry.target);
        }
    });
}, {
    rootMargin: '200px'
});

// Thiết lập kết nối WebSocket cho phân trang
function connectPaginationWebSocket() {
    const wsBase = window.WS_URL || 'ws://localhost:8000';
    const tokenParam = window.API_KEY ? `?token=${encodeURIComponent(window.API_KEY)}` : '';
    
    paginationSocket = new WebSocket(`${wsBase}/ws/pagination${tokenParam}`);
    Pagnitionsocket = paginationSocket;

    paginationSocket.onopen = function(event) {
        console.log("WebSocket phân trang đã kết nối");
    };

    paginationSocket.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            if (data.kq && data.kq.length > 0) {
                updateUIWithPagination(data.kq, data.page);
            }
        } catch (err) {
            console.error("Lỗi xử lý dữ liệu phân trang:", err);
        }
    };

    paginationSocket.onclose = function(event) {
        console.log("WebSocket phân trang đã đóng:", event);
    };

    paginationSocket.onerror = function(error) {
        console.error("Lỗi WebSocket phân trang:", error);
    };
}

// Alias tương thích ngược
const connectPagnitionWebSocket = connectPaginationWebSocket;

// Gửi yêu cầu lấy batch kết quả tiếp theo
function requestNextBatch(page) {
    const sock = paginationSocket || Pagnitionsocket;
    if (sock && sock.readyState === WebSocket.OPEN) {
        const message = {
            type: 'pagination_query',
            model: currentModelType,
            mode: currentModeType,
            page: page
        };
        sock.send(JSON.stringify(message));
    } else {
        console.warn('WebSocket phân trang chưa sẵn sàng, đang kết nối lại...');
        connectPaginationWebSocket();
    }
}

// Cập nhật giao diện và quan sát phần tử cuối cùng
function updateUIWithPagination(results, page) {
    const updatedDivs = updatePagnitionRightPanel_list(results, page);
    const lastDiv = updatedDivs[updatedDivs.length - 1];
    if (lastDiv) {
        lastDiv.id = `page-end-${page}`;
        batchObserver.observe(lastDiv);
    }
}

const updateUIWithPagnition = updateUIWithPagination;

// Khởi tạo kết nối khi DOM sẵn sàng
document.addEventListener('DOMContentLoaded', () => {
    connectPaginationWebSocket();
});


function getPagnitionEntityInfo(result) {
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

function createPagnitionImageDiv(result, index) {
    const info = getPagnitionEntityInfo(result);

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
        <img alt="" class="result" loading="lazy" id="${index}"
          data-src="${info.imgSrc}"
          src="${info.imgSrc}">
        <div class="infor">${info.frameInfo}</div>
        <div name="similarity_search" class="similarity_search" title="Phóng to hình ảnh"></div>
        <div class="export_icon" title="Thêm vào danh sách xuất"></div>
    `;

    const img = div.querySelector('img');
    img.setAttribute('draggable', 'true');
    img.addEventListener('dragstart', drag);

    // Add middle click event listener
    div.addEventListener('mousedown', (event) => {
        if (event.button === 1) { // Middle mouse button
            event.preventDefault(); // Prevent default middle-click behavior
            addImageToExportArea(info.frameId, info.imgSrc, info.frameInfo);
        }
    });

    // Using unified event listeners
    const exportIcon = div.querySelector('.export_icon');
    if (exportIcon) {
        exportIcon.addEventListener('click', () => {
            addImageToExportArea(info.frameId, info.imgSrc, info.frameInfo);
        });
    }

    return div;
}

function updatePagnitionRightPanel_list(results, page) {
    const listPhoto = document.getElementById("list-photo");
    const fragment = document.createDocumentFragment();

    const startingIndex = listPhoto.children.length;

    const updatedDivs = results.map((result, index) => {
        const globalIndex = startingIndex + index;
        const div = createPagnitionImageDiv(result, globalIndex + 1);
        fragment.appendChild(div);

        // Observe the image for lazy-loading
        const img = div.querySelector('img');
        imageObserver.observe(img);

        return div;
    });

    listPhoto.appendChild(fragment);

    return Array.from(listPhoto.children);
}

function resetSearch() {
    const listPhoto = document.getElementById("list-photo");

    // Clear all existing results
    while (listPhoto.firstChild) {
        listPhoto.removeChild(listPhoto.firstChild);
    }

    // Reset pagination state
    currentPage = 0;
}
