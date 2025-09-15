"""Enhanced profile processing with LLM integration."""

import asyncio
import json
import time
import logging
from typing import Dict, Any, Optional, List
from app.models.profile import ProcessingProfile, ProcessingStep, ModelConfig
from app.providers import ModelSelector, OllamaProvider, OpenRouterProvider, LLMProviderError
from app.config import settings
from .profile_loader import get_profile_manager, ProfileLoadError
from .executor import ProfileExecutor


logger = logging.getLogger(__name__)


class IntelligenceEngine:
    """Enhanced profile processor with LLM integration."""

    def __init__(self):
        # Initialize providers
        self.providers = {}
        self.model_selector: Optional[ModelSelector] = None
        self.profile_executor: Optional[ProfileExecutor] = None
        self._initialize_providers()
        
        # Initialize profile manager
        self.profile_manager = get_profile_manager()

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
            
            # Create profile executor
            self.profile_executor = ProfileExecutor(self.model_selector)
            
            logger.info(f"Initialized {len(self.providers)} LLM providers: {list(self.providers.keys())}")
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM providers: {e}")
            # Continue with placeholder functionality
            self.providers = {}
            self.model_selector = None
            self.profile_executor = None

    async def get_available_profiles(self) -> Dict[str, Any]:
        """Get list of available processing profiles."""
        profiles = self.profile_manager.list_available_profiles()
        return {"profiles": profiles}

    async def get_profile_details(self, profile_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific profile."""
        profile_details = self.profile_manager.get_profile_details(profile_id)
        if not profile_details:
            raise ValueError(f"Profile {profile_id} not found")
        
        return profile_details

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
        
        # Load the profile
        profile = self.profile_manager.load_profile(profile_id)
        if not profile:
            raise ValueError(f"Profile {profile_id} not found")

        start_time = time.time()
        
        # Check if LLM processing is available
        if not self.profile_executor:
            logger.warning("LLM providers not available, using placeholder processing")
            return await self._placeholder_processing(transcript, profile_id)

        try:
            # Use the new profile executor for full multi-step processing
            result = await self.profile_executor.execute_profile(
                profile=profile,
                transcript=transcript,
                global_overrides=overrides
            )
            
            # Convert ProfileResult to expected format
            return self._format_profile_result(result)

        except Exception as e:
            logger.error(f"Profile execution failed, falling back to placeholder: {e}")
            return await self._placeholder_processing(transcript, profile_id)
    
    def _format_profile_result(self, result) -> Dict[str, Any]:
        """Format ProfileResult to match expected API response format."""
        if not result.success:
            raise ValueError(f"Profile execution failed: {result.error}")
        
        # Extract step outputs for backward compatibility
        entities = {}
        summary = {}
        
        # Try to extract common data from step outputs
        final_output = result.final_output
        
        # Look for common step patterns
        if "extract_entities" in final_output:
            entities = final_output["extract_entities"]
        if "analyze_decisions" in final_output:
            decisions_data = final_output["analyze_decisions"]
            if isinstance(decisions_data, dict):
                summary.update(decisions_data)
        
        # Fallback: use all step outputs as-is
        if not entities and not summary:
            # Just include all outputs
            for step_id, output in final_output.items():
                if step_id != "_metadata" and output:
                    if "entities" in str(step_id).lower():
                        entities.update(output if isinstance(output, dict) else {})
                    else:
                        summary[step_id] = output
        
        # Ensure basic structure exists
        if not entities:
            entities = {"people": [], "companies": [], "dates": [], "locations": []}
        if not summary:
            summary = {"key_points": [], "action_items": [], "sentiment": "neutral"}
        
        return {
            "entities": entities,
            "summary": summary,
            "processing_metadata": final_output.get("_metadata", {
                "profile_used": result.profile_id,
                "steps_completed": result.successful_steps,
                "total_tokens": result.total_tokens_used,
                "processing_time_ms": result.total_execution_time_ms
            }),
            "raw_step_outputs": {k: v for k, v in final_output.items() if k != "_metadata"}
        }

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