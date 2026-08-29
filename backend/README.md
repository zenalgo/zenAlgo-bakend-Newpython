# ZenAlgo Algorithmic & Copy-Trading Backend

A high-performance, asynchronous algorithmic and copy-trading backend platform migrated from Java Spring Boot to **Python 3.12+ & FastAPI**. 

The platform supports secure JWT authentication, multi-tenant database transactions, pessimistic ledger locking for double-spend protection, automated options contract routing, and real-time order placements to the Dhan HQ broker.

---

## 🛠️ Tech Stack
* **Runtime**: Python 3.12+
* **Web Framework**: FastAPI (Asynchronous ASGI)
* **ORM**: SQLAlchemy 2.0 (Asyncpg driver)
* **Database**: PostgreSQL 15+
* **Migrations**: Alembic
* **Cache**: Redis
* **Scheduling**: APScheduler (India-Kolkata Market hours aware)
* **Testing**: Pytest (Pytest-asyncio)

---

## 📂 Project Structure
```text
backend/
├── app/
│   ├── auth/                # JWT Auth, Login, Registration
│   ├── brokers/             # Dhan HQ integrations & Routing IP configs
│   ├── core/                # Config settings, DB connections, custom exceptions
│   ├── execution/           # Asynchronous signal batching & order loops
│   ├── strategies/          # Option leg rules validation & strategy versioning
│   ├── subscriptions/       # Plan access maps, daily quota checks, billing
│   ├── users/               # Trader profiles & admin routing
│   └── main.py              # Application entrypoint & request trace middleware
├── migrations/              # Alembic SQL schema migrations
├── tests/                   # Pytest automation suite
└── workers/
    └── scheduler.py         # APScheduler Indian market hour trigger ticks
```

---

## 🚀 Getting Started

### Prerequisites
Make sure you have Python 3.12+ and PostgreSQL installed locally, or Docker.

### 1. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your details:
```bash
cp .env.example .env
```

### 2. Running Locally

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the API Server**:
   ```bash
   python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

3. **Start the Cron Scheduler Worker** (in a separate terminal):
   ```bash
   python3 -m workers.scheduler
   ```

---

### 3. Running via Docker Compose (Includes DB & Redis)
To spin up all services together automatically:
```bash
docker-compose up --build
```

---

## 🔍 API Documentation
Once the server is running, you can explore and test the endpoints via:
* **Interactive Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc Visual Docs**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🧪 Running Automated Tests
Run full integration and unit tests using `pytest`:
```bash
python3 -m pytest
```
All database queries are executed in isolated test environments using a connection pool configured with `NullPool` to prevent cross-event-loop connection leakage.
