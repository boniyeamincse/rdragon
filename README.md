# ReconDragon 🐉

**Reconnaissance Made Powerful**

ReconDragon is a comprehensive, modular reconnaissance framework designed for security professionals, penetration testers, and red teamers. It provides a unified interface for running various reconnaissance tasks against targets, with support for both CLI and web-based operation.

## 🚀 Features

- **Modular Architecture**: Extensible plugin system for adding new reconnaissance capabilities
- **Multiple Interfaces**: CLI, REST API, and web dashboard
- **Worker Architecture**: Asynchronous job processing with Redis queue
- **Comprehensive Modules**: Subdomain enumeration, port scanning, vulnerability scanning, OSINT gathering
- **Docker Support**: Containerized deployment for easy setup
- **Legal Compliance**: Built-in safety features and authorization checks

## 📋 Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Modules](#modules)
- [API Documentation](#api-documentation)
- [Configuration](#configuration)
- [Legal & Ethical Usage](#legal--ethical-usage)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## 🛠️ Installation

### Prerequisites

- Python 3.8+
- Docker and Docker Compose (recommended)
- Redis (for worker architecture)

### Docker Installation (Recommended)

```bash
git clone https://github.com/your-org/recon-dragon.git
cd recon-dragon
docker-compose up -d
```

This will start:
- Redis (port 6379)
- API server (port 8000)
- Worker process
- Frontend (port 3000, if configured)

### Manual Installation

```bash
git clone https://github.com/your-org/recon-dragon.git
cd recon-dragon

# Install Python dependencies
pip install -r requirements.txt

# Install external tools (optional, modules will fall back gracefully)
# - nuclei
# - nmap
# - masscan
# - subfinder
# - theHarvester

# Start Redis
redis-server

# Start API server
cd api && uvicorn app:app --host 0.0.0.0 --port 8000

# Start worker
python worker/runner.py

# Start frontend (in another terminal)
cd frontend && npm install && npm run dev
```

## 🚀 Quick Start

### CLI Usage

```bash
# Basic scan with multiple modules
python cli/rdragon.py scan --target example.com --modules subdomains ports web

# List workspaces
python cli/rdragon.py list-workspaces

# Show job details
python cli/rdragon.py show-job <job-id>
```

### API Usage

```bash
# Create a job
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"module": "subfinder", "target": "example.com", "outdir": "./results"}'

# Check job status
curl http://localhost:8000/jobs/<job-id>
```

### Web Interface

Open http://localhost:3000 in your browser for the web dashboard.

## 🏗️ Architecture

ReconDragon uses a distributed architecture:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Frontend  │    │     API     │    │   Worker    │
│   (React)   │◄──►│  (FastAPI)  │◄──►│  (Python)  │
└─────────────┘    └─────────────┘    └─────────────┘
                       │                   │
                       ▼                   ▼
                ┌─────────────┐    ┌─────────────┐
                │   Redis     │    │  Modules   │
                │   Queue     │    │            │
                └─────────────┘    └─────────────┘
```

- **Frontend**: React-based web interface for job management
- **API**: FastAPI server handling HTTP requests and job queuing
- **Worker**: Processes jobs asynchronously using RQ (Redis Queue)
- **Modules**: Individual reconnaissance tools wrapped in Python classes

## 📦 Modules

ReconDragon includes the following modules:

| Module | Description | Dependencies |
|--------|-------------|--------------|
| `subfinder` | Subdomain enumeration | subfinder |
| `subdomains` | Alternative subdomain enumeration | - |
| `nmap` | Port scanning and service detection | nmap |
| `masscan` | Fast port scanning | masscan |
| `nuclei` | Vulnerability scanning with templates | nuclei |
| `harvester` | OSINT data collection | theHarvester |
| `shodan_enrich` | Shodan data enrichment | shodan API key |
| `http_probe` | HTTP service probing | - |
| `httpx_probe` | Advanced HTTP probing | httpx |

### Module Development

Modules inherit from `BaseModule` and implement a `run()` method:

```python
from base import BaseModule

class MyModule(BaseModule):
    @property
    def name(self) -> str:
        return "mymodule"

    @property
    def version(self) -> str:
        return "1.0.0"

    def run(self, target: str, outdir: str, execute: bool = False, **kwargs) -> dict:
        # Implementation here
        pass
```

## 📚 API Documentation

### Endpoints

- `POST /jobs` - Create a new job
- `GET /jobs/{job_id}` - Get job status
- `GET /jobs` - List all jobs
- `GET /workspaces` - List workspaces
- `GET /health` - Health check

### Example API Usage

```python
import requests

# Create job
response = requests.post("http://localhost:8000/jobs", json={
    "module": "nuclei",
    "target": "https://example.com",
    "outdir": "./results"
})
job_id = response.json()["job_id"]

# Check status
status = requests.get(f"http://localhost:8000/jobs/{job_id}")
print(status.json())
```

## ⚙️ Configuration

Configure ReconDragon using environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `DB_URL` | `./recon.db` | SQLite database path |
| `OUTPUT_DIR` | `./workspaces` | Base output directory |
| `WORKSPACE_AUTHORIZED` | `false` | Enable aggressive scanning |
| `NUCLEI_TIMEOUT` | `1800` | Nuclei scan timeout (seconds) |
| `HUNTER_API_KEY` | - | Hunter.io API key |
| `HIBP_API_KEY` | - | HaveIBeenPwned API key |

## ⚖️ Legal & Ethical Usage

**IMPORTANT: ReconDragon is designed for authorized security testing only.**

### Legal Requirements

Before using ReconDragon, ensure compliance with:

- ✅ Obtain explicit written permission from target owners
- ✅ Restrict usage to authorized systems and networks
- ✅ Comply with all applicable laws and regulations
- ✅ Avoid scanning government, critical infrastructure, or sensitive systems
- ✅ Do not use for malicious purposes or unauthorized access
- ✅ Respect robots.txt and rate limits
- ✅ Understand tool limitations and potential for false positives

### Ethical Guidelines

- Use ReconDragon responsibly and professionally
- Document all authorization and scope
- Report findings only to authorized parties
- Maintain confidentiality of discovered information
- Consider impact on target systems and networks

**The authors are not responsible for misuse of this tool.**

## 🧪 Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest

# Run specific module tests
pytest tests/test_nuclei_module.py -v
```

### Code Structure

```
recon-dragon/
├── cli/                    # CLI interface
├── api/                    # FastAPI backend
├── worker/                 # RQ worker
├── frontend/              # React frontend
├── modules/               # Recon modules
├── tests/                 # Unit tests
├── base.py                # Base module class
├── requirements.txt       # Python dependencies
└── docker-compose.yml     # Docker orchestration
```

### Adding New Modules

1. Create `modules/your_module.py`
2. Implement `YourModule(BaseModule)`
3. Add comprehensive tests in `tests/test_your_module.py`
4. Update this README

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Contribution Guidelines

- Follow PEP 8 style guidelines
- Add tests for new functionality
- Update documentation
- Ensure Docker builds pass
- Respect legal and ethical guidelines

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

ReconDragon is a reconnaissance tool intended for authorized security testing and research purposes only. Users are responsible for complying with all applicable laws and regulations. The authors assume no liability for misuse of this software.

## 🙏 Acknowledgments

- [ProjectDiscovery](https://projectdiscovery.io/) for nuclei and subfinder
- [OWASP](https://owasp.org/) for security best practices
- [FastAPI](https://fastapi.tiangolo.com/) for the web framework
- All contributors and the security community

---

**Happy Reconning! 🐉**