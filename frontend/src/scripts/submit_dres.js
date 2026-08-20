
///---------------------------------------------------------------------------------------------///
/// DRES SUBMIT MODULE — HIGH CONTRAST & DYNAMIC SERVER CONFIG
///---------------------------------------------------------------------------------------------///

function showTemporaryAlert(message, type = 'info') {
    let alertElement = document.getElementById('dres-temporary-alert');
    if (!alertElement) {
        alertElement = document.createElement('div');
        alertElement.id = 'dres-temporary-alert';
        document.body.appendChild(alertElement);
    }
    alertElement.textContent = message;
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

    const msgLower = (message || '').toLowerCase();
    if (type === 'success' || msgLower.includes('successful') || msgLower.includes('correct') || msgLower.includes('thành công')) {
        alertElement.style.backgroundColor = '#15803d';
        alertElement.style.color = '#ffffff';
        alertElement.style.border = '2px solid #86efac';
    } else if (type === 'error' || msgLower.includes('wrong') || msgLower.includes('error') || msgLower.includes('thất bại') || msgLower.includes('chưa')) {
        alertElement.style.backgroundColor = '#b91c1c';
        alertElement.style.color = '#ffffff';
        alertElement.style.border = '2px solid #fca5a5';
    } else {
        alertElement.style.backgroundColor = '#0f172a';
        alertElement.style.color = '#38bdf8';
        alertElement.style.border = '2px solid #38bdf8';
    }

    setTimeout(() => {
        if (alertElement && alertElement.parentNode) {
            alertElement.remove();
        }
    }, 3500);
}

// Call this function when the page loads
document.addEventListener('DOMContentLoaded', () => {
    connectWebSocket();
    connectFilterWebSocket();
    connectAlertWebSocket();
});

function getFirstResultForKIS(){
    // Luôn ưu tiên lấy ảnh MỚI NHẤT được người dùng bấm chọn (+)
    if (!exportedImages || exportedImages.length === 0) return null;
    return exportedImages[exportedImages.length - 1];
}

function getFirstResultForVQA(){
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

async function submit_to_dres_v2() {
    const isVqaMode = (typeof activeTask !== 'undefined' && (activeTask === 'vqa' || activeTask === 'qa'))
        || document.querySelector('.task-mode-btn[data-task="qa"].active') !== null
        || (document.querySelector('#vqa') && document.querySelector('#vqa').classList.contains('active'));

    // Kiểm tra điều kiện nộp bài
    if (!isVqaMode) {
        if (!exportedImages || exportedImages.length === 0) {
            showTemporaryAlert("⚠️ Bạn chưa chọn ảnh nào để nộp bài KIS! Vui lòng bấm dấu [+] trên ảnh.", "error");
            return;
        }
    }

    const evaluationID = localStorage.getItem('evaluationID') || '74c9d753-cc72-43b5-8978-64a4113af754';
    const contestSessionID = localStorage.getItem('contestSessionID') || 'TZmWaYvS8WJzrPgEu7KGeKTWyl64Nmj-';
    const dresBaseUrl = (localStorage.getItem('dresBaseUrl') || 'http://192.168.28.151:5000').replace(/\/+$/, '');

    // Đảm bảo lưu vào localStorage
    localStorage.setItem('dresBaseUrl', dresBaseUrl);
    localStorage.setItem('contestSessionID', contestSessionID);
    localStorage.setItem('evaluationID', evaluationID);

    const contestURL = `${dresBaseUrl}/api/v2/submit/${evaluationID}?session=${contestSessionID}`;
    showTemporaryAlert("⏳ Đang gửi kết quả lên hệ thống DRES...", "info");

    if (!isVqaMode) {
        // DẠNG 1: KIS (Known-Item Search)
        const frame_info = getFirstResultForKIS();
        let rawItem = (frame_info.frameInfo || '').split('-')[0] || (frame_info.videoFramePart || '').split('/')[0];
        const item = rawItem.includes('/') ? rawItem.split('/').pop().replace(/\.mp4$/i, '') : rawItem.replace(/\.mp4$/i, '');
        
        let frameMs = 0;
        if (frame_info.timestampMs !== undefined && frame_info.timestampMs !== null) {
            frameMs = parseInt(frame_info.timestampMs);
        } else {
            const timeParts = (frame_info.frameInfo || '').split('-');
            if (timeParts.length > 1 && !isNaN(parseFloat(timeParts[1])) && parseFloat(timeParts[1]) > 0) {
                frameMs = Math.round(parseFloat(timeParts[1]) * 1000.0);
            } else if (frame_info.frameId !== undefined && !isNaN(parseFloat(frame_info.frameId))) {
                frameMs = Math.round(parseFloat(frame_info.frameId) * (1000.0 / 25.0));
            }
        }

        const payload = {
            "answerSets": [{
                "answers": [{
                    "mediaItemName": item,
                    "start": frameMs,
                    "end": frameMs
                }]
            }]
        };
        console.log("🚀 Submitting KIS to DRES:", payload);
        await submitFrameInfo(contestURL, payload);
    } else {
        // DẠNG 2: Q&A (Question & Answer)
        const [targetImg, answer_vqa] = getFirstResultForVQA();
        if (!answer_vqa || !answer_vqa.trim()) {
            showTemporaryAlert("⚠️ Bạn chưa nhập đáp án Q&A! Vui lòng gõ đáp án vào ô màu Cyan trước khi nộp.", "error");
            return;
        }

        let payloadAnswers = [];
        if (targetImg) {
            let rawItem = (targetImg.frameInfo || '').split('-')[0] || (targetImg.videoFramePart || '').split('/')[0];
            const item = rawItem.includes('/') ? rawItem.split('/').pop().replace(/\.mp4$/i, '') : rawItem.replace(/\.mp4$/i, '');
            
            let frameMs = 0;
            if (targetImg.timestampMs !== undefined && targetImg.timestampMs !== null) {
                frameMs = parseInt(targetImg.timestampMs);
            } else {
                const timeParts = (targetImg.frameInfo || '').split('-');
                if (timeParts.length > 1 && !isNaN(parseFloat(timeParts[1])) && parseFloat(timeParts[1]) > 0) {
                    frameMs = Math.round(parseFloat(timeParts[1]) * 1000.0);
                } else if (targetImg.frameId !== undefined && !isNaN(parseFloat(targetImg.frameId))) {
                    frameMs = Math.round(parseFloat(targetImg.frameId) * (1000.0 / 25.0));
                }
            }
            payloadAnswers.push({
                "text": `${answer_vqa.trim()}-${item}-${frameMs}`
            });
        } else {
            // Nộp đáp án thuần văn bản / chữ số (Pure Text QA)
            payloadAnswers.push({
                "text": `${answer_vqa.trim()}`
            });
        }

        const payload = {
            "answerSets": [{
                "answers": payloadAnswers
            }]
        };
        console.log("🚀 Submitting Q&A to DRES:", payload);
        await submitFrameInfo(contestURL, payload);
    }
}

async function submitFrameInfo(url, body) {
    const evaluationID = localStorage.getItem('evaluationID');
    const contestSessionID = localStorage.getItem('contestSessionID');
    const dresBaseUrl = (localStorage.getItem('dresBaseUrl') || 'http://192.168.28.151:5000').replace(/\/+$/, '');

    try {
        let responseData = null;
        let isSuccess = false;

        // 1. Gửi qua Backend Proxy trước để chống lỗi chặn CORS trình duyệt
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
                    isSuccess = true;
                } else if (proxyData.code) {
                    responseData = { status: false, description: proxyData.detail };
                }
            }
        } catch (proxyErr) {
            console.warn("Backend proxy submit failed, fallback to direct fetch:", proxyErr);
        }

        // 2. Fallback gửi trực tiếp nếu proxy chưa trả về kết quả
        if (!responseData && !isSuccess) {
            const response = await fetch(url, {
                method: "POST",
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (!response.ok) {
                let message;
                if (response.status === 401) {
                    message = "❌ Lỗi 401: Phiên đăng nhập DRES đã hết hạn. Vui lòng đăng nhập lại!";
                } else if (response.status === 404) {
                    message = "❌ Kết quả nộp bài: WRONG (Sai)!";
                } else {
                    message = `❌ Lỗi máy chủ DRES: Mã ${response.status}`;
                }
                showTemporaryAlert(message, "error");
                if (typeof sendAlertViaWebSocket === 'function') sendAlertViaWebSocket(message);
                return;
            }
            responseData = await response.json();
        }

        if (!responseData || responseData.submission === 'WRONG' || responseData.status === false) {
            const desc = responseData && responseData.description ? ` (${responseData.description})` : '';
            showTemporaryAlert(`❌ Kết quả nộp bài: WRONG (Chưa chính xác)!${desc}`, "error");
            if (typeof sendAlertViaWebSocket === 'function') sendAlertViaWebSocket('Submission wrong!');
        } else {
            console.log('Submission Success:', responseData);
            showTemporaryAlert("🎉 Nộp bài THÀNH CÔNG (CORRECT)! Kết quả đã được hệ thống DRES ghi nhận!", "success");
            if (typeof sendAlertViaWebSocket === 'function') sendAlertViaWebSocket('Submission successful!');
            // Tự động dọn dẹp danh sách xuất sau khi nộp đúng để sẵn sàng cho câu tiếp theo
            setTimeout(() => {
                if (typeof resetExportArea === 'function') resetExportArea();
            }, 1000);
        }
    } catch (error) {
        console.error('Error during DRES submission:', error);
        showTemporaryAlert(`❌ Lỗi kết nối DRES: ${error.message}`, "error");
        if (typeof sendAlertViaWebSocket === 'function') sendAlertViaWebSocket(`Error: ${error.message}`);
    }
}