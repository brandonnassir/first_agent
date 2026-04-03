# Analytics Chat

> Internal natural-language analytics tool over PostgreSQL.

Ask plain-English questions about your database tables and receive:

- A natural-language answer
- The SQL query used
- A result table
- Generated Python analysis code (reproducible)
- A Plotly visualization (when relevant)
- Generated Python visualization code (reproducible)
- Assumptions and warnings
- Full artifact persistence for every run

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│  Streamlit   │────▶│  Orchestrator│────▶│  LLM Service │
│  Frontend    │     │  (main.py)   │     │  (OpenAI API)│
└─────────────┘     └──────┬───────┘     └──────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Schema   │ │  Query   │ │  Chart   │
        │ Service  │ │  Service │ │  Service │
        └────┬─────┘ └────┬─────┘ └──────────┘
             │            │
             ▼            ▼
        ┌────────────────────┐
        │   PostgreSQL (RO)  │
        └────────────────────┘
```

### Key design principles

- **Read-only** – only `SELECT` / `WITH…SELECT` queries reach the database.
- **No arbitrary code execution** – LLM-generated Python is saved & displayed, never `exec`'d. Charts are rendered by trusted backend logic.
- **Artifact persistence** – every run produces a timestamped folder with all inputs, outputs, and metadata.
- **Modular & testable** – each concern lives in its own module with clear interfaces.

---

## Project structure

```
analytics-chat/
├── app/
│   ├── __init__.py
│   ├── main.py              # Orchestrator
│   ├── config.py            # Env-based configuration
│   ├── db.py                # SQLAlchemy database layer
│   ├── models.py            # Pydantic models
│   ├── prompts.py           # LLM prompt templates
│   ├── llm_service.py       # OpenAI-compatible LLM client
│   ├── schema_service.py    # Table metadata collection
│   ├── sql_validator.py     # Read-only SQL validation
│   ├── query_service.py     # Safe SQL execution
│   ├── artifact_service.py  # Run artifact persistence
│   ├── chart_service.py     # Trusted chart rendering
│   ├── response_formatter.py# Response assembly
│   └── utils.py             # Shared helpers
├── ui/
│   └── streamlit_app.py     # Streamlit frontend
├── tests/
│   ├── test_sql_validator.py
│   ├── test_schema_service.py
│   └── test_query_service.py
├── artifacts/                # Generated run folders
├── .env.example
├── requirements.txt
├── run.sh
└── README.md
```

---

## Setup

### 1. Clone and install

```bash
cd analytics-chat
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Description |
|---|---|
| `POSTGRES_HOST` | PostgreSQL host |
| `POSTGRES_PORT` | PostgreSQL port (default 5432) |
| `POSTGRES_DB` | Database name |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Database password |
| `OPENAI_API_KEY` | OpenAI (or compatible) API key |
| `LLM_MODEL` | Model name, e.g. `gpt-4o` |
| `LLM_BASE_URL` | API base URL (default OpenAI) |

Optional tuning variables:

| Variable | Default | Description |
|---|---|---|
| `QUERY_TIMEOUT_SECONDS` | 30 | Statement timeout |
| `MAX_RESULT_ROWS` | 10000 | Hard row cap |
| `DISPLAY_ROWS` | 500 | Rows shown in UI |
| `SAMPLE_ROWS` | 5 | Sample rows for schema context |
| `ARTIFACTS_DIR` | artifacts | Output directory |

### 3. Run the app

```bash
streamlit run ui/streamlit_app.py
```

Or use the helper script:

```bash
chmod +x run.sh
./run.sh
```

---

## Safety model

| Protection | Implementation |
|---|---|
| Read-only SQL | Validator rejects INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, GRANT, REVOKE, COPY, CREATE and other DDL/DML keywords |
| Single statement | Semicolon-separated statements are rejected |
| Statement type | Only `SELECT` and `WITH…SELECT` are allowed |
| Row limit | Automatic `LIMIT` appended when absent (skipped for aggregations) |
| Timeout | PostgreSQL `statement_timeout` set via connection options |
| No code execution | LLM Python code is displayed and saved, never evaluated |
| Parameterized queries | Schema introspection uses SQLAlchemy `text()` with bind parameters |

---

## Artifact structure

Each run creates a folder like `artifacts/run_20240401T120000Z_a1b2c3d4/` containing:

| File | Contents |
|---|---|
| `prompt.txt` | User question |
| `selected_tables.json` | Tables the user selected |
| `schema_context.json` | Full schema metadata sent to the LLM |
| `llm_request.json` | Raw LLM API request payload |
| `llm_response.json` | Raw LLM API response payload |
| `generated_sql.sql` | The SQL query |
| `analysis.py` | Reproducible Python analysis code |
| `chart.py` | Reproducible Python visualization code |
| `result.csv` | Query results as CSV |
| `result.parquet` | Query results as Parquet |
| `chart.html` | Interactive Plotly chart |
| `chart.png` | Static chart image (requires kaleido) |
| `summary.md` | Human-readable run summary |
| `metadata.json` | Machine-readable run metadata |

---

## Testing

```bash
cd analytics-chat
pytest tests/ -v
```

Tests cover:

- SQL validator: acceptance of valid queries, rejection of dangerous SQL
- Schema service: metadata formatting, error handling
- Query service: DataFrame output, exception handling, validation integration

---

## Next-step improvements

- **Conversation history** – multi-turn chat with context carry-over
- **Query caching** – cache identical queries to reduce DB load
- **User authentication** – integrate with SSO / LDAP
- **Role-based table access** – restrict visible schemas per user
- **Streaming LLM responses** – show partial results as they arrive
- **FastAPI backend** – decouple frontend from backend for team deployment
- **Result bookmarking** – save and share interesting analyses
- **Scheduled reports** – run saved queries on a cron
- **Cost tracking** – log LLM token usage per run
- **Column-level statistics** – pass min/max/distinct counts into the prompt for better SQL
