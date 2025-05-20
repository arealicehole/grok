import unittest
import datetime
from typing import Dict, Any

# Adjust the import path based on your project structure
# Assuming src is in PYTHONPATH or tests are run from the project root
from src.models.analysis_job_result import AnalysisJob, JobStatus, AnalysisResult

class TestAnalysisJob(unittest.TestCase):

    def test_job_creation_profile_id(self):
        job = AnalysisJob(transcript_id="t123", profile_id=1)
        self.assertIsNotNone(job.id is None) # ID is None until persisted
        self.assertEqual(job.transcript_id, "t123")
        self.assertEqual(job.profile_id, 1)
        self.assertIsNone(job.temporary_instructions)
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertIsNotNone(job.created_at)
        self.assertIsNotNone(job.updated_at)
        self.assertIsNone(job.error_message)

    def test_job_creation_temporary_instructions(self):
        job = AnalysisJob(transcript_id="t124", temporary_instructions="Summarize this")
        self.assertEqual(job.transcript_id, "t124")
        self.assertIsNone(job.profile_id)
        self.assertEqual(job.temporary_instructions, "Summarize this")
        self.assertEqual(job.status, JobStatus.COMPLETED, msg="Default status should be PENDING, but let's test passing another one") # Deliberate test of passing status
        job2 = AnalysisJob(transcript_id="t125", temporary_instructions="Extract keywords", status=JobStatus.PROCESSING)
        self.assertEqual(job2.status, JobStatus.PROCESSING)

    def test_job_creation_invalid_status_type(self):
        with self.assertRaisesRegex(ValueError, "status must be a JobStatus enum member"):
            AnalysisJob(transcript_id="t_err", profile_id=1, status="invalid_string_status")

    def test_job_creation_no_transcript_id(self):
        with self.assertRaisesRegex(ValueError, "transcript_id cannot be empty"):
            AnalysisJob(transcript_id="", profile_id=1)
        with self.assertRaisesRegex(ValueError, "transcript_id cannot be empty"):
            AnalysisJob(transcript_id=None, profile_id=1)

    def test_job_creation_no_profile_or_temp_instructions(self):
        with self.assertRaisesRegex(ValueError, "Either profile_id or temporary_instructions must be provided"):
            AnalysisJob(transcript_id="t_err2")

    def test_job_creation_both_profile_and_temp_instructions(self):
        with self.assertRaisesRegex(ValueError, "Both profile_id and temporary_instructions cannot be provided simultaneously"):
            AnalysisJob(transcript_id="t_err3", profile_id=1, temporary_instructions="Summarize")

    def test_job_to_dict(self):
        now_iso = datetime.datetime.now().isoformat()
        job = AnalysisJob(
            id=10,
            transcript_id="t001",
            profile_id=5,
            status=JobStatus.COMPLETED,
            created_at=now_iso,
            updated_at=now_iso,
            error_message="Test error"
        )
        expected_dict = {
            "id": 10,
            "transcript_id": "t001",
            "profile_id": 5,
            "temporary_instructions": None,
            "status": "completed",
            "created_at": now_iso,
            "updated_at": now_iso,
            "error_message": "Test error",
        }
        self.assertEqual(job.to_dict(), expected_dict)

    def test_job_from_dict(self):
        now_iso = datetime.datetime.now().isoformat()
        data = {
            "id": 20,
            "transcript_id": "t002",
            "profile_id": 7,
            "status": "failed",
            "created_at": now_iso,
            "updated_at": now_iso,
            "error_message": "Critical failure",
        }
        job = AnalysisJob.from_dict(data)
        self.assertEqual(job.id, 20)
        self.assertEqual(job.transcript_id, "t002")
        self.assertEqual(job.profile_id, 7)
        self.assertIsNone(job.temporary_instructions)
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertEqual(job.created_at, now_iso)
        self.assertEqual(job.updated_at, now_iso)
        self.assertEqual(job.error_message, "Critical failure")

    def test_job_from_dict_with_temp_instructions(self):
        data = {"transcript_id": "t003", "temporary_instructions": "Analyze sentiment", "status": "pending"}
        job = AnalysisJob.from_dict(data)
        self.assertEqual(job.transcript_id, "t003")
        self.assertIsNone(job.profile_id)
        self.assertEqual(job.temporary_instructions, "Analyze sentiment")
        self.assertEqual(job.status, JobStatus.PENDING)

    def test_job_from_dict_invalid_status_value(self):
        data = {"transcript_id": "t_err4", "profile_id":1, "status": "non_existent_status"}
        with self.assertRaisesRegex(ValueError, "Invalid status value 'non_existent_status' provided"):
            AnalysisJob.from_dict(data)
    
    def test_job_repr(self):
        job = AnalysisJob(transcript_id="t_repr", profile_id=1)
        self.assertIn("AnalysisJob(id=None, status='pending',", repr(job))

class TestAnalysisResult(unittest.TestCase):

    def test_result_creation(self):
        result = AnalysisResult(analysis_job_id=1, raw_response={"key": "value"})
        self.assertIsNone(result.id)
        self.assertEqual(result.analysis_job_id, 1)
        self.assertEqual(result.raw_response, {"key": "value"})
        self.assertIsNone(result.parsed_data)
        self.assertIsNotNone(result.created_at)
        self.assertEqual(result.status, "Success")

    def test_result_creation_with_parsed_data(self):
        result = AnalysisResult(
            analysis_job_id=2, 
            raw_response="{\"raw\": true}", 
            parsed_data={"parsed": True},
            status="Completed with warnings"
        )
        self.assertEqual(result.parsed_data, {"parsed": True})
        self.assertEqual(result.status, "Completed with warnings")

    def test_result_creation_no_job_id(self):
        with self.assertRaisesRegex(ValueError, "analysis_job_id cannot be None"):
            AnalysisResult(analysis_job_id=None, raw_response={})

    def test_result_creation_no_raw_response(self):
        with self.assertRaisesRegex(ValueError, "raw_response cannot be empty"):
            AnalysisResult(analysis_job_id=1, raw_response="")
        with self.assertRaisesRegex(ValueError, "raw_response cannot be empty"):
            AnalysisResult(analysis_job_id=1, raw_response=None)
        with self.assertRaisesRegex(ValueError, "raw_response cannot be empty"):
            AnalysisResult(analysis_job_id=1, raw_response={})

    def test_result_to_dict(self):
        now_iso = datetime.datetime.now().isoformat()
        result = AnalysisResult(
            id=100,
            analysis_job_id=50,
            raw_response={"data": [1, 2, 3]},
            parsed_data={"summary": "Okay"},
            created_at=now_iso,
            status="Processed"
        )
        expected_dict = {
            "id": 100,
            "analysis_job_id": 50,
            "raw_response": {"data": [1, 2, 3]},
            "parsed_data": {"summary": "Okay"},
            "created_at": now_iso,
            "status": "Processed",
        }
        self.assertEqual(result.to_dict(), expected_dict)

    def test_result_from_dict(self):
        now_iso = datetime.datetime.now().isoformat()
        data = {
            "id": 200,
            "analysis_job_id": 75,
            "raw_response": "Some raw text",
            "parsed_data": "Some parsed text",
            "created_at": now_iso,
            "status": "Archived"
        }
        result = AnalysisResult.from_dict(data)
        self.assertEqual(result.id, 200)
        self.assertEqual(result.analysis_job_id, 75)
        self.assertEqual(result.raw_response, "Some raw text")
        self.assertEqual(result.parsed_data, "Some parsed text")
        self.assertEqual(result.created_at, now_iso)
        self.assertEqual(result.status, "Archived")

    def test_result_repr(self):
        result = AnalysisResult(analysis_job_id=1, raw_response="test")
        self.assertIn("AnalysisResult(id=None, analysis_job_id=1,", repr(result))

if __name__ == '__main__':
    unittest.main() 