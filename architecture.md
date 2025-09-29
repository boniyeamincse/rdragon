# ReconDragon Architecture

## Detailed Text Blueprint for Diagramming

Below is a clear, copy-pasteable text description you can drop into a diagram tool (Draw.io, Lucidchart, Figma) or use as the basis for a whiteboard. This includes: components, responsibilities, data flows, sequence of operations, deployment topology, interfaces (APIs/queues/storage), security & gating, and suggested technologies — everything needed to turn into a visual architecture diagram.

### 1. Top-level components (boxes on diagram)

**CLI (rdragon)**
Purpose: user entry for creating jobs, workspaces, and launching scans.
Interfaces: writes job JSON to Backend API or enqueue to Queue.
Runs: local dry-run, or remote job submit.

**Backend API (FastAPI + GraphQL)**
Purpose: accept jobs, store metadata, manage workspaces, user auth.
Interfaces: GraphQL mutations (createJob, updateJob) and queries (jobs, workspaces, jobDetails).
Persists: job records to database.

**Job Queue (Redis / RQ or RabbitMQ / Celery)**
Purpose: reliable job handoff between API and worker(s).
Interfaces: push job payloads (JSON), job status updates.

**Worker Pool (worker/runner)**
Purpose: run modules/plugins in order (subdomain → port → http → vuln → screenshot).
Interface: pulls jobs from queue; writes artifacts to Storage; updates DB via Backend API or direct DB.
Behavior: plugin loader, rate-limiting, retries, sandbox/dry-run modes.

**Modules / Plugins (modules/)**
Purpose: wrappers around tools (subfinder, amass, nmap, masscan, httpx, nuclei, aquatone, shodan).
Contract: run(target, outdir, execute=False) -> dict with standard result schema.

**Artifact Storage (Local FS / S3 / MinIO)**
Purpose: store screenshots, raw scanner outputs (.json/.xml/.txt), parsed summaries.
Interface: worker writes files; Backend or UI retrieves.

**Database (SQLite for dev / PostgreSQL for prod)**
Stores: jobs, workspaces, users, job status, metadata, small parsed results.

**Web UI (React + Tailwind)**
Purpose: visualise workspaces, jobs, hosts, screenshots, export reports.
Interfaces: calls Backend API.

**Cache / Enrichment Services (optional)**
Shodan, Censys, VirusTotal — called by worker plugins with API keys; results cached in Storage/DB.

**Monitoring & Logging**
Centralized logs (ELK / Loki) and metrics (Prometheus + Grafana) for worker health, queue length, scan durations.

### 2. Data flow / sequence (numbered arrows for diagram)

1. User runs `rdragon scan --target example.com --workspace akij` (CLI) → sends GraphQL mutation createJob with job JSON.
2. Backend validates job, saves DB record job{id}, returns job id.
3. Backend enqueues job payload to Redis queue (job_id + workspace + modules + config).
4. Worker pulls job from queue. Worker marks job status running in DB.
5. Worker loads plugin list (subfinder → httpx → nmap → nuclei → screenshots) and executes each in sequence:
   - For each plugin: Validate workspace.authorized & execute flags. Run plugin in dry-run or execute mode. Write raw output to Artifact Storage. Parse summary and write to DB / send event to Backend.
6. Worker updates job progress (per-module) to DB and publishes events (optional websocket).
7. When finished, Worker sets job status completed or failed. Backend notifies Web UI (websocket) or user (email/notification).
8. Web UI fetches job results and artifacts via API for display and export.

### 3. Interfaces & payload examples

**GraphQL Mutation (from CLI / UI)**
```graphql
mutation CreateJob($input: CreateJobInput!) {
  createJob(input: $input) {
    id
    status
    createdAt
  }
}

# Variables:
{
  "input": {
    "target": "example.com",
    "workspace": "akij_scan",
    "modules": ["subfinder","httpx","nmap","nuclei","screenshot"],
    "execute": false,
    "options": { "nmap": {"args":"-sV -Pn"}, "nuclei": {"severity":"high"} }
  }
}
```

**Queue job payload**: same JSON + job_id and created_by.

**Module result schema (standardized)**
```json
{
  "module":"nmap",
  "version":"0.1",
  "target":"example.com",
  "start_time":"2025-09-29T07:00:00Z",
  "end_time":"2025-09-29T07:02:00Z",
  "success": true,
  "summary": {"hosts":1,"open_ports":3},
  "artifacts": ["s3://recondragon/results/job_123/nmap.xml"],
  "raw": {...}
}
```

### 4. Deployment topology (boxes grouped by host)

**Single-server dev:**
All components on one host: Backend + Redis + Worker + DB (SQLite) + Local FS.

**Production (recommended):**
- Backend API (1+ replicas behind LB)
- Worker pool (autoscale based on queue length)
- Redis (cluster or HA)
- PostgreSQL (managed/HA)
- MinIO or S3 for artifacts
- React UI hosted on CDN

**Network layout:**
Internal traffic: Workers ↔ Storage (S3) and Backend DB (private VPC).
External traffic: Backend and UI via HTTPS; Workers only pull jobs and optionally call external tools/networks.

### 5. Security & gating (important boxes/annotations)

**Workspace Authorization:**
Each workspace has authorized: bool, owner, scope (allowed domains/IPs).
Workers must check workspace.authorized before running destructive modules (masscan, sqlmap).

**CLI flags:**
--execute required to actually run tools; otherwise modules return dry-run commands.
--force only for admins + signed workspace.

**Secrets management:**
API keys (Shodan, VirusTotal, etc.) stored in env or secret manager (Vault/KMS). Plugins reference env vars and do not hardcode keys.

**Rate limiting:**
Global and per-module rate limits (config.yml) to prevent accidental DoS.

**Audit logging:**
Every job should record operator_id, timestamp, ip, command, workspace, and execute flag.

**Network isolation:**
Run workers in isolated network namespace; consider egress controls for plugins that call external APIs.

### 6. Scaling & reliability notes (diagram annotations)

Autoscale workers based on queue length or job backlog.
Shard storage by job id (prefix) to avoid hot spots.
Retries: worker should retry transient failures (3 attempts) with exponential backoff.
Idempotency: jobs should be safe to re-run (store last-run metadata).

### 7. Suggested technologies (annotate next to each box)

- CLI: Python Typer (local)
- Backend API: FastAPI + Graphene (GraphQL) + Uvicorn/Gunicorn
- Queue: Redis + RQ or RabbitMQ + Celery
- Workers: Python (module loader), Dockerized
- DB: SQLite (dev) → PostgreSQL (prod)
- Storage: Local FS (dev) → S3 / MinIO (prod)
- Modules: integrate binaries (subfinder, amass, nmap, masscan), Python libs (httpx, python-nmap), Playwright (screenshots)
- UI: React + Tailwind; WebSocket notifications
- Logging/Monitoring: ELK or Loki + Grafana + Prometheus

### 8. Diagram element suggestions (for visual clarity)

Use rounded boxes for services (API, Workers).
Use cylinders for DB & Storage.
Use queue icon for Redis.
Use small gear icons on Modules box to indicate plugin extensibility.
Use dashed lines for optional enrichment APIs (Shodan, Censys).
Annotate arrows with short labels: POST /jobs, enqueue job, pull job, write artifact, update status.

### 9. Example minimal ASCII layout (paste into text box of diagram tool)
```
[ CLI(rdragon) ] --> POST /api/jobs --> [ Backend API ] --> enqueue --> [ Redis Queue ]
                                                        ^                         |
                                                        |                         v
                                                  DB (Postgres)            Worker Pool (workers)
                                                                             /   |    |    \
                                                                             |   |    |    |
                                                                    modules: subfinder,nmap,httpx,nuclei,aquatone
                                                                             |
                                                                        Artifact Storage (S3 / MinIO)
                                                                             |
                                                                      Web UI <-- GET /api/jobs/{id}
```

### 10. Quick checklist to finish your diagram

- Add boxes: CLI, Backend, Queue, Workers, Modules, Artifact Storage, DB, Web UI.
- Show arrows for job submit → queue → worker → storage → UI.
- Mark external APIs (Shodan, Censys) as optional side services called by worker modules.
- Add small security notes near Worker (workspace auth) and Backend (user auth).
- Indicate which components are horizontally scalable (Backend, Workers) and which are stateful (DB, Storage, Redis).

## Component Diagram (Text-based)

```
+----------------+     +-------------------+     +-----------------+
|     Web UI     |<--->|     Web API       |<--->|       DB        |
+----------------+     +-------------------+     +-----------------+
                              |                         |
                              |                         |
                              v                         v
+----------------+     +-------------------+     +-----------------+
|      CLI       |<--->|    Queue (Redis)  |<--->|     Scheduler   |
+----------------+     +-------------------+     +-----------------+
                              |                         |
                              |                         |
                              v                         v
+----------------+     +-------------------+     +-----------------+
|    Worker      |<--->| Module/Plugin Int.|<--->|    Storage      |
+----------------+     +-------------------+     +-----------------+
                                                            |
                                                            v
                                                     +-----------------+
                                                     | Optional S3     |
                                                     +-----------------+
```

## Component Descriptions

### CLI
**Responsibilities:**
- Parse user commands and arguments
- Initialize scans and manage workspaces
- Display results and handle user interactions

**Recommended Libraries/Tools (Python Stack):**
- Click (command-line interface framework)
- Rich (for enhanced terminal output)

**Interface Contracts:**
- Expects command-line arguments: `recon dragon scan --target example.com --modules dns,ports`

### Worker
**Responsibilities:**
- Execute reconnaissance tasks asynchronously
- Process jobs from the queue
- Interact with modules to perform scans

**Recommended Libraries/Tools (Python Stack):**
- RQ (Redis Queue) for job processing
- multiprocessing or asyncio for concurrent tasks

**Interface Contracts:**
- Expects JSON job payload: `{"id": "job123", "workspace": "ws1", "target": "example.com", "modules": ["dns", "ports"]}`

### Module/Plugin Interface
**Responsibilities:**
- Define standard interface for reconnaissance modules
- Load and execute plugins dynamically
- Handle module-specific logic and outputs

**Recommended Libraries/Tools (Python Stack):**
- abc (Abstract Base Classes) for defining interfaces
- importlib for dynamic module loading

**Interface Contracts:**
- Modules implement `run(target, config) -> results` method
- Results format: `{"module": "dns", "data": [{"type": "A", "value": "192.168.1.1"}]}`

### DB
**Responsibilities:**
- Store job metadata, workspaces, and scan results
- Handle data persistence and queries

**Recommended Libraries/Tools (Python Stack):**
- SQLAlchemy (ORM for database interactions)
- SQLite or PostgreSQL as backend

**Interface Contracts:**
- Models: Job (id, status, created_at), Workspace (id, name), Host (ip, domain, results)

### Storage
**Responsibilities:**
- Store raw scan results and artifacts
- Manage file-based outputs from modules

**Recommended Libraries/Tools (Python Stack):**
- pathlib for file operations
- json/yaml for data serialization

**Interface Contracts:**
- File structure: `/workspaces/{ws_id}/jobs/{job_id}/results/{module}.json`

### Web API
**Responsibilities:**
- Provide RESTful endpoints for web UI interactions
- Handle job creation, status queries, and data retrieval

**Recommended Libraries/Tools (Python Stack):**
- FastAPI (web framework)
- Pydantic for data validation

**Interface Contracts:**
- Endpoints as per OpenAPI spec below

### Web UI
**Responsibilities:**
- Render user interface for scan management
- Display results and allow configuration

**Recommended Libraries/Tools:**
- React/Vue.js for frontend (if web-focused)
- Bootstrap/Tailwind for styling

**Interface Contracts:**
- Consumes Web API endpoints; sends JSON requests

### Scheduler
**Responsibilities:**
- Schedule recurring scans
- Manage job queue prioritization

**Recommended Libraries/Tools (Python Stack):**
- APScheduler for task scheduling
- Redis for queue management

**Interface Contracts:**
- Queue job JSON as above

### Queue (Redis)
**Responsibilities:**
- Buffer jobs between CLI/Web API and workers
- Ensure reliable message passing

**Recommended Libraries/Tools:**
- Redis (in-memory data structure store)
- redis-py client

**Interface Contracts:**
- Enqueue/dequeue JSON job objects

### Optional S3
**Responsibilities:**
- Offload large artifacts or results to cloud storage

**Recommended Libraries/Tools:**
- boto3 (AWS SDK for Python)
- MinIO for self-hosted S3-compatible storage

**Interface Contracts:**
- Upload files via key-value interface: `bucket/workspace/job/results.tar.gz`

## Minimal GraphQL Schema Sketch

```graphql
type Query {
  workspaces: [Workspace!]!
  jobs(workspace: ID): [Job!]!
  job(id: ID!): Job
}

type Mutation {
  createJob(input: CreateJobInput!): Job!
  updateJob(id: ID!, input: UpdateJobInput!): Job!
}

type Workspace {
  id: ID!
  name: String!
  jobs: [Job!]!
}

type Job {
  id: ID!
  workspace: Workspace!
  target: String!
  status: JobStatus!
  modules: [String!]!
  createdAt: DateTime!
  startedAt: DateTime
  endedAt: DateTime
  result: JobResult
}

type JobResult {
  summary: String!
  artifacts: [String!]!
  moduleResults: [ModuleResult!]!
}

type ModuleResult {
  module: String!
  success: Boolean!
  summary: String!
  artifacts: [String!]!
}

enum JobStatus {
  QUEUED
  RUNNING
  COMPLETED
  FAILED
}

input CreateJobInput {
  workspace: ID!
  target: String!
  modules: [String!]!
  execute: Boolean
  options: String
}

input UpdateJobInput {
  status: JobStatus
}

scalar DateTime

paths:
  /jobs:
    post:
      summary: Create a new job
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/JobCreate'
            example:
              workspace: "default"
              target: "example.com"
              modules: ["dns", "ports"]
      responses:
        201:
          description: Job created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Job'
              example:
                id: "job123"
                status: "queued"
                created_at: "2023-10-01T12:00:00Z"

  /jobs/{id}:
    get:
      summary: Get job status
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
      responses:
        200:
          description: Job status
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Job'

  /workspaces:
    get:
      summary: List workspaces
      responses:
        200:
          description: List of workspaces
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Workspace'
              example:
                - id: "ws1"
                  name: "default"

  /workspaces/{id}/hosts:
    get:
      summary: Fetch host results for workspace
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
      responses:
        200:
          description: Host results
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Host'
              example:
                - ip: "192.168.1.1"
                  domain: "example.com"
                  results: {"dns": ["A record"], "ports": [80, 443]}

components:
  schemas:
    JobCreate:
      type: object
      properties:
        workspace:
          type: string
        target:
          type: string
        modules:
          type: array
          items:
            type: string
      required: ["workspace", "target", "modules"]

    Job:
      type: object
      properties:
        id:
          type: string
        status:
          type: string
          enum: ["queued", "running", "completed", "failed"]
        created_at:
          type: string
          format: date-time

    Workspace:
      type: object
      properties:
        id:
          type: string
        name:
          type: string

    Host:
      type: object
      properties:
        ip:
          type: string
        domain:
          type: string
        results:
          type: object