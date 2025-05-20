import unittest
from unittest.mock import MagicMock, patch
import customtkinter as ctk
import sys
import os

# Adjust path to import from src
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, parent_dir)

from src.components.output_display.error_display import ErrorDisplayFrame
from src.utils import error_templates

class TestErrorDisplayFrame(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = ctk.CTk()
        cls.app.withdraw() # Hide the main window during tests

    @classmethod
    def tearDownClass(cls):
        cls.app.quit()
        cls.app.destroy()

    def setUp(self):
        self.error_frame = ErrorDisplayFrame(self.app)
        # Ensure the frame is gridded for widget assertions, then remove for clean state
        self.error_frame.grid(row=0, column=0)
        self.error_frame.grid_remove()

    def tearDown(self):
        self.error_frame.destroy()

    def test_initial_state(self):
        self.assertFalse(self.error_frame.winfo_ismapped(), "Error frame should be hidden initially")
        self.assertEqual(self.error_frame.title_label.cget("text"), "")
        self.assertEqual(self.error_frame.message_textbox.get("1.0", "end-1c"), "")
        self.assertEqual(self.error_frame.icon_label.cget("text"), "")
        self.assertFalse(self.error_frame.copy_button.winfo_ismapped(), "Copy button should be hidden initially")
        self.assertFalse(self.error_frame.retry_button.winfo_ismapped(), "Retry button should be hidden initially")

    def test_show_error_api(self):
        details = {"status_code": 500, "error_message": "Server Error", "endpoint": "/api/test"}
        mock_retry_cmd = MagicMock()
        
        self.error_frame.show_error(error_type="api", details=details, icon="❌", retry_command=mock_retry_cmd)
        
        self.assertTrue(self.error_frame.winfo_ismapped())
        expected_title, expected_message = error_templates.format_api_error(**details)
        self.assertEqual(self.error_frame.title_label.cget("text"), expected_title)
        self.assertEqual(self.error_frame.message_textbox.get("1.0", "end-1c"), expected_message)
        self.assertEqual(self.error_frame.icon_label.cget("text"), "❌")
        self.assertTrue(self.error_frame.copy_button.winfo_ismapped())
        self.assertTrue(self.error_frame.retry_button.winfo_ismapped())
        
        # Test retry button command
        self.error_frame.retry_button.invoke()
        mock_retry_cmd.assert_called_once()

    def test_show_error_parsing(self):
        details = {"error_type": "JSONError", "details": "Unexpected token", "file_source": "data.json"}
        self.error_frame.show_error(error_type="parsing", details=details, icon="🧩")
        
        self.assertTrue(self.error_frame.winfo_ismapped())
        expected_title, expected_message = error_templates.format_parsing_error(**details)
        self.assertEqual(self.error_frame.title_label.cget("text"), expected_title)
        self.assertEqual(self.error_frame.message_textbox.get("1.0", "end-1c"), expected_message)
        self.assertEqual(self.error_frame.icon_label.cget("text"), "🧩")
        self.assertTrue(self.error_frame.copy_button.winfo_ismapped())
        self.assertFalse(self.error_frame.retry_button.winfo_ismapped(), "Retry button should be hidden if no command")

    def test_show_error_large_output(self):
        details = {"output_size_kb": 1500, "limit_kb": 1000, "content_type": "Report"}
        self.error_frame.show_error(error_type="large_output", details=details)
        
        self.assertTrue(self.error_frame.winfo_ismapped())
        expected_title, expected_message = error_templates.format_large_output_error(**details)
        self.assertEqual(self.error_frame.title_label.cget("text"), expected_title)
        self.assertEqual(self.error_frame.message_textbox.get("1.0", "end-1c"), expected_message)
        self.assertEqual(self.error_frame.icon_label.cget("text"), "🔔") # Default icon for large_output
        self.assertTrue(self.error_frame.copy_button.winfo_ismapped())

    def test_show_error_generic(self):
        details = {"custom_title": "Custom Error", "custom_message": "Something went wrong."}
        self.error_frame.show_error(error_type="generic", details=details, icon="⚙️")
        
        self.assertTrue(self.error_frame.winfo_ismapped())
        expected_title, expected_message = error_templates.format_generic_error(**details)
        self.assertEqual(self.error_frame.title_label.cget("text"), expected_title)
        self.assertEqual(self.error_frame.message_textbox.get("1.0", "end-1c"), expected_message)
        self.assertEqual(self.error_frame.icon_label.cget("text"), "⚙️")

    def test_clear_error(self):
        self.error_frame.show_error(error_type="generic", details={"custom_title": "T", "custom_message": "M"})
        self.assertTrue(self.error_frame.winfo_ismapped())
        self.error_frame.clear_error()
        self.assertFalse(self.error_frame.winfo_ismapped(), "Error frame should be hidden after clear_error")
        self.assertEqual(self.error_frame.title_label.cget("text"), "")
        self.assertEqual(self.error_frame.message_textbox.get("1.0", "end-1c"), "")

    @patch('tkinter.messagebox.showinfo')
    @patch.object(ErrorDisplayFrame, 'clipboard_append') # Mock clipboard_append
    @patch.object(ErrorDisplayFrame, 'clipboard_clear')  # Mock clipboard_clear
    def test_copy_details(self, mock_clipboard_clear, mock_clipboard_append, mock_showinfo):
        details = {"custom_title": "Test Copy", "custom_message": "Details to copy."}
        self.error_frame.show_error(error_type="generic", details=details)
        
        self.error_frame.copy_button.invoke()
        
        mock_clipboard_clear.assert_called_once()
        expected_copied_text = f"Error: {details['custom_title']}\n\n{details['custom_message']}"
        mock_clipboard_append.assert_called_once_with(expected_copied_text)
        mock_showinfo.assert_called_once_with("Copied", "Error details copied to clipboard.")

    @patch('tkinter.messagebox.showerror')
    @patch.object(ErrorDisplayFrame, 'clipboard_append', side_effect=Exception("Clipboard error"))
    @patch.object(ErrorDisplayFrame, 'clipboard_clear')
    def test_copy_details_failure(self, mock_clipboard_clear, mock_clipboard_append_fails, mock_showerror):
        details = {"custom_title": "Copy Fail", "custom_message": "Test."}
        self.error_frame.show_error(error_type="generic", details=details)
        
        self.error_frame.copy_button.invoke()
        
        mock_clipboard_clear.assert_called_once()
        mock_clipboard_append_fails.assert_called_once()
        mock_showerror.assert_called_once_with("Copy Failed", "Could not copy to clipboard: Clipboard error")

if __name__ == '__main__':
    unittest.main() 