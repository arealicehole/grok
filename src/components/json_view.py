import customtkinter as ctk
import tkinter
import json
import tkinter.messagebox # Added for success message
from src.components.json_tokenizer import JsonTokenizer, Token, JsonTokenType # Added import
from typing import Any

class JsonViewFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.textbox = ctk.CTkTextbox(self, wrap="none", state="disabled", corner_radius=0)
        self.textbox.grid(row=0, column=0, sticky="nsew")

        self.tokenizer = JsonTokenizer()
        self.current_json_string = ""
        self.json_syntax_error_details: dict | None = None # Store error details like {'message': str, 'lineno': int, 'colno': int, 'pos': int}
        
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
        mode = ctk.get_appearance_mode()
        # Color definitions: (Light Mode, Dark Mode)
        # Using more distinct dark mode colors
        colors = {
            JsonTokenType.KEY.name: ("#A31515", "#9CDCFE"),          # DarkRed (Light) / LightBlue (Dark)
            JsonTokenType.STRING.name: ("#A31515", "#CE9178"),       # DarkRed (Light) / Orange-ish (Dark)
            JsonTokenType.NUMBER.name: ("#098658", "#B5CEA8"),       # DarkGreen (Light) / LightGreen-ish (Dark)
            JsonTokenType.BOOLEAN.name: ("#0000FF", "#569CD6"),      # Blue (Light) / Blue (Dark)
            JsonTokenType.NULL.name: ("#0000FF", "#569CD6"),         # Blue (Light) / Blue (Dark)
            JsonTokenType.LBRACE.name: ("#000000", "#D4D4D4"),       # Black (Light) / LightGray (Dark)
            JsonTokenType.RBRACE.name: ("#000000", "#D4D4D4"),       # Black (Light) / LightGray (Dark)
            JsonTokenType.LBRACKET.name: ("#000000", "#D4D4D4"),     # Black (Light) / LightGray (Dark)
            JsonTokenType.RBRACKET.name: ("#000000", "#D4D4D4"),     # Black (Light) / LightGray (Dark)
            JsonTokenType.COMMA.name: ("#000000", "#D4D4D4"),        # Black (Light) / LightGray (Dark)
            JsonTokenType.COLON.name: ("#000000", "#D4D4D4"),        # Black (Light) / LightGray (Dark)
            JsonTokenType.ERROR.name: ("#FF0000", "#F44747"),        # Red (Light) / LightRed (Dark)
            "JSON_SYNTAX_ERROR": ("#FF0000", "#FF0000"), # Red underline or distinct background
        }

        for token_type_name, color_pair in colors.items():
            chosen_color = color_pair[1] if mode == "Dark" else color_pair[0]
            if token_type_name == "JSON_SYNTAX_ERROR":
                 # For syntax errors, let's use a background or very distinct color
                error_fg = "#FFFFFF" if mode == "Dark" else "#000000"
                error_bg = chosen_color
                self.textbox.tag_config(token_type_name, foreground=error_fg, background=error_bg)
                # CTkTextbox might not support underline directly in tag_config in all versions/OS
                # self.textbox.tag_config(token_type_name, underline=True, foreground=chosen_color)
            else:
                self.textbox.tag_config(token_type_name, foreground=chosen_color)

    def display_json(self, data: Any):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.json_syntax_error_details = None # Reset error details

        temp_json_string = ""
        if isinstance(data, str):
            temp_json_string = data
            try:
                # Validate and reformat if it's a valid JSON string
                parsed_data = json.loads(data)
                self.current_json_string = json.dumps(parsed_data, indent=4)
            except json.JSONDecodeError as e:
                # If it's a string but not valid JSON, store error and use the string as is for tokenization
                self.json_syntax_error_details = {'message': e.msg, 'lineno': e.lineno, 'colno': e.colno, 'pos': e.pos}
                self.current_json_string = data # Keep original erroneous string
        elif isinstance(data, (dict, list)):
            try:
                self.current_json_string = json.dumps(data, indent=4)
            except TypeError as e:
                self.current_json_string = f"Error: Could not serialize data to JSON. {e}"
                self.textbox.insert("1.0", self.current_json_string)
                self.textbox.configure(state="disabled")
                return
        else:
            self.current_json_string = str(data) # Fallback for other types

        # Final check for syntax errors on the string that will be rendered
        # This catches errors if input was dict/list that stringified to bad JSON,
        # or if an already-erroneous string was passed and not caught above.
        if not self.json_syntax_error_details: # Only check if no error found yet
            try:
                json.loads(self.current_json_string) # Just to validate
            except json.JSONDecodeError as e:
                self.json_syntax_error_details = {'message': e.msg, 'lineno': e.lineno, 'colno': e.colno, 'pos': e.pos}
        
        self._configure_tags() # Ensure tags are up-to-date with current theme

        tokens = self.tokenizer.tokenize(self.current_json_string)
        self._apply_highlighting(tokens, self.current_json_string)
        
        self.textbox.configure(state="disabled")
        self.textbox.see("1.0") # Scroll to top

    def _apply_highlighting(self, tokens: list[Token], json_string: str):
        self.textbox.configure(state="normal") # Ensure textbox is enabled for modification
        self.textbox.delete("1.0", "end") # Clear previous content
        self.textbox.insert("1.0", json_string) # Insert the entire string at once

        for token in tokens:
            if token.type == JsonTokenType.WHITESPACE: # Skip applying style to whitespace tokens
                continue
            
            start_index = f"1.0 + {token.start_pos}c"
            end_index = f"1.0 + {token.end_pos}c"
            try:
                self.textbox.tag_add(token.type.name, start_index, end_index)
            except tkinter.TclError as e:
                print(f"Error applying tag {token.type.name} from {start_index} to {end_index}: {e}")

        if self.json_syntax_error_details:
            error_pos = self.json_syntax_error_details['pos']
            # Ensure error_pos is within the bounds of the string
            if 0 <= error_pos < len(json_string):
                error_start_tk_idx = f"1.0 + {error_pos}c"
                error_end_tk_idx = f"1.0 + {error_pos + 1}c" # Highlight one character
                
                try:
                    self.textbox.tag_add("JSON_SYNTAX_ERROR", error_start_tk_idx, error_end_tk_idx)
                    self.textbox.see(error_start_tk_idx) # Scroll to the error
                except tkinter.TclError as e:
                    # This can happen if line/col from json.loads is off due to how text widget handles lines/tabs
                    print(f"Error applying syntax error tag at {error_start_tk_idx}: {e}")
            elif error_pos == len(json_string) and len(json_string) > 0 : # Error at the very end (e.g. unexpected EOF)
                error_start_tk_idx = f"1.0 + {error_pos -1}c" # Highlight the last character before EOF
                error_end_tk_idx = f"1.0 + {error_pos}c"
                try:
                    self.textbox.tag_add("JSON_SYNTAX_ERROR", error_start_tk_idx, error_end_tk_idx)
                    self.textbox.see(error_start_tk_idx) # Scroll to the error
                except tkinter.TclError as e:
                     print(f"Error applying syntax error tag at EOF {error_start_tk_idx}: {e}")
            else:
                print(f"Syntax error position {error_pos} is out of bounds for string length {len(json_string)}.")
        
        # self.textbox.configure(state="disabled") # Already handled by display_json

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
    test_data_syntax_error_str = '{"name": "Test", "version": 1.2, "active": tru "description": null}' # Error: tru instead of true
    test_data_syntax_error_unterm_str = '{"name": "Test", "value": "unterminated string }'

    controls_frame = ctk.CTkFrame(app)
    controls_frame.pack(pady=10)

    ctk.CTkButton(controls_frame, text="Show Valid JSON", command=lambda: json_view_frame.display_json(test_data_valid)).pack(side="left", padx=5)
    ctk.CTkButton(controls_frame, text="Show Empty JSON", command=lambda: json_view_frame.display_json(test_data_empty)).pack(side="left", padx=5)
    ctk.CTkButton(controls_frame, text="Show None (Clear)", command=lambda: json_view_frame.display_json(test_data_none)).pack(side="left", padx=5)
    ctk.CTkButton(controls_frame, text="Syntax Error (tru)", command=lambda: json_view_frame.display_json(test_data_syntax_error_str)).pack(side="left", padx=5)
    ctk.CTkButton(controls_frame, text="Syntax Error (Unterm Str)", command=lambda: json_view_frame.display_json(test_data_syntax_error_unterm_str)).pack(side="left", padx=5)

    json_view_frame.display_json(test_data_valid) # Initial display

    app.mainloop() 