import customtkinter as ctk
import tkinter
import json
import tkinter.messagebox # Added for success message

class JsonViewFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        self.textbox = ctk.CTkTextbox(
            self, 
            wrap="none", # No wrap for structured JSON
            state="disabled", # Initially read-only
            font=("Courier New", 12) # Monospaced font
        )
        self.textbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        self.copy_button = ctk.CTkButton(
            self,
            text="Copy JSON",
            command=self._copy_json_to_clipboard
        )
        self.copy_button.grid(row=1, column=0, sticky="ew", padx=5, pady=(0,5))
        
        # Configure tags for syntax highlighting
        self._configure_tags()

    def _copy_json_to_clipboard(self):
        """Copies the current content of the JSON textbox to the clipboard."""
        json_content = self.textbox.get("1.0", "end-1c") # -1c to exclude trailing newline
        if json_content:
            try:
                self.clipboard_clear()
                self.clipboard_append(json_content)
                self.update() # Important for tkinter clipboard to work reliably
                tkinter.messagebox.showinfo("Copied", "JSON content copied to clipboard.", parent=self)
            except tkinter.TclError:
                tkinter.messagebox.showerror("Error", "Could not copy to clipboard. Another application may be using it.", parent=self)
        else:
            tkinter.messagebox.showwarning("Empty", "Nothing to copy.", parent=self)

    def _configure_tags(self):
        """Configures tags for syntax highlighting in the CTkTextbox."""
        # Define colors (can be themed later if needed)
        colors = {
            "key": ("#0000FF", "#ADD8E6"),      # Blue (light), LightBlue (dark)
            "string": ("#008000", "#90EE90"),   # Green (light), LightGreen (dark)
            "number": ("#A52A2A", "#F08080"),   # Brown (light), LightCoral (dark)
            "boolean": ("#FF8C00", "#FFA500"),  # DarkOrange (light), Orange (dark)
            "null": ("#808080", "#D3D3D3"),     # Gray (light), LightGray (dark)
            "punctuation": ("#000000", "#FFFFFF") # Black (light), White (dark) - for braces, commas etc.
        }

        # CTkTextbox uses a single foreground color. We might need to adjust strategy
        # or use a regular tkinter.Text for more complex tag coloring.
        # For now, demonstrating with a single color per tag.
        # A more robust solution might involve checking appearance mode.
        
        # Simple foreground colors for now
        self.textbox.tag_config("key", foreground=colors["key"][0]) 
        self.textbox.tag_config("string", foreground=colors["string"][0])
        self.textbox.tag_config("number", foreground=colors["number"][0])
        self.textbox.tag_config("boolean", foreground=colors["boolean"][0])
        self.textbox.tag_config("null", foreground=colors["null"][0])
        self.textbox.tag_config("punctuation", foreground=colors["punctuation"][0])

    def set_json_data(self, data: dict):
        """Formats, highlights, and displays the JSON data."""
        if data is None:
            self.textbox.configure(state="normal")
            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", "No JSON data to display.")
            self.textbox.configure(state="disabled")
            return

        try:
            # Pretty print the JSON
            json_string = json.dumps(data, indent=2)
            
            self.textbox.configure(state="normal")
            self.textbox.delete("1.0", "end")
            
            # Apply highlighting (placeholder for now, will be complex)
            # For a simple start, let's just insert the string
            # and try to highlight keys as an example.
            self._apply_highlighting(json_string)
            
            self.textbox.configure(state="disabled")

        except TypeError as e:
            self.textbox.configure(state="normal")
            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", f"Error: Invalid data for JSON display.\n{e}")
            self.textbox.configure(state="disabled")
        except Exception as e: # Catch-all for other errors during processing
            self.textbox.configure(state="normal")
            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", f"An unexpected error occurred during JSON display:\n{e}")
            self.textbox.configure(state="disabled")
            
    def _apply_highlighting(self, json_string: str):
        """
        Applies syntax highlighting to the JSON string.
        This is a simplified version. A robust version would use a proper JSON tokenizer/parser
        or a library like Pygments if compatible.
        """
        self.textbox.insert("1.0", json_string) # Insert the whole string first

        # Very basic example: Highlight quoted keys (simplistic regex)
        # This is not robust and just for initial demonstration.
        # A full implementation needs to parse or tokenize the JSON.
        import re
        key_pattern = r'\"([^\"]+)\"\s*:' # Matches "key" :
        
        current_pos = "1.0"
        while True:
            match = self.textbox.search(key_pattern, current_pos, "end", regexp=True, nocase=True)
            if not match:
                break
            
            # The match gives the start of the whole pattern. We want to color just the key part.
            # Let's find the start and end of the actual key within the match.
            # match_content = self.textbox.get(match, f"{match} + {len(match.group(0))}c") # This is incorrect for CTkTextbox search.
            # Need to parse start index and add length.
            
            # For simplicity, let's color the whole matched "key": part for now.
            # A more precise approach is needed.
            key_start_index = match
            # To get the key itself (inside quotes), we'd need to analyze the matched string.
            # For CTkTextbox.search, `match` is the start index as "line.char".
            # We need to find the length of the matched string to get the end index.
            
            # Get the line and char from the start index
            line, char = map(int, key_start_index.split('.'))
            
            # Read the line text to find the actual match content and its length for this line
            line_text = self.textbox.get(f"{line}.0", f"{line}.end")
            
            # Re-run regex on this specific line_text starting from char
            # This gets complicated quickly due to multiline matches and widget indexing.
            
            # --- Simplified placeholder for applying tag ---
            # This simplified version highlights based on the *first* capture group of the regex *if* the regex matched
            # It doesn't correctly calculate the end position of just the key within the quotes.
            # A real solution needs a proper tokenizer.
            
            # Let's iterate line by line and apply regex.
            # This is still not perfect but better than trying to search the whole widget at once with one regex for highlighting.
            
            # Clear and re-insert for this placeholder approach.
            # A better way is to insert char by char or token by token.
            
            # Reset content and iterate to apply tags
            self.textbox.delete("1.0", "end")
            
            # More robust tokenization and tagging would be needed here.
            # For now, inserting plain and then attempting to tag parts.
            
            idx = 0
            lines = json_string.split('\n')
            for line_num, line_content in enumerate(lines):
                # Insert the line
                self.textbox.insert(f"{line_num + 1}.0", line_content + "\n")
                
                # Example: Highlight keys on this line
                start_char = 0
                for m in re.finditer(key_pattern, line_content):
                    key_with_quotes = m.group(0) # This is "key":
                    key_start = m.start(0)
                    key_end = m.end(0)
                    # Apply tag to "key":
                    self.textbox.tag_add("key", f"{line_num + 1}.{key_start}", f"{line_num + 1}.{key_end}")

                # Example: Highlight string values
                string_pattern = r':\s*\"([^\"]*)\"'
                for m in re.finditer(string_pattern, line_content):
                    val_start = m.start(1) # Group 1 is the content within quotes
                    val_end = m.end(1)
                    self.textbox.tag_add("string", f"{line_num + 1}.{val_start-1}", f"{line_num + 1}.{val_end+1}") # Add quotes to tag

                # Add more patterns for numbers, booleans, null similarly
                # ... (this is becoming a mini-parser, complex)
                
            # Fallback to inserting the whole string if the line-by-line regex is too complex for initial step
            # For the very first step, let's just insert the plain JSON to get the component integrated.
            # The highlighting logic will be iterative.
            # self.textbox.insert("1.0", json_string) # Fallback for now

        # For the very first step, let's just insert the plain JSON.
        # Highlighting will be refined in the next iteration of this subtask.
        # The above regex is getting complex.

        # Resetting to simple insert for now.
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", json_string)


if __name__ == '__main__':
    app = ctk.CTk()
    app.title("JSON View Test")
    app.geometry("700x500")

    json_view_frame = JsonViewFrame(app)
    json_view_frame.pack(fill="both", expand=True, padx=10, pady=10)

    test_data_valid = {
        "name": "Test Product",
        "version": 1.23,
        "active": True,
        "description": "This is a test object with various data types.",
        "tags": ["test", "example", "json"],
        "address": None,
        "meta": {
            "created_at": "2023-10-26T10:00:00Z",
            "dimensions": {"height": 10, "width": 20, "depth": 5.5}
        }
    }
    test_data_empty = {}
    test_data_none = None
    test_data_invalid_for_json_dumps = {"key": datetime.datetime.now()} # datetime is not directly serializable

    controls_frame = ctk.CTkFrame(app)
    controls_frame.pack(pady=10)

    ctk.CTkButton(controls_frame, text="Show Valid JSON", command=lambda: json_view_frame.set_json_data(test_data_valid)).pack(side="left", padx=5)
    ctk.CTkButton(controls_frame, text="Show Empty JSON", command=lambda: json_view_frame.set_json_data(test_data_empty)).pack(side="left", padx=5)
    ctk.CTkButton(controls_frame, text="Show None (Clear)", command=lambda: json_view_frame.set_json_data(test_data_none)).pack(side="left", padx=5)
    # ctk.CTkButton(controls_frame, text="Show Invalid Data", command=lambda: json_view_frame.set_json_data(test_data_invalid_for_json_dumps)).pack(side="left", padx=5)


    json_view_frame.set_json_data(test_data_valid) # Initial display

    app.mainloop() 