"""Step execution engine for multi-step profile processing."""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from ..models.profile import ProcessingProfile, ProcessingStep, ModelConfig
from ..providers.selector import ModelSelector
from ..providers.base import LLMResponse, LLMProvider
from .interpolation import StepContext, OutputValidator, InterpolationError


logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """Error during step execution."""
    pass


class StepResult:
    """Result of a single step execution."""
    
    def __init__(
        self,
        step_id: str,
        success: bool,
        output: Any = None,
        error: Optional[str] = None,
        execution_time_ms: int = 0,
        tokens_used: int = 0,
        model_used: Optional[str] = None,
        provider_used: Optional[str] = None,
        retry_count: int = 0
    ):
        self.step_id = step_id
        self.success = success
        self.output = output
        self.error = error
        self.execution_time_ms = execution_time_ms
        self.tokens_used = tokens_used
        self.model_used = model_used
        self.provider_used = provider_used
        self.retry_count = retry_count
        self.timestamp = datetime.now(timezone.utc)


class ProfileResult:
    """Result of complete profile execution."""
    
    def __init__(
        self,
        profile_id: str,
        success: bool,
        step_results: List[StepResult],
        final_output: Dict[str, Any],
        total_execution_time_ms: int,
        total_tokens_used: int,
        error: Optional[str] = None
    ):
        self.profile_id = profile_id
        self.success = success
        self.step_results = step_results
        self.final_output = final_output
        self.total_execution_time_ms = total_execution_time_ms
        self.total_tokens_used = total_tokens_used
        self.error = error
        self.timestamp = datetime.now(timezone.utc)
        
        # Compute summary stats
        self.successful_steps = sum(1 for r in step_results if r.success)
        self.failed_steps = sum(1 for r in step_results if not r.success)
        self.total_retries = sum(r.retry_count for r in step_results)


class StepExecutor:
    """Executes individual processing steps."""
    
    def __init__(self, model_selector: ModelSelector):
        self.model_selector = model_selector
        self.logger = logging.getLogger(f"{__name__}.StepExecutor")
    
    async def execute_step(
        self,
        step: ProcessingStep,
        context: StepContext,
        global_overrides: Optional[Dict[str, Any]] = None
    ) -> StepResult:
        """
        Execute a single processing step.
        
        Args:
            step: Step definition
            context: Execution context with variables
            global_overrides: Global configuration overrides
            
        Returns:
            StepResult with execution details
        """
        start_time = time.time()
        retry_count = 0
        last_error = None
        
        self.logger.info(f"Executing step: {step.step_id}")
        
        # Validate variables are available
        missing_vars = context.validate_step_variables(
            step.prompt_template, step.step_id, step.dependencies
        )
        if missing_vars:
            error_msg = f"Missing variables for step {step.step_id}: {missing_vars}"
            self.logger.error(error_msg)
            return StepResult(
                step_id=step.step_id,
                success=False,
                error=error_msg,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )
        
        # Attempt execution with retries
        while retry_count <= step.max_retries:
            try:
                result = await self._execute_step_attempt(step, context, global_overrides)
                
                # Success - record timing and return
                execution_time = int((time.time() - start_time) * 1000)
                result.execution_time_ms = execution_time
                result.retry_count = retry_count
                
                self.logger.info(
                    f"Step {step.step_id} completed successfully "
                    f"(attempt {retry_count + 1}, {execution_time}ms, {result.tokens_used} tokens)"
                )
                
                return result
                
            except Exception as e:
                last_error = str(e)
                retry_count += 1
                
                self.logger.warning(
                    f"Step {step.step_id} failed (attempt {retry_count}): {last_error}"
                )
                
                if retry_count <= step.max_retries and step.retry_on_failure:
                    # Brief delay before retry
                    await asyncio.sleep(0.5 * retry_count)
                else:
                    break
        
        # All retries exhausted
        execution_time = int((time.time() - start_time) * 1000)
        error_msg = f"Step failed after {retry_count} attempts: {last_error}"
        
        self.logger.error(f"Step {step.step_id} failed permanently: {error_msg}")
        
        return StepResult(
            step_id=step.step_id,
            success=False,
            error=error_msg,
            execution_time_ms=execution_time,
            retry_count=retry_count - 1
        )
    
    async def _execute_step_attempt(
        self,
        step: ProcessingStep,
        context: StepContext,
        global_overrides: Optional[Dict[str, Any]] = None
    ) -> StepResult:
        """Execute a single attempt of a step."""
        
        # 1. Interpolate prompt template
        try:
            prompt = context.interpolate_prompt(
                step.prompt_template,
                step.step_id,
                step.dependencies
            )
        except InterpolationError as e:
            raise ExecutionError(f"Prompt interpolation failed: {e}")
        
        # 2. Prepare model configuration with overrides
        model_config = self._apply_config_overrides(step.llm_config, global_overrides, step.step_id)
        
        # 3. Select and execute with LLM provider
        try:
            provider = await self.model_selector.select_provider(model_config, global_overrides)
            llm_response = await provider.generate_completion(prompt, model_config)
        except Exception as e:
            raise ExecutionError(f"LLM generation failed: {e}")
        
        # 4. Validate and process output
        try:
            if step.output_format == "json":
                # Parse and validate JSON
                schema_dict = None
                if step.output_schema:
                    schema_dict = {
                        "type": step.output_schema.type,
                        "required_fields": step.output_schema.required_fields
                    }
                
                parsed_output = OutputValidator.validate_json_output(
                    llm_response.content, schema_dict
                )
                final_output = parsed_output
            else:
                # Text output
                final_output = llm_response.content.strip()
            
        except InterpolationError as e:
            raise ExecutionError(f"Output validation failed: {e}")
        
        # 5. Update context with step output
        context.add_step_output(step.step_id, final_output, step.pass_to_next)
        
        return StepResult(
            step_id=step.step_id,
            success=True,
            output=final_output,
            tokens_used=llm_response.tokens_used,
            model_used=llm_response.model,
            provider_used=llm_response.provider
        )
    
    def _apply_config_overrides(
        self,
        base_config: ModelConfig,
        global_overrides: Optional[Dict[str, Any]],
        step_id: str
    ) -> ModelConfig:
        """Apply global and step-specific overrides to model configuration."""
        
        # Start with base configuration
        config_dict = base_config.model_dump()
        
        if not global_overrides:
            return ModelConfig(**config_dict)
        
        # Apply global overrides
        for key, value in global_overrides.items():
            if key.startswith("global_") and key != "global_overrides":
                # Map global_temperature -> temperature
                actual_key = key.replace("global_", "")
                if actual_key in config_dict:
                    config_dict[actual_key] = value
            elif key in ["force_provider", "force_model"]:
                # Direct provider/model overrides
                if key == "force_provider":
                    config_dict["provider"] = value
                elif key == "force_model":
                    config_dict["model"] = value
        
        # Apply step-specific overrides
        step_overrides = global_overrides.get("step_overrides", {}).get(step_id, {})
        for key, value in step_overrides.items():
            if key in config_dict:
                config_dict[key] = value
        
        return ModelConfig(**config_dict)


class ProfileExecutor:
    """Executes complete processing profiles."""
    
    def __init__(self, model_selector: ModelSelector):
        self.step_executor = StepExecutor(model_selector)
        self.logger = logging.getLogger(f"{__name__}.ProfileExecutor")
    
    async def execute_profile(
        self,
        profile: ProcessingProfile,
        transcript: str,
        global_overrides: Optional[Dict[str, Any]] = None
    ) -> ProfileResult:
        """
        Execute a complete processing profile.
        
        Args:
            profile: Profile definition
            transcript: Input transcript text
            global_overrides: Global configuration overrides
            
        Returns:
            ProfileResult with complete execution details
        """
        start_time = time.time()
        self.logger.info(f"Starting profile execution: {profile.profile_id}")
        
        # Initialize execution context
        context = StepContext(transcript)
        step_results: List[StepResult] = []
        total_tokens = 0
        
        try:
            # Validate profile before execution
            interpolation_issues = profile.validate_interpolation_variables()
            if interpolation_issues:
                error_msg = f"Profile validation failed: {interpolation_issues}"
                return ProfileResult(
                    profile_id=profile.profile_id,
                    success=False,
                    step_results=[],
                    final_output={},
                    total_execution_time_ms=int((time.time() - start_time) * 1000),
                    total_tokens_used=0,
                    error=error_msg
                )
            
            # Execute steps in dependency order
            execution_order = profile.get_execution_order()
            
            for step_id in execution_order:
                step = profile.get_step(step_id)
                if not step:
                    continue
                
                # Execute step
                step_result = await self.step_executor.execute_step(
                    step, context, global_overrides
                )
                step_results.append(step_result)
                total_tokens += step_result.tokens_used
                
                # Check if step was required and failed
                if step.required and not step_result.success:
                    error_msg = f"Required step '{step_id}' failed: {step_result.error}"
                    self.logger.error(error_msg)
                    
                    return ProfileResult(
                        profile_id=profile.profile_id,
                        success=False,
                        step_results=step_results,
                        final_output={},
                        total_execution_time_ms=int((time.time() - start_time) * 1000),
                        total_tokens_used=total_tokens,
                        error=error_msg
                    )
            
            # Compile final output
            final_output = self._compile_final_output(step_results, profile)
            execution_time = int((time.time() - start_time) * 1000)
            
            self.logger.info(
                f"Profile {profile.profile_id} completed successfully "
                f"({execution_time}ms, {total_tokens} tokens, {len(step_results)} steps)"
            )
            
            return ProfileResult(
                profile_id=profile.profile_id,
                success=True,
                step_results=step_results,
                final_output=final_output,
                total_execution_time_ms=execution_time,
                total_tokens_used=total_tokens
            )
            
        except Exception as e:
            error_msg = f"Profile execution failed: {e}"
            self.logger.exception(error_msg)
            
            return ProfileResult(
                profile_id=profile.profile_id,
                success=False,
                step_results=step_results,
                final_output={},
                total_execution_time_ms=int((time.time() - start_time) * 1000),
                total_tokens_used=total_tokens,
                error=error_msg
            )
    
    def _compile_final_output(
        self,
        step_results: List[StepResult],
        profile: ProcessingProfile
    ) -> Dict[str, Any]:
        """Compile final output from all step results."""
        
        final_output = {}
        
        # Include all successful step outputs
        for result in step_results:
            if result.success and result.output is not None:
                final_output[result.step_id] = result.output
        
        # Add execution metadata
        final_output["_metadata"] = {
            "profile_id": profile.profile_id,
            "profile_name": profile.name,
            "profile_version": profile.version,
            "steps_completed": len([r for r in step_results if r.success]),
            "steps_failed": len([r for r in step_results if not r.success]),
            "total_tokens": sum(r.tokens_used for r in step_results),
            "total_execution_time_ms": sum(r.execution_time_ms for r in step_results),
            "step_summary": [
                {
                    "step_id": r.step_id,
                    "success": r.success,
                    "execution_time_ms": r.execution_time_ms,
                    "tokens_used": r.tokens_used,
                    "model_used": r.model_used,
                    "provider_used": r.provider_used,
                    "retry_count": r.retry_count
                }
                for r in step_results
            ]
        }
        
        return final_output