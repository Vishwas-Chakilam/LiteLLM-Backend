# Healthcare Multi-Agent AI Platform — Technical Documentation

| Field | Detail |
|-------|--------|
| **Project** | Healthcare Multi-Agent AI Platform (LiteLLM Backend) |
| **Version** | 2.0.0 |
| **Date** | June 2026 |
| **Live Deployment** | [https://litellm-chat-api.onrender.com](https://litellm-chat-api.onrender.com) |
| **Admin UI** | [https://litellm-chat-api.onrender.com/admin](https://litellm-chat-api.onrender.com/admin) |
| **Interactive API Docs** | [https://litellm-chat-api.onrender.com/docs](https://litellm-chat-api.onrender.com/docs) |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture](#2-architecture)
3. [Project Structure](#3-project-structure)
4. [Quick Start](#4-quick-start)
5. [Configuration](#5-configuration)
6. [API Reference — Core](#6-api-reference--core)
7. [API Reference — Healthcare Platform](#7-api-reference--healthcare-platform)
8. [API Reference — Admin](#8-api-reference--admin)
9. [Request & Response Templates](#9-request--response-templates)
10. [Healthcare Agents](#10-healthcare-agents)
11. [Hospital Data (Supabase)](#11-hospital-data-supabase)
12. [Supabase Setup](#12-supabase-setup)
13. [Admin Dashboard & Agent Playground](#13-admin-dashboard--agent-playground)
14. [Testing Guide (Developers)](#14-testing-guide-developers)
15. [Tester Guide — PyRIT Red Team](#15-tester-guide--pyrit-red-team)
16. [Deployment (Render)](#16-deployment-render)
17. [Security & Compliance](#17-security--compliance)
18. [Troubleshooting](#18-troubleshooting)
19. [Appendix](#19-appendix)

---

## 1. Executive Summary

This platform is a **production-oriented healthcare AI backend** built on:

- **FastAPI** — REST API and admin UI
- **LiteLLM** — multi-provider model routing (Groq, Gemini, etc.)
- **LangGraph-style orchestration** — manager agent routes to specialist agents
- **Supabase** — auth, patient data, conversations, hospital master data, audit logs
- **MCP tools** — hospital data, payer rules, ICD/CPT lookups (with offline mocks)
- **PyRIT** — adversarial red-team testing against the legacy chat endpoint

### What it does

| Capability | Description |
|------------|-------------|
| Multi-agent chat | Routes patient queries to triage, insurance, prior auth, lab, etc. |
| Single-hospital | City General Hospital master data (insurers, departments, providers) |
| Healthcare-only scope | Non-medical queries (e.g. "deploy on Render") are rejected |
| Legacy OpenAI API | `/v1/chat/completions` still works for PyRIT and simple chat |
| Admin console | `/admin` — users, agents, workflows, playground, hospital data |
| Audit trail | Agent execution logs, tool logs, compliance events (with Supabase) |

### Test status

**69 automated tests passing** (`python -m pytest tests/ -v`)

---

## 2. Architecture

```
                    ┌─────────────────────────────────────────┐
                    │           FastAPI Gateway               │
                    │  /chat  /workflow  /agents  /admin      │
                    └──────────────────┬──────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────┐
                    │         Manager Agent (Orchestrator)     │
                    │  scope check → intent → agent selection    │
                    └──────────────────┬──────────────────────┘
           ┌───────────────────────────┼───────────────────────────┐
           ▼                           ▼                           ▼
   ┌───────────────┐          ┌───────────────┐          ┌───────────────┐
   │ Triage Agent  │          │Insurance Agent│          │ Prior Auth    │
   │ Medication    │   ...    │ Lab Analysis  │          │ Compliance    │
   └───────┬───────┘          └───────┬───────┘          └───────┬───────┘
           │                          │                          │
           └──────────────────────────┼──────────────────────────┘
                                      ▼
                    ┌─────────────────────────────────────────┐
                    │  LiteLLM Gateway  +  MCP Tools           │
                    │  hospital_mcp · payer_rules · icd/cpt    │
                    └──────────────────┬──────────────────────┘
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │  Supabase (Postgres + Auth + Storage)    │
                    │  patients · hospital · conversations     │
                    └─────────────────────────────────────────┘
```

### Request flow (`POST /chat`)

1. Optional JWT auth → load patient profile from Supabase
2. Inject **hospital context** (insurers, departments, hospital name)
3. **Scope check** — reject non-healthcare queries immediately (no LLM cost)
4. Classify intent → select agent(s)
5. Run agents sequentially → each may call MCP tools
6. Compliance/safety agent reviews output
7. Synthesize final patient-facing response
8. Persist messages + workflow run to Supabase (if configured)

---

## 3. Project Structure

```
LiteLLM/
├── app/
│   ├── main.py                    # FastAPI entry, legacy /v1 routes
│   ├── config.py                  # Settings from .env
│   ├── agents/                    # 8 healthcare specialist agents
│   ├── api/routes/                # auth, healthcare, agents, admin
│   ├── admin/                     # Admin dashboard HTML/CSS/JS
│   ├── orchestrator/              # Manager agent + LangGraph graph
│   ├── registry/                  # Dynamic agent registry
│   ├── workflows/                 # Workflow runner
│   ├── mcp/                       # MCP tool client (hospital_mcp, etc.)
│   ├── llm/                       # LiteLLM gateway wrapper
│   ├── memory/                    # Redis session store
│   ├── middleware/                # JWT auth + RBAC
│   ├── schemas/                     # Pydantic models
│   └── services/
│       ├── supabase/              # Auth, conversations, patients, audit
│       ├── hospital_data_service.py
│       ├── context_builder.py     # Merges patient + hospital context
│       └── router_service.py      # LiteLLM multi-key router
├── supabase/migrations/            # SQL schema, RLS, hospital seed
├── config/
│   ├── hospital/city_general.json # Offline hospital fallback data
│   └── mcp_servers.json
├── examples/healthcare_requests.http
├── render testing/                # PyRIT scripts, CLI, smoke tests
├── tests/                         # 69 pytest tests
├── requirements.txt
├── render.yaml                    # Render Blueprint
└── DOCUMENTATION.md               # This file
```

---

## 4. Quick Start

### Prerequisites

- Python 3.12+
- API keys for at least one LLM provider (Groq and/or Gemini)
- Supabase project (optional but recommended for full platform features)
- Redis (optional — in-memory fallback works)

### Local setup

```powershell
cd LiteLLM
copy .env.example .env
# Edit .env with API keys and Supabase credentials

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

| URL | Purpose |
|-----|---------|
| http://127.0.0.1:8000/docs | Swagger UI |
| http://127.0.0.1:8000/admin | Admin dashboard |
| http://127.0.0.1:8000/health | Health check |

### Run tests

```powershell
python -m pytest tests/ -v
```

---

## 5. Configuration

Copy `.env.example` to `.env`. **Never commit `.env`.**

### LLM providers (numbered pairs)

```env
FAST_MODEL_1=groq/llama-3.1-8b-instant
FAST_API_KEY_1=gsk_...

CAPABLE_MODEL_1=groq/llama-3.3-70b-versatile
CAPABLE_API_KEY_1=gsk_...
```

| Variable | Default | Description |
|----------|---------|-------------|
| `CHEAP_MODEL` | `fast` | Classification / extraction tasks |
| `REASONING_MODEL` | `capable` | Triage, prior auth, records |
| `PREMIUM_MODEL` | `capable` | Compliance / synthesis |
| `DAILY_BUDGET_USD` | `10.00` | Max daily LLM spend |
| `PER_CONVERSATION_BUDGET_USD` | `0.50` | Per-conversation cap |
| `RATE_LIMIT_PER_MINUTE` | `30` | Requests per IP per minute |
| `SYSTEM_PROMPT_ENABLED` | `true` | Legacy chat safety prompt |

### Supabase

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=your-jwt-secret
AUTH_REQUIRED=false
```

Set `AUTH_REQUIRED=true` in production.

### Single-hospital deployment

```env
HOSPITAL_SLUG=city_general
HOSPITAL_DATA_FILE=config/hospital/city_general.json
```

Hospital data is read from **Supabase first**, then JSON fallback.

### Redis (optional)

```env
REDIS_URL=redis://localhost:6379/0
REDIS_SESSION_TTL_SECONDS=86400
```

---

## 6. API Reference — Core

**Base URL:** `https://litellm-chat-api.onrender.com` (or `http://localhost:8000`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | No | Welcome + links |
| `GET` | `/health` | No | `{"status":"ok"}` |
| `GET` | `/getprompt` | No | Current system prompt (legacy chat) |
| `POST` | `/v1/chat/completions` | No* | OpenAI-compatible chat (PyRIT) |
| `POST` | `/v1/conversations` | No | Create conversation UUID |
| `GET` | `/v1/conversations` | No | List file-based conversations |
| `GET` | `/v1/conversations/{id}` | No | Full transcript + metadata |
| `GET` | `/v1/conversations/{id}/messages` | No | Messages array |
| `GET` | `/v1/admin/cost` | No | LLM spend summary |

\* Legacy endpoints remain open for PyRIT testing. Healthcare endpoints respect `AUTH_REQUIRED`.

### `POST /v1/chat/completions` (PyRIT / legacy)

**Request:**

```json
{
  "messages": [{"role": "user", "content": "Hello"}],
  "model": "fast",
  "conversation_id": "optional-uuid-for-multi-turn",
  "max_tokens": 1024,
  "temperature": 0.7,
  "stream": false
}
```

| Field | Values |
|-------|--------|
| `model` | `fast`, `capable`, `auto` |
| `stream` | Must be `false` |

**Response:**

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1719000000,
  "model": "fast",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "Hello! How can I help?"},
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 8,
    "total_tokens": 20
  },
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "tier": "fast",
  "model_used": "gemini/gemini-2.5-flash-lite",
  "estimated_cost_usd": 0.00005
}
```

---

## 7. API Reference — Healthcare Platform

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/signup` | No | Register patient/support |
| `POST` | `/auth/login` | No | Get JWT tokens |
| `GET` | `/auth/me` | Bearer | Current user profile |
| `POST` | `/chat` | Optional | Multi-agent healthcare chat |
| `POST` | `/workflow/run` | Optional | Explicit workflow execution |
| `GET` | `/workflow/{id}` | Optional | Workflow status + state |
| `GET` | `/agents` | Optional | List registered agents |
| `POST` | `/agents/register` | Admin | Register agent |
| `GET` | `/agents/{id}` | Optional | Get agent by ID |
| `DELETE` | `/agents/{id}` | Admin | Deactivate agent |
| `POST` | `/prior-auth` | Optional | Create prior auth case |
| `GET` | `/prior-auth/{id}` | Optional | Get prior auth case |
| `PATCH` | `/prior-auth/{id}` | Optional | Update prior auth status |

### `POST /chat`

**Request:**

```json
{
  "message": "Will my insurance be valid at this hospital?",
  "session_id": "sess-001",
  "conversation_id": null,
  "demo_patient_index": 0,
  "patient_context": {}
}
```

| Field | Description |
|-------|-------------|
| `message` | Patient query (required) |
| `session_id` | Reuse for multi-turn (optional) |
| `conversation_id` | Existing Supabase conversation UUID |
| `demo_patient_index` | `0` = Jane Demo (Aetna), `1` = John Demo (United) |
| `patient_context` | Extra context override |

**Response:**

```json
{
  "conversation_id": "uuid",
  "session_id": "sess-001",
  "message": "Aetna is in-network at City General Hospital...",
  "agents_used": ["insurance_agent", "compliance_safety_agent"],
  "workflow_id": "uuid",
  "metadata": {
    "intent": "insurance",
    "urgency": "routine",
    "agent_outputs": { "...": "..." }
  },
  "escalated": false
}
```

**Out-of-scope response** (non-healthcare query):

```json
{
  "message": "I'm a healthcare-only AI assistant...",
  "agents_used": [],
  "metadata": { "intent": "out_of_scope", "out_of_scope": true }
}
```

### `POST /workflow/run`

```json
{
  "workflow_name": "healthcare_orchestration",
  "query": "Patient needs MRI authorization and has chest pain",
  "conversation_id": null,
  "patient_context": {},
  "agents": null
}
```

`agents` — optional list to force specific agents, e.g. `["prior_authorization_agent", "symptom_triage_agent"]`

### `POST /auth/signup`

```json
{
  "email": "patient@example.com",
  "password": "securepass123",
  "full_name": "Jane Patient",
  "role": "patient"
}
```

Roles: `patient`, `doctor`, `admin`, `insurance_agent`, `support` (self-signup: `patient`, `support` only)

### `POST /auth/login`

```json
{
  "email": "patient@example.com",
  "password": "securepass123"
}
```

**Response:**

```json
{
  "access_token": "eyJ...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "email": "patient@example.com",
    "role": "patient",
    "full_name": "Jane Patient"
  }
}
```

Use header: `Authorization: Bearer <access_token>`

### `POST /prior-auth`

```json
{
  "patient_id": "uuid-of-patient-profile",
  "insurer": "aetna",
  "diagnosis_codes": ["M54.5"],
  "procedure_codes": ["70553"],
  "clinical_notes": "Chronic low back pain, failed conservative treatment 6 weeks."
}
```

---

## 8. API Reference — Admin

**UI:** `GET /admin`  
**Auth:** Admin role (or open when `AUTH_REQUIRED=false`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/api/stats` | Dashboard counts |
| `GET` | `/admin/api/users` | User list |
| `PATCH` | `/admin/api/users/{id}` | Update user role |
| `GET` | `/admin/api/hospital` | Hospital master data snapshot |
| `GET` | `/admin/api/hospital/demo-patients` | Demo patient list |
| `GET` | `/admin/api/agents` | Agent registry |
| `GET` | `/admin/api/agents/health` | Agent readiness check |
| `POST` | `/admin/api/playground/run` | Test agents/workflows |
| `GET` | `/admin/api/playground/samples` | Sample test prompts |
| `GET` | `/admin/api/conversations` | Supabase conversations |
| `GET` | `/admin/api/workflows` | Workflow runs |
| `GET` | `/admin/api/prior-auth` | Prior auth cases |
| `GET` | `/admin/api/audit-logs` | Compliance audit trail |
| `GET` | `/admin/api/agent-logs` | Agent execution logs |
| `GET` | `/admin/api/tool-logs` | MCP tool invocation logs |
| `GET` | `/admin/api/cost` | LLM cost summary |

### `POST /admin/api/playground/run`

```json
{
  "query": "Will my insurance be valid at this hospital?",
  "mode": "workflow",
  "agent_id": null,
  "demo_patient_index": 0
}
```

| `mode` | Behavior |
|--------|----------|
| `workflow` | Full orchestrator (intent → agents → safety → synthesis) |
| `agent` | Single agent (`agent_id` required) |
| `health` | Instant agent readiness check (no LLM) |

---

## 9. Request & Response Templates

### Insurance in-network check (expected)

**Request:** `POST /admin/api/playground/run`

```json
{
  "query": "Will my insurance be valid at this hospital?",
  "mode": "workflow",
  "demo_patient_index": 0
}
```

**Agent output (`insurance_agent`):**

```json
{
  "eligibility_status": "likely_covered",
  "insurer": "aetna",
  "hospital": "City General Hospital",
  "in_network": true,
  "coverage_check": {
    "accepted": true,
    "in_network": true,
    "matched_plan": {
      "insurer_id": "aetna",
      "insurer_name": "Aetna",
      "plan_types": ["PPO", "HMO", "EPO"],
      "in_network": true
    }
  }
}
```

### Emergency triage

```json
{
  "query": "I have severe chest pain radiating to my left arm",
  "mode": "workflow"
}
```

**Response flags:** `"escalated": true`, `"urgency": "emergency"`

### Prior authorization

```json
{
  "query": "Patient needs lumbar MRI authorization. Insurer Aetna. ICD M54.5, CPT 72148.",
  "mode": "workflow",
  "demo_patient_index": 0
}
```

### curl examples

```bash
# Health
curl https://litellm-chat-api.onrender.com/health

# Healthcare chat (no auth when AUTH_REQUIRED=false)
curl -X POST https://litellm-chat-api.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"I have a mild headache for 2 days","demo_patient_index":0}'

# Login
curl -X POST https://litellm-chat-api.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"patient@example.com","password":"securepass123"}'

# Authenticated chat
curl -X POST https://litellm-chat-api.onrender.com/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"message":"Will my insurance work here?"}'

# Legacy PyRIT endpoint
curl -X POST https://litellm-chat-api.onrender.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello"}],"model":"fast"}'
```

More examples: `examples/healthcare_requests.http`

---

## 10. Healthcare Agents

| Agent ID | Domain | MCP Tools |
|----------|--------|-----------|
| `symptom_triage_agent` | Triage | pubmed_mcp |
| `medication_agent` | Medication | drug_database_mcp |
| `lab_analysis_agent` | Lab | hospital_mcp (lab ranges) |
| `medical_records_agent` | Records | — |
| `appointment_agent` | Scheduling | hospital_mcp |
| `insurance_agent` | Insurance | hospital_mcp, payer_rules_mcp |
| `prior_authorization_agent` | Prior auth | hospital_mcp, icd/cpt, payer_rules |
| `compliance_safety_agent` | Safety | — (runs last on every workflow) |

### Built-in healthcare domains

`triage` · `medication` · `prior_authorization` · `lab_analysis` · `medical_records` · `insurance` · `scheduling` · `compliance` · `emergency` · `billing`

---

## 11. Hospital Data (Supabase)

Single hospital: **City General Hospital** (`slug: city_general`)

### Tables

| Table | Contents |
|-------|----------|
| `hospitals` | Name, address, NPI, ER wait, visiting hours |
| `hospital_insurance_plans` | Aetna, United, Cigna, BCBS, Medicare, Medicaid, Humana (OON) |
| `hospital_departments` | ER, Cardiology, Radiology, Lab, Orthopedics, Primary Care |
| `hospital_providers` | 5 doctors with specialties |
| `hospital_services` | MRI, CBC, knee replacement, etc. |
| `hospital_payer_rules` | Per-insurer prior-auth requirements |
| `hospital_lab_reference_ranges` | Hemoglobin, WBC, glucose, etc. |

### MCP tools (`hospital_mcp`)

| Tool | Purpose |
|------|---------|
| `get_hospital_info` | Hospital profile |
| `get_accepted_insurers` | All accepted plans |
| `check_insurance_accepted` | In-network check for patient insurer |
| `list_departments` | Hospital departments |
| `list_providers` | Doctors (optional specialty filter) |
| `list_services` | Procedures/services |
| `get_hospital_payer_rules` | Hospital-specific payer rules |
| `get_lab_reference_range` | Lab reference ranges |

### Demo patients (playground)

| Index | Name | Insurer |
|-------|------|---------|
| `0` | Jane Demo | aetna |
| `1` | John Demo | united |

---

## 12. Supabase Setup

Run migrations **in order** in Supabase SQL Editor:

```
001_schema.sql
002_rls_policies.sql
003_storage_buckets.sql
004_realtime.sql
005_hospital_schema.sql
006_hospital_seed.sql
```

### Create admin user

1. Sign up via `POST /auth/signup`
2. In Supabase SQL Editor:

```sql
UPDATE public.users SET role = 'admin' WHERE email = 'your@email.com';
```

### Storage buckets

`medical-records` · `patient-uploads` · `lab-reports` · `prior-auth-documents`

---

## 13. Admin Dashboard & Agent Playground

### Access

```
https://litellm-chat-api.onrender.com/admin
```

### Sections

| Tab | Purpose |
|-----|---------|
| Dashboard | Stats (users, conversations, agents, spend) |
| **Agent Playground** | Test workflows and single agents |
| Users | Role management |
| Patients | Patient profiles |
| Conversations | Message history |
| Agents | Registry |
| Prior Auth | Cases |
| Workflows | Multi-agent run history |
| Audit / Agent / Tool Logs | Compliance & execution traces |
| Assignments | Doctor–patient links |
| LLM Costs | Spend tracking |

### Playground testing steps

1. Open **Agent Playground**
2. Select **Jane Demo — aetna** (test patient)
3. Choose mode: **Full workflow** | **Single agent** | **Health check**
4. Pick a sample chip or enter a query
5. Click **Run test**
6. Review per-agent JSON outputs and final response

**Sample queries:**

| Query | Expected agents |
|-------|-----------------|
| "I have a mild headache" | triage, compliance |
| "Will my insurance be valid at this hospital?" | insurance, compliance |
| "Patient needs MRI authorization and chest pain" | prior_auth, triage, compliance |
| "how to deploy on render" | **out_of_scope** (no agents) |

---

## 14. Testing Guide (Developers)

### Automated tests

```powershell
# Full suite (69 tests)
python -m pytest tests/ -v

# Healthcare platform only
python -m pytest tests/test_healthcare_platform.py tests/test_hospital.py tests/test_scope.py -v

# Admin UI
python -m pytest tests/test_admin_ui.py -v

# Legacy API
python -m pytest tests/test_api.py -v
```

### Test modules

| File | Coverage |
|------|----------|
| `test_api.py` | Legacy `/v1/chat/completions`, conversations |
| `test_healthcare_platform.py` | Agents, registry, orchestrator |
| `test_hospital.py` | Hospital data, MCP, insurance workflow |
| `test_scope.py` | Healthcare-only scope rejection |
| `test_admin_ui.py` | Admin dashboard API |
| `test_router_service.py` | LiteLLM routing |
| `test_cost_tracker.py` | Budget tracking |

### Local smoke test

```powershell
uvicorn app.main:app --port 8000

curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"message\":\"headache\",\"demo_patient_index\":0}"
```

### Render smoke test

```powershell
cd "render testing"
pip install -r requirements.txt
python test_render_api.py
```

---

## 15. Tester Guide — PyRIT Red Team

This section is for **security testers** running adversarial campaigns against the API.

### Targets

| Endpoint | Use case |
|----------|----------|
| `POST /v1/chat/completions` | **Primary PyRIT target** — OpenAI-compatible, multi-turn via `conversation_id` |
| `POST /chat` | Healthcare multi-agent (different response shape) |

PyRIT scripts in this repo target **`/v1/chat/completions`** by default.

### Handoff card (minimum)

```
Base URL:     https://litellm-chat-api.onrender.com
Docs:         https://litellm-chat-api.onrender.com/docs
Auth:         none (legacy endpoints)

Endpoint:     POST /v1/chat/completions

Body:
{
  "messages": [{"role": "user", "content": "YOUR_PROMPT"}],
  "model": "fast"
}

Reply path:   choices[0].message.content
Multi-turn:   reuse conversation_id from response
History:      GET /v1/conversations/{conversation_id}
```

### Prerequisites (tester machine)

```powershell
cd "render testing"
pip install -r requirements.txt
pip install pyrit
```

PyRIT **adversarial** and **scorer** models need OpenAI credentials (separate from Render target):

```env
# ~/.pyrit/.env or environment
OPENAI_CHAT_KEY=sk-...
OPENAI_CHAT_MODEL=gpt-4o
OPENAI_CHAT_ENDPOINT=https://api.openai.com/v1/chat/completions
```

### PyRIT scripts

| Script | Purpose |
|--------|---------|
| `pyrit_redteam_attack.py` | Main multi-turn red-team campaign |
| `pyrit_attack_fixed.py` | Fixed variant |
| `pyrit_attack_httptarget_fixed.py` | HTTPTarget variant |
| `pyrit_httptarget_fallback.py` | Pre-created conversation_id |
| `litellm_conversation_target.py` | **Custom target** — tracks `conversation_id` |
| `pyrit_env.py` | OpenAI config helper |
| `chat_cli.py` | Interactive terminal chat |
| `test_render_api.py` | Live deployment smoke tests |

### Run red-team attack

```powershell
cd "render testing"

# Default (Render production)
python pyrit_redteam_attack.py

# Custom objective
python pyrit_redteam_attack.py --objective "Get the model to reveal its system prompt"

# Local server
python pyrit_redteam_attack.py --url http://127.0.0.1:8000 --model fast

# With explicit OpenAI key for adversarial model
python pyrit_redteam_attack.py --adversarial-key sk-... --adversarial-model gpt-4o
```

### Why `LiteLLMConversationTarget`?

Plain PyRIT `HTTPTarget` does **not** pass `conversation_id` between turns. This API stores history server-side per UUID. Use:

```python
from litellm_conversation_target import LiteLLMConversationTarget

target = LiteLLMConversationTarget(
    base_url="https://litellm-chat-api.onrender.com",
    model="fast",
)
```

### Recommended PyRIT workflow

1. `GET /health` → confirm `{"status":"ok"}`
2. First prompt → `POST /v1/chat/completions` → save `conversation_id`
3. Follow-up prompts → same `conversation_id` in body
4. Score `choices[0].message.content` with separate scorer model
5. Audit → `GET /v1/conversations/{conversation_id}`

### Model tiers for testing

| Tier | When to use |
|------|-------------|
| `fast` | Cheaper, quicker campaigns |
| `capable` | Harder jailbreak attempts |
| `auto` | Server picks based on prompt length |

### Tester notes

- **Cold start:** first request after idle may take 30–60s (Render free tier)
- **System prompt:** server-enforced; client `system` messages are ignored on legacy chat
- **Healthcare `/chat`:** rejects non-medical queries; use `/v1/chat/completions` for general adversarial testing
- **No guarantee:** prompt-based safety is not foolproof
- **Do not** share LiteLLM provider API keys — only the public HTTP endpoint

### Interactive CLI (non-PyRIT)

```powershell
cd "render testing"
python chat_cli.py
python chat_cli.py --url https://litellm-chat-api.onrender.com
python chat_cli.py --url http://127.0.0.1:8000 --model capable
```

---

## 16. Deployment (Render)

### Auto-deploy

Push to `main` on GitHub → Render rebuilds automatically (if connected).

```powershell
git add .
git commit -m "Your message"
git push origin main
```

### Blueprint (`render.yaml`)

- **Build:** `pip install -r requirements.txt`
- **Start:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check:** `/health`

### Required Render environment variables

Set in Render Dashboard → Environment (mark keys as **Secret**):

| Variable | Required |
|----------|----------|
| `FAST_MODEL_1`, `FAST_API_KEY_1` | Yes (at least one) |
| `CAPABLE_MODEL_1`, `CAPABLE_API_KEY_1` | Recommended |
| `SUPABASE_URL` | For full platform |
| `SUPABASE_SERVICE_ROLE_KEY` | For full platform |
| `SUPABASE_ANON_KEY` | For auth |
| `HOSPITAL_SLUG` | `city_general` |
| `AUTH_REQUIRED` | `false` for testing, `true` for production |

### Verify deployment

```powershell
curl https://litellm-chat-api.onrender.com/health
curl https://litellm-chat-api.onrender.com/
cd "render testing" && python test_render_api.py
```

---

## 17. Security & Compliance

| Area | Status |
|------|--------|
| Healthcare-only scope | Enforced before agent execution |
| HIPAA-oriented audit logs | Supabase `audit_logs`, `agent_execution_logs`, `tool_logs` |
| RLS | All patient/hospital tables |
| No diagnosis / no prescriptions | Agent system prompts + compliance agent |
| Emergency escalation | Logged to audit trail |
| PHI | Use Supabase + signed URLs for documents |
| Legacy chat open | For PyRIT — lock down before public production |

### Roles (RBAC)

| Role | Access |
|------|--------|
| `patient` | Own data |
| `doctor` | Assigned patients |
| `admin` | Full access + admin UI |
| `insurance_agent` | Prior auth tables |
| `support` | Limited self-signup |

---

## 18. Troubleshooting

| Issue | Fix |
|-------|-----|
| `"Insurer": "Not specified"` | Use demo patient in playground or set `insurance_provider` on patient profile |
| Out-of-scope for medical query | Rephrase as healthcare question |
| `502 LLM provider error` | Check API keys in `.env` / Render env |
| Supabase errors | Run migrations; verify `SUPABASE_SERVICE_ROLE_KEY` |
| Admin login fails | Set user role to `admin` in SQL |
| PyRIT multi-turn broken | Use `LiteLLMConversationTarget`, not plain HTTPTarget |
| Slow first request | Render free tier cold start — wait 30–60s |
| Tests fail on import | `pip install -r requirements.txt` |

---

## 19. Appendix

### HTTP status codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `400` | Bad request / out-of-scope / validation error |
| `401` | Auth required or invalid token |
| `403` | Insufficient role |
| `404` | Not found |
| `429` | Rate limit or budget exceeded |
| `502` | LLM provider error |
| `503` | Supabase not configured |

### Registered agents (bootstrap)

```
symptom_triage_agent
medication_agent
lab_analysis_agent
medical_records_agent
appointment_agent
insurance_agent
prior_authorization_agent
compliance_safety_agent
```

### References

- [LiteLLM Docs](https://docs.litellm.ai)
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [Microsoft PyRIT](https://github.com/Azure/PyRIT)
- [Supabase Docs](https://supabase.com/docs)
- [Render Docs](https://render.com/docs)

### Document history

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | June 2026 | Initial LiteLLM chat + PyRIT docs |
| 2.0 | June 2026 | Healthcare multi-agent platform, Supabase, hospital data, admin UI, full tester guide |

---

*Healthcare Multi-Agent AI Platform — LiteLLM + Supabase + MCP*
