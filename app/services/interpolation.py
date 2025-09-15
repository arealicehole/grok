"""Variable interpolation system for profile processing."""

import re
import json
from typing import Dict, Any, List, Optional, Union
from string import Template


class InterpolationError(Exception):
    """Error during variable interpolation."""
    pass


class VariableInterpolator:
    """Handles variable interpolation in prompt templates."""
    
    def __init__(self):
        self.placeholder_pattern = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')
    
    def extract_variables(self, template: str) -> List[str]:
        """Extract all variable names from template."""
        return self.placeholder_pattern.findall(template)
    
    def validate_template(self, template: str) -> bool:
        """Validate template syntax."""
        try:
            # Check for balanced braces
            brace_count = 0
            for char in template:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count < 0:
                        return False
            
            if brace_count != 0:
                return False
            
            # Check for valid variable names
            variables = self.extract_variables(template)
            for var in variables:
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var):
                    return False
            
            return True
        except Exception:
            return False
    
    def interpolate(
        self,
        template: str,
        variables: Dict[str, Any],
        strict: bool = True
    ) -> str:
        """
        Interpolate variables into template.
        
        Args:
            template: Template string with {variable} placeholders
            variables: Dictionary of variable values
            strict: If True, raises error for missing variables
        
        Returns:
            Interpolated string
        
        Raises:
            InterpolationError: If required variables are missing or invalid
        """
        if not self.validate_template(template):
            raise InterpolationError(f"Invalid template syntax: {template}")
        
        # Extract required variables
        required_vars = set(self.extract_variables(template))
        provided_vars = set(variables.keys())
        
        # Check for missing variables in strict mode
        if strict:
            missing_vars = required_vars - provided_vars
            if missing_vars:
                raise InterpolationError(
                    f"Missing required variables: {sorted(missing_vars)}"
                )
        
        # Prepare variables for interpolation
        safe_variables = {}
        for var_name in required_vars:
            if var_name in variables:
                value = variables[var_name]
                
                # Convert complex types to JSON strings
                if isinstance(value, (dict, list)):
                    safe_variables[var_name] = json.dumps(value, indent=2)
                elif value is None:
                    safe_variables[var_name] = ""
                else:
                    safe_variables[var_name] = str(value)
            elif not strict:
                # In non-strict mode, leave missing variables as placeholders
                safe_variables[var_name] = f"{{{var_name}}}"
        
        # Perform interpolation using string.Template for safety
        try:
            # Convert {var} to $var format for Template
            template_str = re.sub(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', r'$\1', template)
            template_obj = Template(template_str)
            
            # Interpolate with safe substitution
            if strict:
                result = template_obj.substitute(safe_variables)
            else:
                result = template_obj.safe_substitute(safe_variables)
                # Convert back any remaining $var to {var}
                result = re.sub(r'\$([a-zA-Z_][a-zA-Z0-9_]*)', r'{\1}', result)
            
            return result
            
        except KeyError as e:
            raise InterpolationError(f"Variable substitution failed: {e}")
        except Exception as e:
            raise InterpolationError(f"Interpolation error: {e}")


class StepContext:
    """Manages variable context for step execution."""
    
    def __init__(self, transcript: str):
        self.variables: Dict[str, Any] = {"transcript": transcript}
        self.step_outputs: Dict[str, Any] = {}
        self.interpolator = VariableInterpolator()
    
    def add_step_output(self, step_id: str, output: Any, pass_to_next: bool = True):
        """Add output from completed step."""
        self.step_outputs[step_id] = output
        
        if pass_to_next:
            # Add step output to global variables
            self.variables[step_id] = output
    
    def get_variables_for_step(self, step_id: str, dependencies: List[str]) -> Dict[str, Any]:
        """Get all variables available for a specific step."""
        available_vars = {"transcript": self.variables["transcript"]}
        
        # Add dependent step outputs
        for dep_step_id in dependencies:
            if dep_step_id in self.step_outputs:
                available_vars[dep_step_id] = self.step_outputs[dep_step_id]
        
        # Add any other global variables that were passed to next
        for var_name, value in self.variables.items():
            if var_name != "transcript" and var_name not in dependencies:
                # Only include if it's a step output that was passed to next
                if var_name in self.step_outputs:
                    available_vars[var_name] = value
        
        return available_vars
    
    def interpolate_prompt(
        self,
        template: str,
        step_id: str,
        dependencies: List[str],
        strict: bool = True
    ) -> str:
        """Interpolate prompt template for specific step."""
        variables = self.get_variables_for_step(step_id, dependencies)
        return self.interpolator.interpolate(template, variables, strict)
    
    def validate_step_variables(
        self,
        template: str,
        step_id: str,
        dependencies: List[str]
    ) -> List[str]:
        """Validate that all required variables are available for step."""
        required_vars = set(self.interpolator.extract_variables(template))
        available_vars = set(self.get_variables_for_step(step_id, dependencies).keys())
        
        missing_vars = required_vars - available_vars
        return sorted(missing_vars)


class OutputValidator:
    """Validates step outputs against expected schemas."""
    
    @staticmethod
    def validate_json_output(output: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate and parse JSON output.
        
        Args:
            output: JSON string from LLM
            schema: Optional schema for validation
            
        Returns:
            Parsed JSON object
            
        Raises:
            InterpolationError: If JSON is invalid or doesn't match schema
        """
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError as e:
            raise InterpolationError(f"Invalid JSON output: {e}")
        
        if schema:
            OutputValidator._validate_against_schema(parsed, schema)
        
        return parsed
    
    @staticmethod
    def _validate_against_schema(data: Any, schema: Dict[str, Any]):
        """Basic schema validation."""
        schema_type = schema.get("type", "object")
        required_fields = schema.get("required_fields", [])
        
        if schema_type == "object" and isinstance(data, dict):
            # Check required fields
            missing_fields = []
            for field in required_fields:
                if field not in data:
                    missing_fields.append(field)
            
            if missing_fields:
                raise InterpolationError(
                    f"Missing required fields in output: {missing_fields}"
                )
                
        elif schema_type == "array" and not isinstance(data, list):
            raise InterpolationError(f"Expected array output, got {type(data).__name__}")
        elif schema_type == "string" and not isinstance(data, str):
            raise InterpolationError(f"Expected string output, got {type(data).__name__}")


# Utility functions for common interpolation tasks
def safe_interpolate(template: str, variables: Dict[str, Any]) -> str:
    """Safely interpolate template with error handling."""
    interpolator = VariableInterpolator()
    try:
        return interpolator.interpolate(template, variables, strict=False)
    except InterpolationError:
        # Return template with variables marked as unavailable
        return template


def extract_template_variables(template: str) -> List[str]:
    """Extract all variables from template."""
    interpolator = VariableInterpolator()
    return interpolator.extract_variables(template)


def validate_template_syntax(template: str) -> bool:
    """Validate template has correct syntax."""
    interpolator = VariableInterpolator()
    return interpolator.validate_template(template)