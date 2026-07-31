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
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    if (!badge || !dot || !text) return;

    badge.className = `system-status-badge ${status}`;
    dot.className = `status-dot ${status}`;

    if (status === 'connected') {
        text.textContent = message || 'Hệ thống: Sẵn sàng 🟢';
    } else if (status === 'disconnected') {
        text.textContent = message || 'Hệ thống: Ngoại tuyến 🔴';
    } else {
        text.textContent = message || 'Hệ thống: Đang kết nối... 🟡';
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

let socket_share; // WebSocket để chia sẻ hình ảnh giữa các client

/**
 * Gửi cập nhật VQA input cho các client khác qua WebSocket share_image.
 * @param {string} frameId - ID của frame
 * @param {string} vqaInput - Nội dung VQA input cần chia sẻ
 */
function sendVqaInputUpdate(frameId, vqaInput) {
    if (socket_share && socket_share.readyState === WebSocket.OPEN) {
        const message = JSON.stringify({
            type: 'vqa_input_update',
            frameId: frameId,
            vqaInput: vqaInput
        });
        socket_share.send(message);
    } else {
        console.error('WebSocket share không mở. Không thể gửi VQA input update.');
    }
}

/**
 * Kết nối đến WebSocket /ws/share_image.
 * Xử lý việc chia sẻ hình ảnh và VQA input giữa các client.
 */
function connectWebSocketcrossing() {
  const tokenParam = window.API_KEY ? `?token=${encodeURIComponent(window.API_KEY)}` : '';
  socket_share = new WebSocket(`ws://localhost:8000/ws/share_image${tokenParam}`);
  
  socket_share.onopen = () => {
    console.log('Share WebSocket đã kết nối (/ws/share_image)');
  };

  socket_share.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      
      if (data.type === 'image_share') {
        // Nhận hình ảnh được chia sẻ từ client khác
        if (data.frameId && data.src && data.frameInfo) {
          addImageToExportArea(data.frameId, data.src, data.frameInfo, false);
        } else {
          console.error("Dữ liệu hình ảnh nhận không đủ thuộc tính:", data);
        }
      } else if (data.type === 'vqa_input_update') {
        // Nhận cập nhật VQA input từ client khác
        if (data.frameId && data.vqaInput !== undefined) {
          updateVqaInput(data.frameId, data.vqaInput);
        } else {
          console.error("Dữ liệu VQA input update không đủ thuộc tính:", data);
        }
      }
    } catch (error) {
      console.error("Lỗi parse dữ liệu share:", error);
    }
  };

  socket_share.onerror = (error) => {
    console.error('Lỗi Share WebSocket:', error);
  };

  socket_share.onclose = () => {
    console.log('Share WebSocket bị đóng. Thử kết nối lại sau 5 giây...');
    setTimeout(connectWebSocketcrossing, 5000);
  };
}




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
 * Thực hiện tìm kiếm tương tự với frame có ID cho trước.
 * @param {string} vectorId - ID của vector/frame cần tìm
 */
function performSimilaritySearch(vectorId) {
    if (similaritySearchSocket.readyState === WebSocket.OPEN) {
        requestTime = performance.now();
        toggleLoadingIndicator(true);
        similaritySearchSocket.send(JSON.stringify({ vector: vectorId }));
    } else {
        console.error('Similarity Search WebSocket chưa mở');
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

// Khởi tạo tất cả các WebSocket còn lại khi tải app
// (connectWebSocket và connectWebSocketcrossing được gọi trong DOMContentLoaded của submit_dres.js)
connectSimilaritySearchWebSocket();
connectFilterWebSocket();
