import tkinter
import tkinter.messagebox as messagebox
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox  # Ensure this is installed or handled
import os
from functools import partial # Needed for delete button command
import threading
import queue
import logging
from typing import Optional, Dict, List, Any, Set # Added List, Any, Set
import datetime # Added for time formatting

# Use relative imports since main_app is inside the src package
# Conditionally adjust imports if running as __main__
if __name__ == "__main__" and __package__ is None:
    import sys
    from os import path
    # Add the parent directory (grok) to sys.path to allow absolute imports from src
    sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
    # Now use absolute imports based on the adjusted path
    from src.components.transcript_input import TranscriptInput
    from src.models.analysis_profile import AnalysisProfile
    from src.components.profile_editor import ProfileEditorWindow
    from src.storage_manager import StorageManager
    from src.components.output_container import OutputDisplayFrame
    from src.profile_utils import (
        clone_profile, # Still used for duplication logic
        export_profile_utility, # New utility for export UI flow
        import_profile_utility, # New utility for import UI flow
    )
    from src.exceptions import ProfileStorageError, ProfileNotFoundError, ProfileValidationError
else:
    from .components.transcript_input import TranscriptInput
    from .models.analysis_profile import AnalysisProfile
    from .components.profile_editor import ProfileEditorWindow
    from .storage_manager import StorageManager
    from .components.output_container import OutputDisplayFrame
    from .profile_utils import (
        clone_profile, # Still used for duplication logic
        export_profile_utility, # New utility for export UI flow
        import_profile_utility, # New utility for import UI flow
    )
    from .exceptions import ProfileStorageError, ProfileNotFoundError, ProfileValidationError

# --- Constants ---
AUTO_SAVE_INTERVAL_MS = 5000 # 5 seconds
AUTO_SAVE_FILENAME = "transcript_autosave.tmp"

# --- Helper function for time formatting ---
def format_relative_time(iso_timestamp_str: Optional[str]) -> str:
    if not iso_timestamp_str:
        return "Never"
    try:
        dt = datetime.datetime.fromisoformat(iso_timestamp_str.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        diff = now - dt

        if diff.total_seconds() < 60:
            return "Just now"
        elif diff.total_seconds() < 3600: # Less than 1 hour
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} min ago"
        elif diff.total_seconds() < 86400: # Less than 1 day
            hours = int(diff.total_seconds() / 3600)
            return f"{hours} hr ago"
        elif diff.days < 7:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.days < 30:
            weeks = diff.days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        elif diff.days < 365:
            months = diff.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        else:
            return dt.strftime("%b %d, %Y")
    except ValueError:
        return "Invalid date"

class GrokApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        self.logger.info("Initializing GrokApp...")
        
        # --- Initialize Storage Manager ---
        try:
            self.storage_manager = StorageManager(storage_type='sqlite')
        except Exception as e:
            print(f"FATAL ERROR: Failed to initialize StorageManager: {e}")
            # Optionally show a critical error message box and exit?
            self.storage_manager = None # Indicate storage is unavailable
        
        # Auto-save state
        self.last_saved_text = "" # Initialize with empty string

        # Profile selection state
        self.profiles_list: List[AnalysisProfile] = [] # Initialize profiles_list
        self.profile_radio_var = ctk.StringVar(value="") # Holds the ID of the selected profile
        self.profile_buttons = {} # Dictionary to potentially hold radiobutton widgets by ID
        self.profile_row_frames = [] # List to hold the profile row frame widgets for highlighting
        self.selected_profile_frames: Dict[str, ctk.CTkFrame] = {} # Stores profile_id -> frame
        self.selected_profile_color = ("gray70", "gray30") # Example highlight color (light, dark)

        # --- New variables for multi-profile checkbox selection ---
        self.selected_profile_ids: Set[str] = set() # Stores IDs of all checked profiles
        self.profile_checkboxes: Dict[str, ctk.CTkCheckBox] = {} # Maps profile_id to CTkCheckBox widget
        self.profile_checkbox_vars: Dict[str, ctk.IntVar] = {} # Maps profile_id to CTkIntVar for checkbox state
        # --- End new variables ---

        # --- Per-Profile Analysis State ---
        self.analysis_results: Dict[str, Any] = {}  # Stores successful analysis data, keyed by profile_id
        self.analysis_status: Dict[str, str] = {}   # Stores status ('idle', 'loading', 'success', 'error'), keyed by profile_id
        self.analysis_errors: Dict[str, Any] = {}   # Stores error information, keyed by profile_id
        # --- End Per-Profile Analysis State ---

        self.edit_profile_button = None # Placeholder for the edit button widget
        self.delete_profile_button = None # Placeholder for delete
        self.duplicate_profile_button = None # Placeholder for duplicate
        self.export_profile_button = None # Placeholder for export

        # Processing state
        self.is_processing = False
        # self.current_transcript_text: str - We'll get this directly from the input component
        # self.selected_profile_id: str - We'll get this from self.profile_radio_var

        # Configure window
        self.title("Grok - AI Transcript Analysis")
        self.geometry("1200x800") # Increased initial size
        ctk.set_appearance_mode("System")  # Use system theme (light/dark)
        ctk.set_default_color_theme("blue") # Default color theme

        # Configure grid layout
        self.grid_columnconfigure(0, weight=1) # Left panel (Transcript)
        self.grid_columnconfigure(1, weight=1) # Right panel (Profiles & Output)
        self.grid_rowconfigure(0, weight=0)    # Header row
        self.grid_rowconfigure(1, weight=1)    # Main content row
        self.grid_rowconfigure(2, weight=0)    # Controls (Process button) row
        # Removed some rows, will adjust status/error display later if needed within OutputDisplayFrame or a new status bar

        # --- Header ---
        self.header_label = ctk.CTkLabel(self, text="Grok Transcript Analysis", font=ctk.CTkFont(size=20, weight="bold"))
        self.header_label.grid(row=0, column=0, columnspan=2, padx=20, pady=10, sticky="nw")

        # --- Transcript Input Panel (Left) ---
        self.transcript_input_component = TranscriptInput(self)
        self.transcript_input_component.grid(row=1, column=0, padx=(20,10), pady=(0, 5), sticky="nsew")

        # --- Right Panel (Profiles and Output) ---
        self.right_panel_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.right_panel_frame.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(0,5))
        self.right_panel_frame.grid_rowconfigure(0, weight=1) # Profile management
        self.right_panel_frame.grid_rowconfigure(1, weight=2) # Output display (more space)
        self.right_panel_frame.grid_columnconfigure(0, weight=1)

        # --- Profile Management Frame (Inside Right Panel) ---
        self.profile_frame = ctk.CTkFrame(self.right_panel_frame)
        self.profile_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        # Configure rows/columns inside the profile frame
        self.profile_frame.grid_columnconfigure(0, weight=1) # Make content fill width
        self.profile_frame.grid_rowconfigure(0, weight=0) # Label row
        self.profile_frame.grid_rowconfigure(1, weight=0) # Filter/Sort row
        self.profile_frame.grid_rowconfigure(2, weight=1) # Scrollable frame row expands
        self.profile_frame.grid_rowconfigure(3, weight=0) # Button frame row fixed size

        self.profile_label = ctk.CTkLabel(self.profile_frame, text="Analysis Profiles", font=ctk.CTkFont(size=16, weight="bold"))
        self.profile_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")

        # --- Filter and Sort Controls Frame ---
        self.profile_filter_sort_frame = ctk.CTkFrame(self.profile_frame, fg_color="transparent")
        self.profile_filter_sort_frame.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="ew")
        self.profile_filter_sort_frame.grid_columnconfigure(0, weight=1) # Filter entry
        self.profile_filter_sort_frame.grid_columnconfigure(1, weight=0) # Sort dropdown
        self.profile_filter_sort_frame.grid_columnconfigure(2, weight=0) # Select All button
        self.profile_filter_sort_frame.grid_columnconfigure(3, weight=0) # Deselect All button

        self.profile_filter_entry = ctk.CTkEntry(self.profile_filter_sort_frame, placeholder_text="Filter by name...")
        self.profile_filter_entry.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")
        self.profile_filter_entry.bind("<KeyRelease>", lambda event: self._load_profiles())

        self.profile_sort_var = ctk.StringVar(value="Order") # Default sort
        sort_options = ["Order", "Name", "Last Used", "Usage Count"]
        self.profile_sort_menu = ctk.CTkOptionMenu(
            self.profile_filter_sort_frame,
            values=sort_options,
            variable=self.profile_sort_var,
            command=lambda choice: self._load_profiles()
        )
        self.profile_sort_menu.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="e")

        self.select_all_button = ctk.CTkButton(self.profile_filter_sort_frame, text="Select All", command=self._select_all_profiles, width=80)
        self.select_all_button.grid(row=0, column=2, padx=(5,0), pady=5, sticky="e")

        self.deselect_all_button = ctk.CTkButton(self.profile_filter_sort_frame, text="Deselect All", command=self._deselect_all_profiles, width=90)
        self.deselect_all_button.grid(row=0, column=3, padx=(5,0), pady=5, sticky="e")

        # Scrollable frame for profile list
        self.profile_scrollable_frame = ctk.CTkScrollableFrame(self.profile_frame)
        self.profile_scrollable_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # --- Setup Profile Control Buttons ---
        self._setup_profile_controls()

        # --- Output Display Frame (Inside Right Panel) ---
        self.output_display_frame = OutputDisplayFrame(self.right_panel_frame)
        self.output_display_frame.grid(row=1, column=0, sticky="nsew", pady=(10,0))

        # --- Processing Controls Frame (Row 2, spans both columns) ---
        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.grid(row=2, column=0, columnspan=2, padx=20, pady=(5,5), sticky="ew")
        self.controls_frame.grid_columnconfigure(0, weight=1) # Center the button

        self.process_button = ctk.CTkButton(
            self.controls_frame,
            text="Process Transcript",
            state="disabled",
            command=self.start_analysis_processing
        )
        self.process_button.grid(row=0, column=0, padx=10, pady=10) # EW sticky removed to keep it centered

        # --- Status Frame (Row 3) ---
        self.status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.status_frame.grid(row=3, column=0, columnspan=2, padx=20, pady=(0,5), sticky="ew")
        self.status_frame.grid_columnconfigure(0, weight=1) # Status label
        self.status_frame.grid_columnconfigure(1, weight=0) # Progress bar
        self.status_frame.grid_columnconfigure(2, weight=0) # Time estimate
        self.status_frame.grid_columnconfigure(3, weight=0) # Cancel button

        self.status_label = ctk.CTkLabel(self.status_frame, text="Ready")
        self.status_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.progress_bar = ctk.CTkProgressBar(self.status_frame, width=250)
        self.progress_bar.grid(row=0, column=1, padx=10, pady=5, sticky="e")
        self.progress_bar.set(0)
        self.progress_bar.grid_remove()

        self.time_estimate_frame = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        self.time_estimate_frame.grid(row=0, column=2, padx=10, pady=5, sticky="e")
        self.time_estimate_frame.grid_remove()

        self.time_icon_label = ctk.CTkLabel(self.time_estimate_frame, text="⏱️") # Using an emoji for icon
        self.time_icon_label.grid(row=0, column=0, padx=(0,5), pady=0, sticky="e")

        self.time_estimate_label = ctk.CTkLabel(self.time_estimate_frame, text="Estimating...")
        self.time_estimate_label.grid(row=0, column=1, padx=0, pady=0, sticky="e")

        self.cancel_button = ctk.CTkButton(
            self.status_frame,
            text="Cancel",
            width=80,
            command=self.cancel_analysis_processing
        )
        self.cancel_button.grid(row=0, column=3, padx=10, pady=5, sticky="e")
        self.cancel_button.grid_remove()

        # --- Error Display Frame (Row 4) ---
        self.error_display_frame = ctk.CTkFrame(self, fg_color=("#FFE6E6", "#5A0000")) # Example error colors
        self.error_display_frame.grid(row=4, column=0, columnspan=2, padx=20, pady=5, sticky="ew")
        self.error_display_frame.grid_columnconfigure(0, weight=0) # Icon
        self.error_display_frame.grid_columnconfigure(1, weight=1) # Message
        self.error_display_frame.grid_columnconfigure(2, weight=0) # Retry
        self.error_display_frame.grid_columnconfigure(3, weight=0) # Clear
        self.error_display_frame.grid_remove()  # Initially hidden

        self.error_icon_label = ctk.CTkLabel(self.error_display_frame, text="⚠️", font=ctk.CTkFont(size=20))
        self.error_icon_label.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="w")

        self.error_message_label = ctk.CTkLabel(self.error_display_frame, text="Error message goes here.", wraplength=700) # Adjusted wraplength
        self.error_message_label.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        self.retry_button = ctk.CTkButton(
            self.error_display_frame, 
            text="Retry", 
            width=60,
            command=self.retry_analysis # Changed from self.start_analysis_processing
        )
        self.retry_button.grid(row=0, column=2, padx=5, pady=10)

        self.clear_error_button = ctk.CTkButton(
            self.error_display_frame, 
            text="✕", 
            width=30, # Compact clear button
            command=self._clear_error_message
        )
        self.clear_error_button.grid(row=0, column=3, padx=(5, 10), pady=10)

        # --- Bottom Bar (Row 5) --- (Original bottom_frame, now at row 5)
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.grid(row=5, column=0, columnspan=2, padx=20, pady=(0, 10), sticky="ew")

        # Configure columns within the bottom frame
        self.bottom_frame.grid_columnconfigure(0, weight=0) # Clear button
        self.bottom_frame.grid_columnconfigure(1, weight=1) # Spacer
        self.bottom_frame.grid_columnconfigure(2, weight=0) # Char count

        # Initialize character count (Moved to component)
        # self._on_transcript_change(None) 

        # Load profiles into the UI
        self._load_profiles()

        # Initial check for edit button state based on default selection
        self._update_edit_button_state() 
        self._update_management_button_states() # Call this to ensure all buttons are correct initially
        self._check_process_button_state() # Initial check for process button

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
        """Loads profiles from storage and populates the scrollable list,
        including instruction preview, last used time, and usage count.
        Applies filtering and sorting.
        """
        self.logger.debug("Loading profiles into UI...")
        if not self.storage_manager:
            self.logger.error("StorageManager not initialized, cannot load profiles.")
            # Display an error or empty state in the profile list area
            for widget in self.profile_scrollable_frame.winfo_children():
                widget.destroy()
            error_label = ctk.CTkLabel(self.profile_scrollable_frame, text="Error: Profile storage unavailable.", text_color="red")
            error_label.pack(pady=20)
            return

        # Clear existing profile widgets
        for widget in self.profile_scrollable_frame.winfo_children():
            widget.destroy()
        # self.profile_buttons = {} # Clear stored radio buttons - Replaced by checkboxes
        self.profile_row_frames = [] # Clear stored row frames - May no longer be needed or used differently
        self.selected_profile_frames.clear() # May no longer be needed or used differently

        # Clear checkbox specific dictionaries
        self.profile_checkboxes.clear()
        self.profile_checkbox_vars.clear()

        try:
            # Get filter text
            filter_text = self.profile_filter_entry.get().lower().strip()
            
            # Get sort criteria
            sort_by_map = {
                "Order": "order",
                "Name": "name",
                "Last Used": "last_used_timestamp",
                "Usage Count": "usage_count"
            }
            sort_by_criteria = sort_by_map.get(self.profile_sort_var.get(), "order")
            
            # Determine sort order (timestamps are newest first, counts are highest first)
            sort_order_asc = True
            if sort_by_criteria == "last_used_timestamp" or sort_by_criteria == "usage_count":
                sort_order_asc = False

            fetched_profiles: List[AnalysisProfile] = self.storage_manager.get_all_profiles(
                sort_by=sort_by_criteria, 
                sort_order='ASC' if sort_order_asc else 'DESC'
            )
            
            if filter_text:
                self.profiles_list = [p for p in fetched_profiles if filter_text in p.name.lower()] # Update self.profiles_list after filtering
            else:
                self.profiles_list = fetched_profiles # Update self.profiles_list with all fetched profiles

        except ProfileStorageError as e:
            self.logger.error(f"Error loading profiles from storage: {e}", exc_info=True)
            CTkMessagebox(title="Error", message=f"Could not load profiles: {e}", icon="cancel")
            # Display an error in the scrollable frame
            error_label = ctk.CTkLabel(self.profile_scrollable_frame, text="Error loading profiles.", text_color="red")
            error_label.pack(pady=20)
            return
        except Exception as e: # Catch any other unexpected errors
            self.logger.error(f"Unexpected error loading profiles: {e}", exc_info=True)
            CTkMessagebox(title="Error", message=f"An unexpected error occurred: {e}", icon="cancel")
            return

        if not self.profiles_list:
            self.logger.info("No profiles found or matched filters.")
            empty_label_text = "No profiles match filter." if filter_text else "No profiles yet. Create one!"
            empty_label = ctk.CTkLabel(self.profile_scrollable_frame, text=empty_label_text)
            empty_label.pack(pady=20)
            # Ensure edit/delete buttons are disabled if list is empty
            self._update_management_button_states() 
            self._check_process_button_state() # Also check process button
            return

        # selected_profile_id_str = self.profile_radio_var.get() # Old single selection tracking
        
        # Re-populate with (potentially filtered and sorted) profiles
        for profile in self.profiles_list: # Iterate over the updated self.profiles_list
            profile_id_str = str(profile.id) # Ensure ID is string for var and dict keys

            # --- Create a frame for each profile row ---
            # This frame will now contain a checkbox and then the details_frame
            row_frame = ctk.CTkFrame(self.profile_scrollable_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=(2,0), padx=2)
            row_frame.grid_columnconfigure(0, weight=0) # Checkbox column (fixed width)
            row_frame.grid_columnconfigure(1, weight=1) # Main content (details_frame)
            row_frame.grid_columnconfigure(2, weight=0) # Column for the arrow_buttons_frame

            # --- Checkbox for selection ---
            checkbox_var = ctk.IntVar()
            if profile_id_str in self.selected_profile_ids:
                checkbox_var.set(1)
            else:
                checkbox_var.set(0)
            
            checkbox = ctk.CTkCheckBox(row_frame, 
                                         text="", # No text for checkbox itself, name is in details_frame
                                         variable=checkbox_var, 
                                         command=lambda p_id=profile_id_str, c_var=checkbox_var: self._handle_profile_checkbox_toggle(p_id, c_var),
                                         width=20) # Small width for checkbox only
            checkbox.grid(row=0, column=0, padx=(5,0), pady=(5,5), sticky="n") # Align to top of cell
            self.profile_checkboxes[profile_id_str] = checkbox
            self.profile_checkbox_vars[profile_id_str] = checkbox_var

            # --- Profile Details Frame (within row_frame, next to checkbox) ---
            details_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            details_frame.grid(row=0, column=1, sticky="ew", padx=(5,0))
            details_frame.grid_columnconfigure(0, weight=1)

            # Profile Name (Bold)
            name_label = ctk.CTkLabel(details_frame, text=profile.name, font=ctk.CTkFont(weight="bold"))
            name_label.grid(row=0, column=0, sticky="w")

            # Instruction Preview (Truncated)
            instruction_preview = (profile.instructions[:70] + '...') if profile.instructions and len(profile.instructions) > 70 else profile.instructions
            if not instruction_preview: instruction_preview = "No instructions." # Placeholder
            preview_label = ctk.CTkLabel(details_frame, text=instruction_preview, font=ctk.CTkFont(size=10), text_color=("gray50", "gray50"))
            preview_label.grid(row=1, column=0, sticky="w")
            
            # Last Used and Usage Count
            last_used_str = format_relative_time(profile.last_used_timestamp)
            usage_str = f"Used: {profile.usage_count} time{'s' if profile.usage_count != 1 else ''}"
            
            usage_info_label = ctk.CTkLabel(details_frame, text=f"{last_used_str}  •  {usage_str}", font=ctk.CTkFont(size=9), text_color=("gray60", "gray40"))
            usage_info_label.grid(row=2, column=0, sticky="w", pady=(0,3))

            # --- Clickable area for selection (REMOVED - now handled by checkbox) ---
            # clickable_elements = [row_frame, details_frame, name_label, preview_label, usage_info_label]
            # for elem in clickable_elements:
            #      elem.bind("<Button-1>", partial(self._handle_profile_selection, profile_id_str, row_frame))
            
            # --- Create a frame for arrow buttons, to group them vertically on the side ---
            arrow_buttons_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            # Place this frame in column 2 of the row_frame, aligned to the right.
            arrow_buttons_frame.grid(row=0, column=2, sticky="e", padx=(2, 0))

            # Up arrow button within the arrow_buttons_frame
            up_arrow_button = ctk.CTkButton(arrow_buttons_frame, text="↑", width=25, command=partial(self._move_profile_up, profile_id_str))
            up_arrow_button.pack(side="top", pady=(0, 1))  # Stack on top, add padding below

            # Down arrow button within the arrow_buttons_frame
            down_arrow_button = ctk.CTkButton(arrow_buttons_frame, text="↓", width=25, command=partial(self._move_profile_down, profile_id_str))
            down_arrow_button.pack(side="top", pady=(1, 0)) # Stack below the up arrow, add padding above

            # --- Separator ---
            separator = ctk.CTkFrame(self.profile_scrollable_frame, height=1, fg_color=("gray80", "gray20"))
            separator.pack(fill="x", padx=5, pady=(0,3))

        self._update_management_button_states() # Update button states based on new list & selection
        self._check_process_button_state() # Also check process button state

    def _highlight_selected_profile(self, profile_id_to_select: str):
        """Highlights the specified profile row and unhighlights others."""
        # This method might be removed or repurposed if highlighting is not used with checkboxes
        # For now, let's assume it's not directly used by checkbox selection
        self._unhighlight_all_profiles() 
        
        if profile_id_to_select in self.selected_profile_frames: # self.selected_profile_frames might be deprecated
            frame_to_highlight = self.selected_profile_frames[profile_id_to_select]
            # frame_to_highlight.configure(fg_color=self.selected_profile_color) # No longer changing bg color based on this
            # for child in frame_to_highlight.winfo_children():
            #     if isinstance(child, ctk.CTkFrame):
            #         child.configure(fg_color=self.selected_profile_color)
            pass # Highlighting logic removed/commented for now

    def _unhighlight_all_profiles(self):
        """Removes highlight from all profile rows."""
        # This method might be removed or repurposed
        # for frame_id, frame in self.selected_profile_frames.items(): # self.selected_profile_frames might be deprecated
            # frame.configure(fg_color="transparent") 
            # for child in frame.winfo_children():
            #      if isinstance(child, ctk.CTkFrame):
            #         child.configure(fg_color="transparent")
        pass # Highlighting logic removed/commented for now

    def _handle_profile_selection(self, profile_id: str, selected_frame: ctk.CTkFrame, event=None):
        """Handles profile selection when a row is clicked. (Legacy - might be removed or adapted if single-click focus is needed)"""
        self.logger.debug(f"Legacy _handle_profile_selection called for: {profile_id}. Checkbox selection is primary.")
        # self.profile_radio_var.set(profile_id) # This sets the single-select var. Decide if still needed for Edit/Delete.
        
        # self._highlight_selected_profile(profile_id) # Highlighting removed from here

        # Update button states based on the new selection
        # self._update_management_button_states() # This should be called by checkbox toggle now
        # self._check_process_button_state() # This should be called by checkbox toggle now
        pass # Most logic moved to _handle_profile_checkbox_toggle

    def _handle_profile_checkbox_toggle(self, profile_id: str, checkbox_var: ctk.IntVar):
        """Handles the toggling of a profile selection checkbox."""
        if checkbox_var.get() == 1: # If checkbox is checked
            self.selected_profile_ids.add(profile_id)
        else:
            if profile_id in self.selected_profile_ids:
                self.selected_profile_ids.remove(profile_id)
        
        self._check_process_button_state()
        self._update_management_button_states() # Update based on new selection

    def _select_all_profiles(self):
        """Selects all profiles."""
        for profile_id, checkbox in self.profile_checkboxes.items():
            checkbox_var = self.profile_checkbox_vars.get(profile_id)
            if checkbox_var:
                checkbox_var.set(1) # Set underlying variable
                checkbox.select() # Visually select
            self.selected_profile_ids.add(profile_id)
        self._check_process_button_state()
        self._update_management_button_states()

    def _deselect_all_profiles(self):
        """Deselects all profiles."""
        for profile_id, checkbox in self.profile_checkboxes.items():
            checkbox_var = self.profile_checkbox_vars.get(profile_id)
            if checkbox_var:
                checkbox_var.set(0) # Set underlying variable
                checkbox.deselect() # Visually deselect
        self.selected_profile_ids.clear()
        self._check_process_button_state()
        self._update_management_button_states()

    def _move_profile_up(self, profile_id: str):
        """Moves the selected profile one position up in the order."""
        self.logger.info(f"Attempting to move profile ID {profile_id} up.")
        
        # --- Added Checks ---
        current_index = -1
        for i, p in enumerate(self.profiles_list):
            if str(p.id) == profile_id: # Ensure string comparison
                current_index = i
                break
        
        if current_index == -1:
            self.logger.error(f"Move Up Error: Profile ID {profile_id} not found in current UI list.")
            messagebox.showerror("Error", f"Could not find profile ID {profile_id} to move up.")
            return
            
        if current_index == 0: 
            self.logger.warning(f"Cannot move profile ID {profile_id} up. Already at top.")
            # No need for messagebox, button should be disabled, but good to log.
            return
            
        profile_to_move = self.profiles_list[current_index]
        profile_above = self.profiles_list[current_index - 1]

        # Check if adjacent profile is somehow missing (shouldn't happen with index check, but safety)
        if not profile_to_move or not profile_above:
             self.logger.error(f"Move Up Error: Profile data missing for ID {profile_id} or adjacent profile.")
             messagebox.showerror("Error", "Internal error: Profile data missing for reorder.")
             return
        # --- End Added Checks ---
            
        # Swap their order values
        original_order_move = profile_to_move.order
        original_order_above = profile_above.order
        
        # Ensure orders are valid integers before swapping
        if original_order_move is None or original_order_above is None:
            self.logger.error(f"Move Up Error: Missing order value for profile {profile_to_move.id} ({original_order_move}) or {profile_above.id} ({original_order_above}).")
            messagebox.showerror("Error", "Cannot reorder profiles with missing order values. Please contact support or reset profile order.")
            # Consider adding a way to reset/recalculate order if this happens
            return

        self.logger.info(f"Preparing to swap order: Profile {profile_to_move.id} (order {original_order_move}) <-> Profile {profile_above.id} (order {original_order_above})")
        
        updates = [
            (str(profile_to_move.id), original_order_above),
            (str(profile_above.id), original_order_move)
        ]
        
        # Call storage manager to update order
        try:
            success = self.storage_manager.update_profile_order(updates)
            if success:
                self.logger.info(f"Successfully updated order via storage manager for profiles {profile_to_move.id} and {profile_above.id}.")
                # Ensure selection is maintained after reload
                current_selection = self.profile_radio_var.get() 
                self._load_profiles() # Reload the list
                self.profile_radio_var.set(current_selection) # Reapply selection
                self._update_management_button_states() # Update highlights/states
            else:
                # This path means the repository returned False, indicating not all rows were updated
                self.logger.error(f"Storage manager failed to update order for profiles {profile_to_move.id} and {profile_above.id}. Repository returned False.")
                messagebox.showerror("Error", "Failed to update profile order. The database might be inconsistent.")
        except ProfileStorageError as e:
             self.logger.error(f"Storage error during profile order update: {e}", exc_info=True)
             messagebox.showerror("Error", f"Database error updating profile order: {e}")
        except Exception as e: # Catch any other unexpected errors
             self.logger.error(f"Unexpected error during profile order update: {e}", exc_info=True)
             messagebox.showerror("Error", f"An unexpected error occurred: {e}")

    def _move_profile_down(self, profile_id: str):
        """Moves the selected profile one position down in the order."""
        self.logger.info(f"Attempting to move profile ID {profile_id} down.")

        # --- Added Checks ---
        current_index = -1
        for i, p in enumerate(self.profiles_list):
            if str(p.id) == profile_id: # Ensure string comparison
                current_index = i
                break
        
        if current_index == -1:
            self.logger.error(f"Move Down Error: Profile ID {profile_id} not found in current UI list.")
            messagebox.showerror("Error", f"Could not find profile ID {profile_id} to move down.")
            return
            
        if current_index >= len(self.profiles_list) - 1:
            self.logger.warning(f"Cannot move profile ID {profile_id} down. Already at bottom.")
            # No need for messagebox, button should be disabled
            return
            
        profile_to_move = self.profiles_list[current_index]
        profile_below = self.profiles_list[current_index + 1]

        if not profile_to_move or not profile_below:
             self.logger.error(f"Move Down Error: Profile data missing for ID {profile_id} or adjacent profile.")
             messagebox.showerror("Error", "Internal error: Profile data missing for reorder.")
             return
        # --- End Added Checks ---
            
        # Swap their order values
        original_order_move = profile_to_move.order
        original_order_below = profile_below.order
        
        # Ensure orders are valid integers before swapping
        if original_order_move is None or original_order_below is None:
            self.logger.error(f"Move Down Error: Missing order value for profile {profile_to_move.id} ({original_order_move}) or {profile_below.id} ({original_order_below}).")
            messagebox.showerror("Error", "Cannot reorder profiles with missing order values. Please contact support or reset profile order.")
            return

        self.logger.info(f"Preparing to swap order: Profile {profile_to_move.id} (order {original_order_move}) <-> Profile {profile_below.id} (order {original_order_below})")
        
        updates = [
            (str(profile_to_move.id), original_order_below),
            (str(profile_below.id), original_order_move)
        ]
        
        # Call storage manager to update order
        try:
            success = self.storage_manager.update_profile_order(updates)
            if success:
                self.logger.info(f"Successfully updated order via storage manager for profiles {profile_to_move.id} and {profile_below.id}.")
                # Ensure selection is maintained after reload
                current_selection = self.profile_radio_var.get()
                self._load_profiles() # Reload the list
                self.profile_radio_var.set(current_selection) # Reapply selection
                self._update_management_button_states() # Update highlights/states
            else:
                self.logger.error(f"Storage manager failed to update order for profiles {profile_to_move.id} and {profile_below.id}. Repository returned False.")
                messagebox.showerror("Error", "Failed to update profile order. The database might be inconsistent.")
        except ProfileStorageError as e:
             self.logger.error(f"Storage error during profile order update: {e}", exc_info=True)
             messagebox.showerror("Error", f"Database error updating profile order: {e}")
        except Exception as e: # Catch any other unexpected errors
             self.logger.error(f"Unexpected error during profile order update: {e}", exc_info=True)
             messagebox.showerror("Error", f"An unexpected error occurred: {e}")

    def _on_profile_selected(self):
        """Callback function when a profile radio button is selected."""
        selected_id = self.profile_radio_var.get()
        print(f"Selected Profile ID: {selected_id}")
        # Enable/disable Edit button based on selection
        self._update_edit_button_state()
        # Also update other buttons that depend on selection
        self._update_management_button_states()
        # Add logic here later: 
        # - Load selected profile details? 
        # - Update other UI elements?
        # - Store the selection?

    def _update_edit_button_state(self):
        """Enables or disables the Edit Profile button based on selection."""
        if self.edit_profile_button:
            # Convert to int for checking, though 0 would also evaluate to False
            selected_id_str = self.profile_radio_var.get()
            if selected_id_str: # Check if a profile is selected (string is not empty)
                 self.edit_profile_button.configure(state="normal")
            else:
                 self.edit_profile_button.configure(state="disabled")

    def _confirm_delete_profile(self, profile_id: str, profile_name: str):
        """Shows confirmation dialog specifically for the delete button next to a profile."""
        # --- Added Check ---
        profile_exists_in_list = any(str(p.id) == profile_id for p in self.profiles_list)
        if not profile_exists_in_list:
             self.logger.error(f"Delete Confirmation Error: Profile ID {profile_id} ('{profile_name}') not found in current UI list before confirmation.")
             messagebox.showerror("Error", f"Cannot delete profile '{profile_name}'. It might have already been removed.")
             return
        # --- End Added Check ---

        self.logger.info(f"Showing delete confirmation for Profile ID: {profile_id}, Name: '{profile_name}'")
        msg = CTkMessagebox(title="Confirm Delete", 
                            message=f"Are you sure you want to permanently delete profile '{profile_name}' (ID: {profile_id})?",
                            icon="warning", option_1="Cancel", option_2="Delete")
        response = msg.get()

        if response == "Delete":
            self.logger.info(f"Deletion confirmed for Profile ID: {profile_id}")
            try:
                deleted = self.storage_manager.delete_profile(profile_id)
                if deleted:
                    self.logger.info(f"Profile {profile_id} deleted successfully via storage manager.")
                    # If the deleted profile was the selected one, clear selection
                    if self.profile_radio_var.get() == str(profile_id):
                         self.logger.info(f"Cleared selection as deleted profile {profile_id} was selected.")
                         self.profile_radio_var.set("") 
                    self._load_profiles() # Reload list
                    # Button states are updated implicitly by _load_profiles -> _handle_profile_selection or lack thereof
                else:
                    # This path means the repository returned False
                    self.logger.error(f"Storage manager failed to delete profile ID {profile_id} ('{profile_name}'). Repository returned False (profile likely not found in DB).")
                    CTkMessagebox(title="Error", message=f"Failed to delete profile '{profile_name}'. It might have already been removed or a database issue occurred.", icon="cancel")
            except ProfileStorageError as e:
                self.logger.error(f"Storage error during profile deletion (ID: {profile_id}): {e}", exc_info=True)
                CTkMessagebox(title="Error", message=f"Database error deleting profile: {e}", icon="cancel")
            except Exception as e: # Catch any other unexpected errors
                self.logger.error(f"Unexpected error during profile deletion (ID: {profile_id}): {e}", exc_info=True)
                CTkMessagebox(title="Error", message=f"An unexpected error occurred: {e}", icon="cancel")

    def _update_management_button_states(self):
        """Enables or disables Edit, Delete, Duplicate, Export buttons based on selection."""
        # selected_id_str = self.profile_radio_var.get() # Old single selection var
        # self.logger.debug(f"_update_management_button_states: Called with profile_radio_var = '{selected_id_str}'")
        # profile_selected = bool(selected_id_str) # Old single selection check

        num_selected = len(self.selected_profile_ids)
        self.logger.debug(f"_update_management_button_states: Called with {num_selected} profiles selected.")

        # Management buttons should only be active if exactly one profile is selected
        new_state = "normal" if num_selected == 1 else "disabled"
        
        if self.edit_profile_button: self.edit_profile_button.configure(state=new_state)
        if self.delete_profile_button: self.delete_profile_button.configure(state=new_state)
        if self.duplicate_profile_button: self.duplicate_profile_button.configure(state=new_state)
        if self.export_profile_button: self.export_profile_button.configure(state=new_state)
        # Import and Create buttons are always enabled

    def _setup_profile_controls(self):
        """Sets up the Create, Edit, Delete, Duplicate, Import, Export buttons below the profile list."""
        # Button Frame
        button_frame = ctk.CTkFrame(self.profile_frame)
        button_frame.grid(row=3, column=0, padx=10, pady=(10,10), sticky="ew")
        # Configure columns to distribute space. 3 main action buttons, then import/export.
        button_frame.grid_columnconfigure(0, weight=1) # Create
        button_frame.grid_columnconfigure(1, weight=1) # Edit
        button_frame.grid_columnconfigure(2, weight=1) # Delete
        button_frame.grid_columnconfigure(3, weight=1) # Duplicate
        button_frame.grid_columnconfigure(4, weight=0) # Spacer or separator
        button_frame.grid_columnconfigure(5, weight=1) # Import
        button_frame.grid_columnconfigure(6, weight=1) # Export

        self.create_profile_button = ctk.CTkButton(button_frame, text="Create New", command=self._open_profile_editor)
        self.create_profile_button.grid(row=0, column=0, padx=(0,5), pady=5, sticky="ew")

        self.edit_profile_button = ctk.CTkButton(button_frame, text="Edit Selected", command=self._edit_selected_profile, state="disabled")
        self.edit_profile_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        self.delete_profile_button = ctk.CTkButton(button_frame, text="Delete", command=self._delete_selected_profile, state="disabled", fg_color="#D32F2F", hover_color="#B71C1C")
        self.delete_profile_button.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        self.duplicate_profile_button = ctk.CTkButton(button_frame, text="Duplicate", command=self._duplicate_selected_profile, state="disabled")
        self.duplicate_profile_button.grid(row=0, column=3, padx=(5,10), pady=5, sticky="ew")
        
        # Optional: Add a small separator if desired visually
        # separator = ctk.CTkFrame(button_frame, width=2, fg_color=("gray70", "gray30"))
        # separator.grid(row=0, column=4, padx=5, pady=5, sticky="ns")

        self.import_profile_button = ctk.CTkButton(button_frame, text="Import", command=self._import_profile)
        self.import_profile_button.grid(row=0, column=5, padx=(10,5), pady=5, sticky="ew")

        self.export_profile_button = ctk.CTkButton(button_frame, text="Export", command=self._export_selected_profile, state="disabled")
        self.export_profile_button.grid(row=0, column=6, padx=(5,0), pady=5, sticky="ew")

        # Initial update
        self._update_management_button_states()

    def _open_profile_editor(self):
        """Opens the ProfileEditorWindow, assuming it handles create/edit internally now."""
        if not self.storage_manager:
            CTkMessagebox(title="Error", message="Storage Manager is not available.", icon="cancel")
            return
            
        # Instantiate ProfileEditorWindow WITHOUT mode/profile args
        editor = ProfileEditorWindow(
            master=self, 
            storage_manager=self.storage_manager, 
            on_save_callback=self._handle_save_callback 
            # We assume ProfileEditorWindow fetches profile if needed, or knows it's in create mode
        )
        # grab_set is handled within ProfileEditorWindow's __init__
        
    def _handle_save_callback(self, result: Optional[Dict]):
        """Handles the callback after the editor window is closed (saved or cancelled)."""
        if not result: # Cancelled or closed without saving
             return

        try:
            mode = result.get('mode')
            saved_profile = result.get('profile')

            if not saved_profile or not mode:
                self.logger.error(f"Save callback received invalid result dict: {result}")
                return

            # Ensure saved_profile is an AnalysisProfile object
            if not isinstance(saved_profile, AnalysisProfile):
                self.logger.error(f"Save callback profile is not an AnalysisProfile object: {type(saved_profile)}")
                return

            if mode == 'create':
                self.logger.info(f"Profile '{saved_profile.name}' created, reloading list.")
                self._load_profiles() # Refresh the list
                # Find the newly created profile ID to select it
                try:
                    # Use the ID directly from the saved object
                    new_profile_id_str = str(saved_profile.id)
                    # Call the corrected selection method
                    self._select_newly_created_profile(new_profile_id_str)
                    # self.logger.info(f"Selected newly created profile ID: {new_profile_id_str}") # Log is in _select_newly_created_profile
                    # _update_management_button_states is called by _select_newly_created_profile
                except AttributeError:
                     self.logger.error(f"Saved profile object lacks an ID attribute after creation.")

            elif mode == 'edit':
                # If editing was successful, reload and re-select
                self.logger.info(f"Profile (ID: {saved_profile.id}) updated, reloading list.")
                current_selection = str(saved_profile.id) # Keep track of the ID
                self._load_profiles() # Refresh the list
                self.profile_radio_var.set(current_selection) # Re-select the edited profile
                self._update_management_button_states() # Update highlights/states
            else:
                 self.logger.warning(f"Save callback received unknown mode: {mode}")

        except AttributeError as e:
            self.logger.error(f"Error accessing attributes in save callback result: {e}. Result was: {result}", exc_info=True)
        except Exception as e:
            self.logger.error(f"Unexpected error in _handle_save_callback: {e}", exc_info=True)

    # --- Wrapper methods to trigger actions from inline buttons using ID --- 
    def _trigger_edit_for_id(self, profile_id: Optional[str]):
        """Selects the profile by ID and triggers the main edit action."""
        if profile_id is None:
             self.logger.error("_trigger_edit_for_id called with None ID.")
             return
        self.logger.info(f"Inline edit button clicked for Profile ID: {profile_id}")
        # Set the selection variable first
        self.profile_radio_var.set(profile_id)
        # Find the corresponding frame to highlight (optional but good UI)
        self._update_management_button_states() # This will update highlights based on var
        # Call the main edit function which uses the selection variable
        self._edit_selected_profile()

    def _trigger_duplicate_for_id(self, profile_id: Optional[str]):
        """Selects the profile by ID and triggers the main duplicate action."""
        if profile_id is None:
             self.logger.error("_trigger_duplicate_for_id called with None ID.")
             return
        self.logger.info(f"Inline duplicate button clicked for Profile ID: {profile_id}")
        self.profile_radio_var.set(profile_id)
        self._update_management_button_states()
        self._duplicate_selected_profile()
        
    def _trigger_export_for_id(self, profile_id: Optional[str]):
        """Selects the profile by ID and triggers the main export action."""
        if profile_id is None:
             self.logger.error("_trigger_export_for_id called with None ID.")
             return
        self.logger.info(f"Inline export button clicked for Profile ID: {profile_id}")
        self.profile_radio_var.set(profile_id)
        self._update_management_button_states()
        self._export_selected_profile()
    # ---------------------------------------------------------------------

    def _edit_selected_profile(self):
        """Opens the profile editor for the currently selected profile."""
        selected_id_str = self.profile_radio_var.get()
        if not selected_id_str:
            messagebox.showwarning("No Selection", "Please select a profile to edit.")
            return

        try:
            # Use the selected ID string directly with the storage manager
            profile_to_edit = self.storage_manager.get_profile_by_id(selected_id_str)
            if profile_to_edit:
                # Pass the ID to the editor window
                self.logger.info(f"_edit_selected_profile: Opening editor, assuming it will handle ID {selected_id_str}")
                editor = ProfileEditorWindow(
                    master=self,
                    storage_manager=self.storage_manager,
                    profile_id=selected_id_str, # Pass the ID here
                    on_save_callback=self._handle_save_callback
                )
            else:
                # This case means the selected ID exists in the radio var but not in DB
                self.logger.error(f"Edit Error: Selected profile ID {selected_id_str} not found in storage.")
                messagebox.showerror("Error", f"Cannot edit profile. Profile ID {selected_id_str} not found in database. Please refresh.")
                # Maybe clear selection and reload?
                self.profile_radio_var.set("")
                self._load_profiles()

        except ValueError:
            messagebox.showerror("Error", f"Invalid profile selection: {selected_id_str}")
        except ProfileNotFoundError: # Should be caught by the check above, but good practice
             self.logger.error(f"Edit Error: Profile ID {selected_id_str} disappeared before edit dialog.")
             messagebox.showerror("Error", f"Cannot edit profile. Profile ID {selected_id_str} not found. It may have been deleted.")
             self.profile_radio_var.set("")
             self._load_profiles()
        except ProfileStorageError as e:
             self.logger.error(f"Storage error fetching profile {selected_id_str} for edit: {e}", exc_info=True)
             messagebox.showerror("Error", f"Database error loading profile for editing: {e}")

    def _delete_selected_profile(self):
        """Handles deleting the profile selected via the main radio buttons/list."""
        selected_id_str = self.profile_radio_var.get()
        if not selected_id_str:
            messagebox.showwarning("No Selection", "Please select a profile to delete.")
            return

        try:
            # Use the selected ID string directly
            profile_to_delete = self.storage_manager.load_profile(selected_id_str)
            
            if not profile_to_delete:
                self.logger.error(f"Delete Error: Selected profile ID {selected_id_str} not found in storage.")
                messagebox.showerror("Error", f"Cannot delete profile. Selection (ID: {selected_id_str}) not found in list. It may have already been deleted.")
                # Clear selection and reload to be safe
                self.profile_radio_var.set("")
                self._load_profiles() # Reloading here to sync UI if mismatch detected
                return
                
            profile_name = profile_to_delete.name # Get name from the found profile object

            self.logger.info(f"Showing delete confirmation for selected Profile ID: {selected_id_str}, Name: '{profile_name}'")
            # Use the same confirmation dialog as the inline button
            msg = CTkMessagebox(title="Confirm Delete", 
                                message=f"Are you sure you want to permanently delete the selected profile '{profile_name}' (ID: {selected_id_str})?",
                                icon="warning", option_1="Cancel", option_2="Delete")
            response = msg.get()

            if response == "Delete":
                self.logger.info(f"Deletion confirmed for selected Profile ID: {selected_id_str}")
                # Call the actual delete method (same as the inline button uses)
                try:
                    # Pass the string ID to delete_profile
                    deleted = self.storage_manager.delete_profile_by_id(selected_id_str)
                    if deleted:
                        self.logger.info(f"Profile {selected_id_str} deleted successfully via storage manager.")
                        self.profile_radio_var.set("") # Clear selection
                        self._load_profiles() # Reload list
                        # Button states updated implicitly by reload
                    else:
                        self.logger.error(f"Storage manager failed to delete profile ID {selected_id_str} ('{profile_name}'). Repository returned False (profile likely not found in DB).")
                        CTkMessagebox(title="Error", message=f"Failed to delete profile '{profile_name}'. It might have already been removed or a database issue occurred.", icon="cancel")
                except ProfileStorageError as e:
                     self.logger.error(f"Storage error during profile deletion (ID: {selected_id_str}): {e}", exc_info=True)
                     CTkMessagebox(title="Error", message=f"Database error deleting profile: {e}", icon="cancel")
                except Exception as e: # Catch any other unexpected errors
                     self.logger.error(f"Unexpected error during profile deletion (ID: {selected_id_str}): {e}", exc_info=True)
                     CTkMessagebox(title="Error", message=f"An unexpected error occurred: {e}", icon="cancel")

        except ValueError:
            messagebox.showerror("Error", f"Invalid profile selection for deletion: {selected_id_str}")
        # Note: Removed redundant ProfileStorageError and Exception handling here 
        # as it's now wrapped inside the 'if response == "Delete":' block.

    def _duplicate_selected_profile(self):
        """Duplicates the currently selected profile."""
        selected_id_str = self.profile_radio_var.get()
        self.logger.debug(f"_duplicate_selected_profile called for selection: '{selected_id_str}'")
        
        if not selected_id_str:
            CTkMessagebox(title="Info", message="No profile selected to duplicate.", icon="info")
            return
        
        # Simple dialog to get the new name
        dialog = ctk.CTkInputDialog(text="Enter name for the duplicated profile:", title="Duplicate Profile")
        new_name = dialog.get_input()
        
        if not new_name or not new_name.strip():
            self.logger.info("Duplicate profile cancelled or empty name entered.")
            return
        
        new_name = new_name.strip()
        
        try:
            # Load the original profile using the string ID
            original_profile = self.storage_manager.load_profile(selected_id_str)
            if not original_profile:
                # Should not happen if selection is valid, but handle defensively
                CTkMessagebox(title="Error", message=f"Cannot duplicate: Original profile with ID {selected_id_str} not found.", icon="cancel")
                return
            
            # Check if the new name already exists
            existing_with_new_name = self.storage_manager.get_profile_by_name(new_name)
            if existing_with_new_name:
                CTkMessagebox(title="Error", message=f"A profile with the name '{new_name}' already exists. Please choose a different name.", icon="warning")
                return
            
            # Call utility function, passing the storage manager and int ID
            cloned_profile = clone_profile(self.storage_manager, selected_id_str, new_name=new_name)
            if cloned_profile:
                 print(f"Profile duplicated successfully as '{cloned_profile.name}'")
                 self._load_profiles() # Refresh the list
                 # Optionally select the newly created profile
                 self.profile_radio_var.set(str(cloned_profile.id)) # Set selection back to string
                 self._update_management_button_states()
            # clone_profile raises ValueError on name conflict or if source not found
        except (ValueError, ProfileStorageError) as e: # Catch potential errors
             CTkMessagebox(title="Error", message=f"Failed to duplicate profile: {e}", icon="cancel")
        except Exception as e:
             print(f"Error during profile duplication: {e}")
             CTkMessagebox(title="Error", message=f"An unexpected error occurred during duplication: {e}", icon="cancel")

    def _export_selected_profile(self):
        """Handles the export button click."""
        selected_id_str = self.profile_radio_var.get()
        self.logger.debug(f"_export_selected_profile called for selection: '{selected_id_str}'")
        
        if not selected_id_str:
            CTkMessagebox(title="Info", message="No profile selected to export.", icon="info")
            return
            
        try:
            # Ensure export_profile_utility handles string ID
            export_profile_utility(self.storage_manager, selected_id_str) 
        except Exception as e:
            # Utility function handles its own errors and user feedback
            print(f"Error occurred during export process: {e}")

    def _import_profile(self):
        """Handles the import button click."""
        self.logger.info("Attempting to import profile...")
        import_profile_utility(self.storage_manager, on_success_callback=self._load_profiles)

    # --- Transcript Change Handling ---
    def _on_transcript_change_debounced(self):
        """Handles transcript changes after a debounce period."""
        # This method would be called by a debouncer
        self._check_process_button_state()

    def _check_process_button_state(self, *args): # Changed event=None to *args
        """Enables or disables the Process Transcript button based on transcript and profile selection."""
        transcript_present = self.transcript_input_component.textbox.get("0.0", "end-1c").strip()
        # profile_selected = self.profile_radio_var.get() # Old single selection check
        profiles_selected_count = len(self.selected_profile_ids)

        # if transcript_present and profile_selected: # Old condition
        if transcript_present and profiles_selected_count > 0:
            self.process_button.configure(state="normal")
        else:
            self.process_button.configure(state="disabled")

    def start_analysis_processing(self):
        """Initiates the analysis process for the selected profile(s) asynchronously."""
        if self.is_processing:
            self.logger.warning("Processing already in progress.")
            return

        current_transcript_text = self.transcript_input_component.textbox.get("0.0", "end-1c").strip()
        selected_ids_list = list(self.selected_profile_ids)

        if not current_transcript_text:
            self.logger.warning("Attempted to process with empty transcript.")
            CTkMessagebox(title="Input Required", message="Please enter some transcript text to process.", icon="warning")
            return
        
        if not selected_ids_list:
            self.logger.warning("Attempted to process without a profile selected.")
            CTkMessagebox(title="Input Required", message="Please select at least one Analysis Profile to use.", icon="warning")
            return

        self.logger.info(f"Starting asynchronous analysis for {len(selected_ids_list)} profile IDs: {selected_ids_list}")
        self.is_processing = True
        self.current_transcript_text_for_retry = current_transcript_text
        self.current_selected_ids_for_retry = selected_ids_list

        # Initialize per-profile analysis states
        for profile_id_to_init in selected_ids_list:
            self.analysis_status[profile_id_to_init] = 'loading'
            self.analysis_results[profile_id_to_init] = None  # Or some default empty state for results
            self.analysis_errors[profile_id_to_init] = None

        # Fetch profile names for initial UI update (can be done synchronously as it's quick)
        initial_profile_names_for_ui = []
        for profile_id_for_name in selected_ids_list:
            try:
                profile_obj = self.storage_manager.load_profile(profile_id_for_name)
                if profile_obj:
                    initial_profile_names_for_ui.append(profile_obj.name)
                else:
                    initial_profile_names_for_ui.append(f"ID: {profile_id_for_name} (Not Found)")
            except ProfileStorageError:
                initial_profile_names_for_ui.append(f"ID: {profile_id_for_name} (Error Loading)")

        self._update_ui_for_processing_start(initial_profile_names_for_ui) # Pass all names for initial message

        batch_context = {
            "profile_ids_to_process": selected_ids_list,
            "current_index": 0,
            "all_results": [],
            "processed_profile_names_success": [], # For success message
            "failed_profiles_info": {}, # {profile_id: error_message}
            "transcript_text": current_transcript_text,
            "initial_ui_profile_names": initial_profile_names_for_ui # For failure context message
        }
        
        # Start the asynchronous batch processing
        self.after(10, lambda: self._process_profile_batch_step(batch_context))

    def _process_profile_batch_step(self, context: Dict):
        """Processes one profile in the batch and schedules the next one."""
        if not self.is_processing:
            self.logger.info("Batch processing step detected cancellation.")
            # UI reset is handled by cancel_analysis_processing or _finalize_cancelled_processing
            return

        profile_ids = context["profile_ids_to_process"]
        current_index = context["current_index"]
        total_profiles = len(profile_ids)

        if current_index >= total_profiles:
            # All profiles processed, finalize the batch
            self._finalize_batch_processing(context)
            return

        profile_id = profile_ids[current_index]
        profile_to_use = None # Initialize for potential error logging
        
        try:
            self.progress_bar.set(float(current_index) / total_profiles) # Update progress before processing current
            profile_to_use = self.storage_manager.load_profile(profile_id)
            
            if not profile_to_use:
                self.logger.error(f"Profile ID {profile_id} not found during batch step.")
                context["failed_profiles_info"][profile_id] = "Profile not found."
                self.status_label.configure(text=f"Skipped: Profile ID {profile_id} not found ({current_index + 1}/{total_profiles})")
            else:
                self.status_label.configure(text=f"Processing: {profile_to_use.name} ({current_index + 1}/{total_profiles})...")
                self.logger.info(f"Simulating analysis for profile: {profile_to_use.name} ({current_index + 1}/{total_profiles})")
                
                # --- Placeholder for actual analysis call ---
                current_result_data = {
                    "profile_id": profile_id,
                    "profile_name": profile_to_use.name,
                    "json_data": {"message": f"Dummy JSON result for {profile_to_use.name}", "transcript_length": len(context["transcript_text"])},
                    "chat_data": [{"sender": "System", "text": f"Dummy chat result for {profile_to_use.name}"}]
                }
                # --- End Placeholder ---
                context["all_results"].append(current_result_data)
                context["processed_profile_names_success"].append(profile_to_use.name)

                # Update per-profile state for success
                self.analysis_status[profile_id] = 'success'
                self.analysis_results[profile_id] = current_result_data # Store the full data for now
                self.analysis_errors[profile_id] = None

        except ProfileStorageError as e:
            self.logger.error(f"Storage error loading profile {profile_id} in batch: {e}", exc_info=True)
            context["failed_profiles_info"][profile_id] = f"Storage error: {e}"
            self.status_label.configure(text=f"Error loading profile ID {profile_id} ({current_index + 1}/{total_profiles})")
            # Update per-profile state for error
            self.analysis_status[profile_id] = 'error'
            self.analysis_errors[profile_id] = {"type": "ProfileStorageError", "message": str(e)}
            self.analysis_results[profile_id] = None
        except Exception as e:
            profile_name_for_log = getattr(profile_to_use, 'name', 'N/A')
            self.logger.error(f"Error processing profile {profile_id} ({profile_name_for_log}) in batch: {e}", exc_info=True)
            context["failed_profiles_info"][profile_id] = f"Analysis error: {e}"
            self.status_label.configure(text=f"Error with profile {profile_name_for_log} ({current_index + 1}/{total_profiles})")
            # Update per-profile state for error
            self.analysis_status[profile_id] = 'error'
            self.analysis_errors[profile_id] = {"type": "AnalysisError", "message": str(e)}
            self.analysis_results[profile_id] = None
        
        # Schedule next step
        context["current_index"] += 1
        self.after(10, lambda: self._process_profile_batch_step(context))

    def _finalize_batch_processing(self, context: Dict):
        """Finalizes the batch processing, called after all profiles are attempted."""
        if not self.is_processing:
            self.logger.info("Finalizing batch processing detected cancellation.")
            # UI reset by cancel_analysis_processing
            return

        all_results = context["all_results"]
        failed_profiles_info = context["failed_profiles_info"]
        total_profiles_attempted = len(context["profile_ids_to_process"])
        initial_ui_profile_names = context["initial_ui_profile_names"]
        successful_profile_names = context["processed_profile_names_success"]

        self.progress_bar.set(1.0) # Mark progress as complete

        if failed_profiles_info:
            error_summary = f"{len(failed_profiles_info)} of {total_profiles_attempted} profiles failed. Failures: {failed_profiles_info}"
            self._handle_analysis_failure(
                error_message="One or more profiles failed during batch processing.",
                error_details={"summary": error_summary, "failed_ids_info": failed_profiles_info, "successful_results": all_results},
                processed_info=initial_ui_profile_names # Context of what was attempted
            )
        elif not all_results and total_profiles_attempted > 0:
             self._handle_analysis_failure(
                error_message="No results generated from batch. Profiles might be missing or had errors.",
                error_details={"summary": "No results obtained from selected profiles.", "failed_ids_info": failed_profiles_info},
                processed_info=initial_ui_profile_names
            )
        else: # Success or partial success with no critical failures that stopped the batch logic
            self._handle_analysis_success(successful_profile_names)
            
    def _finalize_cancelled_processing(self):
        """Resets UI elements when processing is cancelled."""
        self.logger.info("Finalizing UI for cancelled processing.")
        self.output_display_frame.hide_loading_message() 
        self.output_display_frame.clear_output() 
        self.status_label.configure(text="Analysis cancelled by user.")
        self.process_button.configure(text="Process Transcript", state="disabled") # Keep disabled until conditions met
        
        self.progress_bar.stop()
        self.progress_bar.set(0)
        self.progress_bar.grid_remove()
        self.time_estimate_frame.grid_remove()
        self.cancel_button.grid_remove()
        
        self._check_process_button_state() # Re-evaluate if process button should be enabled

    def _update_ui_for_processing_start(self, profile_names: List[str]):
        self.is_processing = True
        # self.current_processing_profiles = profile_names # This was used for a single name, now batch
        
        num_profiles = len(profile_names)
        if num_profiles == 1:
            display_name_for_status = profile_names[0]
        elif num_profiles > 1:
            display_name_for_status = f"{num_profiles} profiles"
        else:
            display_name_for_status = "selected profiles"

        self.logger.info(f"Updating UI for processing start with {display_name_for_status}")
        self.process_button.configure(text="Processing...", state="disabled")
        
        self.output_display_frame.show_loading_message(f"Preparing to process {display_name_for_status}...")
        
        self.status_label.configure(text=f"Starting for {display_name_for_status} (0/{num_profiles})")
        self.progress_bar.grid()
        self.progress_bar.set(0) # Start progress at 0
        self.progress_bar.configure(mode="determinate") # Use determinate mode for batch
        # self.progress_bar.start() # No longer indeterminate for batch
        self.time_estimate_label.configure(text="Calculating...") # Can be updated per profile later
        self.time_estimate_frame.grid()
        self.cancel_button.grid()

    def _handle_analysis_success(self, processed_profile_names: List[str]):
        """Handles UI updates and data display after successful analysis completion."""
        logger.info(f"Handling successful analysis for profiles: {processed_profile_names}")
        self.is_processing = False
        self.status_label.configure(text=f"Successfully processed {len(processed_profile_names)} profiles.")
        self.process_button.configure(state="normal", text="Start Analysis")
        self.progress_bar.set(0)
        self.progress_bar.grid_remove()

        # Prepare data for OutputDisplayFrame
        display_objects = []
        profile_id_to_name = {p.id: p.name for p in self.profiles_list}

        for profile_id in self.selected_profile_ids:
            profile_name = profile_id_to_name.get(profile_id, "Unknown Profile")
            status = self.analysis_status.get(profile_id, 'unknown') # Default to 'unknown' if not set
            result_data = self.analysis_results.get(profile_id)
            error_data = self.analysis_errors.get(profile_id)

            display_objects.append({
                "profile_id": profile_id,
                "profile_name": profile_name,
                "status": status,
                "result_data": result_data, # This will be the actual analysis output for this profile
                "error_data": error_data   # This will be any error specific to this profile's analysis
            })

        if self.output_display_frame:
            self.output_display_frame.set_data(display_objects) # Pass the list of display objects
            # Ensure the output frame is visible if it was hidden
            if not self.output_display_frame.winfo_ismapped():
                self.output_display_frame.grid()
            self.output_display_frame.show_content() # Ensure content area is shown, not loading message
        else:
            logger.error("OutputDisplayFrame is not initialized.")

    def _handle_analysis_failure(self, error_message, error_details=None, processed_info: Optional[List[str]] = None, is_retryable=True):
        self.is_processing = False # Ensure this is set
        
        processed_info_str = f" (Context: {', '.join(processed_info)})" if processed_info else ""
        self.logger.error(f"Analysis failed: {error_message}{processed_info_str}, Details: {error_details}")
        
        self.status_label.configure(text=f"Error: {error_message[:50]}...") # Truncate for status bar
        self.progress_bar.stop()
        self.progress_bar.configure(progress_color="red") # Indicate error on progress bar
        self.time_estimate_frame.grid_remove()
        self.cancel_button.grid_remove()

        self.output_display_frame.hide_loading_message()

        # Default error details if not provided
        if error_details is None:
            error_details = {"error_message": error_message}
        elif isinstance(error_details, str): # if only a string message was passed
            error_details = {"error_message": error_details, "details_string": error_details}

        # Determine the error type for OutputDisplayFrame more intelligently
        final_error_type = "generic" # Default to generic
        if "status_code" in error_details: # Likely an API error
            final_error_type = "api"
        elif "file_source" in error_details: # Likely a parsing error
            final_error_type = "parsing"
        # Add more conditions if other structured error types are expected

        self.output_display_frame.show_analysis_error(
            error_type=final_error_type, 
            details=error_details,
            retry_command=self.retry_analysis if is_retryable else None
        )
        self._check_process_button_state()

    def cancel_analysis_processing(self):
        """Cancel the ongoing analysis process."""
        self.logger.info("Analysis processing cancellation requested by user.")
        if not self.is_processing:
            self.logger.info("Cancellation requested, but no processing was active.")
            return
           
        self.is_processing = False # Crucial: set flag to stop asynchronous steps
        
        # Call the new method to reset UI specifically for cancellation
        self._finalize_cancelled_processing()

    def retry_analysis(self):
        self.logger.info("Retrying analysis...")
        self.output_display_frame.show_loading_message("Retrying analysis...") # Reset output display to loading
        self.start_analysis_processing()

    def _clear_error_message(self): # This might be deprecated if OutputDisplayFrame handles its own errors
        pass # OutputDisplayFrame manages its own error display.

    def run(self):
        """Starts the GrokApp main event loop."""
        self.logger.info("GrokApp running.")
        # Bind transcript text change to update button state
        # Using <KeyRelease> to capture text changes from typing, pasting, cutting
        self.transcript_input_component.textbox.bind("<KeyRelease>", self._check_process_button_state)
        # Bind profile selection change to update button state
        self.profile_radio_var.trace_add("write", self._check_process_button_state)

        # Initial UI state update after loading everything
        self._update_ui_for_initial_state()
        self.mainloop()

    def _update_ui_for_initial_state(self):
        """Sets the initial visibility of UI elements related to processing."""
        self.progress_bar.set(0)
        self.cancel_button.grid_remove()
        self.time_estimate_frame.grid_remove()
        self.error_display_frame.grid_remove() # This is the main app's error frame, not output_display's
        self.output_display_frame.clear_output() # Ensure output display is clear initially
        self._check_process_button_state() # Ensure process button is correctly set

    def _select_newly_created_profile(self, profile_id: str):
        """Selects and highlights a profile that was just created.
        This method no longer attempts to focus on the (now closed) editor window.
        """
        self.logger.debug(f"Attempting to select newly created profile: {profile_id}")

        # Update checkbox selection state
        if profile_id not in self.selected_profile_ids:
            # This logic assumes we want to primarily select the new one.
            # If multi-select is active, user can manually adjust later.
            # For now, let's make the new profile the primary (or sole) selection.
            
            # Option 1: Clear all other selections and select only the new one
            # for cb_id, var in self.profile_checkbox_vars.items():
            #     var.set(1 if cb_id == profile_id else 0)
            # self.selected_profile_ids = {profile_id} if profile_id in self.profile_checkbox_vars else set()

            # Option 2: Simply add to current selection if multi-select paradigm is preferred for new items
            if profile_id in self.profile_checkbox_vars:
                 self.profile_checkbox_vars[profile_id].set(1)
                 self.selected_profile_ids.add(profile_id)
            else:
                 self.logger.warning(f"Checkbox for new profile ID {profile_id} not found.")
        
        # Update the legacy radio variable if it's still used for single-action buttons like Edit/Delete
        self.profile_radio_var.set(profile_id) 

        # The ProfileListFrame (profile_scrollable_frame) should have updated its internal display
        # The _load_profiles method (called after save) rebuilds the list.
        # We need to ensure the UI reflects the selection.
        # The _handle_profile_checkbox_toggle method updates button states.
        # If a visual highlight beyond the checkbox is needed, that logic would go here or be
        # triggered by the checkbox state change. For now, checkbox itself is the indicator.

        self.logger.info(f"Set selection for newly created profile ID: {profile_id}")
        
        self._update_management_button_states() # Update Edit/Delete/etc button states
        self._check_process_button_state()      # Update Process button state

    def _reset_profile_analysis_state(self, profile_ids_to_reset: Optional[List[str]] = None):
        """Resets the analysis state for specified or all profiles."""
        self.logger.debug(f"Resetting analysis state for profiles: {profile_ids_to_reset if profile_ids_to_reset else 'all'}")

        ids_to_process = []
        if profile_ids_to_reset is None:
            # Get all profile IDs that have any state stored
            # This ensures we only try to pop/set for existing entries if we choose to iterate over a specific dict's keys
            # A more robust way is to collect all known profile IDs from self.profiles_list or storage if available,
            # but for now, let's assume we only care about those with existing state.
            # A simpler approach: iterate over a copy of keys from one of the state dicts.
            ids_to_process = list(self.analysis_status.keys()) 
        else:
            ids_to_process = profile_ids_to_reset

        for profile_id in ids_to_process:
            self.analysis_status.pop(profile_id, None) # Remove or set to idle
            self.analysis_results.pop(profile_id, None)
            self.analysis_errors.pop(profile_id, None)
            # Optionally, set to a default 'idle' state if preferred over popping
            # self.analysis_status[profile_id] = 'idle'
        
        # Potentially trigger a UI update for the output display if it needs to clear views
        if self.output_display_frame:
            # Prepare data for OutputDisplayFrame - similar to _handle_analysis_success
            display_objects = []
            profile_id_to_name = {p.id: p.name for p in self.profiles_list}
            
            for profile_id in self.selected_profile_ids:
                profile_name = profile_id_to_name.get(profile_id, "Unknown Profile")
                status = self.analysis_status.get(profile_id, 'idle') # Default to 'idle' after reset
                result_data = self.analysis_results.get(profile_id)
                error_data = self.analysis_errors.get(profile_id)
                
                display_objects.append({
                    "profile_id": profile_id,
                    "profile_name": profile_name,
                    "status": status,
                    "result_data": result_data,
                    "error_data": error_data
                })
            
            # Update the current_data_list in OutputDisplayFrame and refresh the UI
            self.output_display_frame.current_data_list = display_objects
            self.output_display_frame.refresh_profile_outputs() # Updates views based on current_data_list

if __name__ == "__main__":
    app = GrokApp()
    app.run() 