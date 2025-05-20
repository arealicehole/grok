import customtkinter as ctk
from tkinter import messagebox
from src.utils import error_templates # Import the templates

class ErrorDisplayFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color="transparent") # Or a distinct error background
        self.grid_columnconfigure(1, weight=1)

        self.icon_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=20))
        self.icon_label.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="n")

        self.title_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=16, weight="bold"))
        self.title_label.grid(row=0, column=1, padx=(0,10), pady=(10,5), sticky="nw")

        self.message_textbox = ctk.CTkTextbox(self, wrap="word", height=60)
        self.message_textbox.grid(row=1, column=1, padx=(0,10), pady=(0,10), sticky="nsew")
        self.message_textbox.configure(state="disabled")

        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(row=2, column=1, padx=(0,10), pady=(0,10), sticky="ew")
        
        self.copy_button = ctk.CTkButton(self.button_frame, text="Copy Details", command=self._copy_details)
        self.retry_button = ctk.CTkButton(self.button_frame, text="Retry")
        
        self.grid_remove()

    def _copy_details(self):
        error_title = self.title_label.cget("text")
        error_message = self.message_textbox.get("1.0", "end-1c")
        full_error_details = f"Error: {error_title}\n\n{error_message}"
        
        try:
            self.clipboard_clear()
            self.clipboard_append(full_error_details)
            messagebox.showinfo("Copied", "Error details copied to clipboard.")
        except Exception as e:
            messagebox.showerror("Copy Failed", f"Could not copy to clipboard: {e}")

    def show_error(self, error_type: str, details: dict, icon="⚠️", retry_command=None):
        """ 
        Displays an error using a predefined template.
        error_type: 'api', 'parsing', 'large_output', 'generic'
        details: A dictionary of arguments for the corresponding format function.
        icon: Emoji icon for the error.
        retry_command: Optional command to execute when retry button is pressed.
        """
        title, message = "Error", "An unknown error occurred."

        if error_type == "api":
            title, message = error_templates.format_api_error(**details)
        elif error_type == "parsing":
            title, message = error_templates.format_parsing_error(**details)
        elif error_type == "large_output":
            title, message = error_templates.format_large_output_error(**details)
            icon = "🔔" # Suggest a different icon for warnings/info
        elif error_type == "generic":
            title, message = error_templates.format_generic_error(**details)
        
        self.title_label.configure(text=title)
        self.icon_label.configure(text=icon)
        
        self.message_textbox.configure(state="normal")
        self.message_textbox.delete("1.0", "end")
        self.message_textbox.insert("1.0", message)
        self.message_textbox.configure(state="disabled")

        # Ensure buttons are reset before potentially repacking
        self.copy_button.pack_forget()
        self.retry_button.pack_forget()

        self.copy_button.pack(side="left", padx=(0,5)) # Always show copy button

        if retry_command:
            self.retry_button.configure(command=retry_command)
            self.retry_button.pack(side="left")
        
        self.grid() 

    def clear_error(self):
        self.grid_remove()
        self.title_label.configure(text="")
        self.message_textbox.configure(state="normal")
        self.message_textbox.delete("1.0", "end")
        self.message_textbox.configure(state="disabled")
        self.icon_label.configure(text="")
        self.retry_button.pack_forget()
        self.copy_button.pack_forget()

if __name__ == '__main__':
    app = ctk.CTk()
    app.geometry("500x400") # Increased size for better visibility
    
    error_frame = ErrorDisplayFrame(app)
    error_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10) # Grid it for the test app
    error_frame.grid_remove() # But hide it initially as per default behavior

    def test_retry_action():
        print("Retry action initiated!")
        error_frame.clear_error()

    # Test buttons frame
    test_buttons_frame = ctk.CTkFrame(app)
    test_buttons_frame.grid(row=1, column=0, pady=20)

    show_api_error_btn = ctk.CTkButton(
        test_buttons_frame, 
        text="Show API Error", 
        command=lambda: error_frame.show_error(
            error_type="api", 
            details={"status_code": 503, "error_message": "Service Unavailable", "endpoint": "/v1/process"},
            icon="❌", 
            retry_command=test_retry_action
        )
    )
    show_api_error_btn.pack(pady=5)

    show_parsing_error_btn = ctk.CTkButton(
        test_buttons_frame, 
        text="Show Parsing Error", 
        command=lambda: error_frame.show_error(
            error_type="parsing",
            details={"error_type": "JSONDecodeError", "details": "Unexpected 'EOF' while parsing", "file_source": "input.json"},
            icon="🧩"
        )
    )
    show_parsing_error_btn.pack(pady=5)

    show_large_output_error_btn = ctk.CTkButton(
        test_buttons_frame, 
        text="Show Large Output Error", 
        command=lambda: error_frame.show_error(
            error_type="large_output",
            details={"output_size_kb": 2056.7, "limit_kb": 1024.0, "content_type": "Analysis Report"},
            # icon will be overridden by the show_error method for large_output
        )
    )
    show_large_output_error_btn.pack(pady=5)
    
    show_generic_error_btn = ctk.CTkButton(
        test_buttons_frame, 
        text="Show Generic Error", 
        command=lambda: error_frame.show_error(
            error_type="generic",
            details={"custom_title": "Configuration Missing", "custom_message": "The 'settings.ini' file was not found or is corrupted."},
            icon="⚙️",
            retry_command=test_retry_action
        )
    )
    show_generic_error_btn.pack(pady=5)

    clear_error_btn = ctk.CTkButton(test_buttons_frame, text="Clear Error Display", command=error_frame.clear_error)
    clear_error_btn.pack(pady=10)

    app.mainloop() 