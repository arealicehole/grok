import unittest
import uuid
from datetime import datetime
from unittest.mock import patch, MagicMock
import deepdiff

# Assuming the utilities and models are in src.profile_utils
from src.profile_utils import (
    AnalysisProfile,
    clone_profile,
    create_template_profile,
    diff_profiles,
    search_profiles_by_text,
    validate_schema_compatibility,
    merge_profiles,
    find_profiles_by_schema_element,
    extract_schema_section,
    load_profile,
    save_profile,
    _profiles_db # Accessing placeholder store for test setup
)

class TestProfileUtils(unittest.TestCase):

    def setUp(self):
        """Clear the placeholder store before each test."""
        _profiles_db.clear()
        # Create some base profiles for testing
        self.schema1 = {
            "version": "1.0",
            "inputs": {"in1": {"type": "text"}, "common_in": {"type": "number"}},
            "outputs": {"out1": {"type": "text"}, "common_out": {"type": "boolean"}}
        }
        self.schema2 = {
            "version": "1.0",
            "inputs": {"in2": {"type": "text"}, "common_in": {"type": "number"}},
            "outputs": {"out2": {"type": "json"}, "common_out": {"type": "boolean"}}
        }
        self.schema3_incompatible_type = {
            "version": "1.0",
            "inputs": {"common_in": {"type": "string"}}, # Type mismatch
            "outputs": {}
        }
        self.schema4_incompatible_version = {
            "version": "2.0",
            "inputs": {"common_in": {"type": "number"}},
            "outputs": {}
        }

        self.profile1 = AnalysisProfile(
            name="Test Profile 1",
            instructions="Instructions 1",
            schema_definition=self.schema1
        )
        self.profile2 = AnalysisProfile(
            name="Test Profile 2",
            instructions="Instructions 2 - with search term",
            schema_definition=self.schema2
        )
        self.profile3 = AnalysisProfile(
            name="Test Profile 3 IncompType",
            instructions="Instructions 3",
            schema_definition=self.schema3_incompatible_type
        )
        self.profile4 = AnalysisProfile(
            name="Test Profile 4 IncompVer",
            instructions="Instructions 4",
            schema_definition=self.schema4_incompatible_version
        )

        save_profile(self.profile1)
        save_profile(self.profile2)
        save_profile(self.profile3)
        save_profile(self.profile4)

    def test_clone_profile_basic(self):
        """Test basic cloning."""
        cloned = clone_profile(self.profile1.id)
        self.assertIsNotNone(cloned)
        self.assertNotEqual(cloned.id, self.profile1.id)
        self.assertEqual(cloned.name, f"Copy of {self.profile1.name}")
        self.assertEqual(cloned.instructions, self.profile1.instructions)
        self.assertEqual(cloned.schema_definition, self.profile1.schema_definition)
        self.assertIn(cloned.id, _profiles_db) # Check if saved

    def test_clone_profile_with_new_name(self):
        """Test cloning with a specified new name."""
        new_name = "Cloned Profile New Name"
        cloned = clone_profile(self.profile1.name, new_name=new_name) # Clone by name
        self.assertEqual(cloned.name, new_name)

    def test_clone_profile_with_modifications(self):
        """Test cloning with modifications."""
        mods = {"instructions": "Modified instructions"}
        cloned = clone_profile(self.profile1.id, modifications=mods)
        self.assertEqual(cloned.instructions, "Modified instructions")
        self.assertEqual(cloned.name, f"Copy of {self.profile1.name}") # Name should be default copy name

    def test_clone_profile_source_not_found(self):
        """Test cloning non-existent profile."""
        with self.assertRaisesRegex(ValueError, "Source profile 'nonexistent' not found."):
            clone_profile("nonexistent")

    def test_clone_profile_name_conflict(self):
        """Test cloning when the target name already exists."""
        with self.assertRaisesRegex(ValueError, f"A profile with the name '{self.profile2.name}' already exists."):
             clone_profile(self.profile1.id, new_name=self.profile2.name)

    def test_create_template_profile_basic(self):
        """Test creating a basic template."""
        template_name = "Basic Analysis Template"
        template = create_template_profile("basic")
        self.assertIsNotNone(template)
        self.assertEqual(template.name, template_name)
        self.assertIn("inputs", template.schema_definition)
        self.assertIn("outputs", template.schema_definition)
        self.assertTrue(len(template.instructions) > 0)
        self.assertIn(template.id, _profiles_db) # Check if saved

    def test_create_template_profile_with_name(self):
        """Test creating a template with a custom name."""
        custom_name = "My Basic Template"
        template = create_template_profile("basic", name=custom_name)
        self.assertEqual(template.name, custom_name)

    def test_create_template_profile_unknown_type(self):
        """Test creating a template with an unknown type."""
        with self.assertRaisesRegex(ValueError, "Unknown template type: 'invalid_type'"):
            create_template_profile("invalid_type")

    def test_create_template_profile_name_conflict(self):
        """Test creating a template when the default name conflicts."""
        create_template_profile("basic") # Create one first
        with self.assertRaisesRegex(ValueError, "A profile with the name 'Basic Analysis Template' already exists."):
            create_template_profile("basic") # Try creating again

    def test_diff_profiles_no_difference(self):
        """Test diffing identical profiles (after excluding metadata)."""
        cloned = clone_profile(self.profile1.id)
        # Ensure timestamps are slightly different for a realistic scenario
        cloned.updated_at = datetime.utcnow()
        save_profile(cloned)

        diff = diff_profiles(self.profile1.id, cloned.id)
        # DeepDiff returns empty dict if no differences after excluding metadata
        self.assertEqual(diff, {})

    def test_diff_profiles_with_differences(self):
        """Test diffing profiles with actual differences."""
        diff = diff_profiles(self.profile1.id, self.profile2.id)
        self.assertTrue(len(diff) > 0)
        self.assertIn('values_changed', diff) # Check common deepdiff key
        # Example check:
        self.assertIn("root['name']", diff.get('values_changed', {}))

    def test_diff_profiles_not_found(self):
        """Test diffing when one profile doesn't exist."""
        with self.assertRaisesRegex(ValueError, "Profile 'nonexistent' not found."):
            diff_profiles(self.profile1.id, "nonexistent")
        with self.assertRaisesRegex(ValueError, "Profile 'nonexistent' not found."):
            diff_profiles("nonexistent", self.profile2.id)

    def test_search_profiles_by_text_found(self):
        """Test searching text found in instructions."""
        results = search_profiles_by_text("search term")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.profile2.id)

    def test_search_profiles_by_text_found_in_name(self):
        """Test searching text found in name."""
        results = search_profiles_by_text("Profile 1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.profile1.id)

    def test_search_profiles_by_text_case_insensitive(self):
        """Test case-insensitivity."""
        results = search_profiles_by_text("PROFILE 1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.profile1.id)

    def test_search_profiles_by_text_not_found(self):
        """Test searching text not found."""
        results = search_profiles_by_text("xyz_unique_string_xyz")
        self.assertEqual(len(results), 0)

    def test_search_profiles_specific_fields(self):
        """Test searching only within specific fields."""
        # Search only name, shouldn't find profile 2 via instructions
        results_name = search_profiles_by_text("search term", search_fields=['name'])
        self.assertEqual(len(results_name), 0)

        # Search only instructions, should find profile 2
        results_instr = search_profiles_by_text("search term", search_fields=['instructions'])
        self.assertEqual(len(results_instr), 1)
        self.assertEqual(results_instr[0].id, self.profile2.id)

    def test_validate_schema_compatible(self):
        """Test schemas that should be compatible."""
        is_compatible, issues = validate_schema_compatibility(self.schema1, self.schema2)
        # Compatible because no direct type mismatches on common fields
        self.assertTrue(is_compatible)
        # Should report missing fields as potential issues
        self.assertTrue(any("Input field 'in1' exists" in issue for issue in issues))
        self.assertTrue(any("Input field 'in2' exists" in issue for issue in issues))

    def test_validate_schema_identical(self):
        """Test identical schemas."""
        is_compatible, issues = validate_schema_compatibility(self.schema1, self.schema1)
        self.assertTrue(is_compatible)
        self.assertEqual(len(issues), 0)

    def test_validate_schema_incompatible_type(self):
        """Test schemas with incompatible types for a common field."""
        is_compatible, issues = validate_schema_compatibility(self.schema1, self.schema3_incompatible_type)
        self.assertFalse(is_compatible)
        self.assertTrue(any("Type mismatch for input field 'common_in'" in issue for issue in issues))

    def test_validate_schema_incompatible_version(self):
        """Test schemas with different versions."""
        is_compatible, issues = validate_schema_compatibility(self.schema1, self.schema4_incompatible_version)
        # Compatibility depends on how strictly version is checked
        # The current implementation notes it but doesn't make it incompatible
        self.assertTrue(is_compatible) 
        self.assertTrue(any("Schema version mismatch" in issue for issue in issues))

    def test_validate_schema_invalid_input(self):
        """Test with invalid schema inputs."""
        is_compatible, issues = validate_schema_compatibility(self.schema1, None)
        self.assertFalse(is_compatible)
        self.assertTrue(len(issues) > 0)

        is_compatible, issues = validate_schema_compatibility([], {})
        self.assertFalse(is_compatible)
        self.assertTrue(len(issues) > 0)
        
    def test_merge_profiles_primary_strategy(self):
        """Test merging with the 'primary' strategy."""
        merged_name = "Merged Primary"
        merged = merge_profiles([self.profile1.id, self.profile2.id], merged_name, merge_strategy='primary')
        
        self.assertIsNotNone(merged)
        self.assertEqual(merged.name, merged_name)
        self.assertIn(merged.id, _profiles_db)
        
        # Instructions should be concatenated
        self.assertIn(self.profile1.instructions, merged.instructions)
        self.assertIn(self.profile2.instructions, merged.instructions)
        self.assertIn("---", merged.instructions)
        self.assertIn(f"from Profile: '{self.profile1.name}'", merged.instructions)
        
        # Schema should have fields from both (primary takes precedence on conflicts)
        merged_schema = merged.schema_definition
        self.assertIn("in1", merged_schema["inputs"])
        self.assertIn("in2", merged_schema["inputs"]) # Added from profile2
        self.assertIn("common_in", merged_schema["inputs"])
        self.assertEqual(merged_schema["inputs"]["common_in"]["type"], "number") # From profile1
        
        self.assertIn("out1", merged_schema["outputs"])
        self.assertIn("out2", merged_schema["outputs"]) # Added from profile2
        self.assertIn("common_out", merged_schema["outputs"])
        self.assertEqual(merged_schema["outputs"]["common_out"]["type"], "boolean") # From profile1
        
    def test_merge_profiles_less_than_two(self):
        """Test merging with less than two profiles."""
        with self.assertRaisesRegex(ValueError, "At least two profiles are required for merging."):
            merge_profiles([self.profile1.id], "Merged Fail")
            
    def test_merge_profiles_not_found(self):
        """Test merging when a profile ID is invalid."""
        with self.assertRaisesRegex(ValueError, "Profile 'nonexistent' not found."):
            merge_profiles([self.profile1.id, "nonexistent"], "Merged Fail")
            
    def test_merge_profiles_name_conflict(self):
        """Test merging when the new name conflicts with an existing profile."""
        with self.assertRaisesRegex(ValueError, f"A profile with the name '{self.profile1.name}' already exists."):
            merge_profiles([self.profile2.id, self.profile4.id], self.profile1.name)

    def test_merge_profiles_unsupported_strategy(self):
        """Test merging with an unsupported strategy."""
        with self.assertRaisesRegex(ValueError, "Unsupported merge strategy: 'invalid_strat'"):
            merge_profiles([self.profile1.id, self.profile2.id], "Merged Fail", merge_strategy='invalid_strat')
            
    def test_merge_profiles_not_implemented_strategy(self):
        """Test merging with strategies marked as NotImplemented."""
        with self.assertRaises(NotImplementedError):
            merge_profiles([self.profile1.id, self.profile2.id], "Merged Union", merge_strategy='union')
        with self.assertRaises(NotImplementedError):
             merge_profiles([self.profile1.id, self.profile2.id], "Merged Intersect", merge_strategy='intersection')

    # --- Tests for find_profiles_by_schema_element ---
    
    def test_find_by_schema_element_exists(self):
        """Test finding profiles where an element path exists."""
        # Element exists in profile 1 and 3
        results = find_profiles_by_schema_element("inputs.common_in.type") 
        self.assertEqual(len(results), 3) # schema1, schema2, schema4 have it
        self.assertCountEqual([p.id for p in results], [self.profile1.id, self.profile2.id, self.profile4.id])

        # Element exists only in profile 1
        results = find_profiles_by_schema_element("inputs.in1") 
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.profile1.id)
        
        # Non-existent path
        results = find_profiles_by_schema_element("inputs.nonexistent.path") 
        self.assertEqual(len(results), 0)
        
    def test_find_by_schema_element_with_value(self):
        """Test finding profiles where an element exists and matches a value."""
        # Find where inputs.common_in.type is 'number'
        results = find_profiles_by_schema_element("inputs.common_in.type", value_matcher="number")
        self.assertEqual(len(results), 3) # profile1, profile2, profile4
        self.assertCountEqual([p.id for p in results], [self.profile1.id, self.profile2.id, self.profile4.id])
        
        # Find where inputs.common_in.type is 'string'
        results = find_profiles_by_schema_element("inputs.common_in.type", value_matcher="string")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.profile3.id)
        
        # Find where outputs.common_out exists (profile 1 and 2)
        results_exist = find_profiles_by_schema_element("outputs.common_out")
        self.assertEqual(len(results_exist), 2)
        self.assertCountEqual([p.id for p in results_exist], [self.profile1.id, self.profile2.id])

        # Find where outputs.common_out.type is 'boolean'
        results_match = find_profiles_by_schema_element("outputs.common_out.type", value_matcher=True) # Note: boolean comparison
        self.assertEqual(len(results_match), 0) # Should be False as value is the string "boolean"
        
        results_match_str = find_profiles_by_schema_element("outputs.common_out.type", value_matcher="boolean") 
        self.assertEqual(len(results_match_str), 2) 
        self.assertCountEqual([p.id for p in results_match_str], [self.profile1.id, self.profile2.id])

        # Find with value that doesn't match anything
        results = find_profiles_by_schema_element("inputs.common_in.type", value_matcher="date")
        self.assertEqual(len(results), 0)

    # --- Tests for extract_schema_section --- 

    def test_extract_schema_section_top_level(self):
        """Test extracting top-level sections like 'inputs' or 'outputs'."""
        inputs_section = extract_schema_section(self.profile1.id, "inputs")
        self.assertIsNotNone(inputs_section)
        self.assertEqual(inputs_section, self.profile1.schema_definition["inputs"])
        # Verify it's a copy
        inputs_section["new_key"] = "test"
        self.assertNotIn("new_key", self.profile1.schema_definition["inputs"])
        
        outputs_section = extract_schema_section(self.profile2.name, "outputs") # Test by name
        self.assertIsNotNone(outputs_section)
        self.assertEqual(outputs_section, self.profile2.schema_definition["outputs"])
        
    def test_extract_schema_section_nested(self):
        """Test extracting nested elements."""
        input_type = extract_schema_section(self.profile1.id, "inputs.common_in.type")
        self.assertEqual(input_type, "number")
        
        output_type = extract_schema_section(self.profile2.id, "outputs.out2.type")
        self.assertEqual(output_type, "json")
        
        # Extract a whole sub-object
        common_in_props = extract_schema_section(self.profile1.id, "inputs.common_in")
        self.assertEqual(common_in_props, {"type": "number"})
        
    def test_extract_schema_section_not_found(self):
        """Test extracting non-existent paths."""
        result = extract_schema_section(self.profile1.id, "inputs.nonexistent")
        self.assertIsNone(result)
        
        result = extract_schema_section(self.profile1.id, "nonexistent_top_level")
        self.assertIsNone(result)
        
        result = extract_schema_section(self.profile1.id, "inputs.in1.nonexistent_subpath")
        self.assertIsNone(result)
        
    def test_extract_schema_section_profile_not_found(self):
        """Test extracting from a profile that doesn't exist."""
        with self.assertRaisesRegex(ValueError, "Profile 'nonexistent' not found."):
            extract_schema_section("nonexistent", "inputs")

if __name__ == '__main__':
    unittest.main() 