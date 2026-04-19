# rag-kit

> 4 層 RAG 骨架 — 課堂教材（虎科同學通識課）

可重用的 RAG skeleton，把 **資料、檢索、生成** 三個職責拆開，讓不同資料源 / 檢索策略 / 生成模型之間可以互換。

## 架構

```
┌────────────────────────────────────────────────────────────┐
│                         Application                        │
│                    apps/huwei_landmarks/                   │
│           ( config.py wires + schema.py + line_bot.py )    │
└───────────────────────────┬────────────────────────────────┘
                            │
                   ┌────────▼────────┐
                   │  RAGPipeline    │   src/rag/pipeline.py
                   └────────┬────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
  ┌─────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐
  │ DataSource │     │  Retriever  │     │  Generator  │
  │            │     │             │     │             │
  │ GoogleSheet│     │ AllInPrompt │     │   Gemini    │
  │ CSV        │     │ (future:    │     │ (future:    │
  │            │     │   Vector/   │     │   OpenAI/   │
  │            │     │    BM25)    │     │    Local)   │
  └────────────┘     └─────────────┘     └─────────────┘
```

### 三個 Protocol

```python
class DataSource(Protocol):
    def all_rows(self) -> list[dict]: ...
    def by_key(self, key: str) -> dict | None: ...

class Retriever(Protocol):
    def retrieve(self, query) -> list[str]: ...   # 回傳 key list

class Generator(Protocol):
    def generate(self, payload: dict, query) -> str: ...
```

### Pipeline 流程

```
query ──► Retriever.retrieve()  ──► [keys]
           │
           └─► DataSource.by_key() × N  ──► payload
                │
                └─► Generator.generate(payload, query) ──► answer
```

## 目錄

```
rag-kit/
├── src/rag/
│   ├── data/           # DataSource Protocol + GoogleSheet / CSV
│   ├── retriever/      # Retriever Protocol + AllInPrompt
│   ├── generator/      # Generator Protocol + Gemini
│   └── pipeline.py     # RAGPipeline (組裝三層)
├── apps/
│   └── huwei_landmarks/
│       ├── config.py   # 綁定三層元件
│       ├── schema.py   # Sheet 欄位定義
│       ├── detect.py   # CLI 入口
│       └── line_bot.py # LINE BOT presentation
├── data/               # landmarks.csv、golden/
└── tests/
    ├── test_data_layer.py
    ├── test_retrievers.py
    ├── evaluate.py
    └── fixtures/
```

## 使用

### 安裝

```bash
pip install -e .
# 或
pip install -r requirements.txt
```

設定 `.env`（複製 `.env.example`）：

```
GOOGLE_API_KEY=你的 Gemini 金鑰
HACKMD_TOKEN=你的 HackMD Token（選填）
```

### 跑辨識

```bash
# 單張
python -m apps.huwei_landmarks.detect photo.jpg

# 多張 / 資料夾
python -m apps.huwei_landmarks.detect images/

# URL
python -m apps.huwei_landmarks.detect https://hackmd.io/_uploads/xxx.png

# HackMD 頁面批次
python -m apps.huwei_landmarks.detect --hackmd https://hackmd.io/@user/note

# 用本地 CSV 取代 Google Sheet
python -m apps.huwei_landmarks.detect --csv data/landmarks.csv photo.jpg
```

## 換掉任一層的範例

### 換 DataSource：Google Sheet → 本地 CSV

在 `apps/huwei_landmarks/config.py` 改這一行：

```python
# 原本：
data_source = GoogleSheetDataSource(DEFAULT_SHEET_CSV_URL, key_column=schema.KEY_COLUMN)

# 改成：
data_source = CSVDataSource("data/landmarks.csv", key_column=schema.KEY_COLUMN)
```

其他三層（Retriever / Generator / Pipeline）完全不動。

### 換 Retriever：AllInPrompt → 自訂

只要實作 `Retriever` Protocol 即可：

```python
class MyRetriever:
    def retrieve(self, query) -> list[str]:
        return ["雲林布袋戲館"]  # 你的檢索邏輯

pipeline = RAGPipeline(data_source, MyRetriever(), generator)
```

### 換 Generator：Gemini → 任何其他模型

```python
class MyGenerator:
    def generate(self, payload, query) -> str:
        return my_model.infer(payload, query)

pipeline = RAGPipeline(data_source, retriever, MyGenerator())
```

## 測試

```bash
pytest                          # 跑所有單元測試
python tests/evaluate.py        # 跑 golden 評估（需 GOOGLE_API_KEY）
```

單元測試 **不呼叫外部 API**——只用本地 fixture 驗證 Data/Retriever 行為。
`evaluate.py` 才會真的打 Gemini。

## 非目標 (out of scope)

- 向量化 / embedding retriever — 未來課程再談
- 非虎尾地標的 app — 留給老師結業後自己加
- Sheet 欄位改設計 — 另開 issue
