///---------------------------------------------------------------------------------------------///
/// DRES SUBMISSION & LIVE CONTEST ENGINE (AIC 2026 / VBS)
/// Hỗ trợ đầy đủ KIS, Visual Q&A, và TRAKE với Proxy CORS và Modal cấu hình trực tiếp
///---------------------------------------------------------------------------------------------///

function showTemporaryAlert(message, type = 'info', duration = 4000) {
    let alertElement = document.getElementById('dres-temporary-alert');
    if (!alertElement) {
        alertElement = document.createElement('div');
        alertElement.id = 'dres-temporary-alert';
        document.body.appendChild(alertElement);
    }
    alertElement.innerHTML = message;
    alertElement.style.position = 'fixed';
    alertElement.style.top = '25px';
    alertElement.style.left = '50%';
    alertElement.style.transform = 'translateX(-50%)';
    alertElement.style.padding = '14px 28px';
    alertElement.style.borderRadius = '10px';
    alertElement.style.zIndex = '999999';
    alertElement.style.fontSize = '15px';
    alertElement.style.fontWeight = '700';
    alertElement.style.boxShadow = '0 15px 35px rgba(0,0,0,0.85)';
    alertElement.style.transition = 'all 0.3s ease';
    alertElement.style.display = 'block';

    const msgLower = (message || '').toLowerCase();
    
    // ƯU TIÊN KIỂM TRA LỖI / SAI TRƯỚC (Tránh 'chưa chính xác' bị match nhầm vào 'chính xác')
    const isError = type === 'error' 
        || msgLower.includes('wrong') 
        || msgLower.includes('error') 
        || msgLower.includes('thất bại') 
        || msgLower.includes('chưa chính xác') 
        || msgLower.includes('sai') 
        || msgLower.includes('hết hạn')
        || msgLower.includes('chưa chọn')
        || msgLower.includes('chưa có');

    const isSuccess = !isError && (
        type === 'success' 
        || msgLower.includes('correct') 
        || msgLower.includes('thành công') 
        || msgLower.includes('đã ghi nhận điểm')
        || (msgLower.includes('chính xác') && !msgLower.includes('chưa chính xác'))
    );

    if (isSuccess) {
        alertElement.style.backgroundColor = '#15803d'; // Xanh lá chuẩn
        alertElement.style.color = '#ffffff';
        alertElement.style.border = '2px solid #86efac';
        alertElement.style.boxShadow = '0 0 25px rgba(34, 197, 94, 0.6)';
    } else if (isError) {
        alertElement.style.backgroundColor = '#b91c1c'; // Đỏ chuẩn
        alertElement.style.color = '#ffffff';
        alertElement.style.border = '2px solid #fca5a5';
        alertElement.style.boxShadow = '0 0 25px rgba(239, 68, 68, 0.6)';
    } else {
        alertElement.style.backgroundColor = '#0f172a'; // Xanh dương / Dark slate
        alertElement.style.color = '#38bdf8';
        alertElement.style.border = '2px solid #38bdf8';
        alertElement.style.boxShadow = '0 0 25px rgba(56, 189, 248, 0.4)';
    }

    if (window._dresAlertTimer) clearTimeout(window._dresAlertTimer);
    window._dresAlertTimer = setTimeout(() => {
        if (alertElement && alertElement.parentNode) {
            alertElement.style.display = 'none';
        }
    }, duration);
}

// Trích xuất tên video chuẩn không có đuôi .mp4 và không dính đường dẫn thư mục hay keyframe
function cleanDresVideoName(rawItem) {
    if (!rawItem) return 'video';
    let s = String(rawItem).trim();

    // Nếu có dạng "L01_V001-14.8" hoặc "L01_V001_100" (tách theo timestamp nếu có)
    if (s.includes('-') && !s.includes('/') && !s.includes('\\')) {
        const p = s.split('-');
        if (p.length > 1 && !isNaN(parseFloat(p[1]))) {
            s = p[0].trim();
        }
    }

    // Bỏ query string và protocol URL
    if (s.includes('://')) {
        try {
            const u = new URL(s);
            s = u.pathname;
        } catch (e) {}
    }

    // 1. Dùng Regex chuẩn tìm mã định danh video Lxx_Vxxx
    const lMatch = s.match(/(L\d+_V\d+)/i);
    if (lMatch && lMatch[1]) {
        return lMatch[1].toUpperCase();
    }

    // 2. Dùng Regex chuẩn tìm video_xxx
    const vMatch = s.match(/(video_\d+)/i);
    if (vMatch && vMatch[1]) {
        return vMatch[1];
    }

    // 3. Tách theo đường dẫn / hoặc \
    const parts = s.split(/[/\\]/).filter(Boolean);
    const kfIdx = parts.findIndex(p => p.toLowerCase() === 'keyframes');
    if (kfIdx > 0 && parts[kfIdx - 1] && !parts[kfIdx - 1].includes(':')) {
        s = parts[kfIdx - 1];
    } else {
        let last = parts.pop() || '';
        if (/^keyframe_\d+/i.test(last) || last.toLowerCase().endsWith('.webp') || last.toLowerCase().endsWith('.jpg') || last.toLowerCase().endsWith('.png')) {
            let prev = parts.pop() || '';
            if (prev.toLowerCase() === 'keyframes') {
                prev = parts.pop() || '';
            }
            if (prev && !prev.includes(':')) {
                last = prev;
            }
        }
        s = last;
    }

    // Bỏ đuôi .mp4, .mkv, .webm, .avi, .webp, .jpg
    s = s.replace(/\.(mp4|mkv|avi|mov|webm|webp|jpg|jpeg|png)$/i, '').trim();
    return s || 'video';
}

// Tính timestamp chính xác theo millisecond (ms)
function calculateDresTimestampMs(item) {
    if (!item) return 0;
    if (item.timestampMs !== undefined && item.timestampMs !== null && !isNaN(parseInt(item.timestampMs)) && parseInt(item.timestampMs) > 0) {
        return parseInt(item.timestampMs, 10);
    }
    // Tìm trong chuỗi frameInfo: "L01_V001-14.8"
    if (item.frameInfo && typeof item.frameInfo === 'string') {
        const timeParts = item.frameInfo.split('-');
        if (timeParts.length > 1 && !isNaN(parseFloat(timeParts[1])) && parseFloat(timeParts[1]) > 0) {
            return Math.round(parseFloat(timeParts[1]) * 1000.0);
        }
    }
    // Tính theo frameId (chuẩn 25 FPS)
    const fid = parseInt(item.frameId, 10);
    if (!isNaN(fid) && fid > 0) {
        return Math.round(fid * (1000.0 / 25.0));
    }
    return 0;
}

function getFirstResultForKIS() {
    if (!exportedImages || exportedImages.length === 0) return null;
    // Ưu tiên lấy ảnh mới nhất được thêm vào khay (top of mind của thí sinh)
    return exportedImages[exportedImages.length - 1];
}

function getFirstResultForVQA() {
    let ans = '';
    // 1. Kiểm tra ô nhập đáp án nhanh trên Export Header
    const commonVqa = document.getElementById('vqa-common-answer');
    if (commonVqa && commonVqa.value && commonVqa.value.trim()) {
        ans = commonVqa.value.trim();
    }
    // 2. Nếu chưa có, lấy đáp án từ ô nhập trên thẻ ảnh trong Export Area
    if (!ans) {
        const vqaElements = document.querySelectorAll(".vqa-input");
        for (let el of vqaElements) {
            if (el && el.value && el.value.trim()) {
                ans = el.value.trim();
                break;
            }
        }
    }
    // 3. Nếu vẫn chưa có, lấy đáp án từ ô QA_Query trên Left Panel
    if (!ans) {
        const leftQa = document.querySelector('textarea[name="QA_Query"]');
        if (leftQa && leftQa.value && leftQa.value.trim()) {
            ans = leftQa.value.trim();
        }
    }
    const targetImg = (exportedImages && exportedImages.length > 0) ? exportedImages[exportedImages.length - 1] : null;
    return [targetImg, ans];
}

/**
 * Hàm nộp bài chính lên hệ thống DRES
 * Tự động phân luồng theo 3 task: KIS, VQA (Q&A), TRAKE
 */
async function submit_to_dres_v2() {
    const isVqaMode = (typeof activeTask !== 'undefined' && (activeTask === 'vqa' || activeTask === 'qa'))
        || document.querySelector('.task-mode-btn[data-task="qa"].active') !== null
        || (document.querySelector('#vqa') && document.querySelector('#vqa').classList.contains('active'));

    const isTrakeMode = (typeof activeTask !== 'undefined' && activeTask === 'trake')
        || document.querySelector('.task-mode-btn[data-task="trake"].active') !== null
        || (document.querySelector('#trake-task-btn') && document.querySelector('#trake-task-btn').classList.contains('active'));

    // Kiểm tra có ảnh trong khay chưa
    if (!isVqaMode && (!exportedImages || exportedImages.length === 0)) {
        showTemporaryAlert("⚠️ Bạn chưa chọn frame nào vào Khay Nộp! Vui lòng bấm dấu [+] trên ảnh để chọn trước khi nộp.", "error");
        return;
    }

    const evaluationID = (localStorage.getItem('evaluationID') || '').trim();
    const contestSessionID = (localStorage.getItem('contestSessionID') || '').trim();
    const dresBaseUrl = (localStorage.getItem('dresBaseUrl') || 'http://192.168.28.151:5000').replace(/\/+$/, '');

    if (!contestSessionID) {
        showTemporaryAlert("⚠️ Chưa có Session ID DRES! Đang mở bảng Cấu hình để bạn đăng nhập...", "error");
        openDresConfigModal();
        return;
    }

    if (!evaluationID) {
        showTemporaryAlert("⚠️ Chưa chọn Cuộc thi (Evaluation ID)! Đang mở bảng Cấu hình...", "error");
        openDresConfigModal();
        return;
    }

    const contestURL = `${dresBaseUrl}/api/v2/submit/${evaluationID}?session=${contestSessionID}`;
    showTemporaryAlert("⏳ Đang gửi kết quả lên hệ thống DRES...", "info");

    if (isTrakeMode) {
        // ==========================================
        // DẠNG 1: TRAKE (Targeted Retrieval & Keyframe Extraction)
        // ==========================================
        const currentCandidateId = (typeof activeTrakeCandidate !== 'undefined') ? activeTrakeCandidate : 1;
        let cFrames = exportedImages.filter(img => (img.candidateId || 1) === currentCandidateId);
        if (cFrames.length === 0) cFrames = exportedImages;

        cFrames.sort((a, b) => (a.frameId || 0) - (b.frameId || 0));
        if (cFrames.length === 0) {
            showTemporaryAlert("⚠️ Chưa có frame nào trong Phương án TRAKE hiện tại!", "error");
            return;
        }

        const firstItem = cleanDresVideoName(cFrames[0].videoName || cFrames[0].frameInfo || cFrames[0].videoFramePart);
        const answers = cFrames.map(f => {
            const ms = calculateDresTimestampMs(f);
            const vName = cleanDresVideoName(f.videoName || f.frameInfo || f.videoFramePart) || firstItem;
            return {
                "mediaItemName": vName,
                "start": Math.max(0, ms - 1500),
                "end": ms + 1500
            };
        });

        const payload = {
            "answerSets": [{
                "answers": answers
            }]
        };
        console.log("🚀 Submitting TRAKE to DRES:", payload);
        await submitFrameInfo(contestURL, payload);

    } else if (!isVqaMode) {
        // ==========================================
        // DẠNG 2: KIS (Known-Item Search)
        // ==========================================
        const frame_info = getFirstResultForKIS();
        const item = cleanDresVideoName(frame_info.videoName || frame_info.frameInfo || frame_info.videoFramePart);
        const frameMs = calculateDresTimestampMs(frame_info);

        const payload = {
            "answerSets": [{
                "answers": [{
                    "mediaItemName": item,
                    "start": Math.max(0, frameMs - 2500), // Mở rộng cửa sổ ±2.5s
                    "end": frameMs + 2500
                }]
            }]
        };
        console.log("🚀 Submitting KIS to DRES:", payload);
        await submitFrameInfo(contestURL, payload);

    } else {
        // ==========================================
        // DẠNG 3: Q&A (Question & Answer)
        // ==========================================
        const [targetImg, answer_vqa] = getFirstResultForVQA();
        if (!answer_vqa || !answer_vqa.trim()) {
            showTemporaryAlert("⚠️ Bạn chưa nhập đáp án Q&A! Vui lòng gõ đáp án vào ô màu Cyan trước khi nộp.", "error");
            return;
        }

        const candidateAnswers = answer_vqa.split(/[|;\n]/).map(s => s.trim()).filter(Boolean);
        let payloadAnswers = [];

        if (exportedImages && exportedImages.length > 0) {
            for (let img of exportedImages) {
                const item = cleanDresVideoName(img.videoName || img.frameInfo || img.videoFramePart);
                const frameMs = calculateDresTimestampMs(img);
                const perFrameRaw = (img.frameId !== undefined && typeof vqaInputs !== 'undefined' ? vqaInputs[img.frameId] : '') || '';
                const frameAnswers = perFrameRaw ? perFrameRaw.split(/[|;\n]/).map(s => s.trim()).filter(Boolean) : candidateAnswers;

                for (let ans of frameAnswers) {
                    // ✅ DRES Q&A spec (ApiClientAnswer):
                    // - "text" = đáp án thuần túy (KHÔNG ghép video/timestamp vào đây)
                    // - "mediaItemName" + "start" + "end" = vị trí video để DRES kiểm tra ngữ cảnh
                    payloadAnswers.push({
                        "text": ans,
                        "mediaItemName": item,
                        "start": Math.max(0, frameMs - 2500),
                        "end": frameMs + 2500
                    });
                }
            }
        } else {
            // Fallback: không có frame trong khay, chỉ gửi text đáp án
            for (let ans of candidateAnswers) {
                payloadAnswers.push({
                    "text": ans
                });
            }
        }

        const payload = {
            "answerSets": [{
                "answers": payloadAnswers
            }]
        };
        console.log(`🚀 Submitting Q&A (${payloadAnswers.length} biến thể) to DRES:`, payload);
        await submitFrameInfo(contestURL, payload);
    }
}

/**
 * Nộp trực tiếp 1 frame từ Video Player hoặc Card mà không cần ghim vào khay
 */
async function submitSingleFrameToDres(videoName, frameId, timestampMs, imageSrc) {
    const evaluationID = (localStorage.getItem('evaluationID') || '').trim();
    const contestSessionID = (localStorage.getItem('contestSessionID') || '').trim();
    const dresBaseUrl = (localStorage.getItem('dresBaseUrl') || 'http://192.168.28.151:5000').replace(/\/+$/, '');

    if (!contestSessionID || !evaluationID) {
        showTemporaryAlert("⚠️ Chưa kết nối phiên thi DRES! Đang mở bảng Cấu hình...", "error");
        openDresConfigModal();
        return;
    }

    const item = cleanDresVideoName(videoName);
    let ms = 0;
    if (timestampMs !== undefined && timestampMs !== null && !isNaN(parseInt(timestampMs))) {
        ms = parseInt(timestampMs, 10);
    } else if (frameId !== undefined && !isNaN(parseInt(frameId))) {
        ms = Math.round(parseInt(frameId, 10) * (1000.0 / 25.0));
    }

    const contestURL = `${dresBaseUrl}/api/v2/submit/${evaluationID}?session=${contestSessionID}`;
    const payload = {
        "answerSets": [{
            "answers": [{
                "mediaItemName": item,
                "start": Math.max(0, ms - 2500),
                "end": ms + 2500
            }]
        }]
    };

    showTemporaryAlert(`⏳ Đang nộp trực tiếp ${item} (Frame ${frameId})...`, "info");
    await submitFrameInfo(contestURL, payload);
}

/**
 * Gửi payload nộp bài qua Backend Proxy (chống CORS) và phân tích kết quả phản hồi
 */
async function submitFrameInfo(url, body) {
    const evaluationID = localStorage.getItem('evaluationID');
    const contestSessionID = localStorage.getItem('contestSessionID');
    const dresBaseUrl = (localStorage.getItem('dresBaseUrl') || 'http://192.168.28.151:5000').replace(/\/+$/, '');

    try {
        let responseData = null;
        let isWrong = false;

        // 1. Thử gửi qua Backend Proxy trước để chống 100% lỗi CORS của trình duyệt
        try {
            const proxyResp = await fetch('http://localhost:8000/api/dres/submit', {
                method: "POST",
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    dres_url: dresBaseUrl,
                    evaluation_id: evaluationID,
                    session_id: contestSessionID,
                    payload: body
                })
            });
            if (proxyResp.ok) {
                const proxyData = await proxyResp.json();
                if (proxyData.status === 'success') {
                    responseData = proxyData.dres_response;
                } else if (proxyData.code) {
                    if (proxyData.code === 404 || (proxyData.detail && proxyData.detail.toUpperCase().includes('WRONG'))) {
                        isWrong = true;
                    }
                    responseData = { status: false, description: proxyData.detail };
                }
            }
        } catch (proxyErr) {
            console.warn("Backend proxy submit failed, fallback to direct fetch:", proxyErr);
        }

        // 2. Fallback gửi trực tiếp nếu proxy chưa xử lý được
        if (!responseData) {
            const response = await fetch(url, {
                method: "POST",
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (!response.ok) {
                let message;
                if (response.status === 401) {
                    message = "❌ Lỗi 401: Phiên đăng nhập DRES đã hết hạn. Vui lòng bấm 'DRES' trên thanh công cụ để đăng nhập lại!";
                } else if (response.status === 404) {
                    message = "❌ Kết quả nộp bài: WRONG (Chưa chính xác)!";
                    isWrong = true;
                } else {
                    message = `❌ Lỗi máy chủ DRES: HTTP ${response.status}`;
                }
                showTemporaryAlert(message, "error");
                if (typeof sendAlertViaWebSocket === 'function') sendAlertViaWebSocket(message);
                return;
            }
            responseData = await response.json();
        }

        console.log("📥 Phản hồi từ máy chủ DRES:", responseData);

        // 3. Đánh giá verdict từ máy chủ DRES (Theo OpenAPI DRES v2: status, submission, description)
        const verdict = (responseData?.submission || '').toString().toUpperCase();
        const description = responseData?.description || '';

        if (isWrong || verdict === 'WRONG' || responseData?.status === false) {
            const desc = description ? ` (${description})` : '';
            showTemporaryAlert(`❌ Kết quả nộp bài DRES: <strong style="color:#FCA5A5">WRONG (Chưa chính xác)</strong>!${desc}`, "error", 5000);
            if (typeof sendAlertViaWebSocket === 'function') sendAlertViaWebSocket('Submission wrong!');
        } else if (verdict === 'CORRECT' || verdict === 'SUCCESS') {
            console.log('Submission Success:', responseData);
            showTemporaryAlert("🎉🎉 NỘP BÀI THÀNH CÔNG — <strong style=" + '"color:#86EFAC"' + ">CORRECT (ĐÃ GHI NHẬN ĐIỂM!)</strong>", "success", 6000);
            if (typeof sendAlertViaWebSocket === 'function') sendAlertViaWebSocket('Submission successful!');
            
            // Tự động dọn dẹp khay sau khi nộp đúng để sẵn sàng câu tiếp theo
            setTimeout(() => {
                if (typeof resetExportArea === 'function') resetExportArea();
            }, 1200);
        } else if (verdict === 'INDETERMINATE' || verdict === 'UNDECIDABLE') {
            showTemporaryAlert(`⏳ Đang chờ Giám khảo chấm: <strong>${verdict}</strong> (${description || 'Pending'})`, "info", 5000);
        } else {
            showTemporaryAlert(`ℹ️ Đã gửi đáp án lên DRES: ${verdict || (responseData?.status ? 'Đã nhận' : 'Chưa rõ')} ${description}`, "info", 4000);
        }
    } catch (error) {
        console.error('Error during DRES submission:', error);
        showTemporaryAlert(`❌ Lỗi kết nối DRES: ${error.message}. Vui lòng kiểm tra lại địa chỉ DRES Server!`, "error", 5000);
        if (typeof sendAlertViaWebSocket === 'function') sendAlertViaWebSocket(`Error: ${error.message}`);
    }
}

//---------------------------------------------------------------------------------------------//
// DRES CONFIG & LIVE STATUS MODAL MANAGEMENT
//---------------------------------------------------------------------------------------------//

function openDresConfigModal() {
    let modal = document.getElementById('dresConfigModal');
    if (!modal) {
        console.error("Không tìm thấy element #dresConfigModal");
        return;
    }

    // Load saved values
    const savedUrl = localStorage.getItem('dresBaseUrl') || 'http://192.168.28.151:5000';
    const savedUser = localStorage.getItem('userName') || '';
    const savedSession = localStorage.getItem('contestSessionID') || '';
    const savedEval = localStorage.getItem('evaluationID') || '';

    const urlInp = document.getElementById('dres_modal_url');
    const userInp = document.getElementById('dres_modal_username');
    const sessInp = document.getElementById('dres_modal_session');
    const evalInp = document.getElementById('dres_modal_eval');

    if (urlInp) urlInp.value = savedUrl;
    if (userInp) userInp.value = savedUser;
    if (sessInp) sessInp.value = savedSession;
    if (evalInp) evalInp.value = savedEval;

    modal.style.display = 'flex';
    modal.style.zIndex = '999999';
}

function closeDresConfigModal() {
    const modal = document.getElementById('dresConfigModal');
    if (modal) modal.style.display = 'none';
}

async function testDresConnection() {
    const urlInp = document.getElementById('dres_modal_url');
    const sessInp = document.getElementById('dres_modal_session');
    const statusBox = document.getElementById('dres-modal-status');
    const evalSelect = document.getElementById('dres_modal_eval_select');

    const dresUrl = (urlInp?.value || 'http://192.168.28.151:5000').trim().replace(/\/+$/, '');
    const sessionId = (sessInp?.value || '').trim();

    if (statusBox) {
        statusBox.style.display = 'block';
        statusBox.className = 'dres-status-info';
        statusBox.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang kiểm tra kết nối tới máy chủ DRES...';
    }

    try {
        const resp = await fetch('http://localhost:8000/api/dres/status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dres_url: dresUrl, session_id: sessionId })
        });

        const data = await resp.json();
        if (data.status === 'success' && data.connected) {
            let evalOptions = '';
            if (data.evaluations && data.evaluations.length > 0) {
                evalOptions = data.evaluations.map(ev => `<option value="${ev.id}">${ev.name || ev.id} (${ev.status || 'ACTIVE'})</option>`).join('');
                if (evalSelect) {
                    evalSelect.innerHTML = `<option value="">-- Chọn cuộc thi --</option>` + evalOptions;
                    evalSelect.style.display = 'block';
                    evalSelect.value = data.evaluations[0].id;
                    const evalInp = document.getElementById('dres_modal_eval');
                    if (evalInp) evalInp.value = data.evaluations[0].id;
                }
            }
            if (statusBox) {
                statusBox.className = 'dres-status-success';
                statusBox.innerHTML = `✅ Kết nối DRES Server THÀNH CÔNG! Tìm thấy ${data.evaluations?.length || 0} cuộc thi đang chạy.`;
            }
            updateDresStatusBadge(true);
        } else {
            if (statusBox) {
                statusBox.className = 'dres-status-error';
                statusBox.innerHTML = `❌ Không thể lấy danh sách cuộc thi: ${data.detail || 'Lỗi không xác định'}`;
            }
            updateDresStatusBadge(false);
        }
    } catch (err) {
        if (statusBox) {
            statusBox.className = 'dres-status-error';
            statusBox.innerHTML = `❌ Lỗi kết nối: ${err.message}`;
        }
        updateDresStatusBadge(false);
    }
}

async function loginDresFromModal() {
    const urlInp = document.getElementById('dres_modal_url');
    const userInp = document.getElementById('dres_modal_username');
    const passInp = document.getElementById('dres_modal_password');
    const sessInp = document.getElementById('dres_modal_session');
    const evalInp = document.getElementById('dres_modal_eval');
    const statusBox = document.getElementById('dres-modal-status');

    const dresUrl = (urlInp?.value || 'http://192.168.28.151:5000').trim().replace(/\/+$/, '');
    const username = (userInp?.value || '').trim();
    const password = (passInp?.value || '').trim();

    if (!username || !password) {
        if (statusBox) {
            statusBox.style.display = 'block';
            statusBox.className = 'dres-status-error';
            statusBox.innerHTML = '⚠️ Vui lòng nhập Username và Mật khẩu DRES!';
        }
        return;
    }

    if (statusBox) {
        statusBox.style.display = 'block';
        statusBox.className = 'dres-status-info';
        statusBox.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang đăng nhập vào máy chủ DRES...';
    }

    try {
        const resp = await fetch('http://localhost:8000/api/dres/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dres_url: dresUrl, username, password })
        });

        const data = await resp.json();
        if (resp.ok && data.sessionId) {
            if (sessInp) sessInp.value = data.sessionId;
            if (evalInp && data.evaluationID) evalInp.value = data.evaluationID;

            localStorage.setItem('dresBaseUrl', dresUrl);
            localStorage.setItem('userName', username);
            localStorage.setItem('contestSessionID', data.sessionId);
            if (data.evaluationID) localStorage.setItem('evaluationID', data.evaluationID);

            if (statusBox) {
                statusBox.className = 'dres-status-success';
                statusBox.innerHTML = `🎉 Đăng nhập DRES THÀNH CÔNG!<br>Session ID: <code>${data.sessionId.substring(0, 16)}...</code> | Evaluation ID: <code>${(data.evaluationID || 'Tự động').substring(0, 12)}...</code>`;
            }
            updateDresStatusBadge(true);
            showTemporaryAlert("✅ Đã kết nối phiên thi đấu DRES thành công!", "success");
        } else {
            if (statusBox) {
                statusBox.className = 'dres-status-error';
                statusBox.innerHTML = `❌ Đăng nhập thất bại: ${data.detail || 'Sai tài khoản hoặc mật khẩu'}`;
            }
            updateDresStatusBadge(false);
        }
    } catch (err) {
        if (statusBox) {
            statusBox.className = 'dres-status-error';
            statusBox.innerHTML = `❌ Lỗi kết nối máy chủ: ${err.message}`;
        }
        updateDresStatusBadge(false);
    }
}

function saveDresManualConfig() {
    const urlInp = document.getElementById('dres_modal_url');
    const userInp = document.getElementById('dres_modal_username');
    const sessInp = document.getElementById('dres_modal_session');
    const evalInp = document.getElementById('dres_modal_eval');

    const dresUrl = (urlInp?.value || 'http://192.168.28.151:5000').trim().replace(/\/+$/, '');
    const username = (userInp?.value || '').trim();
    const sessionId = (sessInp?.value || '').trim();
    const evaluationId = (evalInp?.value || '').trim();

    localStorage.setItem('dresBaseUrl', dresUrl);
    if (username) localStorage.setItem('userName', username);
    if (sessionId) localStorage.setItem('contestSessionID', sessionId);
    if (evaluationId) localStorage.setItem('evaluationID', evaluationId);

    showTemporaryAlert("💾 Đã lưu cấu hình DRES thành công!", "success");
    closeDresConfigModal();
    updateDresStatusBadge(Boolean(sessionId && evaluationId));
}

function updateDresStatusBadge(isConnected) {
    const btn = document.getElementById('dres-config-button');
    if (!btn) return;
    if (isConnected) {
        btn.classList.add('connected');
        btn.classList.remove('disconnected');
        btn.innerHTML = '<i class="fa-solid fa-bolt" style="color:#10B981"></i> DRES 🟢';
        btn.title = `Đã kết nối DRES (${localStorage.getItem('dresBaseUrl') || 'Connected'})`;
    } else {
        btn.classList.add('disconnected');
        btn.classList.remove('connected');
        btn.innerHTML = '<i class="fa-solid fa-server"></i> DRES';
        btn.title = 'Nhấp để đăng nhập / cấu hình DRES';
    }
}

// Khởi chạy khi DOM load
document.addEventListener('DOMContentLoaded', () => {
    const sess = localStorage.getItem('contestSessionID');
    const evalId = localStorage.getItem('evaluationID');
    updateDresStatusBadge(Boolean(sess && evalId));

    if (typeof connectWebSocket === 'function') connectWebSocket();
    if (typeof connectFilterWebSocket === 'function') connectFilterWebSocket();
    if (typeof connectAlertWebSocket === 'function') connectAlertWebSocket();
});

// Expose toàn bộ hàm ra window để gọi từ HTML onclick và phím tắt
window.openDresConfigModal = openDresConfigModal;
window.closeDresConfigModal = closeDresConfigModal;
window.testDresConnection = testDresConnection;
window.loginDresFromModal = loginDresFromModal;
window.saveDresManualConfig = saveDresManualConfig;
window.submit_to_dres_v2 = submit_to_dres_v2;
window.submitSingleFrameToDres = submitSingleFrameToDres;
window.updateDresStatusBadge = updateDresStatusBadge;