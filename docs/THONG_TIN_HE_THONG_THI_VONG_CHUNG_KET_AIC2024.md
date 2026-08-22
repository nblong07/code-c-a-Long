# HỘI THI THỬ THÁCH TRÍ TUỆ NHÂN TẠO THÀNH PHỐ HỒ CHÍ MINH NĂM 2024

**Chủ đề:** Truy vấn sự kiện từ video

# Thông tin về hình thức và cách nộp bài vòng thi chung kết

## Nội dung thi vòng chung kết

Yêu cầu truy vấn vòng chung kết thuộc dạng **Known-Item Search** (**KIS**, tạm dịch là “tìm kiếm đối tượng được mô tả trước”), được thể hiện theo một trong hai dạng cụ thể sau:

### Yêu cầu truy vấn dạng văn bản (Textual KIS)

Ban giám khảo cung cấp mô tả bằng ngôn ngữ tự nhiên của một sự kiện. Các đội dự thi cần tìm ra chính xác đoạn video của sự kiện này. Đoạn mô tả có thể gồm nhiều ý, nhiều câu văn.

Ở vòng chung kết, **nội dung đoạn mô tả sẽ được cung cấp dần dần** trong thời gian dành cho câu truy vấn. Nếu đội dự thi tự tin vào kết quả tìm kiếm video từ những gợi ý ban đầu của đoạn mô tả, đội dự thi có thể nộp kết quả ngay để có thể được điểm rất cao cho câu truy vấn này nếu kết quả đúng.

Tuy nhiên, đội dự thi có thể thận trọng để chờ thêm các thông tin mô tả về sự kiện nhằm kiểm chứng kết quả tìm được. Các đội có thể tham khảo cách tính điểm ở vòng chung kết để có chiến thuật nộp bài hợp lý.

### Yêu cầu truy vấn dạng hình ảnh hay video (Video KIS)

Thay vì mô tả bằng ngôn ngữ tự nhiên, các đội dự thi sẽ xem một đoạn video ngắn, **không quá 20 giây**, được trích ra từ một sự kiện nào đó trong kho dữ liệu video đã cho.

Các đội **không được phép chụp ảnh hoặc ghi hình đoạn video này bằng bất kỳ phương tiện điện tử nào để đưa vào công cụ của mình**, mà phải tìm cách phù hợp để diễn tả yêu cầu tìm kiếm, ví dụ như:

- Mô tả bằng ngôn ngữ tự nhiên nội dung video.
- Vẽ lại bối cảnh mình nhìn thấy.

### Yêu cầu truy vấn dạng Q&A

Ban giám khảo cung cấp mô tả bằng ngôn ngữ tự nhiên của một sự kiện và câu hỏi về thông tin trong sự kiện này. Các đội dự thi cần tìm ra chính xác đoạn video của sự kiện.

Đoạn mô tả có thể gồm nhiều ý, nhiều câu văn. Câu trả lời là một chuỗi gồm các ký tự từ **“0” đến “9”**.

Ở vòng chung kết:

- Câu hỏi sẽ được cung cấp ngay từ đầu.
- Nội dung đoạn mô tả sẽ được cung cấp lần lượt theo thời gian dành cho câu truy vấn.
- Nếu đội dự thi tự tin vào kết quả tìm kiếm video từ những mô tả ban đầu, đội dự thi có thể nộp kết quả sớm để có thể được điểm cao cho câu truy vấn này nếu kết quả đúng.
- Đội dự thi cũng có thể thận trọng chờ thêm các mô tả tiếp theo về sự kiện để kiểm chứng kết quả tìm được.

## Cách tính điểm ở vòng chung kết

- Mỗi câu truy vấn được tối đa **100 điểm**.
- Thời gian xử lý tối đa là $t_L$:
  - **4 phút** đối với câu truy vấn dạng **Video KIS**.
  - **5 phút** đối với câu truy vấn dạng **Textual KIS** và **Q&A**.
- Tổng điểm của một đội trong vòng chung kết là tổng điểm của đội trong tất cả câu truy vấn.

Điểm đánh giá của mỗi đội cho một câu truy vấn được tính như sau:

$$
f(t, ws) = \max\left(0, 50 + 50 \cdot f_{TS}(t) - 10 \cdot ws\right)
$$

Trong đó:

- $t$ là thời gian mà đội đã dùng để tìm ra đáp án đúng, với $0 \le t \le t_L$.
- $ws$ là số lượng đáp án sai mà đội đã nộp cho đến khi có đáp án đúng.
- $f_{TS}(t)$ là điểm dành cho thời gian xử lý, giảm tuyến tính từ 50 về 0, tính từ lúc bắt đầu câu truy vấn đến khi hết thời gian $t_L$.

Điểm đánh giá của mỗi câu truy vấn gồm:

- **50 điểm dành cho tính chính xác**.
- **50 điểm dành cho thời gian xử lý**.

Nếu đội trả lời chính xác và không có lần trả lời nào sai trước khi có câu trả lời chính xác, đội sẽ được trọn vẹn 50 điểm cho tính chính xác. Mỗi lần trả lời sai trước khi có câu trả lời chính xác, đội bị mất 10 điểm chính xác.

> Do đó, các đội nên cân nhắc để quyết định khi nào đủ chắc chắn để nộp.

## Hệ thống nộp bài và chấm điểm trực tuyến

Trong vòng chung kết AI Challenge 2024, các đội sẽ nộp bài theo đúng thể thức chuẩn quốc tế trong cuộc thi **VBS (Video Browser Showdown)**:

- https://videobrowsershowdown.org/

Hệ thống server để nộp bài và chấm điểm trực tuyến được sử dụng là **DRES (Distributed Retrieval Evaluation Server)**:

- Nguồn: https://github.com/dres-dev/DRES
- Rossetto L., Gasser R., Sauter L., Bernstein A., Schuldt H. (2021). *A System for Interactive Multimedia Retrieval Evaluations*. In: Lokoč J. et al. (eds), *MultiMedia Modeling. MMM 2021*. Lecture Notes in Computer Science, vol. 12573. Springer, Cham.

> **Lưu ý:** Thí sinh không cần tự deploy hệ thống DRES, chỉ cần đảm bảo mình có thể nộp bài được vào hệ thống DRES theo đúng chuẩn giao tiếp quy định.

Để hỗ trợ các đội làm quen với hệ thống, Ban tổ chức mở server thử nghiệm và thi thử tại địa chỉ https://eventretrieval.one từ **12 giờ ngày 15/10/2024** đến **8 giờ ngày 20/10/2024**. Thông tin tài khoản được gửi cho các đội thi vào ngày 15/10.

## Hướng dẫn xem thông tin truy vấn trên DRES

Đội thi đăng nhập vào web và bấm vào biểu tượng hình con mắt để xem thông tin truy vấn hiện tại.

![Màn hình danh sách truy vấn đang diễn ra trên DRES](assets/dres_ongoing_runs.png)

## Hướng dẫn submit kết quả vào hệ thống chấm điểm tự động DRES

Đội thi xem hướng dẫn cơ bản dưới đây để nộp bài. Ngoài ra, có thể tham khảo thêm tại:

- https://github.com/dres-dev/Client-Examples

Các đội thi chưa hiểu rõ cách nộp bài có thể tham gia buổi tập huấn của Ban tổ chức để hiểu rõ hơn về cách thức nộp.

### Bước 1: Lấy `sessionId`

Các đội cần đăng nhập vào hệ thống DRES để lấy `sessionId` của đội trong cuộc thi.

`sessionId` có thể được xem như một **token định danh** của đội trong cuộc thi. Có hai cách để lấy `sessionId`.

#### Cách 1: Lấy trên giao diện web

1. Vào đường dẫn https://eventretrieval.one/login hoặc đường dẫn mà Ban tổ chức cung cấp trong buổi thi chính thức.
2. Điền `username` và `password` của đội được Ban tổ chức cung cấp.
3. Sau khi đăng nhập thành công, truy cập https://eventretrieval.one/user để lấy thông tin `sessionId`.

#### Cách 2: Gửi POST request qua API

**Endpoint**

```http
POST https://eventretrieval.one/api/v2/login
Content-Type: application/json
```

**Request body**

```json
{
  "username": "<username>",
  "password": "<password>"
}
```

**Server response**

```json
{
  "id": "<id>",
  "username": "<username>",
  "role": "PARTICIPANT",
  "sessionId": "<sessionID>"
}
```

### Bước 2: Lấy `evaluationID`

Thực hiện GET request để lấy `evaluationID`.

**Endpoint**

```http
GET https://eventretrieval.one/api/v2/client/evaluation/list?session=<sessionID>
```

**Query parameter**

```json
{
  "session": "<sessionID>"
}
```

**Server response**

```json
[
  {
    "id": "<evaluationID>",
    "name": "<evaluation_name>",
    "type": "SYNCHRONOUS",
    "status": "ACTIVE"
  }
]
```

### Bước 3: Submit đáp án

Thực hiện POST request dùng token định danh theo API sau để submit đáp án.

Kết quả của đoạn video được nộp dưới định dạng thời gian xuất hiện của frame được tìm thấy trong video gốc, đơn vị là **milisecond (ms)**.

> **Lưu ý:**
>
> - `Item` được tính là tên file video **không có phần đuôi định dạng**.
> - Không được nộp trùng kết quả cho cùng một truy vấn.

**Endpoint**

```http
POST https://eventretrieval.one/api/v2/submit/<evaluationID>?session=<sessionID>
Content-Type: application/json
```

**Query parameter**

```json
{
  "session": "<sessionID>"
}
```

#### Request body cho Q&A

```json
{
  "answerSets": [
    {
      "answers": [
        {
          "text": "<ANSWER-QA>"
        }
      ]
    }
  ]
}
```

Trong đó:

```text
<ANSWER-QA> = <ANSWER>-<VIDEO_ID>-<TIME(ms)>
```

#### Request body cho KIS

```json
{
  "answerSets": [
    {
      "answers": [
        {
          "mediaItemName": "<VIDEO_ID>",
          "start": "<TIME(ms)>",
          "end": "<TIME(ms)>"
        }
      ]
    }
  ]
}
```
