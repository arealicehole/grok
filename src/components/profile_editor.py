import customtkinter as ctk
from typing import Optional, Callable, List, Set, Dict # Added List, Set, Dict
from src.profile_repository import ProfileRepository
from src.models.analysis_profile import AnalysisProfile # Corrected import location
from CTkMessagebox import CTkMessagebox # Assuming CTkMessagebox is available

# Predefined tags (can be loaded from config later)
PREDEFINED_TAGS = [
    "Meeting", "Interview", "Lecture", "General", "Medical", "Legal",
    "Technical", "Customer Service", "Podcast", "Dictation"
]

class ProfileEditorWindow(ctk.CTkToplevel):
    def __init__(self, master, repository: ProfileRepository, profile_id: Optional[str] = None, on_save_callback: Optional[Callable] = None):
        super().__init__(master)

        self.repository = repository
        self.profile_id = profile_id
        self.on_save_callback = on_save_callback
        self.is_dirty = False
        self.current_profile: Optional[AnalysisProfile] = None
        self.tag_checkboxes: Dict[str, ctk.CTkCheckBox] = {} # To store tag checkboxes
        self.selected_tags: Set[str] = set() # Track currently selected tags

        self.title("Edit Profile" if profile_id else "Create New Profile")
        self.geometry("600x550") # Increased size for tags
        self.resizable(True, True)
        self.grab_set()

        # Configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) # Instructions textbox expands
        self.grid_rowconfigure(4, weight=0) # Tags frame fixed size initially
        self.grid_rowconfigure(5, weight=0) # Button frame fixed size

        self._create_widgets()
        self._load_profile_data()
        self._bind_events()

    def _create_widgets(self):
        """Create all the UI widgets for the editor window."""
        # --- Profile Name ---
        name_frame = ctk.CTkFrame(self, fg_color="transparent")
        name_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        name_frame.grid_columnconfigure(1, weight=1)

        name_label = ctk.CTkLabel(name_frame, text="Profile Name:")
        name_label.grid(row=0, column=0, padx=(0, 10), sticky="w")
        self.name_entry = ctk.CTkEntry(name_frame)
        self.name_entry.grid(row=0, column=1, sticky="ew")

        # --- Instructions ---
        instructions_label = ctk.CTkLabel(self, text="Instructions:")
        instructions_label.grid(row=1, column=0, padx=20, pady=(0, 5), sticky="nw")

        self.instructions_text = ctk.CTkTextbox(self, wrap="word", height=150)
        self.instructions_text.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="nsew")

        # --- Tags Section ---
        tags_label = ctk.CTkLabel(self, text="Tags:")
        tags_label.grid(row=3, column=0, padx=20, pady=(5, 5), sticky="nw")

        tags_frame = ctk.CTkScrollableFrame(self, height=100)
        tags_frame.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="nsew")
        tags_frame.grid_columnconfigure(0, weight=1) # Allow checkboxes to align left

        for i, tag in enumerate(sorted(PREDEFINED_TAGS)):
            checkbox = ctk.CTkCheckBox(tags_frame, text=tag, command=self._on_tag_change)
            checkbox.grid(row=i, column=0, padx=10, pady=2, sticky="w")
            self.tag_checkboxes[tag] = checkbox

        # --- Buttons ---
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=5, column=0, padx=20, pady=(10, 20), sticky="ew") # Adjusted row index
        button_frame.grid_columnconfigure(0, weight=1)

        self.cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=self._cancel)
        self.cancel_button.grid(row=0, column=1, padx=(0, 10))

        self.save_button = ctk.CTkButton(button_frame, text="Save", command=self._save_profile)
        self.save_button.grid(row=0, column=2)

    def _load_profile_data(self):
        """Load data into the form if editing an existing profile."""
        if self.profile_id:
            try:
                self.current_profile = self.repository.get_profile(self.profile_id)
                if self.current_profile:
                    self.name_entry.insert(0, self.current_profile.name)
                    self.instructions_text.insert("1.0", self.current_profile.instructions or "")
                    # Load tags
                    if hasattr(self.current_profile, 'tags') and self.current_profile.tags:
                         self.selected_tags = set(self.current_profile.tags)
                         for tag, checkbox in self.tag_checkboxes.items():
                             if tag in self.selected_tags:
                                 checkbox.select()
                             else:
                                 checkbox.deselect()
                    else:
                         self.selected_tags = set()
                         # Ensure all checkboxes are deselected
                         for checkbox in self.tag_checkboxes.values():
                            checkbox.deselect()
                else:
                    CTkMessagebox(title="Error", message=f"Profile with ID {self.profile_id} not found.", icon="cancel")
                    self.destroy()
            except Exception as e:
                 CTkMessagebox(title="Error", message=f"Failed to load profile: {e}", icon="cancel")
                 self.destroy()

        self.after(100, lambda: self.name_entry.focus())
        self.is_dirty = False # Reset dirty flag after loading

    def _bind_events(self):
        """Bind events to track changes and handle window closing."""
        self.name_entry.bind("<KeyRelease>", self._mark_as_dirty)
        self.instructions_text.bind("<KeyRelease>", self._mark_as_dirty)
        # Tag changes are handled by checkbox command pointing to _on_tag_change
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Control-s>", lambda event: self._save_profile())
        self.bind("<Escape>", lambda event: self._cancel())

    def _on_tag_change(self):
        """Callback when a tag checkbox state changes. Updates selected_tags and dirty flag."""
        self.selected_tags.clear()
        for tag, checkbox in self.tag_checkboxes.items():
            if checkbox.get() == 1:
                self.selected_tags.add(tag)
        self._mark_as_dirty()

    def _mark_as_dirty(self, event=None):
        """Mark the form as having unsaved changes."""
        self.is_dirty = True

    def _validate_form(self) -> tuple[bool, Optional[str]]:
        """Validate the form data."""
        name = self.name_entry.get().strip()
        if not name:
            return False, "Profile name is required."

        if len(name) > 100:
             return False, "Profile name must be 100 characters or less."

        try:
            existing_profile = self.repository.get_profile_by_name(name)
            if existing_profile:
                current_profile_id = self.current_profile.id if self.current_profile else None
                if not current_profile_id or existing_profile.id != current_profile_id:
                    return False, f"A profile with the name '{name}' already exists."
        except Exception as e:
             return False, f"Error checking profile name uniqueness: {e}"

        return True, None

    def _save_profile(self):
        """Validate and save the profile data."""
        is_valid, error_msg = self._validate_form()
        if not is_valid:
            CTkMessagebox(title="Validation Error", message=error_msg, icon="warning")
            return

        try:
            name = self.name_entry.get().strip()
            instructions = self.instructions_text.get("1.0", "end-1c").strip()
            tags_to_save = sorted(list(self.selected_tags)) # Get selected tags

            if self.current_profile: # Editing existing profile
                self.current_profile.name = name
                self.current_profile.instructions = instructions
                self.current_profile.tags = tags_to_save # Update tags
                profile_to_save = self.current_profile
            else: # Creating new profile
                 profile_to_save = AnalysisProfile(name=name, instructions=instructions, tags=tags_to_save)
                 # Assuming AnalysisProfile accepts tags in constructor

            saved_profile = self.repository.save_profile(profile_to_save)

            if saved_profile:
                 CTkMessagebox(title="Success", message="Profile saved successfully.", icon="check")
                 self.is_dirty = False
                 if self.on_save_callback:
                     self.on_save_callback()
                 self.destroy()
            else:
                 CTkMessagebox(title="Error", message="Failed to save profile. Repository returned failure.", icon="cancel")

        except Exception as e:
            CTkMessagebox(title="Error", message=f"An error occurred while saving: {e}", icon="cancel")


    def _cancel(self):
        """Handle cancel action, checking for unsaved changes."""
        if self.is_dirty:
            response = CTkMessagebox(
                title="Unsaved Changes",
                message="You have unsaved changes. Are you sure you want to discard them and close?",
                icon="warning",
                option_1="Cancel",
                option_2="Discard"
            )
            if response.get() == "Discard":
                self.destroy()
        else:
            self.destroy()

# Example Usage (requires adjustments in main_app.py)
# if __name__ == '__main__':
#     import os
#     from src.profile_repository import ProfileRepository # Make sure path is correct
#     from src.models.analysis_profile import AnalysisProfile # Corrected import path
#
#     # Example setup
#     app = ctk.CTk()
#     app.geometry("200x100")
#
#     # Initialize repository (adjust path as needed)
#     # Ensure the directory exists
#     config_dir = os.path.expanduser("~/.config/analysis_profiles")
#     os.makedirs(config_dir, exist_ok=True)
#     db_path = os.path.join(config_dir, "profiles.db")
#     repo = ProfileRepository(db_path)
#
#     def open_create_editor():
#         editor = ProfileEditorWindow(app, repo, on_save_callback=lambda: print("Save callback triggered!"))
#         # No need for editor.mainloop() when using grab_set()
#
#     def open_edit_editor(profile_id_to_edit):
#          if not profile_id_to_edit:
#               print("No profile ID provided for editing.")
#               return
#          editor = ProfileEditorWindow(app, repo, profile_id=profile_id_to_edit, on_save_callback=lambda: print("Save callback triggered!"))
#
#     create_button = ctk.CTkButton(app, text="Create Profile", command=open_create_editor)
#     create_button.pack(pady=10)
#
#     # Example: Button to edit a specific profile (replace with actual ID)
#     # You would typically get this ID from a list selection
#     # example_id = "some-uuid-string" # Replace with a real ID from your db
#     # edit_button = ctk.CTkButton(app, text="Edit Profile", command=lambda: open_edit_editor(example_id))
#     # edit_button.pack(pady=10)
#
#     app.mainloop() 