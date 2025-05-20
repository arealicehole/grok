import unittest
from unittest.mock import patch, mock_open
import customtkinter as ctk
import json
import sys
import os

# Adjust path to import from src
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, parent_dir)

from src.components.output_display.json_view import JsonViewFrame, MAX_DISPLAY_CHARS, MAX_DISPLAY_LINES

class TestJsonViewFrame(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = ctk.CTk()
        cls.app.withdraw() # Hide main window

    @classmethod
    def tearDownClass(cls):
        cls.app.quit()
        cls.app.destroy()

    def setUp(self):
        self.json_view = JsonViewFrame(self.app)
        self.json_view.pack() # Pack to ensure winfo_ismapped works if needed, and for widget creation

    def tearDown(self):
        self.json_view.destroy()

    def get_textbox_content(self):
        return self.json_view.textbox.get("1.0", "end-1c")

    def test_initial_state(self):
        self.assertEqual(self.get_textbox_content(), "")
        self.assertIsNone(self.json_view.full_json_data)
        self.assertFalse(self.json_view.is_truncated)
        self.assertEqual(self.json_view.status_label.cget("text"), "")
        self.assertFalse(self.json_view.view_full_button.winfo_ismapped())

    def test_set_json_data_none(self):
        self.json_view.set_json_data(None)
        self.assertEqual(self.get_textbox_content(), "No JSON data to display.")
        self.assertIsNone(self.json_view.full_json_data)
        self.assertFalse(self.json_view.is_truncated)

    def test_set_json_data_simple(self):
        data = {"key": "value", "number": 123}
        self.json_view.set_json_data(data)
        expected_json_str = json.dumps(data, indent=2)
        self.assertEqual(self.get_textbox_content(), expected_json_str)
        self.assertEqual(self.json_view.full_json_data, expected_json_str)
        self.assertFalse(self.json_view.is_truncated)
        self.assertIn(f"{expected_json_str.count('\n') + 1} lines", self.json_view.status_label.cget("text"))
        self.assertFalse(self.json_view.view_full_button.winfo_ismapped())

    def test_set_json_data_serialization_error(self):
        # Functions are not directly serializable to JSON
        data = {"error": lambda x: x}
        self.json_view.set_json_data(data)
        self.assertIn("Error: Could not serialize data to JSON.", self.get_textbox_content())
        self.assertIsNone(self.json_view.full_json_data)
        self.assertFalse(self.json_view.is_truncated)

    def test_truncation_by_lines(self):
        # Create data that exceeds MAX_DISPLAY_LINES but not necessarily MAX_DISPLAY_CHARS per line
        data = [f"Line {i}" for i in range(MAX_DISPLAY_LINES + 10)]
        self.json_view.set_json_data(data)
        
        self.assertTrue(self.json_view.is_truncated)
        self.assertIn("... (Content Truncated)", self.get_textbox_content())
        # Check if the number of lines in textbox is MAX_DISPLAY_LINES + truncation message lines
        # (json.dumps adds lines for brackets, so exact count is tricky without full dump)
        # For simplicity, check if the truncation message is there and button is visible.
        self.assertTrue(self.json_view.view_full_button.winfo_ismapped())
        self.assertIn(f"Output truncated. Showing ~{MAX_DISPLAY_LINES} lines", self.json_view.status_label.cget("text"))

    def test_truncation_by_chars(self):
        # Create data that is one long line exceeding MAX_DISPLAY_CHARS
        data = {"long_string": "a" * (MAX_DISPLAY_CHARS + 100)}
        self.json_view.set_json_data(data)
        
        self.assertTrue(self.json_view.is_truncated)
        self.assertIn("... (Content Truncated)", self.get_textbox_content())
        self.assertTrue(len(self.get_textbox_content()) <= MAX_DISPLAY_CHARS + len("\n\n... (Content Truncated)") + 20) # Allowance for formatting
        self.assertTrue(self.json_view.view_full_button.winfo_ismapped())
        self.assertIn(f"Output truncated.", self.json_view.status_label.cget("text")) # Char count can be complex here

    def test_clear_view(self):
        data = {"key": "value"}
        self.json_view.set_json_data(data)
        self.json_view.clear_view()
        self.test_initial_state() # Should revert to initial state

    @patch('tkinter.filedialog.asksaveasfilename')
    @patch('tkinter.messagebox.showinfo')
    def test_view_full_output_save_success(self, mock_showinfo, mock_asksaveasfilename):
        data = {"large_data": ["item"] * (MAX_DISPLAY_LINES + 5)}
        self.json_view.set_json_data(data) # Ensure full_json_data is populated
        
        mock_asksaveasfilename.return_value = "test_output.json"
        
        with patch('builtins.open', mock_open()) as mock_file:
            self.json_view._view_full_output()
            mock_file.assert_called_once_with("test_output.json", 'w', encoding='utf-8')
            mock_file().write.assert_called_once_with(self.json_view.full_json_data)
        
        mock_showinfo.assert_called_once_with("Saved", "Full JSON output saved to test_output.json")

    @patch('tkinter.filedialog.asksaveasfilename')
    @patch('tkinter.messagebox.showerror')
    def test_view_full_output_save_fail_exception(self, mock_showerror, mock_asksaveasfilename):
        data = {"data": "test"}
        self.json_view.set_json_data(data)
        mock_asksaveasfilename.return_value = "test_output.json"
        
        with patch('builtins.open', mock_open()) as mock_file:
            mock_file.side_effect = IOError("Disk full")
            self.json_view._view_full_output()
            mock_showerror.assert_called_once_with("Save Failed", "Could not save file: Disk full")

    @patch('tkinter.filedialog.asksaveasfilename')
    def test_view_full_output_save_cancel(self, mock_asksaveasfilename):
        data = {"data": "test"}
        self.json_view.set_json_data(data)
        mock_asksaveasfilename.return_value = "" # User cancels save dialog
        
        with patch('builtins.open', mock_open()) as mock_file:
            self.json_view._view_full_output()
            mock_file.assert_not_called()

    def test_view_full_output_no_data(self):
        self.json_view.full_json_data = None
        with patch('tkinter.messagebox.showinfo') as mock_showinfo:
            self.json_view._view_full_output()
            mock_showinfo.assert_called_once_with("No Data", "No full JSON data available to display.")

if __name__ == '__main__':
    unittest.main() 