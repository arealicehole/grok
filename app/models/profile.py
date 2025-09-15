"""Processing profile models for multi-step analysis."""

from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
import re
import json


class ModelConfig(BaseModel):
    """Configuration for LLM model requests."""
    provider: Literal["local", "openrouter"] = Field(default="local", description="LLM provider")
    model: str = Field(default="llama3.1:8b", description="Model identifier")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=2000, ge=100, le=50000, description="Maximum tokens to generate")
    timeout_seconds: int = Field(default=30, ge=5, le=300, description="Request timeout")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Top-p nucleus sampling")
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0, description="Presence penalty")
    
    @field_validator('model')
    @classmethod
    def validate_model_for_provider(cls, v, info):
        """Validate model compatibility with provider."""
        provider = info.data.get('provider', 'local')
        
        # Common model patterns for validation
        local_models = ['llama3.1:8b', 'mistral:7b', 'codellama:7b', 'phi3:mini']
        openrouter_patterns = [
            'openai/', 'anthropic/', 'google/', 'meta-llama/', 'microsoft/', 'mistralai/'
        ]
        
        if provider == "local" and v not in local_models and not any(v.startswith(p) for p in ['llama', 'mistral', 'phi', 'codellama']):
            # Allow flexibility for local models but warn about common patterns
            pass
        elif provider == "openrouter" and not any(v.startswith(p) for p in openrouter_patterns):
            # OpenRouter models should follow provider/model pattern
            pass
            
        return v


class StepOutputSchema(BaseModel):
    """Schema definition for step output validation."""
    type: Literal["object", "array", "string"] = Field(default="object", description="Output type")
    required_fields: List[str] = Field(default_factory=list, description="Required fields for object type")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Field definitions for object type")
    example: Optional[Dict[str, Any]] = Field(default=None, description="Example output")


class ProcessingStep(BaseModel):
    """Single step in a multi-step processing profile."""
    step_id: str = Field(..., min_length=1, max_length=50, description="Unique step identifier")
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable step name")
    description: Optional[str] = Field(None, description="Step description")
    prompt_template: str = Field(..., min_length=10, description="Prompt template with placeholders")
    llm_config: ModelConfig = Field(default_factory=ModelConfig, description="Model configuration")
    output_format: Literal["json", "text"] = Field(default="json", description="Expected output format")
    output_schema: Optional[StepOutputSchema] = Field(default=None, description="Output validation schema")
    required: bool = Field(default=True, description="Whether step is required for profile completion")
    pass_to_next: bool = Field(default=True, description="Whether to pass output to subsequent steps")
    retry_on_failure: bool = Field(default=True, description="Whether to retry failed step")
    max_retries: int = Field(default=2, ge=0, le=5, description="Maximum retry attempts")
    dependencies: List[str] = Field(default_factory=list, description="Step IDs this step depends on")
    
    @field_validator('prompt_template')
    @classmethod
    def validate_prompt_template(cls, v):
        """Validate prompt template syntax and placeholders."""
        # Check for required {transcript} placeholder
        if '{transcript}' not in v:
            raise ValueError("Prompt template must include {transcript} placeholder")
        
        # Validate placeholder syntax using regex
        placeholder_pattern = r'\{[a-zA-Z_][a-zA-Z0-9_]*\}'
        placeholders = re.findall(placeholder_pattern, v)
        
        # Check for invalid placeholder syntax
        invalid_pattern = r'\{[^}]*[^a-zA-Z0-9_}][^}]*\}'
        invalid_placeholders = re.findall(invalid_pattern, v)
        if invalid_placeholders:
            raise ValueError(f"Invalid placeholder syntax: {invalid_placeholders}")
        
        return v
    
    @field_validator('dependencies')
    @classmethod
    def validate_dependencies(cls, v):
        """Validate dependency step IDs."""
        for dep in v:
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', dep):
                raise ValueError(f"Invalid dependency step ID: {dep}")
        return v
    
    def get_placeholder_variables(self) -> List[str]:
        """Extract all placeholder variables from prompt template."""
        placeholder_pattern = r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
        return re.findall(placeholder_pattern, self.prompt_template)


class ProfileMetadata(BaseModel):
    """Metadata for profile management."""
    author: Optional[str] = Field(default=None, description="Profile author")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Last update timestamp")
    source: Optional[str] = Field(default="user", description="Profile source (user, builtin, imported)")
    license: Optional[str] = Field(default=None, description="License information")


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
    metadata: ProfileMetadata = Field(default_factory=ProfileMetadata, description="Profile metadata")
    
    @field_validator('steps')
    @classmethod
    def validate_steps_unique_ids(cls, v):
        """Ensure all step IDs are unique."""
        step_ids = [step.step_id for step in v]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("All step IDs must be unique")
        return v
    
    @model_validator(mode='after')
    def validate_step_dependencies(self):
        """Validate step dependencies form a valid DAG."""
        step_ids = {step.step_id for step in self.steps}
        
        # Check all dependencies exist
        for step in self.steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    raise ValueError(f"Step '{step.step_id}' depends on non-existent step '{dep}'")
        
        # Check for circular dependencies using topological sort
        visited = set()
        rec_stack = set()
        
        def has_cycle(step_id: str, graph: Dict[str, List[str]]) -> bool:
            """DFS to detect cycles."""
            visited.add(step_id)
            rec_stack.add(step_id)
            
            for neighbor in graph.get(step_id, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, graph):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(step_id)
            return False
        
        # Build dependency graph
        dep_graph = {}
        for step in self.steps:
            dep_graph[step.step_id] = step.dependencies
        
        # Check for cycles
        for step_id in step_ids:
            if step_id not in visited:
                if has_cycle(step_id, dep_graph):
                    raise ValueError("Circular dependency detected in profile steps")
        
        return self
    
    def get_execution_order(self) -> List[str]:
        """Get steps in dependency-resolved execution order."""
        # Topological sort
        in_degree = {step.step_id: len(step.dependencies) for step in self.steps}
        queue = [step_id for step_id, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            current = queue.pop(0)
            result.append(current)
            
            # Update in-degrees for dependent steps
            for step in self.steps:
                if current in step.dependencies:
                    in_degree[step.step_id] -= 1
                    if in_degree[step.step_id] == 0:
                        queue.append(step.step_id)
        
        return result
    
    def get_step(self, step_id: str) -> Optional[ProcessingStep]:
        """Get step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None
    
    def validate_interpolation_variables(self) -> Dict[str, List[str]]:
        """Validate that all interpolation variables are available."""
        available_vars = {'transcript'}  # Always available
        step_outputs = {}  # Track what each step provides
        issues = {}
        
        for step_id in self.get_execution_order():
            step = self.get_step(step_id)
            if not step:
                continue
                
            # Get variables this step needs
            needed_vars = set(step.get_placeholder_variables())
            
            # Check if all needed variables are available
            missing_vars = needed_vars - available_vars
            if missing_vars:
                issues[step_id] = list(missing_vars)
            
            # Add this step's output to available variables if it passes to next
            if step.pass_to_next:
                available_vars.add(step.step_id)
                step_outputs[step.step_id] = step.output_format
        
        return issues