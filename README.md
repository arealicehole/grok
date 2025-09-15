# Grok Intelligence Engine

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Pydantic](https://img.shields.io/badge/pydantic-v2-orange.svg?style=for-the-badge)](https://pydantic.dev)

**AI-powered transcript analysis microservice for the Jubal Personal Operating System ecosystem.**

Grok provides intelligent, multi-step profile-based processing of audio transcripts with support for both local (Ollama) and cloud (OpenRouter) LLM providers. Built with FastAPI and designed for containerized deployment in microservices architectures.

## 🚀 Quick Start

### Prerequisites

- **Docker Desktop** 4.0+
- **Docker Compose** v2.0+
- **Shared Jubal Network** (for service registry)

### Run with Docker Compose

```bash
# Clone repository
git clone https://github.com/arealicehole/grok.git
cd grok

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Start the service
docker compose up -d

# Verify service health
curl http://localhost:8002/health
```

## 📋 Current Status

### ✅ **Phase 2.1 Complete**: FastAPI Backend Scaffolding

**Recent Accomplishments:**

- ✅ **Complete FastAPI Application**: Implemented with Jubal service contracts
- ✅ **Pydantic v2 Compatibility**: All serialization issues resolved
- ✅ **Docker Integration**: Container runs successfully with shared infrastructure
- ✅ **Service Registry**: Redis-based registration implemented
- ✅ **API Endpoints**: All core endpoints functional and tested

### 🏗️ **In Development**: Phase 3 - Core Intelligence Framework

**Next Major Features:**
- 🔄 Local LLM Integration (Ollama)
- 🔄 Cloud Provider Integration (OpenRouter)
- 🔄 Multi-step Profile Processing Engine
- 🔄 Built-in Analysis Profiles

## 🔌 API Endpoints

### Service Management

| Endpoint | Method | Description | Status |
|----------|--------|-------------|---------|
| `/health` | GET | Service health check | ✅ |
| `/capabilities` | GET | Service capabilities declaration | ✅ |
| `/services` | GET | List registered Jubal services | ✅ |

### Profile Management

| Endpoint | Method | Description | Status |
|----------|--------|-------------|---------|
| `/profiles` | GET | List available processing profiles | ✅ |
| `/profiles/{id}` | GET | Get specific profile details | ✅ |

### Processing

| Endpoint | Method | Description | Status |
|----------|--------|-------------|---------|
| `/process` | POST | Process transcript with specified profile | ✅ |

### Example Usage

```bash
# Health check
curl http://localhost:8002/health

# List available profiles
curl http://localhost:8002/profiles | jq .

# Process a transcript
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "meeting-001",
    "data": {
      "type": "text/plain",
      "content": "John: Welcome to our meeting. Jane: Thanks, lets discuss the API requirements.",
      "encoding": "utf-8"
    },
    "metadata": {
      "profile_id": "business_meeting"
    }
  }' | jq .
```

## 🏗️ Architecture

### Container Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Jubal Network                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────┐ │
│  │   Jubal Core    │  │  Recall Adapter │  │   Grok   │ │
│  │    (8000)       │  │     (8001)      │  │  (8002)  │ │
│  └─────────────────┘  └─────────────────┘  └──────────┘ │
│             │                   │               │       │
│             └───────────────────┼───────────────┘       │
│                                 │                       │
│  ┌─────────────────┐            │        ┌──────────────┐ │
│  │  Redis Registry │←───────────┘        │  Supabase    │ │
│  │     (6379)      │                     │ (54325+)     │ │
│  └─────────────────┘                     └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Application Structure

```
grok/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry
│   ├── config.py               # Settings management
│   ├── models/
│   │   ├── __init__.py
│   │   ├── jubal.py           # Jubal service contracts
│   │   └── profile.py         # Processing profile schemas
│   └── services/
│       ├── __init__.py
│       ├── registry.py        # Redis service registry
│       └── processor.py       # Profile processing engine
├── profiles/                   # Processing profile definitions
├── docs/                      # Project documentation
├── Dockerfile                 # Container definition
├── docker-compose.yml         # Service orchestration
├── requirements.txt           # Python dependencies
└── .env.example               # Environment configuration template
```

## 🔧 Configuration

### Environment Variables

```bash
# Service Configuration
GROK_SERVICE_PORT=8002
GROK_DEBUG=true

# Jubal Integration
GROK_JUBAL_CORE_URL=http://jubal-core:8000
GROK_REDIS_URL=redis://jubal-redis:6379/0

# LLM Providers
GROK_OLLAMA_URL=http://host.docker.internal:11434
GROK_OPENROUTER_API_KEY=your_openrouter_api_key_here
GROK_OPENROUTER_URL=https://openrouter.ai/api/v1

# Default Models
GROK_DEFAULT_MODEL_PROVIDER=local
GROK_DEFAULT_LOCAL_MODEL=llama3.1:8b
GROK_DEFAULT_OPENROUTER_MODEL=openai/gpt-4o-mini

# Processing Configuration
GROK_MAX_CONCURRENT_JOBS=5
GROK_DEFAULT_TEMPERATURE=0.2
GROK_DEFAULT_MAX_TOKENS=2000

# File Management
GROK_PROFILES_DIR=./profiles
GROK_AUTO_PROCESS_NEW_FILES=false
```

### Docker Compose Services

- **grok-adapter**: Main application service (port 8002)
- **External Dependencies**:
  - `jubal-redis`: Service registry (shared)
  - `jubal-network`: Service communication network (shared)

## 📊 Processing Profiles

Grok uses **multi-step processing profiles** to analyze transcripts. Each profile defines a sequence of LLM operations with specific prompts and model configurations.

### Available Profiles

| Profile ID | Description | Steps | Estimated Tokens |
|------------|-------------|-------|------------------|
| `business_meeting` | Extract entities, decisions, action items | 3 | 4,500 |
| `project_planning` | Analyze requirements, timelines, risks | 4 | 5,200 |
| `personal_notes` | Process notes for organization | 3 | 3,000 |

### Profile Structure

```json
{
  "profile_id": "business_meeting",
  "name": "Business Meeting Analysis",
  "description": "Extract entities, decisions, and action items from business meetings",
  "steps": [
    {
      "step_id": "extract_entities",
      "name": "Extract Key Entities",
      "prompt_template": "Extract people, companies, and dates from: {transcript}",
      "llm_config": {
        "provider": "local",
        "model": "llama3.1:8b",
        "temperature": 0.1
      },
      "output_format": "json"
    }
  ]
}
```

## 🧪 Development

### Local Development Setup

```bash
# 1. Clone repository
git clone https://github.com/arealicehole/grok.git
cd grok

# 2. Set up Python environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your configuration

# 4. Start dependencies (Redis, Supabase)
# Note: Use shared Jubal infrastructure

# 5. Run application
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8002
```

### Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run unit tests
pytest tests/

# Integration testing with curl
./scripts/test_endpoints.sh

# End-to-end testing with sample data
curl -X POST http://localhost:8002/process -d @test_data/business_meeting.json
```

### Docker Development

```bash
# Build container
docker compose build grok-adapter

# Start services
docker compose up -d

# View logs
docker compose logs grok-adapter -f

# Rebuild and restart
docker compose up grok-adapter --build --force-recreate
```

## 🔌 Jubal Integration

### Service Registration

Grok automatically registers with the Redis service registry on startup:

```json
{
  "service": "grok-adapter",
  "version": "1.0.0",
  "host": "grok-adapter",
  "port": 8002,
  "health_endpoint": "/health",
  "capabilities": ["analyze", "extract", "summarize"]
}
```

### Jubal Envelope Format

All processing requests follow the Jubal envelope contract:

```json
{
  "job_id": "unique-job-identifier",
  "pipeline_id": "optional-pipeline-id",
  "data": {
    "type": "text/plain",
    "content": "transcript content here",
    "encoding": "utf-8"
  },
  "metadata": {
    "profile_id": "business_meeting",
    "overrides": {}
  },
  "trace": {}
}
```

### Response Format

```json
{
  "job_id": "unique-job-identifier",
  "status": "completed",
  "data": {
    "type": "application/json",
    "content": {
      "entities": {"people": ["John", "Jane"], "companies": ["Acme Corp"]},
      "summary": {"key_points": ["API requirements discussed"]},
      "processing_metadata": {"steps_completed": 3, "total_tokens": 150}
    },
    "encoding": "utf-8"
  },
  "error": null,
  "metadata": {
    "profile_id": "business_meeting",
    "timestamp": "2025-09-15T22:41:55.057669+00:00"
  }
}
```

## 🚀 Deployment

### Production Deployment

```bash
# Build production image
docker compose build grok-adapter

# Deploy with resource limits
docker compose -f docker-compose.prod.yml up -d

# Health check
curl https://your-domain.com/health
```

### Akash Network Deployment

(Coming in Phase 7)

```yaml
# deploy.yml for Akash Network
version: "2.0"
services:
  grok:
    image: grok-adapter:latest
    expose:
      - port: 8002
        as: 80
        to:
          - global: true
profiles:
  compute:
    grok:
      resources:
        cpu:
          units: 1.0
        memory:
          size: 2Gi
        storage:
          size: 5Gi
  placement:
    akash:
      attributes:
        host: akash
      signedBy:
        anyOf:
          - "akash1365yvmc4s7awdyj3n2sav7xfx76adc6dnmlx63"
      pricing:
        grok:
          denom: uakt
          amount: 1000
deployment:
  grok:
    akash:
      profile: grok
      count: 1
```

## 📚 Documentation

- [Development Plan](DEVELOPMENT_PLAN.md) - Comprehensive roadmap and implementation strategy
- [Project Scope](docs/grok-project-scope.md) - Overall Jubal ecosystem context
- [Integration Guide](docs/grok-integration.md) - Integration with Jubal services
- [API Reference](docs/api-reference.md) - Detailed API documentation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

### Development Guidelines

- Follow [FastAPI best practices](https://fastapi.tiangolo.com/tutorial/)
- Use [Pydantic v2](https://docs.pydantic.dev/latest/) for data validation
- Maintain test coverage above 80%
- Follow [semantic versioning](https://semver.org/)
- Document all API changes

## 📄 License

This project is part of the Jubal Personal Operating System ecosystem. See the [Jubal repository](https://github.com/arealicehole/jubal) for licensing information.

## 🔗 Related Projects

- [Jubal Core](https://github.com/arealicehole/jubal) - Personal Operating System framework
- [Recall](https://github.com/arealicehole/recall) - Audio processing and transcription adapter

## 📞 Support

For support and questions:

- Open an issue in this repository
- Check the [Jubal documentation](https://github.com/arealicehole/jubal)
- Join the community discussions

---

**Built with ❤️ for the Jubal ecosystem**