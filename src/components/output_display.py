import customtkinter as ctk
from .error_display import ErrorDisplayFrame
from .json_view import JsonViewFrame
from .chat_view import ChatViewFrame # Import the actual ChatViewFrame

class OutputDisplayFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0) # Controls/Status bar for truncation
        self.grid_columnconfigure(0, weight=1)

        self.current_view_mode = "json" # or "chat"
        self.current_data = None

        # View Toggle Frame
        self.toggle_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.toggle_frame.grid(row=0, column=0, padx=10, pady=(10,5), sticky="ew")

        self.json_button = ctk.CTkButton(self.toggle_frame, text="JSON View", command=lambda: self.switch_view("json"))
        self.json_button.pack(side="left", padx=5)

        self.chat_button = ctk.CTkButton(self.toggle_frame, text="Chat View", command=lambda: self.switch_view("chat"))
        self.chat_button.pack(side="left", padx=5)
        # self.chat_button.configure(state="disabled") # Until ChatView is ready

        # Content Frame (will hold JSON or Chat view)
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        self.json_view = JsonViewFrame(self.content_frame)
        self.chat_view = ChatViewFrame(self.content_frame) # Initialize ChatViewFrame
        # self.placeholder_chat_view = ctk.CTkLabel(self.content_frame, text="Chat View (Not Implemented)", font=ctk.CTkFont(size=16))

        # Bottom: Truncation Controls Frame (initially empty, populated by _update_truncation_controls)
        self.truncation_controls_frame = ctk.CTkFrame(self, fg_color="transparent", height=30)
        self.truncation_controls_frame.grid(row=2, column=0, padx=10, pady=(0,5), sticky="ew")
        self.truncation_status_label = ctk.CTkLabel(self.truncation_controls_frame, text="")
        self.view_full_json_button = ctk.CTkButton(self.truncation_controls_frame, text="Save Full JSON", command=self._save_full_json)
        self.save_full_chat_button = ctk.CTkButton(self.truncation_controls_frame, text="Save Full Chat", command=self._save_full_chat)

        # Error Display Frame (initially hidden, overlays content when active)
        self.error_display = ErrorDisplayFrame(self)
        self.error_display.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=10, pady=10)
        self.error_display.grid_remove() # Hide it initially

        self._update_button_states()
        self.switch_view(self.current_view_mode) # Show initial view
        self._update_truncation_controls() # Initial check

    def _save_full_json(self):
        if self.json_view:
            self.json_view._view_full_output() # Assuming this method now saves

    def _save_full_chat(self):
        if self.chat_view:
            self.chat_view.save_full_chat_data_to_file()

    def _update_truncation_controls(self):
        # Clear previous controls
        self.truncation_status_label.pack_forget()
        self.view_full_json_button.pack_forget()
        self.save_full_chat_button.pack_forget()
        self.truncation_controls_frame.grid_remove() # Hide if not needed

        show_bar = False
        status_text = ""

        if self.current_view_mode == "json" and self.json_view and self.json_view.is_truncated:
            status_text = self.json_view.status_label.cget("text") # Get text from JsonView's own status
            self.view_full_json_button.pack(side="right", padx=5)
            show_bar = True
        elif self.current_view_mode == "chat" and self.chat_view and self.chat_view.is_truncated:
            total_msgs = len(self.chat_view.full_chat_data) if self.chat_view.full_chat_data else 0
            displayed_msgs = len(self.chat_view._message_widgets)
            status_text = f"Chat truncated. Displaying {displayed_msgs} of {total_msgs} messages."
            self.save_full_chat_button.pack(side="right", padx=5)
            show_bar = True
        
        if show_bar:
            self.truncation_status_label.configure(text=status_text)
            self.truncation_status_label.pack(side="left", padx=5)
            self.truncation_controls_frame.grid() # Show the bar
        else:
            self.truncation_controls_frame.grid_remove()

    def switch_view(self, mode):
        self.current_view_mode = mode
        self._update_button_states()
        self.error_display.grid_remove() # Ensure error is hidden when switching views

        self.json_view.grid_remove()
        self.chat_view.grid_remove()

        if mode == "json":
            self.json_view.grid(row=0, column=0, sticky="nsew")
            if self.current_data:
                self.json_view.set_json_data(self.current_data.get("json_data"))
            else:
                self.json_view.clear_view()
        elif mode == "chat":
            self.chat_view.grid(row=0, column=0, sticky="nsew")
            if self.current_data:
                self.chat_view.set_chat_data(self.current_data.get("chat_data"))
            else:
                self.chat_view.clear_view()
        self._update_truncation_controls()
        
    def _update_button_states(self):
        json_fg = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        json_hover = ctk.ThemeManager.theme["CTkButton"]["hover_color"]
        chat_fg = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        chat_hover = ctk.ThemeManager.theme["CTkButton"]["hover_color"]

        if self.current_view_mode == "json":
            self.json_button.configure(fg_color=json_fg)
            self.chat_button.configure(fg_color=chat_hover) 
        elif self.current_view_mode == "chat":
            self.json_button.configure(fg_color=json_hover)
            self.chat_button.configure(fg_color=chat_fg)

    def set_data(self, data):
        """ data is expected to be a dict, e.g., {"json_data": {...}, "chat_data": [...]} """
        self.current_data = data
        self.error_display.grid_remove() # Clear any previous errors
        self.content_frame.grid() # Ensure content frame is visible
        
        if self.current_view_mode == "json":
            self.json_view.set_json_data(data.get("json_data"))
        elif self.current_view_mode == "chat":
            self.chat_view.set_chat_data(data.get("chat_data"))
        self._update_truncation_controls()

    def show_analysis_error(self, error_type: str, details: dict, retry_command=None):
        self.content_frame.grid_remove() # Hide content view
        self.truncation_controls_frame.grid_remove() # Hide truncation bar on error
        self.error_display.show_error(error_type=error_type, details=details, retry_command=retry_command)
        self.error_display.grid() # Ensure error display is visible

    def clear_output(self):
        self.current_data = None
        self.json_view.clear_view()
        self.chat_view.clear_view()
        self.error_display.clear_error()
        self.error_display.grid_remove()
        self.content_frame.grid() # Show content frame again
        self._update_truncation_controls()

if __name__ == '__main__':
    app = ctk.CTk()
    app.title("Output Display Test")
    app.geometry("800x650") # Slightly taller for truncation bar

    output_display = OutputDisplayFrame(app)
    output_display.pack(expand=True, fill="both", padx=10, pady=10)

    def mock_retry_analysis():
        print("Retrying analysis...")
        output_display.clear_output()
        app.after(1000, lambda: output_display.set_data({
            "json_data": {"status": "Retried successfully!", "result": "Some new data"},
            "chat_data": [{"sender":"System", "text":"Retry successful. Displaying new data."}]
        }))

    # Test Data
    sample_json_data = {"key1": "value1", "key2": list(range(10)), "nested": {"a":1, "b": "hello world "*10}}
    sample_chat_data = [
        {"sender": "Bot", "text": "Hello from the main display! How can I help?", "is_user": False},
        {"sender": "User", "text": "I'd like to see the chat view integration.", "is_user": True},
        {"sender": "Bot", "text": "Certainly! Here it is.", "is_user": False}
    ]
    
    # Data for truncation tests (using constants from respective view modules for consistency if possible)
    # For JsonViewFrame - it has its own MAX_DISPLAY_LINES/CHARS
    # from .json_view import MAX_DISPLAY_LINES as JSON_MAX_LINES # Would be ideal
    JSON_MAX_LINES_TEST = 30 # Smaller for quicker test display
    large_json_for_main_test = {f"item_{i}": f"Main display large string for item {i}. " * 5 for i in range(JSON_MAX_LINES_TEST + 20)} 
    
    # For ChatViewFrame - it has its own MAX_CHAT_MESSAGES
    # from .chat_view import MAX_CHAT_MESSAGES as CHAT_MAX_MESSAGES
    CHAT_MAX_MESSAGES_TEST = 20 # Smaller for quicker test display
    large_chat_for_main_test = [{
        "sender":f"Msg{i}", 
        "text":f"Message {i} in main display test for chat truncation.", 
        "is_user": i % 2 == 0
    } for i in range(CHAT_MAX_MESSAGES_TEST + 10)]

    def load_sample_data():
        output_display.set_data({"json_data": sample_json_data, "chat_data": sample_chat_data})

    def load_large_json_data(): # Test JSON truncation
        output_display.switch_view("json") # Ensure JSON view is active
        output_display.set_data({"json_data": large_json_for_main_test, "chat_data": sample_chat_data})

    def load_large_chat_data(): # Test Chat truncation
        output_display.switch_view("chat") # Ensure Chat view is active
        output_display.set_data({"json_data": sample_json_data, "chat_data": large_chat_for_main_test})

    def show_api_fail():
        output_display.show_analysis_error(
            error_type="api", 
            details={"status_code": 500, "error_message": "Internal Server Simulation Error", "endpoint": "/test/analyze"},
            retry_command=mock_retry_analysis
        )
    
    def show_parsing_fail():
        output_display.show_analysis_error(
            error_type="parsing",
            details={"error_type": "DataCorrupted", "details": "Missing crucial fields in input data", "file_source": "user_upload.csv"}
        )

    def clear_all_output():
        output_display.clear_output()

    controls = ctk.CTkFrame(app)
    controls.pack(pady=10)
    ctk.CTkButton(controls, text="Load Sample Data", command=load_sample_data).pack(side="left", padx=5)
    ctk.CTkButton(controls, text="Load Large JSON", command=load_large_json_data).pack(side="left", padx=5)
    ctk.CTkButton(controls, text="Load Large Chat", command=load_large_chat_data).pack(side="left", padx=5)
    ctk.CTkButton(controls, text="Simulate API Error", command=show_api_fail).pack(side="left", padx=5)
    ctk.CTkButton(controls, text="Simulate Parsing Error", command=show_parsing_fail).pack(side="left", padx=5)
    ctk.CTkButton(controls, text="Clear Output", command=clear_all_output).pack(side="left", padx=5)

    app.mainloop() 