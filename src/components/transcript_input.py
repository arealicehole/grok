import customtkinter as ctk
import time

class TranscriptInput(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        
        # Configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        
        # Text area
        self.textbox = ctk.CTkTextbox(self, wrap="word", font=ctk.CTkFont(size=14))
        self.textbox.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="nsew")
        self.textbox.insert("0.0", "Paste your transcript here...")
        self.textbox.bind("<FocusIn>", self.clear_placeholder)
        
        # Bottom controls frame
        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.controls_frame.grid_columnconfigure(0, weight=1)
        
        # Character count
        self.char_count = ctk.CTkLabel(self.controls_frame, text="Characters: 0")
        self.char_count.grid(row=0, column=0, sticky="w")
        
        # Clear button
        self.clear_button = ctk.CTkButton(self.controls_frame, text="Clear", command=self.clear_text)
        self.clear_button.grid(row=0, column=1, padx=(10, 0))
        
        # Setup auto-save timer
        self.textbox.bind("<KeyRelease>", self.on_text_change)
        self.last_save_time = 0
        
        # Setup keyboard shortcuts
        self.textbox.bind("<Control-a>", self.select_all)
    
    def clear_placeholder(self, event):
        if self.textbox.get("0.0", "end-1c") == "Paste your transcript here...":
            self.textbox.delete("0.0", "end")
    
    def clear_text(self):
        self.textbox.delete("0.0", "end")
        self.update_char_count()
    
    def on_text_change(self, event):
        self.update_char_count()
        current_time = time.time()
        if current_time - self.last_save_time > 5:  # Auto-save every 5 seconds
            self.auto_save()
            self.last_save_time = current_time
    
    def update_char_count(self):
        count = len(self.textbox.get("0.0", "end-1c"))
        self.char_count.configure(text=f"Characters: {count}")
    
    def auto_save(self):
        # Implement auto-save functionality
        # For now just print, but could save to file or local storage
        print("Auto-saving transcript...")
    
    def select_all(self, event):
        self.textbox.tag_add("sel", "0.0", "end")
        return "break"  # Prevents default behavior 