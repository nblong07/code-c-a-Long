/**
 * web_socket.js - Quản lý tất cả các kết nối WebSocket của ứng dụng.
 *
 * Các WebSocket được sử dụng:
 *   - /ws                : Tìm kiếm chính (text / temporal / multi-query)
 *   - /ws/share_image    : Chia sẻ hình ảnh giữa các client (crossing)
 *   - /ws/similarity_search : Tìm kiếm tương tự theo vector
 *   - /ws/filter_query   : Lọc kết quả hiện tại
 *   - /ws/log            : Ghi log từ server
 *   - /ws/share_query    : Chia sẻ query giữa các client
 *   - /ws/group_search   : Tìm kiếm theo nhóm
 *   - /ws/alerts         : Nhận thông báo từ server
 *   - /ws/pagnition      : Phân trang kết quả tìm kiếm
 */

let socket;       // WebSocket chính để tìm kiếm
let requestTime;  // Lưu thời điểm gửi request để đo hiệu suất

/**
 * Cập nhật trạng thái kết nối hệ thống trên thanh Header
 */
function updateSystemStatusBadge(status, message) {
    const badge = document.getElementById('system-status-badge');
    const redLight = document.getElementById('tl-red');
    const yellowLight = document.getElementById('tl-yellow');
    const greenLight = document.getElementById('tl-green');
    if (!badge) return;

    badge.className = `traffic-light-status ${status}`;
    const defaultMsg = status === 'connected' ? 'Hệ thống: Sẵn sàng 🟢' : (status === 'disconnected' ? 'Hệ thống: Ngắt kết nối 🔴' : 'Hệ thống: Đang kết nối 🟡');
    badge.setAttribute('title', message || defaultMsg);

    if (redLight && yellowLight && greenLight) {
        redLight.classList.remove('active');
        yellowLight.classList.remove('active');
        greenLight.classList.remove('active');

        if (status === 'connected') {
            greenLight.classList.add('active');
        } else if (status === 'disconnected') {
            redLight.classList.add('active');
        } else {
            yellowLight.classList.add('active');
        }
    }
}

/**
 * Kết nối đến WebSocket chính (/ws).
 * Tự động kết nối lại sau 5 giây nếu bị ngắt.
 */
let isReconnecting = false;

function connectWebSocket() {
    if (!isReconnecting) {
        updateSystemStatusBadge('connecting', 'Đang kết nối hệ thống...');
    }
    const tokenParam = window.API_KEY ? `?token=${encodeURIComponent(window.API_KEY)}` : '';
    const wsUrl = window.WS_URL ? `${window.WS_URL}/ws${tokenParam}` : `ws://localhost:8000/ws${tokenParam}`;
    socket = new WebSocket(wsUrl);
    
    socket.onopen = () => {
        console.log('WebSocket chính đã kết nối (/ws)');
        isReconnecting = false;
        updateSystemStatusBadge('connected', 'Hệ thống: Sẵn sàng 🟢');
    };

    // Nhận kết quả tìm kiếm từ backend
    socket.onmessage = (event) => {
        const receiveTime = performance.now();
        console.log(`Dữ liệu nhận từ backend. Thời gian xử lý: ${receiveTime - requestTime} ms`);
        
        try {
            data = JSON.parse(event.data);
            if (data.kq) {
                // Cập nhật giao diện với kết quả tìm kiếm
                updateUIWithSearchResults(data.kq);
                const updateCompleteTime = performance.now();
                console.log(`Cập nhật UI xong. Tổng thời gian: ${updateCompleteTime - requestTime} ms`);
                console.log(`---------------------------------------------------------------------`);
                toggleLoadingIndicator(false);
            } else {
                console.error("Dữ liệu nhận không có thuộc tính 'kq':", data);
                toggleLoadingIndicator(false);
            }
        } catch (error) {
            console.error("Lỗi parse dữ liệu nhận:", error);
            toggleLoadingIndicator(false);
        }
    };

    socket.onerror = (error) => {
        console.error('Lỗi WebSocket chính:', error);
        updateSystemStatusBadge('disconnected', 'Hệ thống: Lỗi kết nối 🔴');
    };

    socket.onclose = () => {
        console.log('WebSocket chính bị đóng. Thử kết nối lại sau 5 giây...');
        isReconnecting = true;
        updateSystemStatusBadge('disconnected', 'Hệ thống: Ngắt kết nối 🔴');
        // Tự động kết nối lại
        setTimeout(connectWebSocket, 5000);
    };
}

/*
 * Lưu ý: connectWebSocket() và connectWebSocketcrossing() được gọi
 * trong DOMContentLoaded của submit_dres.js để tránh kết nối đôi.
 * Không gọi lại ở đây.
 */






///---------------------------------------------------------------------------------------------///
///---------------------------------------------------------------------------------------------///
///---------------------------------------------------------------------------------------------///

let similaritySearchSocket; // WebSocket cho tìm kiếm tương tự

/**
 * Kết nối đến WebSocket /ws/similarity_search.
 * Dùng để tìm các frame tương tự dựa theo vector embedding.
 */
function connectSimilaritySearchWebSocket() {
    const tokenParam = window.API_KEY ? `?token=${encodeURIComponent(window.API_KEY)}` : '';
    similaritySearchSocket = new WebSocket(`ws://localhost:8000/ws/similarity_search${tokenParam}`);
    
    similaritySearchSocket.onopen = () => {
        console.log('Similarity Search WebSocket đã kết nối (/ws/similarity_search)');
    };

    // Nhận kết quả tìm kiếm tương tự
    similaritySearchSocket.onmessage = (event) => {
        const receiveTime = performance.now();
        console.log(`Similarity Search: dữ liệu nhận. Thời gian: ${receiveTime - requestTime} ms`);
        
        try {
            data = JSON.parse(event.data);
            if (data.kq) {
                updateUIWithSearchResults(data.kq);
                const updateCompleteTime = performance.now();
                console.log(`Cập nhật UI xong. Tổng thời gian: ${updateCompleteTime - requestTime} ms`);
                toggleLoadingIndicator(false);
            } else if (data.error) {
                console.error("Lỗi từ server:", data.error);
                toggleLoadingIndicator(false);
            } else {
                console.error("Dữ liệu không có thuộc tính 'kq':", data);
                toggleLoadingIndicator(false);
            }
        } catch (error) {
            console.error("Lỗi parse dữ liệu similarity search:", error);
            toggleLoadingIndicator(false);
        }
    };

    similaritySearchSocket.onerror = (error) => {
        console.error('Lỗi Similarity Search WebSocket:', error);
        toggleLoadingIndicator(false);
    };

    similaritySearchSocket.onclose = () => {
        console.log('Similarity Search WebSocket bị đóng. Thử kết nối lại sau 5 giây...');
        setTimeout(connectSimilaritySearchWebSocket, 5000);
    };
}

/**
 * Thực hiện tìm kiếm tương tự với frame có ID hoặc URL hình ảnh cho trước.
 * @param {string} vectorId - ID của vector/frame cần tìm
 * @param {string} imageSrc - Đường dẫn URL hoặc file của hình ảnh
 */
function performSimilaritySearch(vectorId, imageSrc = '') {
    if (similaritySearchSocket && similaritySearchSocket.readyState === WebSocket.OPEN) {
        requestTime = performance.now();
        toggleLoadingIndicator(true);
        similaritySearchSocket.send(JSON.stringify({ vector: vectorId, image_src: imageSrc }));
    } else {
        console.warn('Similarity Search WebSocket chưa sẵn sàng, đang thử kết nối lại...');
        connectSimilaritySearchWebSocket();
        setTimeout(() => {
            if (similaritySearchSocket && similaritySearchSocket.readyState === WebSocket.OPEN) {
                requestTime = performance.now();
                toggleLoadingIndicator(true);
                similaritySearchSocket.send(JSON.stringify({ vector: vectorId, image_src: imageSrc }));
            } else {
                toggleLoadingIndicator(false);
                if (typeof showNotification === 'function') {
                    showNotification('Không thể kết nối đến máy chủ Similarity Search', 'error');
                }
            }
        }, 500);
    }
}

/**
 * Thực hiện Refine Search dựa trên các ảnh đã chọn
 * @param {Array} relevantIds - Mảng chứa các ID (ví dụ 'L21_V001_1000') của các frame được đánh dấu là relevant
 */
function performRefineSearch(relevantIds) {
    if (socket.readyState === WebSocket.OPEN) {
        requestTime = performance.now();
        toggleLoadingIndicator(true);
        const data = {
            type: "refine_query",
            original_vector: [], // Không dùng original_vector, server sẽ tự tính centroid
            relevant_ids: relevantIds,
            non_relevant_ids: [],
            alpha: 1.0,
            beta: 0.75,
            gamma: 0.15,
            top_k: 100
        };
        socket.send(JSON.stringify(data));
    } else {
        console.error('Main WebSocket chưa mở. Không thể Refine Search.');
        toggleLoadingIndicator(false);
    }
}





///---------------------------------------------------------------------------------------------///
///---------------------------------------------------------------------------------------------///
///---------------------------------------------------------------------------------------------///

let filterSocket; // WebSocket cho lọc kết quả

/**
 * Kết nối đến WebSocket /ws/filter_query.
 * Dùng để lọc lại kết quả tìm kiếm hiện tại (filter theo object, OCR, v.v.)
 */
function connectFilterWebSocket() {
    const tokenParam = window.API_KEY ? `?token=${encodeURIComponent(window.API_KEY)}` : '';
    filterSocket = new WebSocket(`ws://localhost:8000/ws/filter_query${tokenParam}`);
    
    filterSocket.onopen = () => {
        console.log('Filter WebSocket đã kết nối (/ws/filter_query)');
    };

    filterSocket.onmessage = (event) => {
        const receiveTime = performance.now();
        console.log(`Filter: dữ liệu nhận. Thời gian: ${receiveTime - requestTime} ms`);
        
        try {
            data = JSON.parse(event.data);
            if (data.kq) {
                updateUIWithSearchResults(data.kq);
                const updateCompleteTime = performance.now();
                console.log(`Cập nhật UI xong. Tổng thời gian: ${updateCompleteTime - requestTime} ms.`);
                toggleLoadingIndicator(false);
            } else if (data.error) {
                console.error("Lỗi từ server:", data.error);
            } else {
                console.error("Dữ liệu không có thuộc tính 'kq':", data);
            }
        } catch (error) {
            console.error("Lỗi parse dữ liệu filter:", error);
        }
    };

    filterSocket.onerror = (error) => {
        console.error('Lỗi Filter WebSocket:', error);
    };

    filterSocket.onclose = () => {
        console.log('Filter WebSocket bị đóng. Thử kết nối lại sau 5 giây...');
        setTimeout(connectFilterWebSocket, 5000);
    };
}


///---------------------------------------------------------------------------------------------///
///---------------------------------------------------------------------------------------------///
///---------------------------------------------------------------------------------------------///



let logSocket; // WebSocket để nhận log từ server

/**
 * Kết nối đến WebSocket /ws/log.
 * Dùng để hiển thị log/thông báo từ server ở console.
 */
function connectLogWebSocket() {
  const tokenParam = window.API_KEY ? `?token=${encodeURIComponent(window.API_KEY)}` : '';
  logSocket = new WebSocket(`ws://localhost:8000/ws/log${tokenParam}`);
  
  logSocket.onopen = function(e) {
    console.log("[open] Log WebSocket đã kết nối (/ws/log)");
  };

  logSocket.onmessage = function(event) {
    const response = JSON.parse(event.data);
    console.log(`[message] Log từ server: ${response.message}`);
  };

  logSocket.onclose = function(event) {
    if (event.wasClean) {
      console.log(`[close] Log WebSocket đóng sạch, code=${event.code} lý do=${event.reason}`);
    } else {
      console.log('[close] Log WebSocket mất kết nối đột ngột');
    }
  };

  logSocket.onerror = function(error) {
    console.log(`[error] Log WebSocket: ${error.message}`);
  };
}

// Khởi tạo log WebSocket khi tải app
connectLogWebSocket();




///---------------------------------------------------------------------------------------------///
///---------------------------------------------------------------------------------------------///
///---------------------------------------------------------------------------------------------///

// send message

let querySocket; // WebSocket để chia sẻ query giữa các client

/**
 * Kết nối đến WebSocket /ws/share_query.
 * Dùng để chia sẻ query tìm kiếm với các client trong cùng phiên.
 */
function connectQueryWebSocket() {
    const tokenParam = window.API_KEY ? `?token=${encodeURIComponent(window.API_KEY)}` : '';
    querySocket = new WebSocket(`ws://localhost:8000/ws/share_query${tokenParam}`);
    
    querySocket.onopen = () => {
        console.log('Query WebSocket đã kết nối (/ws/share_query)');
    };

    querySocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'shared_query') {
            // Hiển thị query được chia sẻ từ client khác
            addToSharedQueries(data.query);
        }
    };

    querySocket.onerror = (error) => {
        console.error('Lỗi Query WebSocket:', error);
    };

    querySocket.onclose = () => {
        console.log('Query WebSocket bị đóng. Thử kết nối lại sau 5 giây...');
        setTimeout(connectQueryWebSocket, 5000);
    };
}

// Khởi tạo query-share WebSocket khi tải app
connectQueryWebSocket();



///---------------------------------------------------------------------------------------------///
///---------------------------------------------------------------------------------------------///
///---------------------------------------------------------------------------------------------///



let groupSearchSocket; // WebSocket cho tìm kiếm theo nhóm

/**
 * Kết nối đến WebSocket /ws/group_search.
 * Dùng để tìm kiếm tất cả các frame trong cùng video với frame được chọn (Ctrl+Click).
 */
function connectGroupSearchWebSocket() {
    const tokenParam = window.API_KEY ? `?token=${encodeURIComponent(window.API_KEY)}` : '';
    groupSearchSocket = new WebSocket(`ws://localhost:8000/ws/group_search${tokenParam}`);
    
    groupSearchSocket.onopen = () => {
        console.log('Group Search WebSocket đã kết nối (/ws/group_search)');
    };

    groupSearchSocket.onmessage = (event) => {
        const receiveTime = performance.now();
        console.log(`Group Search: dữ liệu nhận. Thời gian: ${receiveTime - requestTime} ms`);
        
        try {
            data = JSON.parse(event.data);
            if (data.kq) {
                updateUIWithSearchResults(data.kq);
                const updateCompleteTime = performance.now();
                console.log(`Cập nhật UI xong. Tổng thời gian: ${updateCompleteTime - requestTime} ms`);
                toggleLoadingIndicator(false);
            } else if (data.error) {
                console.error("Lỗi từ server:", data.error);
                toggleLoadingIndicator(false);
            } else {
                console.error("Dữ liệu không có thuộc tính 'results':", data);
                toggleLoadingIndicator(false);
            }
        } catch (error) {
            console.error("Lỗi parse dữ liệu group search:", error);
            toggleLoadingIndicator(false);
        }
    };

    groupSearchSocket.onerror = (error) => {
        console.error('Lỗi Group Search WebSocket:', error);
        toggleLoadingIndicator(false);
    };

    groupSearchSocket.onclose = () => {
        console.log('Group Search WebSocket bị đóng. Thử kết nối lại sau 5 giây...');
        setTimeout(connectGroupSearchWebSocket, 5000);
    };
}

// Khởi tạo group-search WebSocket khi tải app
connectGroupSearchWebSocket();





///---------------------------------------------------------------------------------------------///
///---------------------------------------------------------------------------------------------///
///---------------------------------------------------------------------------------------------///



let alertSocket; // WebSocket để nhận/gửi thông báo

/**
 * Kết nối đến WebSocket /ws/alerts.
 * Dùng để nhận thông báo từ server (ví dụ: submit đúng/sai).
 */
function connectAlertWebSocket() {
    const tokenParam = window.API_KEY ? `?token=${encodeURIComponent(window.API_KEY)}` : '';
    alertSocket = new WebSocket(`ws://localhost:8000/ws/alerts${tokenParam}`);
    
    alertSocket.onopen = () => {
        console.log('Alert WebSocket đã kết nối (/ws/alerts)');
    };

    alertSocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'alert' && data.message) {
                // Hiển thị thông báo tạm thời trên màn hình
                showTemporaryAlert(data.message);
            }
        } catch (error) {
            console.error("Lỗi parse dữ liệu alert:", error);
        }
    };

    alertSocket.onerror = (error) => {
        console.error('Lỗi Alert WebSocket:', error);
    };

    alertSocket.onclose = () => {
        console.log('Alert WebSocket bị đóng. Thử kết nối lại sau 5 giây...');
        setTimeout(connectAlertWebSocket, 5000);
    };
}

/**
 * Gửi cảnh báo/thông báo cho các client khác qua WebSocket alerts.
 * @param {string} message - Nội dung thông báo
 */
/**
 * Gửi cảnh báo/thông báo cho các client khác qua WebSocket alerts.
 * @param {string} message - Nội dung thông báo
 */
function sendAlertViaWebSocket(message) {
    if (alertSocket && alertSocket.readyState === WebSocket.OPEN) {
        const alertData = {
            type: 'alert',
            message: message
        };
        alertSocket.send(JSON.stringify(alertData));
    } else {
        console.error('Alert WebSocket chưa mở. Không thể gửi alert.');
    }
}

/**
 * Tìm kiếm nhóm / lân cận bằng ID ảnh
 */
function performGroupSearch(imageId) {
    if (typeof groupSearchSocket !== 'undefined' && groupSearchSocket && groupSearchSocket.readyState === WebSocket.OPEN) {
        requestTime = performance.now();
        if (typeof toggleLoadingIndicator === 'function') toggleLoadingIndicator(true);
        groupSearchSocket.send(JSON.stringify({ imageId: imageId }));
    } else if (socket && socket.readyState === WebSocket.OPEN) {
        requestTime = performance.now();
        if (typeof toggleLoadingIndicator === 'function') toggleLoadingIndicator(true);
        socket.send(JSON.stringify({ type: 'group_search', imageId: imageId }));
    } else {
        console.error('WebSocket is not open for group search');
        if (typeof toggleLoadingIndicator === 'function') toggleLoadingIndicator(false);
    }
}

/**
 * Lấy nội dung truy vấn từ Search Scene
 */
async function getQueryContent(searchScene) {
    const textArea = searchScene.querySelector('textarea[name="Text_Query"]');
    const imageDropArea = searchScene.querySelector('.image-drop-area');
    const soundTextArea = searchScene.querySelector('textarea[name="Sound_Text"]');
    let detailsTextArea = searchScene.querySelector('textarea[name="QunNhiuChien_Query"]') || "";

    if (textArea && textArea.style.display !== 'none') { 
        const originalText = textArea.value;
        const translateCheckbox = document.getElementById('translate-checkbox');
        if (translateCheckbox && translateCheckbox.checked && typeof translateText === 'function') {
            const translatedText = await translateText(originalText);
            const translatedDetailText = detailsTextArea ? await translateText(detailsTextArea.value) : "";
            textArea.value = translatedText;
            if (detailsTextArea) detailsTextArea.value = translatedDetailText;
            return { type: 'text', content: translatedText, detail: translatedDetailText };
        } else {
            return { type: 'text', content: originalText };
        }
    } else if (imageDropArea && imageDropArea.style.display === 'flex') {
        const img = imageDropArea.querySelector('img');
        const translatedDetailText = (detailsTextArea && typeof translateText === 'function') ? await translateText(detailsTextArea.value) : "";
        if (detailsTextArea) detailsTextArea.value = translatedDetailText;
        if (img) {
            return { type: 'image', content: img.src, detail: translatedDetailText };
        }
    } else if (soundTextArea && soundTextArea.style.display !== 'none') {
        return { type: 'sound', content: soundTextArea.value };
    }
    return { type: 'text', content: '', detail: detailsTextArea ? detailsTextArea.value : "" };
}

/**
 * Thực hiện tìm kiếm kết hợp nhiều cảnh
 */
async function performCombinedSearch() {
    const searchScenes = document.querySelectorAll('.Search_Scene');
    const queries = [];

    const activeModelButton = document.querySelector('.model-option button.active');
    const modelType = activeModelButton ? activeModelButton.className.split(' ')[0] : 'unknown';

    for (const scene of searchScenes) {
        const activeModeButton = scene.querySelector('.mode-button button.active');
        const modeType = activeModeButton ? activeModeButton.className.split(' ')[0] : 'unknown';

        const query = await getQueryContent(scene);
        if (query.content) {
            queries.push({
                ...query,
                mode: modeType
            });
        }
    }

    if (socket && socket.readyState === WebSocket.OPEN) {
        let message = {
            type: 'multi_query',
            model: modelType,
            queries: queries.map(q => ({
                type: q.type,
                content: q.type === 'image' ? (q.content.includes(',') ? q.content.split(',')[1] : q.content) : q.content,
                mode: q.mode,
                detail: q.detail
            }))
        };

        requestTime = performance.now();
        socket.send(JSON.stringify(message));
    } else {
        console.error('WebSocket is not open. ReadyState:', socket ? socket.readyState : 'null');
        connectWebSocket();
    }
}

/**
 * Tìm kiếm kết hợp phân trang
 */
async function performPagnitionCombinedSearch() {
    if (typeof resetSearch === 'function') resetSearch();
    const searchScenes = document.querySelectorAll('.Search_Scene');
    const queries = [];

    const activeModelButton = document.querySelector('.model-option button.active');
    const modelType = activeModelButton ? activeModelButton.className.split(' ')[0] : 'unknown';

    const activeModeButton = document.querySelector('.mode-button button.active');
    const modeType = activeModeButton ? activeModeButton.className.split(' ')[0] : 'unknown';

    for (const scene of searchScenes) {
        const query = await getQueryContent(scene);
        if (query.content) {
            queries.push(query);
        }
    }

    if (typeof Pagnitionsocket !== 'undefined' && Pagnitionsocket && Pagnitionsocket.readyState === WebSocket.OPEN) {
        let message = {
            type: 'multi_query',
            model: modelType,
            mode: modeType,
            queries: queries.map(q => ({
                type: q.type,
                content: q.type === 'image' ? q.content.split(',')[1] : q.content
            })),
        };

        requestTime = performance.now();
        Pagnitionsocket.send(JSON.stringify(message));
    } else {
        console.error('Pagnitionsocket is not open.');
        connectWebSocket();
    }
}

// Khởi tạo tất cả các WebSocket còn lại khi tải app
connectSimilaritySearchWebSocket();
connectFilterWebSocket();
