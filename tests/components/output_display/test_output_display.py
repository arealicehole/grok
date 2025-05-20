import unittest
from unittest.mock import MagicMock, patch
import customtkinter as ctk
import sys
import os

# Adjust path to import from src
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, parent_dir)

from src.components.output_display import OutputDisplayFrame
# Assuming child views (JsonViewFrame, ChatViewFrame, ErrorDisplayFrame) are correctly imported by OutputDisplayFrame

class TestOutputDisplayFrame(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = ctk.CTk()
        cls.app.withdraw() # Hide main window

    @classmethod
    def tearDownClass(cls):
        # cls.app.quit() # This can sometimes cause issues if tests run too quickly or an error occurs
        cls.app.destroy()

    def setUp(self):
        self.output_display = OutputDisplayFrame(self.app)
        self.output_display.pack() # Ensure it's created

        # Mock child views to isolate OutputDisplayFrame logic
        self.output_display.json_view = MagicMock()
        self.output_display.chat_view = MagicMock()
        self.output_display.error_display = MagicMock()

    def tearDown(self):
        self.output_display.destroy()

    def test_initial_state(self):
        self.assertEqual(self.output_display.current_view_mode, "json")
        self.assertIsNone(self.output_display.current_data)
        # Check if json_view is visible and chat_view is not (or vice-versa depending on default)
        self.output_display.json_view.grid.assert_called() # Assuming it was called during init switch_view
        self.output_display.chat_view.grid_remove.assert_called() 
        self.output_display.error_display.grid_remove.assert_called()
        self.assertFalse(self.output_display.truncation_controls_frame.winfo_ismapped())

    def test_switch_view_to_chat(self):
        self.output_display.switch_view("chat")
        self.assertEqual(self.output_display.current_view_mode, "chat")
        self.output_display.json_view.grid_remove.assert_called_with()
        self.output_display.chat_view.grid.assert_called_with(row=0, column=0, sticky="nsew")
        self.output_display.error_display.grid_remove.assert_called_with() # Ensure error is hidden

    def test_switch_view_to_json(self):
        # First switch to chat, then back to json to check transitions
        self.output_display.switch_view("chat")
        self.output_display.switch_view("json")
        self.assertEqual(self.output_display.current_view_mode, "json")
        self.output_display.chat_view.grid_remove.assert_called_with()
        self.output_display.json_view.grid.assert_called_with(row=0, column=0, sticky="nsew")

    def test_set_data_json_view(self):
        self.output_display.switch_view("json") # Ensure current view is json
        data = {"json_data": {"key": "value"}, "chat_data": [{"text": "hi"}]}
        self.output_display.set_data(data)
        self.assertEqual(self.output_display.current_data, data)
        self.output_display.json_view.set_json_data.assert_called_once_with(data.get("json_data"))
        self.output_display.chat_view.set_chat_data.assert_not_called() # Should not be called if view is json
        self.output_display.error_display.grid_remove.assert_called_with()

    def test_set_data_chat_view(self):
        self.output_display.switch_view("chat")
        data = {"json_data": {"key": "value"}, "chat_data": [{"text": "hi"}]}
        self.output_display.set_data(data)
        self.assertEqual(self.output_display.current_data, data)
        self.output_display.chat_view.set_chat_data.assert_called_once_with(data.get("chat_data"))
        self.output_display.json_view.set_json_data.assert_not_called()

    def test_show_analysis_error(self):
        error_details = {"status_code": 500, "error_message": "Test Error"}
        mock_retry = MagicMock()
        self.output_display.show_analysis_error(error_type="api", details=error_details, retry_command=mock_retry)
        
        # Check content_frame is hidden
        # self.assertFalse(self.output_display.content_frame.winfo_ismapped()) # Difficult to check directly with mocks
        self.output_display.error_display.show_error.assert_called_once_with(error_type="api", details=error_details, retry_command=mock_retry)
        self.output_display.error_display.grid.assert_called_with() # Ensure error display is shown
        self.assertFalse(self.output_display.truncation_controls_frame.winfo_ismapped())

    def test_clear_output(self):
        self.output_display.set_data({"json_data": {"a":1}, "chat_data": [{"t":"m"}]})
        self.output_display.show_analysis_error("generic", {"custom_title":"E", "custom_message":"Msg"})
        
        self.output_display.clear_output()
        self.assertIsNone(self.output_display.current_data)
        self.output_display.json_view.clear_view.assert_called_once()
        self.output_display.chat_view.clear_view.assert_called_once()
        self.output_display.error_display.clear_error.assert_called_once()
        self.output_display.error_display.grid_remove.assert_called() # Called during clear and set_data/switch_view
        # self.assertTrue(self.output_display.content_frame.winfo_ismapped()) # Content frame should be visible
        self.assertFalse(self.output_display.truncation_controls_frame.winfo_ismapped())

    def test_truncation_controls_json_view_truncated(self):
        self.output_display.switch_view("json")
        self.output_display.json_view.is_truncated = True
        self.output_display.json_view.status_label.cget = MagicMock(return_value="JSON Truncated Info")
        self.output_display.set_data({"json_data": {"large": "data"}}) # Triggers _update_truncation_controls
        
        self.assertTrue(self.output_display.truncation_controls_frame.winfo_ismapped())
        self.assertEqual(self.output_display.truncation_status_label.cget("text"), "JSON Truncated Info")
        self.assertTrue(self.output_display.view_full_json_button.winfo_ismapped())
        self.assertFalse(self.output_display.save_full_chat_button.winfo_ismapped())

    def test_truncation_controls_chat_view_truncated(self):
        self.output_display.switch_view("chat")
        self.output_display.chat_view.is_truncated = True
        self.output_display.chat_view.full_chat_data = ["msg1", "msg2", "msg3"] # Example data
        self.output_display.chat_view._message_widgets = [MagicMock(), MagicMock()] # Example displayed widgets
        self.output_display.set_data({"chat_data": self.output_display.chat_view.full_chat_data})

        self.assertTrue(self.output_display.truncation_controls_frame.winfo_ismapped())
        self.assertIn("Chat truncated. Displaying 2 of 3 messages.", self.output_display.truncation_status_label.cget("text"))
        self.assertTrue(self.output_display.save_full_chat_button.winfo_ismapped())
        self.assertFalse(self.output_display.view_full_json_button.winfo_ismapped())

    def test_truncation_controls_not_truncated(self):
        self.output_display.switch_view("json")
        self.output_display.json_view.is_truncated = False
        self.output_display.set_data({"json_data": {"small": "data"}})
        self.assertFalse(self.output_display.truncation_controls_frame.winfo_ismapped())

    def test_save_full_json_button_command(self):
        self.output_display.switch_view("json")
        self.output_display.json_view.is_truncated = True # To show the button
        self.output_display.set_data({"json_data": {"large": "data"}})
        
        self.output_display.view_full_json_button.invoke() # Simulate button click
        self.output_display.json_view._view_full_output.assert_called_once()

    def test_save_full_chat_button_command(self):
        self.output_display.switch_view("chat")
        self.output_display.chat_view.is_truncated = True # To show the button
        self.output_display.chat_view.full_chat_data = ["test"]
        self.output_display.set_data({"chat_data": ["test"]})

        self.output_display.save_full_chat_button.invoke()
        self.output_display.chat_view.save_full_chat_data_to_file.assert_called_once()

if __name__ == '__main__':
    unittest.main() 