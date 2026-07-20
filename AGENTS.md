# AGENTS.md — RecupDz Enterprise Architecture Audit

> Generated: 2026-07-18 | Backend: Django 4.2.13 + DRF 3.14 + Hermes 3 (Ollama)

---

## 1. PROJECT OVERVIEW

RecupDz is a waste management platform for Algeria covering BSD tracking, nomenclature, declarations, inspections, traceability, and an enterprise AI assistant with 20 domain tools.

| Metric | Value |
|--------|-------|
| Django apps | 13 |
| Django models | 28 |
| API endpoints | ~141 |
| AI tools | 20 |
| AI repositories | 16 |
| AI services | 5 |
| AI infrastructure modules | 14 |
| Total Python files | ~250+ |
| Database | SQLite3 (dev) |
| Auth | JWT (SimpleJWT 8h/7d) |
| RBAC | 7 roles, Django Groups |

---

## 2. ARCHITECTURE DIAGRAM

```
React Frontend
       │
       ▼
Django REST Framework (DRF)
  ├── JWT Auth (SimpleJWT)
  ├── RBAC (ModulePermission + 7 roles)
  └── AuditLogMiddleware
       │
       ├──► accounts (User, AuditLog, RBAC)
       ├──► recuperateurs (Recuperateur, Agrement, Specialisation)
       ├──► nomenclature (Nomenclature, DesignationDechet)
       ├──► bsd (BordereauSuiviDechet)
       ├──► bl (BonLivraison)
       ├──► bc (BonCommande)
       ├──► declarations (Declaration DSD)
       ├──► inspections (Inspection)
       ├──► operateurs (Operateur)
       ├──► traceability (Traceability)
       ├──► administration (AdministrationEnvironnement)
       ├──► archive (Document)
       │
       └──► ai_assistant
            │
            ├── Gateway Views (chat, stream, health, capabilities, metrics)
            ├── AgentOrchestrator (mandatory 7-step workflow)
            ├── EnterprisePipeline (public API)
            ├── AI Router (50+ deterministic rules)
            ├── OllamaService (Hermes 3 LLM)
            │
            ├── 20 Domain Tools ──► 16 Repositories ──► Django ORM ──► PostgreSQL
            ├── RAG (embeddings, vector store, retriever)
            ├── Workflow Engine (planner, reasoner, executor, recovery)
            ├── Memory (session, conversation, summary, user, cache)
            └── Infrastructure (cache, metrics, tracing, audit, security, rate-limit)
```

---

## 3. COMPONENT AUDIT — BUSINESS APPS

### 3.1 accounts
| Component | Status | Notes |
|-----------|--------|-------|
| Models | ✅ Exists | `User` (AbstractUser, 7 roles), `AuditLog` |
| Views | ✅ Exists | 8 function-based views |
| Serializers | ✅ Exists | `UserSerializer`, inline Role/Permission serializers |
| Services | ❌ Missing | Auth logic inline in views |
| Repository | ❌ Missing | Direct ORM queries in views |
| Tests | ❌ Missing | No test file |
| AI Ready | ⚠️ Partial | `user_repository.py` exists in ai_assistant but not in accounts |

### 3.2 recuperateurs
| Component | Status | Notes |
|-----------|--------|-------|
| Models | ✅ Exists | `Recuperateur`, `AgrementRecuperateur`, `DocumentRecuperateur`, `CategorieSpecialisation`, `SousCategorieSpecialisation`, `DetailSpecialisation` |
| Views | ✅ Exists | 2 ViewSets + 3 function views |
| Serializers | ✅ Exists | 9 serializers |
| Services | ❌ Missing | Business logic inline in views |
| Repository | ❌ Missing | Direct ORM queries in views |
| Tests | ❌ Missing | No test file |
| AI Ready | ✅ | `recuperateur_repository.py` in ai_assistant bridges to DB |

### 3.3 nomenclature
| Component | Status | Notes |
|-----------|--------|-------|
| Models | ✅ Exists | `Nomenclature` (328 entries), `DesignationDechet` |
| Views | ✅ Exists | 1 ReadOnlyModelViewSet + 1 function view |
| Serializers | ✅ Exists | 2 serializers |
| Services | ❌ Missing | Read-only, minimal logic |
| Repository | ❌ Missing | Direct ORM in views |
| Tests | ❌ Missing | No test file |
| AI Ready | ✅ | `nomenclature_repository.py` in ai_assistant |

### 3.4 bsd (Bordereau de Suivi des Déchets)
| Component | Status | Notes |
|-----------|--------|-------|
| Models | ✅ Exists | `BordereauSuiviDechet` (auto-numbered BSD-{YYYY}-{UUID}) |
| Views | ✅ Exists | 1 ViewSet + 2 function views (PDF/Word gen) |
| Serializers | ✅ Exists | `BSDSerializer` |
| Services | ❌ Missing | Signature logic inline in view |
| Repository | ❌ Missing | Direct ORM in views |
| Tests | ❌ Missing | No test file |
| AI Ready | ✅ | `bsd_repository.py` in ai_assistant |

### 3.5 bl (Bon de Livraison)
| Component | Status | Notes |
|-----------|--------|-------|
| Models | ✅ Exists | `BonLivraison` (auto-numbered PBL{YY}{UUID}) |
| Views | ✅ Exists | 1 ViewSet + 2 function views |
| Serializers | ✅ Exists | `BLSerializer` |
| Services | ❌ Missing | Logic inline |
| Repository | ❌ Missing | Direct ORM |
| Tests | ❌ Missing | No test file |
| AI Ready | ✅ | `bl_repository.py` in ai_assistant |

### 3.6 bc (Bon de Commande)
| Component | Status | Notes |
|-----------|--------|-------|
| Models | ✅ Exists | `BonCommande` (auto-numbered prefix-based) |
| Views | ✅ Exists | 1 ViewSet + 2 function views |
| Serializers | ✅ Exists | `BCSerializer` |
| Services | ❌ Missing | Logic inline |
| Repository | ❌ Missing | Direct ORM |
| Tests | ❌ Missing | No test file |
| AI Ready | ✅ | `bc_repository.py` in ai_assistant |

### 3.7 declarations (DSD)
| Component | Status | Notes |
|-----------|--------|-------|
| Models | ✅ Exists | `Declaration` (39 fields, Sections A/B/C) |
| Views | ✅ Exists | 1 ViewSet + 2 function views |
| Serializers | ✅ Exists | `DeclarationSerializer` |
| Services | ❌ Missing | Logic inline |
| Repository | ❌ Missing | Direct ORM |
| Tests | ❌ Missing | No test file |
| AI Ready | ✅ | `declaration_repository.py` in ai_assistant |

### 3.8 inspections
| Component | Status | Notes |
|-----------|--------|-------|
| Models | ✅ Exists | `Inspection` (ROUTINE/SURPRISE/PLAINTE/SUIVI) |
| Views | ✅ Exists | 1 ViewSet + 2 function views |
| Serializers | ✅ Exists | `InspectionSerializer` |
| Services | ❌ Missing | Logic inline |
| Repository | ❌ Missing | Direct ORM |
| Tests | ❌ Missing | No test file |
| AI Ready | ✅ | `inspection_repository.py` in ai_assistant |

### 3.9 operateurs
| Component | Status | Notes |
|-----------|--------|-------|
| Models | ✅ Exists | `Operateur` (7 types, with agrément, transport, CET fields) |
| Views | ✅ Exists | 1 ViewSet with `stats` and `verifier_compatibilite` actions |
| Serializers | ✅ Exists | 2 serializers |
| Services | ❌ Missing | Logic inline |
| Repository | ❌ Missing | Direct ORM |
| Tests | ❌ Missing | No test file |
| AI Ready | ✅ | `operateur_repository.py` in ai_assistant |

### 3.10 traceability
| Component | Status | Notes |
|-----------|--------|-------|
| Models | ✅ Exists | `Traceability` (sequential counter, multi-destination, JSON repartitions) |
| Views | ✅ Exists | 1 ViewSet with `stats` action + audit logging |
| Serializers | ✅ Exists | `TraceabilitySerializer` |
| Services | ❌ Missing | Logic inline |
| Repository | ❌ Missing | Direct ORM |
| Tests | ❌ Missing | No test file |
| AI Ready | ✅ | `traceability_repository.py` in ai_assistant |

### 3.11 administration
| Component | Status | Notes |
|-----------|--------|-------|
| Models | ✅ Exists | `AdministrationEnvironnement` (Ministry, Direction, AND) |
| Views | ✅ Exists | 1 ViewSet (basic CRUD) |
| Serializers | ✅ Exists | `AdministrationSerializer` |
| Services | ❌ Missing | — |
| Repository | ❌ Missing | — |
| Tests | ❌ Missing | No test file |
| AI Ready | ⚠️ Partial | No repository in ai_assistant |

### 3.12 archive
| Component | Status | Notes |
|-----------|--------|-------|
| Models | ✅ Exists | `Document` (file upload, categories, size) |
| Views | ✅ Exists | 1 ViewSet (MultiPart parser for file uploads) |
| Serializers | ✅ Exists | `DocumentSerializer` |
| Services | ❌ Missing | — |
| Repository | ❌ Missing | — |
| Tests | ❌ Missing | No test file |
| AI Ready | ✅ | `archive_repository.py` in ai_assistant |

---

## 4. COMPONENT AUDIT — AI ASSISTANT MODULE

### 4.1 Enterprise Layer
| Component | Status | Path | Notes |
|-----------|--------|------|-------|
| AgentOrchestrator | ✅ Exists | `enterprise/agent_orchestrator.py` | 7-step mandatory workflow, business-first policy, anti-hallucination guard, follow-up generation |
| EnterprisePipeline | ✅ Exists | `enterprise/pipeline.py` | Public API delegating to AgentOrchestrator |
| AI Router | ✅ Exists | `enterprise/ai_router.py` | 50+ deterministic regex rules, French/English, glossary-aware |
| Container (DI) | ✅ Exists | `enterprise/container.py` | 20 tools, all infrastructure services wired |
| Adapters | ✅ Exists | `enterprise/adapters.py` | OllamaLLMAdapter, ToolExecutorAdapter, DeterministicFormatter |

### 4.2 Tools (20 registered)
| Tool | Status | Actions | AI Ready |
|------|--------|---------|----------|
| `waste_tool` | ✅ | 7 | ✅ |
| `declaration_tool` | ✅ | 6 | ✅ |
| `producteur_tool` | ✅ | 5 | ✅ |
| `transporteur_tool` | ✅ | 5 | ✅ |
| `partner_tool` | ✅ | 5 | ✅ |
| `entreprise_tool` | ✅ | 7 | ✅ |
| `statistiques_tool` | ✅ | 8 | ✅ |
| `rapport_tool` | ✅ | 5 | ✅ |
| `reglementation_tool` | ✅ | 5 | ✅ |
| `authentification_tool` | ✅ | 3 | ✅ |
| `glossaire_tool` | ✅ | 3 | ✅ |
| `nomenclature_tool` | ✅ | 4 | ✅ |
| `notification_tool` | ✅ | 6 | ✅ |
| `dashboard_tool` | ✅ | 5 | ✅ |
| `bsd_tool` | ✅ | — | ✅ |
| `bc_tool` | ✅ | — | ✅ |
| `bl_tool` | ✅ | — | ✅ |
| `inspection_tool` | ✅ | — | ✅ |
| `archive_tool` | ✅ | — | ✅ |
| `traceability_tool` | ✅ | — | ✅ |

### 4.3 Repositories (16)
| Repository | Status | Bridges To |
|------------|--------|------------|
| `base_repository.py` | ✅ | Abstract base |
| `archive_repository.py` | ✅ | `archive.Document` |
| `bc_repository.py` | ✅ | `bc.BonCommande` |
| `bl_repository.py` | ✅ | `bl.BonLivraison` |
| `bsd_repository.py` | ✅ | `bsd.BordereauSuiviDechet` |
| `dashboard_repository.py` | ✅ | Cross-module KPI aggregation |
| `declaration_repository.py` | ✅ | `declarations.Declaration` |
| `glossary_repository.py` | ✅ | glossaire_data.py + KnowledgeBase |
| `inspection_repository.py` | ✅ | `inspections.Inspection` |
| `knowledge_repository.py` | ✅ | `ai_assistant.KnowledgeBase` |
| `nomenclature_repository.py` | ✅ | `nomenclature.Nomenclature` |
| `notification_repository.py` | ✅ | Generated from live data (no model) |
| `operateur_repository.py` | ✅ | `operateurs.Operateur` |
| `recuperateur_repository.py` | ✅ | `recuperateurs.Recuperateur` |
| `traceability_repository.py` | ✅ | `traceability.Traceability` |
| `user_repository.py` | ✅ | `accounts.User` |

### 4.4 Services (5)
| Service | Status | Notes |
|---------|--------|-------|
| `ollama_service.py` | ✅ | HTTP client for Ollama API (Hermes 3) |
| `chat_service.py` | ✅ | Chat orchestration |
| `prompt_builder.py` | ✅ | System prompt construction |
| `response_parser.py` | ✅ | LLM response parsing |
| `streaming.py` | ✅ | SSE streaming support |

### 4.5 Infrastructure (14 modules)
| Module | Status | Notes |
|--------|--------|-------|
| `audit/audit.py` | ✅ | AuditLogger with AuditAction enum |
| `caching/cache.py` | ✅ | CacheManager + InMemoryCache |
| `metrics/collector.py` | ✅ | Prometheus-compatible metrics |
| `tracing/tracer.py` | ✅ | Request tracing with spans |
| `monitoring/health.py` | ✅ | HealthCheck component |
| `security/sanitizer.py` | ✅ | Input sanitization |
| `rate_limiting/limiter.py` | ✅ | Rate limiting |
| `permissions/framework.py` | ✅ | AI-specific permissions |
| `middleware.py` | ✅ | RequestTracking, SecurityHeaders, RateLimit, Audit (not registered globally) |
| `configuration/settings.py` | ✅ | AI-specific settings |
| `documentation/openapi.py` | ✅ | API documentation |
| `performance/profiler.py` | ✅ | Performance profiling |
| `testing/fixtures.py` | ✅ | Test fixtures |

### 4.6 Core Agent (14 modules)
| Module | Status | Notes |
|--------|--------|-------|
| `interfaces.py` | ✅ | ABCs: LLMProvider, Tool, MemoryStore, ContextBuilder, Planner, Reasoner, Router, Executor, Formatter, Agent |
| `config.py` | ✅ | AgentConfig (frozen dataclass), MemoryConfig |
| `context.py` | ✅ | DefaultContextBuilder, DataProvider |
| `memory.py` | ✅ | MemoryManager |
| `planner.py` | ✅ | LLMPlanner |
| `reasoning.py` | ✅ | LLMReasoner |
| `prompts.py` | ✅ | PromptRegistry |
| `agent.py` | ✅ | Agent implementation |
| `gateway.py` | ✅ | Gateway orchestration |
| `router.py` | ✅ | Intent routing |
| `router_agent.py` | ✅ | Router agent |
| `executor.py` | ✅ | Plan executor |
| `formatter.py` | ✅ | Response formatting |

### 4.7 RAG (5 modules)
| Module | Status | Notes |
|--------|--------|-------|
| `document_loader.py` | ✅ | PDF/text loading |
| `embedding_service.py` | ✅ | Embedding generation |
| `vector_store.py` | ✅ | Vector storage |
| `retriever.py` | ✅ | Document retrieval |
| `search_engine.py` | ✅ | Search orchestration |

### 4.8 Workflow Engine (10 sub-packages)
| Module | Status | Notes |
|--------|--------|-------|
| `engine.py` | ✅ | Main workflow engine |
| `agent/agent.py` | ✅ | Workflow agent |
| `builders/builder.py` | ✅ | Workflow builder |
| `decision_tree/engine.py` | ✅ | Decision tree |
| `execution_graph/graph.py` | ✅ | Execution graph |
| `planner/planner.py` | ✅ | Workflow planner |
| `reasoner/reasoner.py` | ✅ | Workflow reasoner |
| `recovery/engine.py` | ✅ | Error recovery |
| `task_queue/queue.py` | ✅ | Task queue |
| `validation/engine.py` | ✅ | Validation engine |

### 4.9 Memory (5 modules)
| Module | Status | Notes |
|--------|--------|-------|
| `session_memory.py` | ✅ | Session-level memory |
| `conversation_memory.py` | ✅ | Conversation memory |
| `summary_memory.py` | ✅ | Summarization memory |
| `user_memory.py` | ✅ | User-level memory |
| `cache_memory.py` | ✅ | Cache-backed memory |

### 4.10 Reasoning Engine (8 modules)
| Module | Status | Notes |
|--------|--------|-------|
| `pipeline.py` | ✅ | Reasoning pipeline |
| `entity_extractor.py` | ✅ | Entity extraction |
| `intent_detector.py` | ✅ | Intent detection |
| `tool_selector.py` | ✅ | Tool selection |
| `planner.py` | ✅ | Reasoning planner |
| `executor.py` | ✅ | Reasoning executor |
| `responder.py` | ✅ | Response generation |
| `validator.py` | ✅ | Input validation |

### 4.11 Tests (3 files)
| File | Tests | Notes |
|------|-------|-------|
| `tests/test_pipeline.py` | 47 | Pipeline + Orchestrator (all pass) |
| `tests/test_infrastructure.py` | 40 | Cache, Metrics, Tracing, Audit, Health |
| `tests/test_container.py` | 3 | Container wiring |

---

## 5. AUTHENTICATION & PERMISSIONS

| Component | Status | Notes |
|-----------|--------|-------|
| Custom User Model | ✅ | `accounts.User` (AbstractUser + 7 roles) |
| JWT Auth | ✅ | SimpleJWT (8h access / 7d refresh) |
| RBAC | ✅ | 7 Django Groups, `setup_rbac` command |
| ModulePermission | ✅ | Object-level RBAC via `module_label` + Django perms |
| Permission Classes | ✅ | 7 classes: IsSuperAdmin, IsAdmin, IsResponsableCollecte, IsAgentCollecte, IsResponsableDecharge, ReadOnly, ModulePermission |
| AuditLogMiddleware | ✅ | Captures client IP |
| Custom Exception Handler | ✅ | French-language 403 responses |
| Custom Pagination | ✅ | StandardPagination (20/page, max 2000) |

---

## 6. GENERATION / EXPORT

| Module | PDF | Word | Status |
|--------|-----|------|--------|
| BSD | ✅ `generate_bsd.py` | ✅ `generate_bsd_word.py` | ReportLab + python-docx |
| BL | ✅ `generate_bl.py` | ✅ `generate_bl_word.py` | ReportLab + python-docx |
| BC | ✅ `generate_bc.py` | ✅ `generate_bc_word.py` | ReportLab + python-docx |
| DSD | ✅ `generate_dsd.py` | ✅ `generate_dsd_word.py` | ReportLab + python-docx |
| PV | ✅ `generate_pv.py` | ✅ `generate_pv_word.py` | ReportLab + python-docx |

---

## 7. CRITICAL GAPS

### 7.1 No Tests Outside AI Module
| App | Tests | Status |
|-----|-------|--------|
| accounts | 0 | ❌ Missing |
| recuperateurs | 0 | ❌ Missing |
| nomenclature | 0 | ❌ Missing |
| bsd | 0 | ❌ Missing |
| bl | 0 | ❌ Missing |
| bc | 0 | ❌ Missing |
| declarations | 0 | ❌ Missing |
| inspections | 0 | ❌ Missing |
| operateurs | 0 | ❌ Missing |
| traceability | 0 | ❌ Missing |
| administration | 0 | ❌ Missing |
| archive | 0 | ❌ Missing |
| ai_assistant | 90 | ✅ |

### 7.2 No Service/Repository Layer in Business Apps
Only `ai_assistant` has a service and repository layer. All 12 business apps keep logic **inline in views** — violating SOLID (SRP, DIP) and making code untestable in isolation.

### 7.3 No Docker / CI/CD
- No `Dockerfile` or `docker-compose.yml`
- No CI pipeline configuration
- Runs on SQLite in dev mode

### 7.4 No Celery / Async Tasks
- No background task processing
- PDF generation is synchronous (blocking)
- No periodic jobs for alert scanning, report generation

### 7.5 No WebSocket / Real-time
- No Django Channels
- SSE streaming exists in AI gateway but no persistent connections

### 7.6 AI Infrastructure Middleware Not Registered
4 middleware classes defined in `infrastructure/middleware.py` but **not added** to Django's `MIDDLEWARE` setting:
- `RequestTrackingMiddleware`
- `SecurityHeadersMiddleware`
- `RateLimitMiddleware`
- `AuditMiddleware`

---

## 8. REFACTORING RECOMMENDATIONS

### Priority 1 — Critical
| # | Issue | Recommendation |
|---|-------|----------------|
| 1 | **No tests for business apps** | Add model + view + serializer tests for all 12 apps. Target: 80%+ coverage |
| 2 | **Inline business logic in views** | Extract Service + Repository layers per app. Follow ai_assistant pattern |
| 3 | **SQLite in production** | Add PostgreSQL (already referenced in AI repositories) + docker-compose |
| 4 | **Synchronous PDF generation** | Add Celery for async document generation |

### Priority 2 — Important
| # | Issue | Recommendation |
|---|-------|----------------|
| 5 | **No error handling patterns** | Standardize error responses across all apps (follow ai_assistant pattern) |
| 6 | **Duplicate serializer logic** | Some serializers inline in views.py (accounts). Extract to serializers.py |
| 7 | **AI middleware not registered** | Register RateLimitMiddleware and SecurityHeadersMiddleware globally |
| 8 | **No API versioning** | Add `/api/v1/` prefix for future-proofing |

### Priority 3 — Nice to Have
| # | Issue | Recommendation |
|---|-------|----------------|
| 9 | **No WebSocket** | Add Django Channels for real-time alerts and notifications |
| 10 | **No OpenAPI/Swagger** | Enable DRF Spectacular or drf-yasg for API documentation |
| 11 | **No health checks** | Add `/health/` endpoint per app |
| 12 | **No caching on business views** | Add DRF cache_page on read-heavy endpoints (nomenclature, recuperateurs) |

---

## 9. KEY FILES INDEX

| File | Path |
|------|------|
| Django Settings | `config/settings.py` |
| Root URLs | `config/urls.py` |
| Custom User | `apps/accounts/models.py` |
| Permissions | `apps/accounts/permissions.py` |
| RBAC Setup | `apps/accounts/management/commands/setup_rbac.py` |
| AI Gateway | `apps/ai_assistant/gateway_views.py` |
| Agent Orchestrator | `apps/ai_assistant/enterprise/agent_orchestrator.py` |
| Enterprise Pipeline | `apps/ai_assistant/enterprise/pipeline.py` |
| AI Router | `apps/ai_assistant/enterprise/ai_router.py` |
| DI Container | `apps/ai_assistant/enterprise/container.py` |
| Ollama Service | `apps/ai_assistant/services/ollama_service.py` |
| Tool Base | `apps/ai_assistant/tools/base_tool.py` |
| Tool Executor | `apps/ai_assistant/tools/tool_executor.py` |
| Core Interfaces | `apps/ai_assistant/core/interfaces.py` |
| Glossary Data | `apps/ai_assistant/glossaire_data.py` |
| Test Suite | `apps/ai_assistant/tests/test_pipeline.py` |

---

## 10. WORKFLOW ENFORCEMENT

The AI assistant follows a **mandatory 7-step workflow** enforced by `AgentOrchestrator`:

```
Step 1: Receive message        → Start trace, audit, cache check
Step 2: Understand intent      → AI Router (deterministic) → Hermes LLM fallback
Step 3: Select tool            → Business-first: AI Router → Hermes → AI Router fallback
Step 4: Execute tool           → Structured JSON from repository layer
Step 5: Anti-hallucination     → Validate tool data (logging only)
Step 6: Generate response      → Hermes LLM with "use ONLY tool data" prompt
Step 7: Generate follow-ups    → 2-3 contextual follow-up questions
```

**Policies:**
- AI NEVER invents data — all facts from tools or explicit knowledge
- Business modules ALWAYS tried before model knowledge
- Tool result JSON passed verbatim to response generator
- Every step traced and instrumented

---

*End of Architecture Audit*
