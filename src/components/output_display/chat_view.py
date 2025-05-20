import customtkinter as ctk
from tkinter import filedialog, messagebox # Added filedialog
import json # For saving structured chat data

MAX_CHAT_MESSAGES = 100  # Example limit for the number of messages to display
MAX_MESSAGE_LENGTH = 2000 # Example limit for individual message length

class ChatViewFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._message_widgets = []
        self.is_truncated = False
        self.full_chat_data = None

        # A frame at the bottom for status messages or "View Full Chat" button
        self.status_controls_frame = ctk.CTkFrame(self, fg_color="transparent") 
        # This frame won't be packed here, but by the parent OutputDisplayFrame if needed,
        # or we can pack it at the bottom of the scrollable area if preferred.

        self.status_label = ctk.CTkLabel(self.status_controls_frame, text="")
        # self.status_label.pack(side="left", padx=5) 

        self.view_full_chat_button = ctk.CTkButton(self.status_controls_frame, text="View Full Chat", command=self._view_full_chat_data)
        # self.view_full_chat_button.pack(side="right", padx=5)

    def _add_message_widget(self, sender: str, text: str, is_user: bool = False):
        """Internal method to create and add a message widget to the view."""
        # Simple display: A frame containing a label for each message
        # More complex layouts (like actual chat bubbles) would involve more detailed widget construction here.
        
        # Determine alignment and color based on whether the message is from the user
        anchor = "e" if is_user else "w"
        frame_fg_color = ("#DBF4FF", "#2B5A7B") if is_user else ("gray85", "gray25")
        text_anchor = "e" if is_user else "w"
        # padx for message container to achieve bubble effect
        container_padx = (50, 5) if is_user else (5, 50) 

        message_container_frame = ctk.CTkFrame(self, fg_color="transparent")
        message_container_frame.pack(fill="x", padx=5, pady=2)

        bubble_frame = ctk.CTkFrame(message_container_frame, fg_color=frame_fg_color, corner_radius=10)
        # Pack the bubble frame to the right if user, left otherwise
        bubble_frame.pack(anchor=anchor, padx=container_padx, pady=2, ipadx=5, ipady=3)

        label = ctk.CTkLabel(bubble_frame, text=f"{text}", wraplength=self.winfo_width()*0.65, justify="left", anchor=text_anchor)
        label.pack(padx=5, pady=2, expand=True, fill="x")
        
        # Store the top-level container for easy removal
        self._message_widgets.append(message_container_frame) 

    def _scroll_to_bottom(self):
        self.update_idletasks()
        self._parent_canvas.yview_moveto(1.0)

    def set_chat_data(self, chat_data_list: list):
        """Clears and populates the chat view with a list of message dictionaries.
        Each dict: {"sender": str, "text": str, "is_user": bool (optional)}
        """ 
        self.clear_view()
        self.full_chat_data = chat_data_list.copy() if chat_data_list else []
        self.is_truncated = False
        # self.status_label.configure(text="") # Clear status
        # self.view_full_chat_button.pack_forget() # Hide button

        if not chat_data_list:
            self._add_message_widget("System", "No chat data to display.")
            return

        display_list = self.full_chat_data
        truncation_message_added = False

        if len(self.full_chat_data) > MAX_CHAT_MESSAGES:
            display_list = self.full_chat_data[:MAX_CHAT_MESSAGES]
            self.is_truncated = True

        for i, msg_data in enumerate(display_list):
            sender = msg_data.get("sender", "Unknown")
            text = msg_data.get("text", "")
            is_user = msg_data.get("is_user", False)
            
            current_message_truncated = False
            if len(text) > MAX_MESSAGE_LENGTH:
                text = text[:MAX_MESSAGE_LENGTH] + "... (Message Truncated)"
                self.is_truncated = True # Overall chat is considered truncated if any message is
                current_message_truncated = True

            # If the entire chat list is truncated and this is the last message to be shown from that truncation
            if self.is_truncated and not current_message_truncated and i == len(display_list) - 1 and len(self.full_chat_data) > MAX_CHAT_MESSAGES:
                text += "\n... (Chat Truncated - Too many messages)"
                truncation_message_added = True

            self._add_message_widget(sender=sender, text=text, is_user=is_user)
        
        if self.is_truncated and not truncation_message_added and len(display_list) > 0 and len(self.full_chat_data) <= MAX_CHAT_MESSAGES:
            # This case handles when only individual messages were truncated, but not the overall list length
            # We might want a general status or just rely on individual message truncation notices.
            # For now, just print a debug message.
            print("Chat has individually truncated messages.")

        if self.is_truncated:
            print(f"Chat was truncated. Total messages: {len(self.full_chat_data)}, Displayed: {len(display_list)}")
            # Here you would typically show the status_label and view_full_chat_button
            # For example, by packing them into self.status_controls_frame which parent would display.
            # self.status_label.configure(text=f"Showing {len(display_list)} of {len(self.full_chat_data)} messages.")
            # self.status_label.pack(side="left", padx=5) 
            # self.view_full_chat_button.pack(side="right", padx=5)

        self._scroll_to_bottom()

    def _view_full_chat_data(self):
        # This method would be responsible for showing the full chat data,
        # e.g., by opening a new window or saving to a file, similar to JsonViewFrame.
        # For now, just a placeholder.
        if self.full_chat_data:
            messagebox.showinfo("Full Chat Data", f"Full chat has {len(self.full_chat_data)} messages. (Display not implemented)")
        else:
            messagebox.showinfo("No Data", "No full chat data available.")

    def save_full_chat_data_to_file(self):
        """Saves the full, untruncated chat data to a file."""
        if not self.full_chat_data:
            messagebox.showinfo("No Data", "No full chat data available to save.")
            return False

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json", # Save as JSON to preserve structure, or .txt for plain
            filetypes=[("JSON files", "*.json"), ("Text files", "*.txt"), ("All files", "*.*")],
            title="Save Full Chat Log"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    if file_path.endswith(".json"):
                        json.dump(self.full_chat_data, f, indent=2)
                    else: # Save as plain text
                        for msg in self.full_chat_data:
                            f.write(f"{msg.get('sender', 'Unknown')}: {msg.get('text', '')}\n")
                messagebox.showinfo("Saved", f"Full chat log saved to {file_path}")
                return True
            except Exception as e:
                messagebox.showerror("Save Failed", f"Could not save file: {e}")
                return False
        return False

    def clear_view(self):
        for widget in self._message_widgets:
            widget.destroy()
        self._message_widgets = []
        self.is_truncated = False
        self.full_chat_data = None
        # if hasattr(self, 'status_label'): self.status_label.configure(text="")
        # if hasattr(self, 'view_full_chat_button'): self.view_full_chat_button.pack_forget()

if __name__ == '__main__':
    app = ctk.CTk()
    app.geometry("600x700") # Wider for better chat bubble display
    app.title("Chat View Test")

    chat_view = ChatViewFrame(app)
    chat_view.pack(expand=True, fill="both", padx=10, pady=10)

    # For testing the status controls, if they were part of ChatViewFrame directly:
    # chat_view.status_controls_frame.pack(side="bottom", fill="x", pady=5, padx=10)

    sample_messages = [
        {"sender": "Alice", "text": "Hello Bob! How are you doing today? This is a slightly longer message to test wrapping and bubble appearance.", "is_user":False},
        {"sender": "Bob", "text": "Hi Alice! I'm doing great, thanks for asking. Just working on some CustomTkinter stuff. It's quite interesting!", "is_user": True},
        {"sender": "Alice", "text": "Oh cool! What are you building? I heard CTk is good for modern UIs.", "is_user":False},
        {"sender": "System", "text": "This is a system message. It might have a different style or no specific sender alignment if it's neutral.", "is_user":False}
    ]

    long_message_text = "This is an extremely long message designed to test the individual message length truncation feature. It keeps going and going " * 100 + " The end of the very long message."
    sample_messages_with_long = sample_messages[:2] + [{"sender": "Charlie", "text": long_message_text, "is_user":False}] + sample_messages[2:]
    
    too_many_messages = []
    for i in range(MAX_CHAT_MESSAGES + 20):
        too_many_messages.append({
            "sender": f"User {i+1}", 
            "text": f"This is message number {i+1} in a very long list of messages. We are testing truncation of the overall message list.", 
            "is_user": i % 3 == 0
        })

    def load_sample():
        chat_view.set_chat_data(sample_messages)
        
    def load_with_long_message():
        chat_view.set_chat_data(sample_messages_with_long)
        
    def load_too_many():
        chat_view.set_chat_data(too_many_messages)

    def clear_chat():
        chat_view.clear_view()

    controls = ctk.CTkFrame(app)
    controls.pack(pady=10, fill="x")
    ctk.CTkButton(controls, text="Load Sample", command=load_sample).pack(side="left", padx=5)
    ctk.CTkButton(controls, text="Load Long Msg", command=load_with_long_message).pack(side="left", padx=5)
    ctk.CTkButton(controls, text="Load Too Many", command=load_too_many).pack(side="left", padx=5)
    ctk.CTkButton(controls, text="Clear", command=clear_chat).pack(side="left", padx=5)

    chat_view.set_chat_data(None) # Start empty
    # chat_view.set_chat_data([{"sender":"Test", "text":"Initial Message"}]) # Test with an initial message
    app.mainloop() 