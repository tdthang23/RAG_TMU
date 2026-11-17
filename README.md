# TMU RAG — Offline Document Ingestion Starter

Project Python cho luận văn **nâng cao độ tin cậy hệ thống hỏi đáp RAG về văn bản quản lý giáo dục tại Trường Đại học Thương mại**.

**Chức năng đã triển khai:** đọc PDF text; nhận diện trang scan và OCR tiếng Việt; đọc Word `.docx` (kể cả bảng); đọc Excel `.xlsx`, `.xlsm` và `.xls` (gói bổ sung); trích xuất metadata sơ bộ; phát hiện chương–điều–khoản; chia passages; liên kết passage với tài liệu gốc; ghi báo cáo chất lượng và lỗi. **Chưa có** embedding, BM25/vector indexing, Module A/B, chatbot, OCR ảnh chèn trong DOCX hoặc kiểm định pháp lý tự động.

> **CẢNH BÁO:** Mẫu kèm theo là GIẢ LẬP và không có giá trị làm căn cứ pháp quy. Khi chạy dữ liệu thật, xóa các file mẫu trong `data/raw/` và cập nhật `data/metadata/registry.csv`.

## 1. Cấu trúc thư mục

```text
rag_tmu_ingestion_project/
├── config.yaml                    # Tham số và đường dẫn
├── pyproject.toml                 # Dependencies + CLI
├── README.md
├── data/
│   ├── raw/                       # Các PDF, Word, Excel đầu vào
│   ├── metadata/registry.csv      # Metadata đã rà soát thủ công
│   └── processed/                 # JSONL + logs được tạo ở đây
├── scripts/
│   └── make_sample_data.py       # Tạo dữ liệu giả lập để thử nghiệm
├── src/tmu_corpus/
│   ├── cli.py                     # python -m tmu_corpus build
│   ├── config.py
│   ├── pdf_reader.py              # Page text / OCR
│   ├── word_reader.py             # DOCX paragraphs + tables
│   ├── excel_reader.py            # Excel sheet/row
│   ├── metadata.py                # Regex metadata + CSV review
│   ├── structure.py               # Chapter/article/clause parsing
│   └── pipeline.py                # Orchestrator + JSONL export
└── tests/test_pipeline.py         # Tests đơn vị và end-to-end
```

## 2. Cài đặt trên Windows (PowerShell)

```powershell
cd D:\du-an\rag_tmu_ingestion_project
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[test]"
```

Nếu PowerShell chặn chạy Activate.ps1, mở CMD và dùng `.venv\Scripts\activate.bat` thay vì chỉnh chính sách hệ thống.

**OCR cho PDF scan** cần thêm Tesseract OCR **cài trên hệ điều hành** (gói `pytesseract` của Python không tự cài engine). Cài Tesseract và dữ liệu ngôn ngữ `vie` + `eng`. Kiểm tra:

```powershell
tesseract --version
tesseract --list-langs
```

Nếu lệnh `tesseract` không được nhận, sửa trường `pdf.tesseract_cmd` trong `config.yaml`:

```yaml
pdf:
  ocr_mode: auto
  ocr_language: vie+eng
  tesseract_cmd: 'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

Nếu chỉ có PDF text và chưa cần OCR, đổi `ocr_mode: never`. Khi gặp trang scan mà không OCR, hệ thống sẽ ghi cảnh báo và **không tự nhận đã đọc thành công trang đó**.

Linux/Ubuntu: tạo `.venv`, `pip install -e ".[test]"`, cài hệ thống `tesseract-ocr` và `tesseract-ocr-vie` qua package manager.

### File Excel đời cũ `.xls`

```powershell
python -m pip install -e ".[xls]"
```

Không cần phần mở rộng này nếu chỉ dùng `.xlsx`/`.xlsm`.

### Word `.doc` (đời cũ)

Project hỗ trợ **`.docx`**. Với `.doc`, hãy mở file trong Word và **Save As → .docx** trước khi đưa vào `data/raw/`. Không đổi mỗi phần mở rộng tên file. Với Word chứa ảnh scan, cần thêm OCR ảnh chèn nếu muốn hỗ trợ sau này.

## 3. Chạy nhanh

Tạo bộ dữ liệu giả lập, bao gồm PDF text, PDF scan, Word và Excel:

```powershell
python scripts/make_sample_data.py
```

Sau đó chạy pipeline:

```powershell
python -m tmu_corpus build --config config.yaml
# tương đương: tmu-corpus build --config config.yaml
```

Xem báo cáo:

```powershell
python -m tmu_corpus report --config config.yaml
```

Chạy kiểm thử:

```powershell
python -m pytest -q
```

## 4. Dùng với văn bản thật

1. Xóa file ví dụ trong `data/raw/` và đưa vào các file PDF/DOCX/XLSX. Có thể chia `data/raw/tmu/` và `data/raw/moet/`.
2. Điền bảng `data/metadata/registry.csv` bằng Excel. Trường `filename` là đường dẫn tương đối trong `data/raw/`, ví dụ `tmu/2026_Quy_che.pdf`.
3. Xác minh các trường pháp lý quan trọng bằng văn bản gốc: `effective_from`, `effective_to`, `applicable_cohorts`, `applicable_programs`, `replaces`. Nếu chưa xác minh, để trống và giữ `verification_status=unverified`.
4. Chạy `python -m tmu_corpus build --config config.yaml`.
5. Đọc `quality_report.json`, `warnings.jsonl`, `errors.jsonl`, kiểm tra ngẫu nhiên passages và đối chiếu trang gốc, **đặc biệt các trang OCR**.
6. Chỉ khi metadata đã được xác minh mới bật lọc `Applicability-aware` trong Module A.

**Không đặt gold_answer, gold_evidence hay nhãn claim trong JSONL corpus online**; tách riêng trong benchmark offline để tránh rò rỉ dữ liệu.

## 5. Đầu ra

- `corpus.json`: một file JSON tổng hợp gồm mảng `documents` và `passages` để dễ mở và tích hợp ban đầu.
- `documents.jsonl`: một dòng/nguồn; `document_id`, `version_id`, `source_sha256`, `metadata`, số passage, OCR pages.
- `passages.jsonl`: một dòng/passage; `passage_id`, `document_id`, `version_id`, `text`, `raw_text`, `hierarchy`, `source_locator`, `metadata` và phương pháp trích xuất.
- `manifest.json`: phiên bản schema, hash các file nguồn để đối chiếu.
- `quality_report.json`: tổng số nguồn, số passage, trang OCR, tình trạng metadata và file lỗi.
- `warnings.jsonl`: các vấn đề phát hiện trong tài liệu, OCR trống/không khả dụng.
- `errors.jsonl`: những file không xử lý được, có nguyên nhân.

Ví dụ (rút gọn):

```json
{
  "passage_id": "DOC_..._P00003",
  "document_id": "DOC_...",
  "version_id": "VER_...",
  "text": "Điều 2. Điều kiện giả lập\n1. Sinh viên đáp ứng điều kiện A.",
  "hierarchy": {"chapter": "I", "article": "2", "article_title": "Điều kiện giả lập", "clause": "1", "point": null},
  "source_locator": [{"page": 1, "line": 9}],
  "extraction_methods": ["native"],
  "metadata": {"verification_status": "unverified"}
}
```

## 6. Chú ý về chất lượng và giới hạn

- PDF text: trích xuất có thể sai thứ tự với văn bản nhiều cột, bảng phức tạp hoặc footer/header; cần rà soát thủ công.
- PDF scan: OCR tiếng Việt có thể sai dấu, số hiệu, ngày tháng, ký tự `Điều`; cần kiểm tra lại văn bản gốc. OCR diễn ra theo trang; trang PDF hỗn hợp vẫn được xử lý.
- Excel: hàng 1 của từng sheet mặc định là header, mỗi dòng dữ liệu được coi là passage. Excel tổng hợp có header nhiều dòng/merged cells có thể cần định nghĩa parser riêng. Giá trị công thức lấy từ cache lưu trong file; nếu file chưa được Excel tính và lưu lại, giá trị có thể thiếu.
- `.xls` cần `xlrd`. `.doc` cần chuyển `.docx` đúng cách. Ảnh scan chèn trong Word chưa OCR.
- Regex chương/điều/khoản là baseline; cần hiệu chỉnh theo thực tế PDF và văn bản TMU (nhất là bảng, mục lục, chú thích, điều khoản dài).
- `mentioned_cohorts` từ tự động trích xuất chỉ là những khóa **được nhắc tới**; `applicable_cohorts` để trống đến khi kiểm tra thủ công hoặc có registry đã xác minh.
- `effective_to = null` không đồng nghĩa văn bản còn hiệu lực. Không tự suy ra quan hệ thay thế chỉ từ ngày ban hành.
- `version_id` dựa trên SHA-256 của file; **không** thay cho mã phiên bản điều khoản pháp lý. Quan hệ sửa đổi ở cấp điều khoản là bước nâng cấp sau.
- Các nội dung/metadata chưa được xác minh không nên bị dùng để khẳng định hiệu lực hoặc tư vấn học vụ.

## 7. Liên kết với Module A và B

```
Document Ingestion (offline) → documents.jsonl + passages.jsonl
                                     ↓
                           BM25 / Vector Index [xây tiếp]
                                     ↓
                  Applicability-aware Retrieval (A)
                                     ↓
                           LLM Generator
                                     ↓
                 Evidence-grounded Verification (B)
```

Phần ingestion này **không được coi là điểm mới của luận văn**. Nó chuẩn bị dữ liệu có cấu trúc và nguồn gốc xác thực để các thực nghiệm E0–E3 dùng chung corpus.
