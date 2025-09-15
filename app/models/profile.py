"""Processing profile models for multi-step analysis."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator


class ModelConfig(BaseModel):
    """Configuration for LLM model requests."""
    provider: str = Field(default="local")
    model: str = Field(default="llama3.1:8b")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, ge=100, le=50000)
    timeout_seconds: int = Field(default=30, ge=5, le=300)


class ProcessingStep(BaseModel):
    """Single step in a multi-step processing profile."""
    step_id: str = Field(..., min_length=1, max_length=50, description="Unique step identifier")
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable step name")
    description: Optional[str] = Field(None, description="Step description")
    prompt_template: str = Field(..., min_length=10, description="Prompt template with placeholders")
    llm_config: ModelConfig = Field(default_factory=ModelConfig, description="Model configuration")
    output_format: str = Field(default="json", pattern="^(json|text)$", description="Expected output format")
    required: bool = Field(default=True, description="Whether step is required for profile completion")
    pass_to_next: bool = Field(default=True, description="Whether to pass output to subsequent steps")

    @field_validator('prompt_template')
    @classmethod
    def validate_prompt_template(cls, v):
        """Ensure prompt template has required placeholders."""
        if '{transcript}' not in v:
            raise ValueError("Prompt template must include {transcript} placeholder")
        return v


class ProcessingProfile(BaseModel):
    """Complete profile definition for transcript analysis."""
    profile_id: str = Field(..., pattern="^[a-z0-9_]+$", description="Unique profile identifier")
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable profile name")
    description: str = Field(..., min_length=1, max_length=500, description="Profile description")
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$", description="Profile version")
    steps: List[ProcessingStep] = Field(..., min_items=1, max_items=10, description="Processing steps")
    final_output_schema: Dict[str, Any] = Field(default_factory=dict, description="Expected output schema")
    tags: List[str] = Field(default_factory=list, description="Profile tags")
    use_cases: List[str] = Field(default_factory=list, description="When to use this profile")
    estimated_tokens: int = Field(default=1000, ge=100, le=50000, description="Estimated token usage")

    @field_validator('steps')
    @classmethod
    def validate_steps_unique_ids(cls, v):
        """Ensure all step IDs are unique."""
        step_ids = [step.step_id for step in v]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("All step IDs must be unique")
        return v