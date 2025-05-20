import customtkinter as ctk
import json
from tkinter import filedialog, messagebox

MAX_DISPLAY_CHARS = 50000  # Max characters to display before truncating
MAX_DISPLAY_LINES = 1000   # Max lines to display before truncating

class JsonViewFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.textbox = ctk.CTkTextbox(self, wrap="word", font=("Courier New", 12))
        self.textbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.textbox.configure(state="disabled")

        self.full_json_data = None
        self.is_truncated = False

        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0,5))

        self.status_label = ctk.CTkLabel(self.controls_frame, text="")
        self.status_label.pack(side="left", padx=5)

        self.view_full_button = ctk.CTkButton(self.controls_frame, text="View Full Output", command=self._view_full_output)
        # self.view_full_button will be packed if needed

    def set_json_data(self, data):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.view_full_button.pack_forget()
        self.status_label.configure(text="")
        self.is_truncated = False

        if data is None:
            self.textbox.insert("1.0", "No JSON data to display.")
            self.full_json_data = None
            self.textbox.configure(state="disabled")
            return

        try:
            self.full_json_data = json.dumps(data, indent=2)
        except TypeError as e:
            self.textbox.insert("1.0", f"Error: Could not serialize data to JSON.\n{e}")
            self.full_json_data = None
            self.textbox.configure(state="disabled")
            return

        num_chars = len(self.full_json_data)
        num_lines = self.full_json_data.count('\n') + 1

        display_text = self.full_json_data

        if num_chars > MAX_DISPLAY_CHARS or num_lines > MAX_DISPLAY_LINES:
            self.is_truncated = True
            # Truncate by lines first, then by characters if still too long
            lines = self.full_json_data.splitlines()
            if num_lines > MAX_DISPLAY_LINES:
                display_text = "\n".join(lines[:MAX_DISPLAY_LINES])
            
            if len(display_text) > MAX_DISPLAY_CHARS:
                display_text = display_text[:MAX_DISPLAY_CHARS]
            
            display_text += "\n\n... (Content Truncated)"
            self.status_label.configure(text=f"Output truncated. Showing ~{MAX_DISPLAY_LINES if num_lines > MAX_DISPLAY_LINES else num_lines} lines / ~{MAX_DISPLAY_CHARS if len(display_text) > MAX_DISPLAY_CHARS else len(display_text)} chars.")
            self.view_full_button.pack(side="right", padx=5)
        else:
            self.status_label.configure(text=f"{num_lines} lines / {num_chars} chars.")

        self.textbox.insert("1.0", display_text)
        self.textbox.configure(state="disabled")

    def _view_full_output(self):
        if not self.full_json_data:
            messagebox.showinfo("No Data", "No full JSON data available to display.")
            return

        # Option 1: Save to file
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("Text files", "*.txt"), ("All files", "*.*")],
            title="Save Full JSON Output"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.full_json_data)
                messagebox.showinfo("Saved", f"Full JSON output saved to {file_path}")
            except Exception as e:
                messagebox.showerror("Save Failed", f"Could not save file: {e}")
        
        # Option 2: Open in a new simple window (can be added if preferred)
        # self._open_full_output_window()

    # def _open_full_output_window(self):
    #     top = ctk.CTkToplevel(self)
    #     top.title("Full JSON Output")
    #     top.geometry("800x600")
    #     text_area = ctk.CTkTextbox(top, wrap="word", font=("Courier New", 12))
    #     text_area.pack(expand=True, fill="both", padx=10, pady=10)
    #     text_area.insert("1.0", self.full_json_data)
    #     text_area.configure(state="disabled")
    #     top.grab_set() # Make it modal

    def clear_view(self):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")
        self.full_json_data = None
        self.is_truncated = False
        self.status_label.configure(text="")
        self.view_full_button.pack_forget()


if __name__ == '__main__':
    app = ctk.CTk()
    app.geometry("700x500")
    app.title("JSON View Test")

    json_view = JsonViewFrame(app)
    json_view.pack(expand=True, fill="both", padx=10, pady=10)

    # Sample Data
    small_data = {"name": "John Doe", "age": 30, "city": "New York"}
    medium_data = {f"key_{i}": f"value_{i} - " + "long string for testing purposes " * 5 for i in range(200)}
    very_large_list = [f"This is line number {i} of a very long list of strings. " * 3 for i in range(MAX_DISPLAY_LINES + 500)]
    very_large_data = { "data": very_large_list, "metadata": {"source": "test_generator", "count": len(very_large_list)}}
    malformed_data_obj = {"data": lambda x: x} # Unserializable

    def show_small():
        json_view.set_json_data(small_data)

    def show_medium():
        json_view.set_json_data(medium_data)

    def show_large():
        json_view.set_json_data(very_large_data)
        
    def show_malformed():
        json_view.set_json_data(malformed_data_obj)
        
    def show_none():
        json_view.set_json_data(None)

    def clear_all():
        json_view.clear_view()

    controls = ctk.CTkFrame(app)
    controls.pack(pady=10)
    ctk.CTkButton(controls, text="Show Small JSON", command=show_small).pack(side="left", padx=5)
    ctk.CTkButton(controls, text="Show Medium JSON", command=show_medium).pack(side="left", padx=5)
    ctk.CTkButton(controls, text="Show Large JSON", command=show_large).pack(side="left", padx=5)
    ctk.CTkButton(controls, text="Show Malformed", command=show_malformed).pack(side="left", padx=5)
    ctk.CTkButton(controls, text="Show None", command=show_none).pack(side="left", padx=5)
    ctk.CTkButton(controls, text="Clear", command=clear_all).pack(side="left", padx=5)

    app.mainloop() 