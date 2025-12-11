# Hướng dẫn chạy Denario Workflow

## Tổng quan

Backend hiện tại đã được tích hợp với Denario workflow cố định. Workflow sẽ tự động chạy qua các bước:

1. **Initialize** → Nhận data_description từ user message
2. **Generate Idea** → Tạo research idea sử dụng Denario
3. **Generate Method** → Tạo methodology sử dụng Denario
4. **Generate Results** → Chạy experiments sử dụng Denario
5. **Generate Paper** → Tạo LaTeX paper sử dụng Denario

## Cài đặt Dependencies

### 1. Cài đặt Python dependencies

```bash
# Từ thư mục root
uv sync

# Hoặc nếu dùng pip
pip install -e .
```

### 2. Đảm bảo Denario dependencies được cài đặt

Denario cần các packages sau (có thể đã có trong pyproject.toml):

- `Pillow` - Cho xử lý images
- `pydantic` - Cho data models
- `python-dotenv` - Cho environment variables
- `langchain` và `langgraph` - Cho workflow
- `langchain-google-genai` - Cho Gemini models
- `langchain-openai` - Cho OpenAI models
- `langchain-anthropic` - Cho Claude models (nếu dùng)
- `PyMuPDF` (fitz) - Cho PDF processing
- `tqdm` - Cho progress bars

**Lưu ý về `cmbagent`:**

- `cmbagent` là **optional dependency** - không bắt buộc cho Denario workflow mặc định
- Denario workflow hiện tại sử dụng "fast" mode (langgraph), không cần cmbagent
- `cmbagent` chỉ cần thiết nếu bạn muốn sử dụng:
  - `enhance_data_description()` - để enhance data description
  - `get_idea()` với `mode="cmbagent"` - để dùng cmbagent backend cho idea generation
  - `get_method()` với `mode="cmbagent"` - để dùng cmbagent backend cho method generation
  - `get_keywords()` - để extract keywords
  - `get_paper()` với `cmbagent_keywords=True` - để dùng cmbagent cho keyword selection

**Cài đặt cmbagent (nếu cần):**

```bash
# Với uv
uv sync --extra cmbagent

# Với pip
pip install cmbagent
```

## Cấu hình Environment Variables

Tạo hoặc cập nhật file `.env` trong thư mục root với các API keys:

```bash
# OpenAI (cho GPT models)
OPENAI_API_KEY=your_openai_key

# Google (cho Gemini models) - REQUIRED cho Denario workflow
GOOGLE_API_KEY=your_google_api_key

# Anthropic (cho Claude models - optional)
ANTHROPIC_API_KEY=your_anthropic_key

# Perplexity (cho citations - optional)
PERPLEXITY_API_KEY=your_perplexity_key

# Semantic Scholar (cho literature search - optional)
SEMANTIC_SCHOLAR_KEY=your_semantic_scholar_key

# Model configuration (optional, Denario có default)
MODEL_NAME=gpt-4o-mini

# LangSmith/LangGraph (optional)
LANGSMITH_API_KEY=your_langsmith_key
```

**Lưu ý:** Denario workflow mặc định sử dụng Gemini models (`gemini-2.0-flash` và `gemini-2.5-flash`), nên `GOOGLE_API_KEY` là **bắt buộc**.

## Chạy Backend

```bash
# Từ thư mục root
cd backend
langgraph dev --allow-blocking
```

Backend sẽ chạy tại: `http://127.0.0.1:2024`

## Chạy Frontend

Trong terminal khác:

```bash
# Từ thư mục root
cd frontend
npm install  # Nếu chưa install
npm run dev
```

Frontend sẽ chạy tại: `http://localhost:3000`

## Sử dụng

1. Mở `http://localhost:3000` trong browser
2. Gửi một message với **data description** của bạn
3. Workflow sẽ tự động chạy qua tất cả các bước:
   - Generate Idea
   - Generate Method
   - Generate Results
   - Generate Paper

## Output Files

Tất cả files được lưu trong `denario_project/` (hoặc project_dir bạn chỉ định):

```
denario_project/
├── input_files/
│   ├── data_description.md
│   ├── idea.md
│   ├── methods.md
│   ├── results.md
│   └── plots/
└── paper/
    └── *.tex (LaTeX files)
```

## Troubleshooting

### Lỗi import denario

- Đảm bảo denario folder có trong Python path
- Kiểm tra `__init__.py` trong denario folder

### Lỗi API keys

- Kiểm tra `.env` file có đúng format không
- Đảm bảo `GOOGLE_API_KEY` được set (bắt buộc cho Gemini models)

### Lỗi cmbagent

- `cmbagent` là optional dependency - chỉ cần nếu sử dụng các tính năng cmbagent mode
- Nếu gặp lỗi ImportError về cmbagent, có 2 lựa chọn:
  1. Cài đặt cmbagent: `uv sync --extra cmbagent` hoặc `pip install cmbagent`
  2. Sử dụng "fast" mode thay vì "cmbagent" mode (mặc định)
- Denario workflow mặc định không cần cmbagent

### Workflow không chạy

- Kiểm tra logs trong terminal
- Đảm bảo user message có content (data_description)
- Kiểm tra LangGraph server đã start thành công

## Cấu trúc Files

```
backend/
├── main.py                    # Entry point - sử dụng Denario workflow
├── denario_workflow.py        # Workflow chính của Denario
├── denario_agent.py           # Agent wrapper
└── ...
```

## Notes

- Workflow là **cố định** và **tự động** - không cần human approval
- Tất cả các bước chạy tuần tự: idea → method → results → paper
- Files được lưu tự động trong project directory
- Có thể theo dõi progress qua messages trong frontend
