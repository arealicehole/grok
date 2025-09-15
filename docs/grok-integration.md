# Grok Integration Guide

## Overview

The Grok adapter provides intelligent transcript analysis using configurable multi-step processing profiles. It integrates with Jubal's microservices architecture to deliver sophisticated text analysis capabilities with support for both local LLMs (via Ollama) and cloud providers (via OpenRouter).

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Transcript    │────│   Grok Adapter   │────│  Processed      │
│   Input         │    │                  │    │  Analysis       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              │ Uses
                              ▼
                      ┌──────────────────┐
                      │   Multi-Step     │
                      │   Profiles       │
                      │   ┌────────────┐ │
                      │   │ Step 1     │ │ ◄── Local LLM
                      │   │ Extract    │ │
                      │   └────────────┘ │
                      │   ┌────────────┐ │
                      │   │ Step 2     │ │ ◄── OpenRouter
                      │   │ Analyze    │ │
                      │   └────────────┘ │
                      │   ┌────────────┐ │
                      │   │ Step 3     │ │ ◄── Configurable
                      │   │ Summarize  │ │
                      │   └────────────┘ │
                      └──────────────────┘
```

## Key Features

### Multi-Step Profile Processing
- **Sequential Processing**: Profiles define multiple processing steps
- **Step Chaining**: Output from one step feeds into the next
- **Per-Step Model Selection**: Each step can use different LLM providers/models
- **Conditional Steps**: Steps can be marked as required or optional

### Flexible Model Support
- **Local Models**: Ollama integration for privacy-focused processing
- **Cloud Models**: OpenRouter integration for advanced capabilities
- **Global Overrides**: Runtime ability to override all model selections
- **Mixed Processing**: Use local models for simple tasks, cloud for complex analysis

### Profile-Driven Analysis
- **Business Meetings**: Entity extraction, decision analysis, action items
- **Project Planning**: Requirements analysis, timeline extraction, risk assessment
- **Personal Notes**: Idea capture, task extraction, insight organization
- **Custom Profiles**: User-created profiles for specific use cases

## API Reference

### Core Endpoints

#### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "grok-adapter",
  "version": "1.0.0",
  "timestamp": "2025-09-15T20:30:00Z"
}
```

#### Service Capabilities
```http
GET /capabilities
```

**Response:**
```json
{
  "service": "grok-adapter",
  "version": "1.0.0",
  "accepts": ["text/plain"],
  "provides": ["application/json"],
  "operations": ["analyze", "extract", "summarize"],
  "features": {
    "multi_step_processing": true,
    "profile_based_analysis": true,
    "model_selection": true,
    "global_overrides": true
  },
  "supported_providers": ["local", "openrouter"],
  "available_profiles": ["business_meeting", "project_planning", "personal_notes"]
}
```

#### Process Transcript
```http
POST /process
```

**Request Body:**
```json
{
  "job_id": "job-123",
  "data": {
    "type": "text/plain",
    "content": "Meeting transcript here...",
    "encoding": "utf-8"
  },
  "metadata": {
    "profile_id": "business_meeting",
    "source": "zoom_recording",
    "duration_minutes": 45
  },
  "overrides": {
    "force_provider": "local",
    "force_model": "llama3.1:8b",
    "temperature": 0.1
  }
}
```

**Response:**
```json
{
  "job_id": "job-123",
  "status": "completed",
  "data": {
    "type": "application/json",
    "content": {
      "entities": {
        "people": ["John Doe", "Jane Smith"],
        "companies": ["Acme Corp"],
        "dates": ["2025-09-20"],
        "locations": ["Conference Room A"]
      },
      "decisions": [
        {
          "decision": "Implement new authentication system",
          "responsible": "Jane Smith",
          "deadline": "2025-09-30",
          "rationale": "Security compliance requirements"
        }
      ],
      "summary": {
        "key_points": ["Security upgrade needed", "Budget approved"],
        "action_items": [
          {
            "task": "Security audit",
            "assignee": "John Doe",
            "due_date": "2025-09-25"
          }
        ],
        "next_meeting": "2025-09-22",
        "sentiment": "positive"
      },
      "processing_metadata": {
        "profile_used": "business_meeting",
        "steps_completed": 3,
        "total_tokens": 2847,
        "processing_time_ms": 4200
      }
    }
  },
  "metadata": {
    "profile_id": "business_meeting",
    "timestamp": "2025-09-15T20:30:00Z"
  }
}
```

### Profile Management

#### List Available Profiles
```http
GET /profiles
```

**Response:**
```json
{
  "profiles": [
    {
      "profile_id": "business_meeting",
      "name": "Business Meeting Analysis",
      "description": "Extract entities, decisions, and action items from business meetings",
      "steps": 3,
      "estimated_tokens": 4500,
      "tags": ["business", "meetings", "decisions"]
    },
    {
      "profile_id": "project_planning",
      "name": "Project Planning Session",
      "description": "Analyze project planning discussions for requirements, timelines, and risks",
      "steps": 4,
      "estimated_tokens": 5200,
      "tags": ["project", "planning", "requirements"]
    }
  ]
}
```

#### Get Profile Details
```http
GET /profiles/{profile_id}
```

**Response:**
```json
{
  "profile_id": "business_meeting",
  "name": "Business Meeting Analysis",
  "description": "Extract entities, decisions, and action items from business meetings",
  "version": "1.0.0",
  "steps": [
    {
      "step_id": "extract_entities",
      "name": "Extract Key Entities",
      "model_config": {
        "provider": "local",
        "model": "llama3.1:8b",
        "temperature": 0.1
      },
      "required": true
    }
  ],
  "final_output_schema": {...},
  "tags": ["business", "meetings", "decisions"],
  "use_cases": ["Team meetings", "Client calls", "Project reviews"],
  "estimated_tokens": 4500
}
```

#### Create Custom Profile
```http
POST /profiles
```

**Request Body:**
```json
{
  "profile_id": "custom_analysis",
  "name": "Custom Analysis Profile",
  "description": "Custom profile for specific analysis needs",
  "steps": [
    {
      "step_id": "analyze_content",
      "name": "Analyze Content",
      "prompt_template": "Analyze this transcript: {transcript}",
      "model_config": {
        "provider": "local",
        "model": "llama3.1:8b",
        "temperature": 0.2
      },
      "required": true
    }
  ],
  "tags": ["custom"],
  "created_by": "user_id"
}
```

### Model Management

#### List Available Models
```http
GET /models
```

**Response:**
```json
{
  "providers": {
    "local": {
      "url": "http://host.docker.internal:11434",
      "models": ["llama3.1:8b", "mistral:7b", "codellama:7b"],
      "status": "available"
    },
    "openrouter": {
      "url": "https://openrouter.ai/api/v1",
      "models": ["openai/gpt-4o", "anthropic/claude-3-sonnet", "openai/gpt-4o-mini"],
      "status": "configured"
    }
  },
  "defaults": {
    "provider": "local",
    "local_model": "llama3.1:8b",
    "openrouter_model": "openai/gpt-4o-mini"
  }
}
```

#### Test Model Availability
```http
POST /models/test
```

**Request Body:**
```json
{
  "provider": "local",
  "model": "llama3.1:8b"
}
```

## Processing Overrides

The Grok adapter supports runtime overrides that allow you to modify processing behavior without changing profile configurations.

### Global Override Types

#### Force Provider
```json
{
  "overrides": {
    "force_provider": "local"  // All steps use local models
  }
}
```

#### Force Model
```json
{
  "overrides": {
    "force_model": "llama3.1:8b"  // All steps use this specific model
  }
}
```

#### Force Parameters
```json
{
  "overrides": {
    "temperature": 0.1,  // Override temperature for all steps
    "max_tokens": 1000   // Override token limit for all steps
  }
}
```

#### Step-Specific Overrides
```json
{
  "overrides": {
    "step_overrides": {
      "extract_entities": {
        "provider": "openrouter",
        "model": "openai/gpt-4o"
      },
      "analyze_decisions": {
        "temperature": 0.2
      }
    }
  }
}
```

## Configuration

### Environment Variables

```bash
# Service Configuration
GROK_SERVICE_PORT=8002
GROK_DEBUG=false

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

# Processing
GROK_MAX_CONCURRENT_JOBS=5
GROK_DEFAULT_TEMPERATURE=0.2
GROK_DEFAULT_MAX_TOKENS=2000

# File Management
GROK_PROFILES_DIR=./profiles
GROK_AUTO_PROCESS_NEW_FILES=false
```

### Docker Configuration

```yaml
# docker-compose.yml
services:
  grok-adapter:
    build: ./adapters/grok-adapter
    container_name: jubal-grok
    ports:
      - "8002:8002"
    environment:
      - GROK_JUBAL_CORE_URL=http://jubal-core:8000
      - GROK_REDIS_URL=redis://jubal-redis:6379/0
      - GROK_OLLAMA_URL=http://host.docker.internal:11434
      - GROK_OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    volumes:
      - ./adapters/grok-adapter/profiles:/app/profiles
    depends_on:
      - redis
      - jubal-core
    networks:
      - jubal-network
```

## Profile Development

### Profile Structure

```json
{
  "profile_id": "unique_identifier",
  "name": "Human Readable Name",
  "description": "What this profile does",
  "version": "1.0.0",
  "steps": [
    {
      "step_id": "unique_step_id",
      "name": "Step Name",
      "description": "What this step does",
      "prompt_template": "Prompt with {transcript} and {previous_step} placeholders",
      "model_config": {
        "provider": "local|openrouter",
        "model": "model_name",
        "temperature": 0.2,
        "max_tokens": 1500
      },
      "output_format": "json|text",
      "pass_to_next": true,
      "required": true
    }
  ],
  "final_output_schema": {
    "type": "object",
    "properties": {...}
  },
  "tags": ["category", "use_case"],
  "use_cases": ["Description of when to use"],
  "estimated_tokens": 4500
}
```

### Prompt Template Variables

Available variables in prompt templates:
- `{transcript}`: Original input transcript
- `{step_id}`: Output from any previous step by step_id
- `{all_steps}`: Combined output from all previous steps

### Best Practices

1. **Step Design**
   - Keep steps focused on single tasks
   - Use local models for simple extraction
   - Use cloud models for complex reasoning
   - Make non-critical steps optional

2. **Prompt Engineering**
   - Be specific about output format
   - Include examples in prompts
   - Use clear instructions
   - Test with various input types

3. **Model Selection**
   - Local models: Entity extraction, simple classification
   - Cloud models: Complex reasoning, nuanced analysis
   - Consider token limits and costs

4. **Output Schema**
   - Define clear JSON schemas
   - Use consistent field names
   - Include metadata fields
   - Plan for downstream processing

## Error Handling

### Error Response Format

```json
{
  "job_id": "job-123",
  "status": "error",
  "error": {
    "code": "MODEL_UNAVAILABLE",
    "message": "Local model llama3.1:8b is not available",
    "details": {
      "provider": "local",
      "model": "llama3.1:8b",
      "step": "extract_entities"
    },
    "recoverable": true,
    "suggested_action": "Check Ollama service or use OpenRouter fallback"
  }
}
```

### Common Error Codes

- `PROFILE_NOT_FOUND`: Requested profile doesn't exist
- `MODEL_UNAVAILABLE`: Specified model is not accessible
- `INVALID_INPUT`: Input validation failed
- `PROCESSING_TIMEOUT`: Step processing exceeded timeout
- `API_RATE_LIMIT`: External API rate limit hit
- `INVALID_JSON`: LLM returned invalid JSON
- `STEP_DEPENDENCY_FAILED`: Required step failed

## Testing

### Unit Testing

```bash
# Run Grok adapter tests
cd adapters/grok-adapter
python -m pytest tests/

# Test specific profile
python -m pytest tests/test_profiles.py::test_business_meeting_profile

# Test model integration
python -m pytest tests/test_models.py
```

### Integration Testing

```bash
# Test with Jubal Core
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "test-123",
    "data": {
      "type": "text/plain",
      "content": "Test meeting transcript...",
      "encoding": "utf-8"
    },
    "metadata": {
      "profile_id": "business_meeting"
    }
  }'
```

### Profile Testing

```bash
# Test profile with sample data
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d @test_data/business_meeting_sample.json

# Validate profile schema
curl -X GET http://localhost:8002/profiles/business_meeting/validate
```

## Performance Considerations

### Token Management
- Monitor token usage across profiles
- Set appropriate max_tokens for each step
- Consider costs for cloud models
- Use local models for high-volume processing

### Concurrency
- Configure GROK_MAX_CONCURRENT_JOBS based on resources
- Local models share GPU/CPU resources
- Cloud models have API rate limits
- Balance throughput with resource constraints

### Caching
- Results cached by input hash
- Configurable TTL per profile
- Cache invalidation on profile updates
- Redis-based distributed caching

## Security Considerations

### API Security
- Validate all profile inputs
- Sanitize prompt templates
- Rate limiting per client
- Audit logging for sensitive data

### Model Security
- Local models run in containers
- OpenRouter API keys in environment
- No sensitive data in logs
- Secure prompt injection prevention

### Data Privacy
- Local processing for sensitive data
- Configurable data retention
- No persistent storage of transcripts
- GDPR compliance considerations

## Monitoring & Observability

### Metrics
- Processing latency per step
- Token usage by model/provider
- Error rates by profile
- Throughput metrics
- Resource utilization

### Logging
- Structured JSON logging
- Step-level trace information
- Error context and stack traces
- Performance timing data
- Model usage statistics

### Health Checks
- Service health endpoint
- Model availability checks
- Profile validation status
- External API connectivity

## Troubleshooting

### Common Issues

#### Local Model Not Available
```bash
# Check Ollama service
curl http://localhost:11434/api/tags

# Check model status
docker logs jubal-grok
```

#### OpenRouter API Issues
```bash
# Verify API key
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  https://openrouter.ai/api/v1/models

# Check adapter logs
docker logs jubal-grok | grep openrouter
```

#### Profile Errors
```bash
# Validate profile JSON
cd adapters/grok-adapter/profiles
python -m json.tool business_meeting.json

# Test profile independently
curl -X GET http://localhost:8002/profiles/business_meeting/validate
```

### Debug Mode

Enable debug logging:
```bash
export GROK_DEBUG=true
export GROK_LOG_LEVEL=DEBUG
```

### Service Registry Issues

```bash
# Check Redis connectivity
docker exec jubal-redis redis-cli ping

# Verify service registration
docker exec jubal-redis redis-cli HGET jubal:services grok-adapter
```

## Future Enhancements

- **Auto Profile Detection**: Analyze transcript to suggest best profile
- **Profile Versioning**: Multiple versions of profiles with A/B testing
- **Real-time Processing**: Stream processing for live transcripts
- **Custom Model Training**: Fine-tune models on user data
- **Visual Profile Builder**: GUI for creating profiles
- **Advanced Orchestration**: Conditional branching in profiles
- **Batch Processing**: Process multiple transcripts efficiently
- **Analytics Dashboard**: Usage statistics and insights

---

*This documentation is specific to the Grok adapter integration with Jubal. Update as features evolve.*