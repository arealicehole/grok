"""Profile loading and file management system."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
import logging

from ..models.profile import ProcessingProfile, ProfileMetadata
from pydantic import ValidationError


logger = logging.getLogger(__name__)


class ProfileLoadError(Exception):
    """Error loading or parsing profile."""
    pass


class ProfileManager:
    """Manages loading, saving, and caching of processing profiles."""
    
    def __init__(self, profiles_dir: str = "./profiles"):
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(exist_ok=True)
        
        # In-memory cache of loaded profiles
        self._profile_cache: Dict[str, ProcessingProfile] = {}
        self._last_loaded: Dict[str, float] = {}
        
        self.logger = logging.getLogger(f"{__name__}.ProfileManager")
        
        # Load built-in profiles on init
        self._load_builtin_profiles()
    
    def _load_builtin_profiles(self):
        """Load built-in profiles from memory."""
        
        # Business Meeting Profile
        business_meeting = {
            "profile_id": "business_meeting",
            "name": "Business Meeting Analysis",
            "description": "Extract entities, decisions, and action items from business meetings",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "extract_entities",
                    "name": "Extract Key Entities",
                    "description": "Identify people, companies, dates, and locations mentioned",
                    "prompt_template": """Extract key entities from this meeting transcript:

{transcript}

Return JSON with:
- people: list of person names mentioned
- companies: list of company/organization names  
- dates: list of dates mentioned
- locations: list of locations mentioned

Format your response as valid JSON only.""",
                    "llm_config": {
                        "provider": "local",
                        "model": "llama3.1:8b",
                        "temperature": 0.1,
                        "max_tokens": 1000
                    },
                    "output_format": "json",
                    "output_schema": {
                        "type": "object",
                        "required_fields": ["people", "companies", "dates", "locations"]
                    }
                },
                {
                    "step_id": "analyze_decisions",
                    "name": "Analyze Decisions Made",
                    "description": "Identify decisions made and action items assigned",
                    "prompt_template": """Based on this transcript and the entities extracted, analyze the decisions made:

Transcript: {transcript}
Entities: {extract_entities}

Identify decisions made in the meeting. Return JSON with:
- decisions: list of decisions with responsible person and deadline
- action_items: concrete next steps identified
- key_topics: main topics discussed

Format your response as valid JSON only.""",
                    "llm_config": {
                        "provider": "local", 
                        "model": "llama3.1:8b",
                        "temperature": 0.2,
                        "max_tokens": 1500
                    },
                    "output_format": "json",
                    "output_schema": {
                        "type": "object",
                        "required_fields": ["decisions", "action_items", "key_topics"]
                    },
                    "dependencies": ["extract_entities"]
                }
            ],
            "tags": ["business", "meetings", "decisions"],
            "use_cases": ["Team meetings", "Project planning", "Client calls"],
            "estimated_tokens": 4000,
            "metadata": {
                "author": "Grok Intelligence Engine",
                "source": "builtin",
                "created_at": "2025-09-15T23:30:00Z"
            }
        }
        
        # Project Planning Profile
        project_planning = {
            "profile_id": "project_planning",
            "name": "Project Planning Session",
            "description": "Analyze project planning discussions for requirements, timelines, and risks",
            "version": "1.0.0",
            "steps": [
                {
                    "step_id": "extract_requirements",
                    "name": "Extract Requirements",
                    "description": "Identify project requirements and specifications",
                    "prompt_template": """Extract project requirements from this planning session:

{transcript}

Return JSON with:
- functional_requirements: list of functional requirements
- non_functional_requirements: list of performance/quality requirements
- constraints: list of constraints and limitations
- stakeholders: list of stakeholders mentioned

Format your response as valid JSON only.""",
                    "llm_config": {
                        "provider": "local",
                        "model": "llama3.1:8b",
                        "temperature": 0.1,
                        "max_tokens": 1500
                    },
                    "output_format": "json",
                    "output_schema": {
                        "type": "object",
                        "required_fields": ["functional_requirements", "non_functional_requirements", "constraints", "stakeholders"]
                    }
                },
                {
                    "step_id": "analyze_timeline",
                    "name": "Analyze Timeline",
                    "description": "Extract timeline information and milestones",
                    "prompt_template": """Based on the requirements and transcript, analyze the project timeline:

Transcript: {transcript}
Requirements: {extract_requirements}

Extract timeline information. Return JSON with:
- milestones: list of key milestones with dates
- phases: project phases identified
- deadlines: important deadlines mentioned
- dependencies: task dependencies identified

Format your response as valid JSON only.""",
                    "llm_config": {
                        "provider": "local",
                        "model": "llama3.1:8b", 
                        "temperature": 0.2,
                        "max_tokens": 1500
                    },
                    "output_format": "json",
                    "output_schema": {
                        "type": "object",
                        "required_fields": ["milestones", "phases", "deadlines", "dependencies"]
                    },
                    "dependencies": ["extract_requirements"]
                },
                {
                    "step_id": "assess_risks",
                    "name": "Risk Assessment",
                    "description": "Identify project risks and mitigation strategies",
                    "prompt_template": """Analyze risks for this project based on the discussion:

Transcript: {transcript}
Requirements: {extract_requirements}
Timeline: {analyze_timeline}

Identify risks and mitigation strategies. Return JSON with:
- risks: list of identified risks with severity
- mitigation_strategies: proposed risk mitigation approaches
- assumptions: key assumptions made
- success_factors: critical success factors

Format your response as valid JSON only.""",
                    "llm_config": {
                        "provider": "openrouter",
                        "model": "openai/gpt-4o-mini",
                        "temperature": 0.3,
                        "max_tokens": 2000
                    },
                    "output_format": "json",
                    "output_schema": {
                        "type": "object", 
                        "required_fields": ["risks", "mitigation_strategies", "assumptions", "success_factors"]
                    },
                    "dependencies": ["extract_requirements", "analyze_timeline"]
                }
            ],
            "tags": ["project", "planning", "requirements", "risk"],
            "use_cases": ["Project kickoffs", "Planning sessions", "Requirement reviews"],
            "estimated_tokens": 6000,
            "metadata": {
                "author": "Grok Intelligence Engine",
                "source": "builtin",
                "created_at": "2025-09-15T23:30:00Z"
            }
        }
        
        # Personal Notes Profile
        personal_notes = {
            "profile_id": "personal_notes",
            "name": "Personal Notes Analysis",
            "description": "Process personal notes and ideas for organization",
            "version": "1.0.0", 
            "steps": [
                {
                    "step_id": "extract_ideas",
                    "name": "Extract Ideas",
                    "description": "Identify main ideas and concepts",
                    "prompt_template": """Analyze these personal notes and extract key ideas:

{transcript}

Return JSON with:
- main_ideas: list of key ideas and concepts
- insights: important insights or realizations
- questions: questions raised or topics to explore
- connections: connections to other topics or ideas

Format your response as valid JSON only.""",
                    "llm_config": {
                        "provider": "local",
                        "model": "llama3.1:8b",
                        "temperature": 0.3,
                        "max_tokens": 1200
                    },
                    "output_format": "json",
                    "output_schema": {
                        "type": "object",
                        "required_fields": ["main_ideas", "insights", "questions", "connections"]
                    }
                },
                {
                    "step_id": "organize_content",
                    "name": "Organize Content",
                    "description": "Organize and categorize the content",
                    "prompt_template": """Based on the ideas extracted, organize and categorize this content:

Original notes: {transcript}
Extracted ideas: {extract_ideas}

Organize the content. Return JSON with:
- categories: content organized by category
- action_items: actionable tasks identified
- topics: main topics covered
- priority: high/medium/low priority items

Format your response as valid JSON only.""",
                    "llm_config": {
                        "provider": "local",
                        "model": "llama3.1:8b",
                        "temperature": 0.2,
                        "max_tokens": 1500
                    },
                    "output_format": "json",
                    "output_schema": {
                        "type": "object",
                        "required_fields": ["categories", "action_items", "topics", "priority"]
                    },
                    "dependencies": ["extract_ideas"]
                }
            ],
            "tags": ["personal", "notes", "ideas", "organization"],
            "use_cases": ["Personal brainstorming", "Note organization", "Idea development"],
            "estimated_tokens": 3500,
            "metadata": {
                "author": "Grok Intelligence Engine", 
                "source": "builtin",
                "created_at": "2025-09-15T23:30:00Z"
            }
        }
        
        # Load built-in profiles into cache
        for profile_data in [business_meeting, project_planning, personal_notes]:
            try:
                profile = ProcessingProfile(**profile_data)
                self._profile_cache[profile.profile_id] = profile
                self.logger.info(f"Loaded built-in profile: {profile.profile_id}")
            except ValidationError as e:
                self.logger.error(f"Failed to load built-in profile {profile_data.get('profile_id')}: {e}")
    
    def load_profile(self, profile_id: str, force_reload: bool = False) -> Optional[ProcessingProfile]:
        """
        Load a profile by ID from cache or file.
        
        Args:
            profile_id: Profile identifier
            force_reload: Force reload from file even if cached
            
        Returns:
            ProcessingProfile if found, None otherwise
        """
        
        # Check cache first (unless force reload)
        if not force_reload and profile_id in self._profile_cache:
            return self._profile_cache[profile_id]
        
        # Try to load from file
        profile_file = self.profiles_dir / f"{profile_id}.json"
        
        if not profile_file.exists():
            self.logger.warning(f"Profile file not found: {profile_file}")
            return self._profile_cache.get(profile_id)  # Return cached version if available
        
        try:
            with open(profile_file, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
            
            # Add file metadata
            stat = profile_file.stat()
            if "metadata" not in profile_data:
                profile_data["metadata"] = {}
            
            profile_data["metadata"]["source"] = "file"
            profile_data["metadata"]["updated_at"] = datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat()
            
            profile = ProcessingProfile(**profile_data)
            
            # Cache the loaded profile
            self._profile_cache[profile_id] = profile
            self._last_loaded[profile_id] = stat.st_mtime
            
            self.logger.info(f"Loaded profile from file: {profile_id}")
            return profile
            
        except (json.JSONDecodeError, ValidationError) as e:
            raise ProfileLoadError(f"Failed to load profile {profile_id}: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error loading profile {profile_id}: {e}")
            return None
    
    def save_profile(self, profile: ProcessingProfile, overwrite: bool = False) -> bool:
        """
        Save a profile to file.
        
        Args:
            profile: Profile to save
            overwrite: Allow overwriting existing files
            
        Returns:
            True if saved successfully
        """
        profile_file = self.profiles_dir / f"{profile.profile_id}.json"
        
        if profile_file.exists() and not overwrite:
            raise ProfileLoadError(f"Profile file already exists: {profile_file}")
        
        try:
            # Update metadata
            profile.metadata.updated_at = datetime.now(timezone.utc).isoformat()
            profile.metadata.source = "user"
            
            # Save to file
            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(profile.model_dump(), f, indent=2, ensure_ascii=False)
            
            # Update cache
            self._profile_cache[profile.profile_id] = profile
            self._last_loaded[profile.profile_id] = profile_file.stat().st_mtime
            
            self.logger.info(f"Saved profile to file: {profile.profile_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save profile {profile.profile_id}: {e}")
            return False
    
    def list_available_profiles(self) -> List[Dict[str, Any]]:
        """
        List all available profiles with basic info.
        
        Returns:
            List of profile summaries
        """
        profiles = []
        
        # Add cached profiles
        for profile in self._profile_cache.values():
            profiles.append({
                "profile_id": profile.profile_id,
                "name": profile.name,
                "description": profile.description,
                "version": profile.version,
                "steps": len(profile.steps),
                "tags": profile.tags,
                "estimated_tokens": profile.estimated_tokens,
                "source": profile.metadata.source,
                "created_at": profile.metadata.created_at,
                "updated_at": profile.metadata.updated_at
            })
        
        # Scan for additional profile files
        for profile_file in self.profiles_dir.glob("*.json"):
            profile_id = profile_file.stem
            
            if profile_id not in self._profile_cache:
                # Try to load basic info without full validation
                try:
                    with open(profile_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    profiles.append({
                        "profile_id": profile_id,
                        "name": data.get("name", profile_id),
                        "description": data.get("description", ""),
                        "version": data.get("version", "unknown"),
                        "steps": len(data.get("steps", [])),
                        "tags": data.get("tags", []),
                        "estimated_tokens": data.get("estimated_tokens", 0),
                        "source": "file",
                        "created_at": None,
                        "updated_at": datetime.fromtimestamp(
                            profile_file.stat().st_mtime, tz=timezone.utc
                        ).isoformat()
                    })
                except Exception as e:
                    self.logger.warning(f"Could not read profile metadata for {profile_file}: {e}")
        
        return sorted(profiles, key=lambda x: x["profile_id"])
    
    def get_profile_details(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific profile.
        
        Args:
            profile_id: Profile identifier
            
        Returns:
            Detailed profile information or None if not found
        """
        profile = self.load_profile(profile_id)
        if not profile:
            return None
        
        return {
            "profile_id": profile.profile_id,
            "name": profile.name,
            "description": profile.description,
            "version": profile.version,
            "steps": [
                {
                    "step_id": step.step_id,
                    "name": step.name,
                    "description": step.description,
                    "output_format": step.output_format,
                    "required": step.required,
                    "dependencies": step.dependencies,
                    "model_config": {
                        "provider": step.llm_config.provider,
                        "model": step.llm_config.model,
                        "temperature": step.llm_config.temperature
                    }
                }
                for step in profile.steps
            ],
            "tags": profile.tags,
            "use_cases": profile.use_cases,
            "estimated_tokens": profile.estimated_tokens,
            "metadata": profile.metadata.model_dump(),
            "execution_order": profile.get_execution_order(),
            "validation_issues": profile.validate_interpolation_variables()
        }
    
    def delete_profile(self, profile_id: str) -> bool:
        """
        Delete a profile from file and cache.
        
        Args:
            profile_id: Profile to delete
            
        Returns:
            True if deleted successfully
        """
        profile_file = self.profiles_dir / f"{profile_id}.json"
        
        try:
            # Remove from cache
            if profile_id in self._profile_cache:
                del self._profile_cache[profile_id]
            
            if profile_id in self._last_loaded:
                del self._last_loaded[profile_id]
            
            # Remove file if it exists
            if profile_file.exists():
                profile_file.unlink()
                self.logger.info(f"Deleted profile file: {profile_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete profile {profile_id}: {e}")
            return False
    
    def validate_profile(self, profile_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate profile data without loading it.
        
        Args:
            profile_data: Profile data dictionary
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        try:
            # Try to create profile instance
            profile = ProcessingProfile(**profile_data)
            
            # Validate interpolation variables
            interpolation_issues = profile.validate_interpolation_variables()
            if interpolation_issues:
                for step_id, missing_vars in interpolation_issues.items():
                    errors.append(f"Step '{step_id}' missing variables: {missing_vars}")
            
            return len(errors) == 0, errors
            
        except ValidationError as e:
            for error in e.errors():
                field = ".".join(str(x) for x in error["loc"])
                errors.append(f"{field}: {error['msg']}")
            
            return False, errors
        except Exception as e:
            return False, [str(e)]


# Global profile manager instance
profile_manager: Optional[ProfileManager] = None


def get_profile_manager() -> ProfileManager:
    """Get the global profile manager instance."""
    global profile_manager
    if profile_manager is None:
        profile_manager = ProfileManager()
    return profile_manager