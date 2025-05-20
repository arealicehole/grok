import unittest
from unittest.mock import patch, mock_open, call
import customtkinter as ctk
import json # For checking saved JSON content
import sys
import os

# Adjust path to import from src
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, parent_dir)

from src.components.output_display.chat_view import ChatViewFrame, MAX_CHAT_MESSAGES, MAX_MESSAGE_LENGTH

class TestChatViewFrame(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = ctk.CTk()
        cls.app.withdraw() # Hide main window

    @classmethod
    def tearDownClass(cls):
        cls.app.quit()
        cls.app.destroy()

    def setUp(self):
        self.chat_view = ChatViewFrame(self.app)
        self.chat_view.pack() # Ensure widget is created and winfo_width is available for wraplength
        # self.chat_view.status_controls_frame.pack() # If testing status bar visibility

    def tearDown(self):
        self.chat_view.destroy()

    def get_displayed_message_texts(self):
        """Helper to get the text from all displayed message labels."""
        texts = []
        for container_frame in self.chat_view._message_widgets:
            bubble_frame = container_frame.winfo_children()[0]
            label = bubble_frame.winfo_children()[0]
            texts.append(label.cget("text"))
        return texts

    def test_initial_state(self):
        self.assertEqual(len(self.chat_view._message_widgets), 0)
        self.assertIsNone(self.chat_view.full_chat_data)
        self.assertFalse(self.chat_view.is_truncated)

    def test_set_chat_data_none(self):
        self.chat_view.set_chat_data(None)
        self.assertEqual(len(self.chat_view._message_widgets), 1)
        self.assertIn("No chat data to display", self.get_displayed_message_texts()[0])
        self.assertEqual(self.chat_view.full_chat_data, [])
        self.assertFalse(self.chat_view.is_truncated)

    def test_set_chat_data_simple(self):
        data = [
            {"sender": "Alice", "text": "Hello"},
            {"sender": "Bob", "text": "Hi", "is_user": True}
        ]
        self.chat_view.set_chat_data(data)
        self.assertEqual(len(self.chat_view._message_widgets), 2)
        displayed_texts = self.get_displayed_message_texts()
        self.assertIn("Hello", displayed_texts[0])
        self.assertIn("Hi", displayed_texts[1])
        self.assertEqual(self.chat_view.full_chat_data, data)
        self.assertFalse(self.chat_view.is_truncated)

    def test_truncation_by_message_count(self):
        data = [{ "sender": f"User{i}", "text": f"Msg {i}"} for i in range(MAX_CHAT_MESSAGES + 5)]
        self.chat_view.set_chat_data(data)
        
        self.assertTrue(self.chat_view.is_truncated)
        self.assertEqual(len(self.chat_view._message_widgets), MAX_CHAT_MESSAGES)
        last_message_text = self.get_displayed_message_texts()[-1]
        self.assertIn("... (Chat Truncated - Too many messages)", last_message_text)

    def test_truncation_by_message_length(self):
        long_text = "a" * (MAX_MESSAGE_LENGTH + 10)
        data = [
            {"sender": "Alice", "text": "Short"},
            {"sender": "Bob", "text": long_text}
        ]
        self.chat_view.set_chat_data(data)
        self.assertTrue(self.chat_view.is_truncated)
        displayed_texts = self.get_displayed_message_texts()
        self.assertIn("... (Message Truncated)", displayed_texts[1])
        self.assertTrue(len(displayed_texts[1]) <= MAX_MESSAGE_LENGTH + len("... (Message Truncated)") + len("Bob: ") + 20) # Approx check

    def test_truncation_both_count_and_length(self):
        long_text = "a" * (MAX_MESSAGE_LENGTH + 10)
        data = [{ "sender": f"User{i}", "text": long_text if i == 0 else f"Msg {i}"} for i in range(MAX_CHAT_MESSAGES + 5)]
        self.chat_view.set_chat_data(data)

        self.assertTrue(self.chat_view.is_truncated)
        self.assertEqual(len(self.chat_view._message_widgets), MAX_CHAT_MESSAGES)
        
        # First message should be truncated by length
        self.assertIn("... (Message Truncated)", self.get_displayed_message_texts()[0])
        # Last displayed message should indicate list truncation
        self.assertIn("... (Chat Truncated - Too many messages)", self.get_displayed_message_texts()[-1])

    def test_clear_view(self):
        data = [{"sender": "Test", "text": "Test"}]
        self.chat_view.set_chat_data(data)
        self.chat_view.clear_view()
        self.assertEqual(len(self.chat_view._message_widgets), 0)
        self.assertIsNone(self.chat_view.full_chat_data)
        self.assertFalse(self.chat_view.is_truncated)

    @patch('tkinter.filedialog.asksaveasfilename')
    @patch('tkinter.messagebox.showinfo')
    def test_save_full_chat_data_json_success(self, mock_showinfo, mock_asksaveasfilename):
        data = [{ "sender": f"User{i}", "text": f"Msg {i}"} for i in range(MAX_CHAT_MESSAGES + 5)]
        self.chat_view.set_chat_data(data) # Populates full_chat_data
        mock_asksaveasfilename.return_value = "test_chat.json"
        
        with patch('builtins.open', mock_open()) as mock_file:
            result = self.chat_view.save_full_chat_data_to_file()
            self.assertTrue(result)
            mock_file.assert_called_once_with("test_chat.json", 'w', encoding='utf-8')
            # Check if json.dump was called with the correct data
            # json.dump(self.chat_view.full_chat_data, mock_file(), indent=2)
            args, kwargs = mock_file().write.call_args_list[0] # json.dump writes multiple times
            written_content = "".join(arg[0] for arg in mock_file().write.call_args_list)
            self.assertEqual(json.loads(written_content), self.chat_view.full_chat_data)
        mock_showinfo.assert_called_once_with("Saved", "Full chat log saved to test_chat.json")

    @patch('tkinter.filedialog.asksaveasfilename')
    @patch('tkinter.messagebox.showinfo')
    def test_save_full_chat_data_txt_success(self, mock_showinfo, mock_asksaveasfilename):
        data = [{"sender": "Alice", "text": "Msg1"}, {"sender": "Bob", "text": "Msg2"}]
        self.chat_view.set_chat_data(data)
        mock_asksaveasfilename.return_value = "test_chat.txt"

        expected_txt_content = "Alice: Msg1\nBob: Msg2\n"
        with patch('builtins.open', mock_open()) as mock_file:
            result = self.chat_view.save_full_chat_data_to_file()
            self.assertTrue(result)
            mock_file.assert_called_once_with("test_chat.txt", 'w', encoding='utf-8')
            # Check individual writes for text mode
            self.assertEqual(mock_file().write.call_count, 2)
            mock_file().write.assert_any_call("Alice: Msg1\n")
            mock_file().write.assert_any_call("Bob: Msg2\n")
        mock_showinfo.assert_called_once_with("Saved", "Full chat log saved to test_chat.txt")

    @patch('tkinter.filedialog.asksaveasfilename')
    @patch('tkinter.messagebox.showerror')
    def test_save_chat_data_fail_exception(self, mock_showerror, mock_asksaveasfilename):
        self.chat_view.set_chat_data([{"sender": "Test", "text": "Data"}])
        mock_asksaveasfilename.return_value = "test.json"
        with patch('builtins.open', mock_open()) as mock_file:
            mock_file.side_effect = IOError("Cannot write")
            result = self.chat_view.save_full_chat_data_to_file()
            self.assertFalse(result)
            mock_showerror.assert_called_once_with("Save Failed", "Could not save file: Cannot write")

    @patch('tkinter.filedialog.asksaveasfilename')
    def test_save_chat_data_cancel(self, mock_asksaveasfilename):
        self.chat_view.set_chat_data([{"sender": "Test", "text": "Data"}])
        mock_asksaveasfilename.return_value = "" # Simulate user cancelling
        with patch('builtins.open', mock_open()) as mock_file:
            result = self.chat_view.save_full_chat_data_to_file()
            self.assertFalse(result)
            mock_file.assert_not_called()

    def test_save_chat_data_no_data(self):
        self.chat_view.full_chat_data = None
        with patch('tkinter.messagebox.showinfo') as mock_showinfo:
            result = self.chat_view.save_full_chat_data_to_file()
            self.assertFalse(result)
            mock_showinfo.assert_called_once_with("No Data", "No full chat data available to save.")

if __name__ == '__main__':
    unittest.main() 