"""Main FastAPI application for Grok Intelligence Engine."""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.models.jubal import JubalEnvelope, JubalResponse
from app.services.registry import ServiceRegistry
from app.services.intelligence import IntelligenceEngine
from app.config import settings

# Global service instances
service_registry = ServiceRegistry()
intelligence_engine = IntelligenceEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    print("Starting Grok Intelligence Engine...")
    
    # Connect to service registry
    connected = await service_registry.connect()
    if connected:
        print("Connected to Jubal service registry")
    else:
        print("Warning: Failed to connect to service registry")
    
    yield
    
    # Shutdown
    print("Shutting down Grok Intelligence Engine...")
    await intelligence_engine.close()
    await service_registry.disconnect()


# FastAPI application setup
app = FastAPI(
    title="Grok Intelligence Engine",
    description="AI-powered transcript analysis microservice for the Jubal ecosystem",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Jubal-required health check endpoint."""
    return {
        "status": "healthy",
        "service": "grok-adapter",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/capabilities")
async def get_capabilities():
    """Jubal-required capabilities declaration."""
    return {
        "service": "grok-adapter",
        "version": "1.0.0",
        "accepts": ["text/plain"],
        "provides": ["application/json"],
        "operations": ["analyze", "extract", "summarize"],
        "features": {
            "multi_step_processing": True,
            "profile_based_analysis": True,
            "model_selection": True,
            "global_overrides": True
        },
        "supported_providers": ["local", "openrouter"],
        "available_profiles": ["business_meeting", "project_planning", "personal_notes"]
    }


@app.post("/process", response_model=JubalResponse)
async def process_transcript(envelope: JubalEnvelope):
    """Main processing endpoint following Jubal contract."""
    
    try:
        # Validate input
        if envelope.data.get("type") != "text/plain":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only text/plain content type supported"
            )

        transcript = envelope.data.get("content", "")
        if not transcript.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty transcript content"
            )

        # Get profile and overrides
        profile_id = envelope.metadata.get("profile_id", "business_meeting")
        overrides = envelope.metadata.get("overrides", {})

        # Process transcript
        result = await intelligence_engine.process_transcript(
            transcript=transcript,
            profile_id=profile_id,
            overrides=overrides
        )

        # Return success response
        return JubalResponse.success(
            job_id=envelope.job_id,
            data={
                "type": "application/json",
                "content": result,
                "encoding": "utf-8"
            },
            metadata={
                **envelope.metadata,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

    except ValueError as e:
        return JubalResponse.create_error(
            job_id=envelope.job_id,
            error_code="PROFILE_NOT_FOUND",
            error_message=str(e)
        )
    except Exception as e:
        return JubalResponse.create_error(
            job_id=envelope.job_id,
            error_code="INTERNAL_ERROR", 
            error_message="Internal processing error",
            recoverable=False
        )


@app.get("/profiles")
async def list_profiles():
    """List available processing profiles."""
    return await intelligence_engine.get_available_profiles()


@app.get("/profiles/{profile_id}")
async def get_profile_details(profile_id: str):
    """Get details for a specific profile."""
    try:
        return await intelligence_engine.get_profile_details(profile_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@app.get("/providers/status")
async def get_provider_status():
    """Get status of all LLM providers."""
    return await intelligence_engine.get_provider_status()

@app.get("/services")
async def list_services():
    """List all registered Jubal services."""
    return await service_registry.get_services()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.service_port)