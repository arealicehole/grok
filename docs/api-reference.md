# Grok Intelligence Engine - API Reference

## Overview

The Grok Intelligence Engine provides a RESTful API for AI-powered transcript analysis. All endpoints follow the Jubal microservice contract format and return JSON responses.

**Base URL**: `http://localhost:8002` (development)

**API Version**: v1.0.0

## Authentication

Currently, the API operates without authentication in development mode. Production deployments will implement Jubal ecosystem authentication.

## Request/Response Format

### Content Type
All requests must include:
```
Content-Type: application/json
```

### Error Responses
All endpoints return errors in the standardized format:
```json
{
  "job_id": "request-identifier",
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "recoverable": true,
    "timestamp": "2025-09-15T22:41:55.057669+00:00"
  },
  "data": null,
  "metadata": {}
}
```

## Service Management Endpoints

### GET /health

Returns the current health status of the service.

**Response:**
```json
{
  "status": "healthy",
  "service": "grok-adapter",
  "version": "1.0.0",
  "timestamp": "2025-09-15T22:41:55.057669+00:00"
}
```

**Status Codes:**
- `200 OK`: Service is healthy
- `503 Service Unavailable`: Service is unhealthy

---

### GET /capabilities

Returns the service capabilities and supported operations according to Jubal specifications.

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

**Status Codes:**
- `200 OK`: Capabilities returned successfully

---

### GET /services

Lists all services registered in the Jubal service registry.

**Response:**
```json
{
  "grok-adapter": {
    "service": "grok-adapter",
    "version": "1.0.0",
    "host": "grok-adapter",
    "port": 8002,
    "health_endpoint": "/health",
    "capabilities": ["analyze", "extract", "summarize"]
  }
}
```

**Status Codes:**
- `200 OK`: Services listed successfully
- `503 Service Unavailable`: Service registry unavailable

## Profile Management Endpoints

### GET /profiles

Lists all available processing profiles with basic information.

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
    },
    {
      "profile_id": "personal_notes",
      "name": "Personal Notes Analysis",
      "description": "Process personal notes and ideas for organization",
      "steps": 3,
      "estimated_tokens": 3000,
      "tags": ["personal", "notes", "ideas"]
    }
  ]
}
```

**Status Codes:**
- `200 OK`: Profiles listed successfully

---

### GET /profiles/{profile_id}

Returns detailed information about a specific processing profile.

**Parameters:**
- `profile_id` (string, required): The unique identifier of the profile

**Example Request:**
```bash
GET /profiles/business_meeting
```

**Response:**
```json
{
  "profile_id": "business_meeting",
  "name": "Business Meeting Analysis",
  "description": "Extract entities, decisions, and action items from business meetings",
  "steps": 3,
  "estimated_tokens": 4500,
  "tags": ["business", "meetings", "decisions"]
}
```

**Status Codes:**
- `200 OK`: Profile details returned successfully
- `404 Not Found`: Profile does not exist

## Processing Endpoints

### POST /process

Processes a transcript using the specified profile and returns structured analysis results.

**Request Body:**
The request must follow the Jubal envelope format:

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
    "overrides": {
      "force_provider": "local",
      "force_model": "llama3.1:8b",
      "step_overrides": {
        "extract_entities": {
          "temperature": 0.1
        }
      }
    }
  },
  "trace": {}
}
```

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `job_id` | string | Yes | Unique identifier for this processing job |
| `pipeline_id` | string | No | Optional pipeline identifier for tracking |
| `data.type` | string | Yes | Must be "text/plain" |
| `data.content` | string | Yes | The transcript text to process |
| `data.encoding` | string | Yes | Content encoding (typically "utf-8") |
| `metadata.profile_id` | string | No | Profile to use (default: "business_meeting") |
| `metadata.overrides` | object | No | Runtime configuration overrides |
| `trace` | object | No | Tracing information for debugging |

**Response:**
```json
{
  "job_id": "unique-job-identifier",
  "status": "completed",
  "data": {
    "type": "application/json",
    "content": {
      "entities": {
        "people": ["John Doe", "Jane Smith"],
        "companies": ["Acme Corp"],
        "dates": ["2025-09-15"],
        "locations": ["Conference Room A"]
      },
      "summary": {
        "key_points": ["Sample analysis of transcript"],
        "action_items": [
          {
            "task": "Placeholder action item",
            "assignee": "TBD",
            "due_date": "2025-09-20"
          }
        ],
        "sentiment": "neutral"
      },
      "processing_metadata": {
        "profile_used": "business_meeting",
        "steps_completed": 3,
        "total_tokens": 150,
        "processing_time_ms": 500
      }
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

**Status Codes:**
- `200 OK`: Processing completed successfully
- `400 Bad Request`: Invalid request format or missing required fields
- `404 Not Found`: Specified profile does not exist
- `500 Internal Server Error`: Processing failed due to internal error

**Error Response Example:**
```json
{
  "job_id": "unique-job-identifier",
  "status": "error",
  "data": null,
  "error": {
    "code": "PROFILE_NOT_FOUND",
    "message": "Profile 'invalid_profile' not found",
    "recoverable": true,
    "timestamp": "2025-09-15T22:41:55.057669+00:00"
  },
  "metadata": {}
}
```

## Global Overrides

The processing endpoint supports global overrides to control model selection and parameters at runtime:

### Provider Overrides
```json
{
  "metadata": {
    "overrides": {
      "force_provider": "local",        // Use only local provider
      "force_model": "llama3.1:8b"      // Use specific model
    }
  }
}
```

### Parameter Overrides
```json
{
  "metadata": {
    "overrides": {
      "global_temperature": 0.5,        // Override temperature for all steps
      "global_max_tokens": 1000         // Override max tokens for all steps
    }
  }
}
```

### Step-Specific Overrides
```json
{
  "metadata": {
    "overrides": {
      "step_overrides": {
        "extract_entities": {
          "provider": "openrouter",
          "model": "openai/gpt-4o-mini",
          "temperature": 0.1
        },
        "analyze_decisions": {
          "temperature": 0.3,
          "max_tokens": 2000
        }
      }
    }
  }
}
```

## Example Usage

### Complete Processing Example

```bash
# Process a business meeting transcript
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "meeting-001",
    "data": {
      "type": "text/plain",
      "content": "John: Welcome to our weekly standup. Jane: Thanks John. I completed the API documentation and started working on the authentication module. John: Great progress! What'\''s next on your roadmap? Jane: I plan to finish authentication by Friday and then move on to the user management features.",
      "encoding": "utf-8"
    },
    "metadata": {
      "profile_id": "business_meeting"
    }
  }'
```

### Using Overrides Example

```bash
# Process with local model override
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "meeting-002",
    "data": {
      "type": "text/plain",
      "content": "Project planning session transcript here...",
      "encoding": "utf-8"
    },
    "metadata": {
      "profile_id": "project_planning",
      "overrides": {
        "force_provider": "local",
        "force_model": "llama3.1:8b",
        "global_temperature": 0.2
      }
    }
  }'
```

## Rate Limits

Current development deployment has no rate limits. Production deployments will implement:

- **Requests per minute**: 60 per IP
- **Concurrent processing jobs**: 5 per service instance
- **Maximum transcript length**: 50,000 characters

## SDK Examples

### Python SDK Example

```python
import requests
import json

class GrokClient:
    def __init__(self, base_url="http://localhost:8002"):
        self.base_url = base_url
    
    def process_transcript(self, transcript: str, profile_id: str = "business_meeting", 
                          job_id: str = None, overrides: dict = None):
        """Process a transcript with the specified profile."""
        
        if not job_id:
            import uuid
            job_id = str(uuid.uuid4())
        
        payload = {
            "job_id": job_id,
            "data": {
                "type": "text/plain",
                "content": transcript,
                "encoding": "utf-8"
            },
            "metadata": {
                "profile_id": profile_id
            }
        }
        
        if overrides:
            payload["metadata"]["overrides"] = overrides
        
        response = requests.post(
            f"{self.base_url}/process",
            headers={"Content-Type": "application/json"},
            json=payload
        )
        
        return response.json()
    
    def list_profiles(self):
        """Get available processing profiles."""
        response = requests.get(f"{self.base_url}/profiles")
        return response.json()
    
    def health_check(self):
        """Check service health."""
        response = requests.get(f"{self.base_url}/health")
        return response.json()

# Usage example
client = GrokClient()

# Check health
health = client.health_check()
print(f"Service status: {health['status']}")

# List profiles
profiles = client.list_profiles()
print(f"Available profiles: {[p['profile_id'] for p in profiles['profiles']]}")

# Process transcript
result = client.process_transcript(
    transcript="John: Let's discuss the quarterly results. Jane: Revenue is up 15% from last quarter.",
    profile_id="business_meeting",
    overrides={"force_provider": "local"}
)

if result["status"] == "completed":
    entities = result["data"]["content"]["entities"]
    print(f"Extracted people: {entities['people']}")
else:
    print(f"Processing failed: {result['error']['message']}")
```

### JavaScript SDK Example

```javascript
class GrokClient {
    constructor(baseUrl = 'http://localhost:8002') {
        this.baseUrl = baseUrl;
    }
    
    async processTranscript(transcript, profileId = 'business_meeting', options = {}) {
        const jobId = options.jobId || this.generateJobId();
        
        const payload = {
            job_id: jobId,
            data: {
                type: 'text/plain',
                content: transcript,
                encoding: 'utf-8'
            },
            metadata: {
                profile_id: profileId
            }
        };
        
        if (options.overrides) {
            payload.metadata.overrides = options.overrides;
        }
        
        const response = await fetch(`${this.baseUrl}/process`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        return await response.json();
    }
    
    async listProfiles() {
        const response = await fetch(`${this.baseUrl}/profiles`);
        return await response.json();
    }
    
    async healthCheck() {
        const response = await fetch(`${this.baseUrl}/health`);
        return await response.json();
    }
    
    generateJobId() {
        return 'job-' + Math.random().toString(36).substr(2, 9);
    }
}

// Usage example
const client = new GrokClient();

// Process transcript
client.processTranscript(
    "Team meeting about project milestones and delivery dates",
    "project_planning"
).then(result => {
    if (result.status === 'completed') {
        console.log('Processing completed:', result.data.content);
    } else {
        console.error('Processing failed:', result.error.message);
    }
});
```

## Webhooks (Future)

Future versions will support webhook notifications for long-running processing jobs:

```json
{
  "webhook_url": "https://your-app.com/grok-webhook",
  "events": ["processing.completed", "processing.failed"],
  "secret": "webhook-secret-for-verification"
}
```

## Changelog

### v1.0.0 (2025-09-15)
- Initial API release
- Basic processing endpoints
- Jubal service contract compliance
- Profile-based processing
- Global override system
- Placeholder processing implementation

### Future Versions
- v1.1.0: LLM provider integration (Ollama, OpenRouter)
- v1.2.0: Real multi-step profile processing
- v1.3.0: Custom profile creation API
- v2.0.0: Authentication and rate limiting