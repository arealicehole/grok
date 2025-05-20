import customtkinter as ctk
import datetime

class ChatMessageWidget(ctk.CTkFrame):
    def __init__(self, master, sender: str, text: str, timestamp: str = None, is_user: bool = False, **kwargs):
        super().__init__(master, **kwargs)

        # Determine alignment and colors based on sender
        # (Simplified: is_user determines alignment for now)
        anchor = "e" if is_user else "w"
        # Dynamic fg_color based on appearance mode and sender
        # fg_color_user_light = "#DCF8C6" # Light green (like WhatsApp user message)
        # fg_color_other_light = "#FFFFFF"
        # fg_color_user_dark = "#056162"  # Darker teal
        # fg_color_other_dark = "#2b2b2b"

        # Using CTk theme-aware colors if possible, or fallback
        # For simplicity, let's use a slightly different shade for user vs other.
        # These can be refined with more specific theme colors.
        if is_user:
            self.configure(fg_color=("gray70", "gray25")) # Slightly different for user
        else:
            self.configure(fg_color=("gray80", "gray30")) # Default frame color or slight variation
        
        self.grid_columnconfigure(0, weight=1)

        # Sender Label (Optional, could be part of message text or implicit)
        # For now, let's make it bold within the text_label for simplicity
        # sender_label = ctk.CTkLabel(self, text=sender, font=ctk.CTkFont(weight="bold"))
        # sender_label.grid(row=0, column=0, padx=10, pady=(5,0), sticky="w")

        # Message Text
        # Using CTkTextbox for potentially selectable text and easier multi-line handling
        self.text_widget = ctk.CTkTextbox(self, wrap="word", activate_scrollbars=False, font=("Arial", 13))
        self.text_widget.insert("1.0", f"{sender}:\n{text}") # Basic sender prefix
        self.text_widget.configure(state="disabled")
        self.text_widget.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        
        # Calculate height based on content dynamically (simplified)
        self.text_widget.update_idletasks() # Ensure widget dimensions are calculated
        num_lines = int(self.text_widget.index("end-1c").split('.')[0])
        # Estimate line height, this is an approximation
        # A more robust way would be to use font metrics
        estimated_line_height = ctk.CTkFont(font=("Arial", 13)).metrics('linespace') 
        if estimated_line_height < 15: estimated_line_height = 20 # Fallback if metrics are odd
        
        padding = 10 # Vertical padding in textbox
        new_height = (num_lines * estimated_line_height) + (2 * padding) 
        # Min/Max height for messages
        new_height = max(50, min(new_height, 300))
        self.text_widget.configure(height=new_height)

        # Timestamp (Optional)
        if timestamp:
            timestamp_label = ctk.CTkLabel(self, text=timestamp, font=ctk.CTkFont(size=9), text_color=("gray50", "gray60"))
            timestamp_label.grid(row=1, column=0, padx=10, pady=(0,5), sticky="e")


class ChatViewFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._message_widgets = []

    def add_message(self, sender: str, text: str, timestamp: str = None, is_user: bool = False):
        """Adds a single message to the chat view."""
        
        # Determine alignment based on sender (is_user)
        # If it's a user message, it will be packed to the right, otherwise to the left.
        # We achieve this by using a container frame that spans the width,
        # and then placing the message widget within that container, anchored appropriately.
        
        # Outer frame to control horizontal placement within the scrollable area
        # This outer frame will take the full width of the scrollable area.
        # The actual message bubble (ChatMessageWidget) will be narrower and placed inside this.
        
        # Max width for message bubbles (e.g., 70-80% of chat view width)
        # For simplicity, we'll let the ChatMessageWidget define its own padding for now.
        # The sticky setting on the message_widget will handle if it expands or not.

        # Create the message widget
        message_widget = ChatMessageWidget(self, sender, text, timestamp, is_user)
        
        # Pack the message widget with appropriate anchoring
        if is_user:
            # User messages align to the right
            message_widget.pack(fill="x", padx=(50, 10), pady=5) # Indent from left
        else:
            # Other messages align to the left
            message_widget.pack(fill="x", padx=(10, 50), pady=5) # Indent from right
            
        self._message_widgets.append(message_widget)
        self._scroll_to_bottom()

    def set_chat_data(self, data: list):
        """Clears existing messages and displays new chat data.

        Args:
            data: A list of message dictionaries. 
                  Each dict should have 'sender' (str) and 'text' (str) keys.
                  Optional: 'timestamp' (str), 'is_user' (bool).
        """
        # Clear existing messages
        for widget in self._message_widgets:
            widget.destroy()
        self._message_widgets = []

        if data is None or not isinstance(data, list):
            # Display a placeholder if no data or incorrect format
            placeholder = ctk.CTkLabel(self, text="No chat data to display or data is in incorrect format.")
            placeholder.pack(pady=20)
            self._message_widgets.append(placeholder) # Keep track to clear later
            return

        for msg_data in data:
            if not isinstance(msg_data, dict):
                print(f"Warning: Skipping invalid message data item: {msg_data}")
                continue
            
            sender = msg_data.get("sender", "Unknown")
            text = msg_data.get("text", "")
            timestamp = msg_data.get("timestamp")
            is_user = msg_data.get("is_user", False)
            
            self.add_message(sender, text, timestamp, is_user)
        
        if not data: # If data was an empty list
            placeholder = ctk.CTkLabel(self, text="No messages in this chat.")
            placeholder.pack(pady=20)
            self._message_widgets.append(placeholder)

    def _scroll_to_bottom(self):
        # Ensure layout is updated, then scroll
        self.update_idletasks()
        self._parent_canvas.yview_moveto(1.0)


if __name__ == '__main__':
    app = ctk.CTk()
    app.title("Chat View Test")
    app.geometry("700x600")

    chat_view_frame = ChatViewFrame(app)
    chat_view_frame.pack(fill="both", expand=True, padx=10, pady=10)

    test_messages = [
        {"sender": "Alice", "text": "Hello Bob! How are you today?", "timestamp": "10:00 AM"},
        {"sender": "Bob", "text": "Hi Alice! I'm doing great, thanks for asking. Just working on this new project.", "timestamp": "10:01 AM", "is_user": True},
        {"sender": "Alice", "text": "Oh, exciting! What kind of project is it?" + " This is a longer message to test wrapping and multiple lines to see how the height calculation works out. It should ideally expand the bubble.", "timestamp": "10:02 AM"},
        {"sender": "System", "text": "User Bob has been marked as active.", "timestamp": "10:02 AM"},
        {"sender": "Bob", "text": "It's a Python application with a CustomTkinter GUI. Trying to make it look nice!", "timestamp": "10:03 AM", "is_user": True},
        {"sender": "Alice", "text": "Sounds cool! Let me know if you need any help or want to bounce ideas.", "timestamp": "10:04 AM"},
    ]

    chat_view_frame.set_chat_data(test_messages)

    # Test adding messages dynamically
    def add_another_message():
        timestamp = datetime.datetime.now().strftime("%I:%M %p") # Corrected strftime
        chat_view_frame.add_message("Charlie", "Just joined the chat! What did I miss?", timestamp=timestamp, is_user=False)
        
    def add_user_message():
        timestamp = datetime.datetime.now().strftime("%I:%M %p") # Corrected strftime
        chat_view_frame.add_message("Bob", "This is another message from me, testing dynamic add!", timestamp=timestamp, is_user=True)

    controls_frame = ctk.CTkFrame(app)
    controls_frame.pack(pady=10)
    ctk.CTkButton(controls_frame, text="Add Other Message", command=add_another_message).pack(side="left", padx=5)
    ctk.CTkButton(controls_frame, text="Add User Message", command=add_user_message).pack(side="left", padx=5)
    ctk.CTkButton(controls_frame, text="Clear and Set Original", command=lambda: chat_view_frame.set_chat_data(test_messages)).pack(side="left", padx=5)
    ctk.CTkButton(controls_frame, text="Set Empty Data", command=lambda: chat_view_frame.set_chat_data([])).pack(side="left", padx=5)
    ctk.CTkButton(controls_frame, text="Set None Data", command=lambda: chat_view_frame.set_chat_data(None)).pack(side="left", padx=5)


    app.mainloop() 