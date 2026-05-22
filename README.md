# 🔬 ScholarSleuth

**An AI-powered academic research assistant built on the Model Context Protocol (MCP).**

ScholarSleuth is a production-grade agentic system that searches, analyzes, compares, and synthesizes academic literature using a decoupled MCP architecture with full OpenTelemetry observability.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Streamlit Chat UI (app.py)                   │
│                  User login • Chat history • Tool display       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                ┌───────────▼───────────┐
                │   LangGraph ReAct     │
                │   Orchestrator Agent  │
                │   (Nvidia NIM LLM)    │
                └───────────┬───────────┘
                            │  bind_tools() + tool calls
                ┌───────────▼───────────┐
                │   MCP Bridge          │
                │   (mcp_bridge.py)     │
                │   Schema fetch +      │
                │   Tool execution      │
                └───────────┬───────────┘
                            │  Streamable HTTP
                ┌───────────▼───────────┐
                │   MCP Server          │
                │   (FastMCP + Uvicorn) │
                │                       │
                │  ┌─────────────────┐  │
                │  │  7 MCP Tools    │  │
                │  │  search, cite,  │  │
                │  │  pdf, library,  │  │
                │  │  bibtex, compare│  │
                │  │  lit. review    │  │
                │  └────────┬────────┘  │
                │           │           │
                │  ┌────────▼────────┐  │
                │  │  3 Academic APIs │  │
                │  │  Semantic Scholar│  │
                │  │  arXiv, OpenAlex│  │
                │  │  + Unpaywall    │  │
                │  └────────┬────────┘  │
                │           │           │
                │  ┌────────▼────────┐  │
                │  │  SQLite (WAL)   │  │
                │  │  Paper cache +  │  │
                │  │  User library   │  │
                │  └─────────────────┘  │
                └───────────────────────┘
                            │
                ┌───────────▼───────────┐
                │  OpenTelemetry LGTM   │
                │  Grafana • Tempo      │
                │  Loki • Prometheus    │
                └───────────────────────┘
```

### Key Design Decisions

- **MCP Sampling**: Complex tools (compare papers, literature review) delegate LLM inference back to the client via the MCP sampling protocol. This keeps the server stateless and LLM-agnostic.
- **Parallel API Fanout**: `search_papers` queries Semantic Scholar, arXiv, and OpenAlex simultaneously via `asyncio.gather()` with per-source fault tolerance.
- **Nvidia NIM Key Rotation**: Multiple API keys with automatic failover on rate-limit errors.
- **Stateless Sessions**: Each tool call opens a fresh MCP session for safety and portability.

---

## MCP Tools

| Tool | Description |
|------|-------------|
| `tool_search_papers` | Multi-source academic search (Semantic Scholar, arXiv, OpenAlex) |
| `tool_analyze_citations` | Citation metrics, influence analysis, and timelines |
| `tool_get_open_access_pdf` | Find legal open-access PDFs via Unpaywall |
| `tool_save_to_library` | Save papers to authenticated user's library |
| `tool_export_bibtex` | Export saved library as BibTeX |
| `tool_compare_papers` | LLM-powered comparative analysis (uses MCP Sampling) |
| `tool_build_literature_review` | Structured literature review with progress notifications (uses MCP Sampling) |

---

## Observability

Every tool call, API request, and database write is instrumented with OpenTelemetry:

- **Traces (Tempo)**: Waterfall diagrams showing nested spans for each tool execution, including parallel API fanout timing.
- **Metrics (Prometheus)**: Counters for tool calls, search requests, database writes, and API failures by source.
- **Logs (Loki)**: Structured logs correlated to trace IDs for instant debugging.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (for the observability stack)
- Nvidia NIM API key(s) from [build.nvidia.com](https://build.nvidia.com)

### 1. Clone and Install

```bash
git clone https://github.com/YOUR_USERNAME/scholarsleuth.git
cd scholarsleuth
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Nvidia NIM API keys
```

### 3. Start the Observability Stack

```bash
docker compose up -d
```

Grafana will be available at `http://localhost:3000` (admin/admin).

### 4. Initialize the Database

```bash
python init_db.py
```

### 5. Start the MCP Server

```bash
python -m mcp_server.server
```

### 6. Launch the Streamlit UI

```bash
streamlit run app.py
```

---

## Project Structure

```
scholarsleuth/
├── app.py                          # Streamlit chat interface
├── obs.py                          # OpenTelemetry setup (traces, metrics, logs)
├── init_db.py                      # Database schema initialization
├── simulate.py                     # Automated multi-conversation test harness
├── docker-compose.yml              # Grafana LGTM observability stack
├── requirements.txt
├── .env.example
│
├── agent/                          # LangGraph orchestration layer
│   ├── graph.py                    # ReAct agent with system prompt + tool binding
│   └── mcp_bridge.py              # MCP ↔ LangChain tool schema bridge
│
├── mcp_client/                     # Client-side MCP session management
│   ├── session.py                  # Streamable HTTP session + sampling handler
│   └── nim.py                      # Nvidia NIM client with key rotation
│
├── mcp_server/                     # MCP Server (FastMCP + Uvicorn)
│   ├── server.py                   # Tool registration + Starlette app
│   ├── db.py                       # Database helpers + auth
│   ├── telemetry.py                # OTel metric counter definitions
│   ├── tools/
│   │   ├── search.py               # Multi-source parallel search
│   │   ├── citations.py            # Citation network analysis
│   │   ├── open_access.py          # Unpaywall PDF lookup
│   │   ├── library.py              # Save/export user library
│   │   └── reasoning.py            # LLM sampling tools (compare + lit review)
│   └── apis/
│       ├── semantic_scholar.py     # Semantic Scholar API wrapper
│       ├── arxiv_search.py         # arXiv API wrapper (async thread pool)
│       ├── openalex.py             # OpenAlex API wrapper
│       └── unpaywall.py            # Unpaywall API wrapper
│
└── tests/
    └── test_tools.py               # End-to-end integration test harness
```

---

## Testing

### Automated Simulation

Run 5 multi-turn conversations covering all tools:

```bash
python simulate.py
```

### Integration Tests

Test individual tools against a running MCP server:

```bash
python -m tests.test_tools "quantum computing"
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM Orchestration | LangGraph (ReAct) + LangChain |
| Tool Protocol | Model Context Protocol (MCP) via Streamable HTTP |
| LLM Backend | Nvidia NIM (configurable model) |
| Academic APIs | Semantic Scholar, arXiv, OpenAlex, Unpaywall |
| Database | SQLite (WAL mode) via aiosqlite |
| Frontend | Streamlit |
| Observability | OpenTelemetry → Grafana (Tempo + Loki + Prometheus) |
| Deployment | Docker Compose |
