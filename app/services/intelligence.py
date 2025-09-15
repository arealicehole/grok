"""Enhanced profile processing with LLM integration."""

import asyncio
import json
import time
import logging
from typing import Dict, Any, Optional, List
from app.models.profile import ProcessingProfile, ProcessingStep, ModelConfig
from app.providers import ModelSelector, OllamaProvider, OpenRouterProvider, LLMProviderError
from app.config import settings


logger = logging.getLogger(__name__)


class IntelligenceEngine:
    """Enhanced profile processor with LLM integration."""

    def __init__(self):
        # Initialize providers
        self.providers = {}
        self.model_selector: Optional[ModelSelector] = None
        self._initialize_providers()

        # Built-in profiles (will be loaded from files in future)
        self.available_profiles = {
            "business_meeting": {
                "profile_id": "business_meeting",
                "name": "Business Meeting Analysis",
                "description": "Extract entities, decisions, and action items from business meetings",
                "steps": 3,
                "estimated_tokens": 4500,
                "tags": ["business", "meetings", "decisions"]
            },
            "project_planning": {
                "profile_id": "project_planning",
                "name": "Project Planning Session",
                "description": "Analyze project planning discussions for requirements, timelines, and risks",
                "steps": 4,
                "estimated_tokens": 5200,
                "tags": ["project", "planning", "requirements"]
            },
            "personal_notes": {
                "profile_id": "personal_notes",
                "name": "Personal Notes Analysis",
                "description": "Process personal notes and ideas for organization",
                "steps": 3,
                "estimated_tokens": 3000,
                "tags": ["personal", "notes", "ideas"]
            }
        }

    def _initialize_providers(self):
        """Initialize LLM providers based on configuration."""
        try:
            # Initialize Ollama provider
            ollama_provider = OllamaProvider(settings.ollama_url)
            self.providers["local"] = ollama_provider
            
            # Initialize OpenRouter provider if API key is available
            if settings.openrouter_api_key:
                openrouter_provider = OpenRouterProvider(
                    api_key=settings.openrouter_api_key,
                    base_url=settings.openrouter_url,
                    app_name=settings.openrouter_app_name,
                    app_url=settings.openrouter_app_url
                )
                self.providers["openrouter"] = openrouter_provider

            # Create model selector
            self.model_selector = ModelSelector(self.providers)
            
            logger.info(f"Initialized {len(self.providers)} LLM providers: {list(self.providers.keys())}")
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM providers: {e}")
            # Continue with placeholder functionality
            self.providers = {}
            self.model_selector = None

    async def get_available_profiles(self) -> Dict[str, Any]:
        """Get list of available processing profiles."""
        return {"profiles": list(self.available_profiles.values())}

    async def get_profile_details(self, profile_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific profile."""
        if profile_id not in self.available_profiles:
            raise ValueError(f"Profile {profile_id} not found")
        
        return self.available_profiles[profile_id]

    async def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all LLM providers."""
        if not self.model_selector:
            return {"providers": {}, "available": False}

        try:
            status = await self.model_selector.get_provider_status()
            return {
                "providers": status,
                "available": any(p.get("available", False) for p in status.values())
            }
        except Exception as e:
            logger.error(f"Error getting provider status: {e}")
            return {"providers": {}, "available": False, "error": str(e)}

    async def process_transcript(
        self, 
        transcript: str, 
        profile_id: str = "business_meeting",
        overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process transcript with specified profile."""
        
        if profile_id not in self.available_profiles:
            raise ValueError(f"Profile {profile_id} not found")

        start_time = time.time()
        
        # Check if LLM processing is available
        if not self.model_selector:
            logger.warning("LLM providers not available, using placeholder processing")
            return await self._placeholder_processing(transcript, profile_id)

        try:
            # For now, use a simple demo processing
            # In Phase 3.2, this will be replaced with full profile execution
            result = await self._demo_llm_processing(transcript, profile_id, overrides)
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            result["processing_metadata"]["processing_time_ms"] = processing_time_ms
            
            return result

        except Exception as e:
            logger.error(f"LLM processing failed, falling back to placeholder: {e}")
            return await self._placeholder_processing(transcript, profile_id)

    async def _demo_llm_processing(
        self, 
        transcript: str, 
        profile_id: str,
        overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Demo LLM processing - simple entity extraction."""
        
        # Configure model based on provider
        if overrides and overrides.get("force_provider") == "openrouter":
            # Use OpenRouter configuration
            config = ModelConfig(
                provider="openrouter",
                model=overrides.get("force_model", settings.default_openrouter_model),
            temperature=settings.default_temperature,
            max_tokens=min(1000, settings.default_max_tokens)  # Conservative for demo
        )
        else:
            # Use local provider configuration
            config = ModelConfig(
                provider=settings.default_model_provider,
                model=settings.default_local_model,
                temperature=settings.default_temperature,
                max_tokens=min(1000, settings.default_max_tokens)  # Conservative for demo
            )

        # Simple entity extraction prompt
        prompt = f"""Extract key information from this meeting transcript:

{transcript}

Please return a JSON object with:
- people: list of person names mentioned
- companies: list of company/organization names  
- dates: list of dates mentioned
- key_points: list of main discussion topics (max 3)

Return only valid JSON, no other text."""

        try:
            # Generate completion
            response = await self.model_selector.generate_completion(
                prompt=prompt,
                config=config,
                global_overrides=overrides
            )

            # Try to parse JSON response
            try:
                parsed_content = json.loads(response.content)
            except json.JSONDecodeError:
                # Fallback to structured data
                parsed_content = {
                    "people": ["[LLM Response]"],
                    "companies": ["[Analysis Available]"],
                    "dates": [],
                    "key_points": [response.content[:100] + "..." if len(response.content) > 100 else response.content]
                }

            return {
                "entities": {
                    "people": parsed_content.get("people", []),
                    "companies": parsed_content.get("companies", []),
                    "dates": parsed_content.get("dates", []),
                    "locations": []  # Not extracted in demo
                },
                "summary": {
                    "key_points": parsed_content.get("key_points", []),
                    "action_items": [],  # Not extracted in demo
                    "sentiment": "neutral"
                },
                "processing_metadata": {
                    "profile_used": profile_id,
                    "steps_completed": 1,
                    "total_tokens": response.tokens_used,
                    "provider_used": response.provider,
                    "model_used": response.model,
                    "llm_processing_time_ms": response.processing_time_ms
                },
                "raw_llm_response": response.content  # For debugging
            }

        except LLMProviderError as e:
            logger.error(f"LLM provider error: {e}")
            # Fallback to placeholder
            raise e

    async def _placeholder_processing(
        self, 
        transcript: str, 
        profile_id: str
    ) -> Dict[str, Any]:
        """Fallback placeholder processing when LLM is unavailable."""
        
        # Simulate processing delay
        await asyncio.sleep(0.1)
        
        return {
            "entities": {
                "people": ["[Placeholder]", "[Analysis]"],
                "companies": ["[Demo Corp]"],
                "dates": ["2025-09-15"],
                "locations": ["[Meeting Room]"]
            },
            "summary": {
                "key_points": [
                    "Placeholder analysis - LLM providers not available",
                    f"Transcript length: {len(transcript)} characters",
                    "Real processing requires Ollama or OpenRouter"
                ],
                "action_items": [
                    {
                        "task": "Set up local Ollama instance for real processing",
                        "assignee": "DevOps",
                        "due_date": "Next deployment"
                    }
                ],
                "sentiment": "neutral"
            },
            "processing_metadata": {
                "profile_used": profile_id,
                "steps_completed": 1,
                "total_tokens": 0,
                "provider_used": "placeholder",
                "model_used": "none",
                "note": "LLM providers not available"
            }
        }

    async def close(self):
        """Close all provider connections."""
        if self.model_selector:
            await self.model_selector.close_all()