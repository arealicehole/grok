import customtkinter as ctk
from CTkMessagebox import CTkMessagebox  # Ensure this is installed or handled
import os

# Use relative imports since main_app is inside the src package
from .components.transcript_input import TranscriptInput
from .profile_repository import ProfileRepository
from .models.analysis_profile import AnalysisProfile
from .components.profile_editor import ProfileEditorWindow

# --- Constants ---
AUTO_SAVE_INTERVAL_MS = 5000 # 5 seconds
AUTO_SAVE_FILENAME = "transcript_autosave.tmp"

class GrokApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Instantiate Profile Repository
        try:
            self.profile_repo = ProfileRepository()
        except Exception as e:
            print(f"Error initializing ProfileRepository: {e}")
            self.profile_repo = None 
        
        # Auto-save state
        self.last_saved_text = "" # Initialize with empty string

        # Profile selection state
        self.profile_radio_var = ctk.StringVar(value="") # Holds the ID of the selected profile
        self.profile_buttons = {} # Dictionary to potentially hold radiobutton widgets by ID

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

        # --- Instantiate and Place TranscriptInput Component --- 
        self.transcript_input_component = TranscriptInput(self)
        self.transcript_input_component.grid(row=1, column=0, padx=20, pady=(0, 5), sticky="nsew")

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

        # Initialize character count (Moved to component)
        # self._on_transcript_change(None) 

        # Load profiles into the UI
        self._load_profiles()

        # Start the auto-save loop (Needs adjustment)
        self.after(AUTO_SAVE_INTERVAL_MS, self._auto_save)

    def _auto_save(self):
        """Periodically saves the transcript text if it has changed."""
        try:
            # Access the textbox within the component
            current_text = self.transcript_input_component.textbox.get("0.0", "end-1c")
            
            # Check if the component's placeholder is active (needs method in component)
            # Simplified check for now: don't save if text is the placeholder string
            # TODO: Refine this by adding an is_placeholder() method to TranscriptInput
            is_placeholder = (current_text == "Paste your transcript here...") 

            if not is_placeholder and current_text != self.last_saved_text:
                try:
                    with open(AUTO_SAVE_FILENAME, "w", encoding='utf-8') as f:
                        f.write(current_text)
                    self.last_saved_text = current_text
                    # print(f"Transcript auto-saved at {datetime.datetime.now()}") 
                except IOError as e:
                    print(f"Error auto-saving transcript: {e}")

        finally:
            # Always reschedule the next check
            self.after(AUTO_SAVE_INTERVAL_MS, self._auto_save)

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