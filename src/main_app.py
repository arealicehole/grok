import customtkinter as ctk
import os # Potentially useful later, added now
import tkinter as tk
from typing import List, Optional # Add typing for clarity

# Assume profile_repository exists and has the expected classes/functions
# We might need to adjust imports based on actual file structure/exports
from .profile_repository import ProfileRepository, AnalysisProfile, ProfileNotFoundError # Assuming ProfileNotFoundError for error handling

# --- Constants ---
AUTO_SAVE_INTERVAL_MS = 5000 # 5 seconds
AUTO_SAVE_FILENAME = "transcript_autosave.tmp"

class GrokApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Instantiate Profile Repository
        # This might need configuration passed in eventually
        try:
            self.profile_repo = ProfileRepository()
        except Exception as e:
            print(f"Error initializing ProfileRepository: {e}")
            # Handle initialization error gracefully (e.g., disable profile features)
            self.profile_repo = None 
        
        # Auto-save state
        self.last_saved_text = "" # Initialize with empty string

        # Profile selection state
        self.profile_radio_var = ctk.StringVar(value="") # Holds the ID of the selected profile
        self.profile_buttons = {} # Dictionary to potentially hold radiobutton widgets by ID

        # Placeholder text and color
        self.placeholder_text = "Paste your transcript here..."
        # Define a placeholder color (adjust as needed for theme)
        # Using a named color that works in both light/dark modes might be tricky
        # Let's use a specific hex for light/dark or derive from theme later if needed
        self.placeholder_color = "gray60" # A medium gray often visible in both modes
        self.default_text_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkTextbox"]["text_color"])

        # Configure window
        self.title("Grok - AI Transcript Analysis")
        self.geometry("900x700")
        ctk.set_appearance_mode("System")  # Use system theme (light/dark)
        ctk.set_default_color_theme("blue") # Default color theme

        # Configure grid layout 
        self.grid_columnconfigure(0, weight=3) # Transcript column (larger)
        self.grid_columnconfigure(1, weight=1) # Profile column (smaller)
        self.grid_rowconfigure(0, weight=0)    # Header row fixed size
        self.grid_rowconfigure(1, weight=1)    # Main content row expands
        self.grid_rowconfigure(2, weight=0)    # Bottom bar row fixed size

        # --- Header --- 
        self.header_label = ctk.CTkLabel(self, text="Grok Transcript Analysis", font=ctk.CTkFont(size=20, weight="bold"))
        # Place header in row 0, spanning both columns. Stick to top-left ('nw')
        self.header_label.grid(row=0, column=0, columnspan=2, padx=20, pady=10, sticky="nw")

        # --- Transcript Input Textbox ---\
        self.transcript_textbox = ctk.CTkTextbox(self, wrap="word", text_color=self.placeholder_color) # Start with placeholder color
        # Place textbox in row 1, column 0. Pad x=20, y=10 bottom. Stick to all sides ('nsew') to fill cell
        self.transcript_textbox.grid(row=1, column=0, padx=20, pady=(0, 5), sticky="nsew") # Reduced bottom padding
        # Insert initial placeholder text
        self.transcript_textbox.insert("0.0", self.placeholder_text)

        # Bind focus events for placeholder behavior
        self.transcript_textbox.bind("<FocusIn>", self._on_textbox_focus_in)
        self.transcript_textbox.bind("<FocusOut>", self._on_textbox_focus_out)
        # Bind key release event to update character count
        self.transcript_textbox.bind("<KeyRelease>", self._on_transcript_change)
        # Bind Ctrl+A for Select All
        self.transcript_textbox.bind("<Control-a>", self._select_all)
        self.transcript_textbox.bind("<Control-A>", self._select_all) # Handle capital A too
        # Bind Ctrl+C/V/X for Copy/Paste/Cut
        self.transcript_textbox.bind("<Control-c>", self._trigger_copy)
        self.transcript_textbox.bind("<Control-C>", self._trigger_copy)
        self.transcript_textbox.bind("<Control-v>", self._trigger_paste)
        self.transcript_textbox.bind("<Control-V>", self._trigger_paste)
        self.transcript_textbox.bind("<Control-x>", self._trigger_cut)
        self.transcript_textbox.bind("<Control-X>", self._trigger_cut)

        # --- Profile Management Frame (Column 1) ---
        self.profile_frame = ctk.CTkFrame(self)
        self.profile_frame.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(0, 5))
        # Configure rows/columns inside the profile frame
        self.profile_frame.grid_columnconfigure(0, weight=1) # Make content fill width
        self.profile_frame.grid_rowconfigure(0, weight=0) # Label row
        self.profile_frame.grid_rowconfigure(1, weight=1) # Scrollable frame row expands

        # Profile section label
        self.profile_label = ctk.CTkLabel(self.profile_frame, text="Analysis Profiles", font=ctk.CTkFont(size=16, weight="bold"))
        self.profile_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")

        # Scrollable frame for profile list
        self.profile_scrollable_frame = ctk.CTkScrollableFrame(self.profile_frame)
        self.profile_scrollable_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # --- Bottom Bar (Row 2) ---
        # Frame to hold the button and label in row 2, spanning both columns
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.grid(row=2, column=0, columnspan=2, padx=20, pady=(0, 10), sticky="ew")

        # Configure columns within the bottom frame
        self.bottom_frame.grid_columnconfigure(0, weight=0) # Clear button
        self.bottom_frame.grid_columnconfigure(1, weight=1) # Spacer
        self.bottom_frame.grid_columnconfigure(2, weight=0) # Char count

        # --- Clear Button ---
        self.clear_button = ctk.CTkButton(self.bottom_frame, text="Clear Transcript", command=self._clear_transcript)
        self.clear_button.grid(row=0, column=0, sticky="w")

        # --- Character Count Label ---
        self.char_count_label = ctk.CTkLabel(self.bottom_frame, text="Characters: 0")
        # Place char count in the bottom frame, column 2. Stick to right ('e')
        self.char_count_label.grid(row=0, column=2, sticky="e")

        # Initialize character count
        self._on_transcript_change(None) # Call initially to set count (pass None as event)

        # Load profiles into the UI
        self._load_profiles()

        # Start the auto-save loop
        self.after(AUTO_SAVE_INTERVAL_MS, self._auto_save)

    def _on_textbox_focus_in(self, event):
        """Clear placeholder text when textbox gains focus."""
        current_text = self.transcript_textbox.get("0.0", "end-1c")
        if current_text == self.placeholder_text:
            self.transcript_textbox.delete("0.0", "end")
            # Set text color to default
            self.transcript_textbox.configure(text_color=self.default_text_color)

    def _on_textbox_focus_out(self, event):
        """Restore placeholder text if textbox is empty when losing focus."""
        current_text = self.transcript_textbox.get("0.0", "end-1c")
        if not current_text:
            self.transcript_textbox.insert("0.0", self.placeholder_text)
            # Set text color back to placeholder color
            self.transcript_textbox.configure(text_color=self.placeholder_color)
        # Also update count when focus leaves (e.g., if text was deleted)
        self._on_transcript_change(event)

    def _clear_transcript(self):
        """Clears the transcript textbox and resets the placeholder."""
        self.transcript_textbox.delete("0.0", "end")
        # Reset placeholder manually by calling focus out logic 
        # (ensures color and text are correct)
        self._on_textbox_focus_out(None) # Pass None as event
        # Explicitly update count after clearing
        self._on_transcript_change(None) 

    def _on_transcript_change(self, event):
        """Update the character count label whenever the text changes."""
        current_text = self.transcript_textbox.get("0.0", "end-1c")
        # Don't count the placeholder text
        if current_text == self.placeholder_text and self.transcript_textbox.cget("text_color") == self.placeholder_color:
            char_count = 0
        else:
            char_count = len(current_text)
        
        self.char_count_label.configure(text=f"Characters: {char_count}")

    def _auto_save(self):
        """Periodically saves the transcript text if it has changed."""
        try:
            current_text = self.transcript_textbox.get("0.0", "end-1c")
            is_placeholder = (current_text == self.placeholder_text and 
                              self.transcript_textbox.cget("text_color") == self.placeholder_color)

            if not is_placeholder and current_text != self.last_saved_text:
                try:
                    with open(AUTO_SAVE_FILENAME, "w", encoding='utf-8') as f:
                        f.write(current_text)
                    self.last_saved_text = current_text
                    # Optional: Add a status message or log
                    # print(f"Transcript auto-saved at {datetime.datetime.now()}") 
                except IOError as e:
                    print(f"Error auto-saving transcript: {e}")
                    # Consider adding user feedback here (e.g., status bar message)

        finally:
            # Always reschedule the next check
            self.after(AUTO_SAVE_INTERVAL_MS, self._auto_save)

    def _select_all(self, event):
        """Selects all text in the transcript textbox."""
        # Add the 'sel' tag to the entire text range
        self.transcript_textbox.tag_add("sel", "1.0", "end")
        # Return "break" to prevent further event propagation (e.g., default OS behavior)
        return "break"

    # --- Clipboard Handlers ---
    def _trigger_copy(self, event):
        """Triggers the built-in Copy virtual event."""
        try:
            self.transcript_textbox.event_generate("<<Copy>>")
        except tk.TclError:
            # Handle case where no text is selected (optional)
            pass 
        return "break" # Prevent default OS copy behavior interference

    def _trigger_paste(self, event):
        """Triggers the built-in Paste virtual event."""
        try:
            self.transcript_textbox.event_generate("<<Paste>>")
        except tk.TclError:
             # Handle potential errors during paste (optional)
            pass
        # Update character count after paste
        self._on_transcript_change(None)
        return "break" # Prevent default OS paste behavior interference

    def _trigger_cut(self, event):
        """Triggers the built-in Cut virtual event."""
        try:
            self.transcript_textbox.event_generate("<<Cut>>")
        except tk.TclError:
            # Handle case where no text is selected (optional)
            pass
        # Update character count after cut
        self._on_transcript_change(None)
        return "break" # Prevent default OS cut behavior interference

    # --- Profile Management Methods ---
    def _load_profiles(self):
        """Fetches profiles and populates the profile selection list."""
        # Clear existing widgets from the scrollable frame
        for widget in self.profile_scrollable_frame.winfo_children():
            widget.destroy()
        self.profile_buttons.clear()

        profiles: List[AnalysisProfile] = []
        if self.profile_repo:
            try:
                # Fetch all profiles (consider pagination/filtering later if needed)
                profiles = self.profile_repo.get_all_profiles() 
            except Exception as e:
                print(f"Error loading profiles: {e}")
                # Display error in the profile frame
                error_label = ctk.CTkLabel(self.profile_scrollable_frame, text="Error loading profiles.", text_color="red")
                error_label.pack(pady=10)
                return # Stop processing if profiles can't be loaded
        else:
            # Handle case where repo failed to initialize
            error_label = ctk.CTkLabel(self.profile_scrollable_frame, text="Profile system unavailable.", text_color="orange")
            error_label.pack(pady=10)
            return

        if not profiles:
            # Display empty state message
            empty_label = ctk.CTkLabel(self.profile_scrollable_frame, text="No profiles found.")
            empty_label.pack(pady=10)
            # Maybe add a button here later to trigger profile creation?
        else:
            # Populate with radio buttons
            default_profile_id_str = None
            for profile in profiles:
                profile_id_str = str(profile.id) # Assuming profile object has 'id' and 'name'
                radio_button = ctk.CTkRadioButton(
                    self.profile_scrollable_frame,
                    text=profile.name, 
                    variable=self.profile_radio_var,
                    value=profile_id_str, 
                    command=self._on_profile_selected
                )
                radio_button.pack(anchor="w", pady=2, padx=5)
                self.profile_buttons[profile_id_str] = radio_button
                
                # Set the first profile as the default selection for now
                if default_profile_id_str is None:
                    default_profile_id_str = profile_id_str

            # Set the default selection if one was found
            if default_profile_id_str:
                self.profile_radio_var.set(default_profile_id_str)
                # Trigger the selection logic initially if needed (or call after mainloop starts)
                # self._on_profile_selected() 

    def _on_profile_selected(self):
        """Callback function when a profile radio button is selected."""
        selected_id = self.profile_radio_var.get()
        print(f"Selected Profile ID: {selected_id}")
        # Add logic here later: 
        # - Load selected profile details? 
        # - Update other UI elements?
        # - Store the selection?

if __name__ == "__main__":
    app = GrokApp()
    app.mainloop() 