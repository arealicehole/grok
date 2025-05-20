import tkinter
import tkinter.messagebox as messagebox
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox  # Ensure this is installed or handled
import os
from functools import partial # Needed for delete button command
import threading
import queue
import logging
from typing import Optional, Dict, List, Any # Added List, Any
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
        self.geometry("900x700")
        ctk.set_appearance_mode("System")  # Use system theme (light/dark)
        ctk.set_default_color_theme("blue") # Default color theme

        # Configure grid layout 
        self.grid_columnconfigure(0, weight=3) # Transcript column (larger)
        self.grid_columnconfigure(1, weight=1) # Profile column (smaller)
        self.grid_rowconfigure(0, weight=0)    # Header row fixed size
        self.grid_rowconfigure(1, weight=1)    # Main content row expands
        self.grid_rowconfigure(2, weight=0)    # Controls (Process button) row
        self.grid_rowconfigure(3, weight=0)    # Status/Progress row
        self.grid_rowconfigure(4, weight=0)    # Error display row
        self.grid_rowconfigure(5, weight=0)    # Original Bottom bar (char count etc.) row

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
        self.profile_frame.grid_rowconfigure(1, weight=0) # Filter/Sort row
        self.profile_frame.grid_rowconfigure(2, weight=1) # Scrollable frame row expands
        self.profile_frame.grid_rowconfigure(3, weight=0) # Button frame row fixed size

        # Profile section label
        self.profile_label = ctk.CTkLabel(self.profile_frame, text="Analysis Profiles", font=ctk.CTkFont(size=16, weight="bold"))
        self.profile_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")

        # --- Filter and Sort Controls Frame ---
        self.profile_filter_sort_frame = ctk.CTkFrame(self.profile_frame, fg_color="transparent")
        self.profile_filter_sort_frame.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="ew")
        self.profile_filter_sort_frame.grid_columnconfigure(0, weight=1) # Filter entry
        self.profile_filter_sort_frame.grid_columnconfigure(1, weight=0) # Sort dropdown

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

        # Scrollable frame for profile list
        self.profile_scrollable_frame = ctk.CTkScrollableFrame(self.profile_frame)
        self.profile_scrollable_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # --- Setup Profile Control Buttons ---
        self._setup_profile_controls()

        # --- Processing Controls Frame (Row 2) ---
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

        self.progress_bar = ctk.CTkProgressBar(self.status_frame, width=250) # Increased width
        self.progress_bar.grid(row=0, column=1, padx=10, pady=5, sticky="e")
        self.progress_bar.set(0) # Initial state
        # self.progress_bar.grid_remove() # Initially hidden, shown during processing

        self.time_estimate_frame = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        self.time_estimate_frame.grid(row=0, column=2, padx=10, pady=5, sticky="e")
        # self.time_estimate_frame.grid_remove() # Initially hidden

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
        # self.cancel_button.grid_remove() # Initially hidden

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
        self.profile_buttons = {} # Clear stored radio buttons
        self.profile_row_frames = [] # Clear stored row frames
        self.selected_profile_frames.clear()

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
            return

        selected_profile_id_str = self.profile_radio_var.get()
        
        # Re-populate with (potentially filtered and sorted) profiles
        for profile in self.profiles_list: # Iterate over the updated self.profiles_list
            profile_id_str = str(profile.id) # Ensure ID is string for var and dict keys

            # --- Create a frame for each profile row ---
            row_frame = ctk.CTkFrame(self.profile_scrollable_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=(2,0), padx=2) # Pack the row frame
            # Configure row_frame to have two columns: details (weight 1) and arrows container (weight 0)
            row_frame.grid_columnconfigure(0, weight=1) # Main content (details_frame)
            row_frame.grid_columnconfigure(1, weight=0) # Column for the arrow_buttons_frame
            
            self.profile_row_frames.append(row_frame) # Store for potential highlighting later
            self.selected_profile_frames[profile_id_str] = row_frame

            # --- Profile Details Frame (within row_frame) ---
            details_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            details_frame.grid(row=0, column=0, sticky="ew", padx=(5,0))
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

            # --- Clickable area for selection ---
            # Bind click to the details_frame for selection
            # Using partial to pass profile_id and the specific row_frame to the handler
            clickable_elements = [row_frame, details_frame, name_label, preview_label, usage_info_label]
            for elem in clickable_elements:
                 elem.bind("<Button-1>", partial(self._handle_profile_selection, profile_id_str, row_frame))
            
            # --- Create a frame for arrow buttons, to group them vertically on the side ---
            arrow_buttons_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            # Place this frame in column 1 of the row_frame, aligned to the right.
            arrow_buttons_frame.grid(row=0, column=1, sticky="e", padx=(2, 0))

            # Up arrow button within the arrow_buttons_frame
            up_arrow_button = ctk.CTkButton(arrow_buttons_frame, text="↑", width=25, command=partial(self._move_profile_up, profile_id_str))
            up_arrow_button.pack(side="top", pady=(0, 1))  # Stack on top, add padding below

            # Down arrow button within the arrow_buttons_frame
            down_arrow_button = ctk.CTkButton(arrow_buttons_frame, text="↓", width=25, command=partial(self._move_profile_down, profile_id_str))
            down_arrow_button.pack(side="top", pady=(1, 0)) # Stack below the up arrow, add padding above

            # --- Separator ---
            separator = ctk.CTkFrame(self.profile_scrollable_frame, height=1, fg_color=("gray80", "gray20"))
            separator.pack(fill="x", padx=5, pady=(0,3))

        # Re-apply selection highlight if a profile was previously selected
        if selected_profile_id_str and selected_profile_id_str in self.selected_profile_frames:
            self._highlight_selected_profile(selected_profile_id_str)
        else: # If previous selection is not in the list (e.g. filtered out), clear selection
            self.profile_radio_var.set("") 
            self._unhighlight_all_profiles()

        self._update_management_button_states() # Update button states based on new list & selection

    def _highlight_selected_profile(self, profile_id_to_select: str):
        """Highlights the specified profile row and unhighlights others."""
        self._unhighlight_all_profiles() # Clear previous highlights
        
        if profile_id_to_select in self.selected_profile_frames:
            frame_to_highlight = self.selected_profile_frames[profile_id_to_select]
            frame_to_highlight.configure(fg_color=self.selected_profile_color)
            # Also ensure child frames/labels get a consistent background or are transparent
            for child in frame_to_highlight.winfo_children():
                if isinstance(child, ctk.CTkFrame): # If it's the details_frame
                    child.configure(fg_color=self.selected_profile_color)

    def _unhighlight_all_profiles(self):
        """Removes highlight from all profile rows."""
        for frame_id, frame in self.selected_profile_frames.items():
            frame.configure(fg_color="transparent") # Reset to default/transparent
            for child in frame.winfo_children():
                 if isinstance(child, ctk.CTkFrame): # If it's the details_frame
                    child.configure(fg_color="transparent")

    def _handle_profile_selection(self, profile_id: str, selected_frame: ctk.CTkFrame, event=None):
        """Handles profile selection when a row is clicked."""
        self.logger.debug(f"Profile selection changed to: {profile_id}")
        self.profile_radio_var.set(profile_id) # Update the variable that tracks selection
        
        self._highlight_selected_profile(profile_id)

        # Update button states based on the new selection
        self._update_management_button_states()
        self._check_process_button_state() # Check if process button should be enabled

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
        selected_id_str = self.profile_radio_var.get()
        self.logger.debug(f"_update_management_button_states: Called with profile_radio_var = '{selected_id_str}'")
        profile_selected = bool(selected_id_str)
        new_state = "normal" if profile_selected else "disabled"
        
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
                    self.profile_radio_var.set(new_profile_id_str)
                    self.logger.info(f"Selecting newly created profile ID: {new_profile_id_str}")
                    self._update_management_button_states() # Update highlights/states
                except AttributeError:
                     self.logger.error(f"Saved profile object lacks an ID attribute after creation.")
                except Exception as e:
                     self.logger.error(f"Error selecting newly created profile '{saved_profile.name}': {e}")

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
        # Any other logic that needs to run on transcript change

    # --- Processing Controls and Status Methods ---
    def _check_process_button_state(self, *args): # Changed event=None to *args
        """Enable or disable the Process button based on transcript and profile selection."""
        transcript_text = self.transcript_input_component.textbox.get("1.0", "end-1c").strip()
        # Check if placeholder is active (using component's method if available, otherwise direct check)
        is_placeholder = self.transcript_input_component.is_placeholder_active() if hasattr(self.transcript_input_component, 'is_placeholder_active') else (transcript_text == "Paste your transcript here...")
        
        has_text = transcript_text and not is_placeholder
        has_profile = bool(self.profile_radio_var.get())

        if has_text and has_profile:
            self.process_button.configure(state="normal")
        else:
            self.process_button.configure(state="disabled")

    def start_analysis_processing(self):
        """Start the transcript analysis process."""
        if not self.profile_radio_var.get(): # Double check profile selection
            self.logger.warning("start_analysis_processing called with no profile selected.")
            CTkMessagebox(title="No Profile", message="Please select an Analysis Profile to proceed.", icon="warning")
            return
        if not self.transcript_input_component.textbox.get("1.0", "end-1c").strip() or \
           (hasattr(self.transcript_input_component, 'is_placeholder_active') and self.transcript_input_component.is_placeholder_active()):
            self.logger.warning("start_analysis_processing called with no transcript text.")
            CTkMessagebox(title="No Transcript", message="Please enter some transcript text to process.", icon="warning")
            return

        self.is_processing = True
        # transcript_text = self.transcript_input_component.textbox.get("1.0", "end-1c") # Get fresh text
        selected_profile_id = self.profile_radio_var.get()
        
        # Find profile name - assumes self.profiles_list is populated correctly
        profile_name = "Selected Profile"
        for p in self.profiles_list:
            if str(p.id) == selected_profile_id:
                profile_name = p.name
                break
        
        self.logger.info(f"Starting analysis with profile: {profile_name} (ID: {selected_profile_id})")

        # Update UI for processing state
        self._update_ui_for_processing_start(profile_name)
        
        # TODO: Here we'll later add the actual backend processing call (Task 4)
        # For now, simulate with a timer for UI testing
        # Simulating some work then calling success/failure handlers
        self.logger.debug("Simulating analysis start...")
        # Example: self.after(2000, lambda: self._handle_analysis_success({"data": "Sample result"}, profile_name))
        self.after(1000, lambda: self._update_progress(0.1, profile_name)) # Start progress simulation

    def _update_ui_for_processing_start(self, profile_name):
        self.process_button.configure(text="Processing...", state="disabled")
        self.status_label.configure(text=f"Processing with {profile_name}...")
        self.progress_bar.configure(mode="indeterminate") # Start as indeterminate
        self.progress_bar.start()
        # self.progress_bar.grid() # Ensure it's visible
        self.cancel_button.grid() # Show cancel button
        self.time_estimate_frame.grid() # Show time estimate frame
        self.time_estimate_label.configure(text="Estimating...")
        self._clear_error_message() # Clear any previous errors

    def _update_progress(self, progress_value, profile_name):
        """Simulate progress updates (will be replaced with actual backend progress)."""
        if not self.is_processing: # Stop if cancelled
            self.logger.debug("_update_progress called but not processing, returning.")
            return
           
        if progress_value < 1.0:
            self.progress_bar.configure(mode="determinate") # Switch to determinate if we have progress
            self.progress_bar.set(progress_value)
            
            remaining_seconds = int((1.0 - progress_value) * 30)  # Example: 30 sec total time for simulation
            self.time_estimate_label.configure(text=f"~{remaining_seconds}s left")
            
            self.logger.debug(f"Simulating progress: {progress_value*100:.0f}%")
            self.after(500, lambda: self._update_progress(progress_value + 0.1, profile_name)) # Simulate next step
        else:
            self.logger.debug("Simulated progress complete. Calling success handler.")
            # Simulate a small delay before marking as complete
            self.after(200, lambda: self._handle_analysis_success({"sample_result": "Analysis was successful!"}, profile_name))

    def _handle_analysis_success(self, result_data, profile_name):
        """Handle successful completion of analysis."""
        self.logger.info(f"Analysis successful for profile: {profile_name}")
        self.is_processing = False
        self.progress_bar.stop()
        self.progress_bar.set(1.0)
        self.status_label.configure(text=f"✔️ Analysis complete: {profile_name}")
        self.process_button.configure(text="Process Transcript", state="normal") # Re-enable
        self._check_process_button_state() # Final check on button state
        self.cancel_button.grid_remove()
        self.time_estimate_frame.grid_remove()
        
        # TODO: Here we'll later add code to display results in the results panel (Task 5)
        self.logger.debug(f"Result data: {result_data}")
        # Example: Display a success message box for now
        # CTkMessagebox(title="Success", message=f"Analysis with '{profile_name}' completed successfully!", icon="check")

    def _handle_analysis_failure(self, error_message, error_type="error", is_retryable=True):
        """Handle analysis failure with appropriate error display."""
        self.logger.error(f"Analysis failed. Error: {error_message}, Type: {error_type}, Retryable: {is_retryable}")
        self.is_processing = False
        self.progress_bar.stop()
        self.progress_bar.set(0)
        self.status_label.configure(text="❌ Analysis failed. See details below.")
        self.process_button.configure(text="Process Transcript", state="normal") # Re-enable
        self._check_process_button_state() # Final check on button state
        self.cancel_button.grid_remove()
        self.time_estimate_frame.grid_remove()
        
        self.error_message_label.configure(text=str(error_message)) # Ensure message is string
        
        if error_type == "warning":
            self.error_display_frame.configure(fg_color=("#FFFBE6", "#5A5000")) # Light Yellow / Dark Yellow
            self.error_icon_label.configure(text="⚠️")
        elif error_type == "info":
            self.error_display_frame.configure(fg_color=("#E6F4FF", "#003A5A")) # Light Blue / Dark Blue
            self.error_icon_label.configure(text="ℹ️")
        else:  # default to error
            self.error_display_frame.configure(fg_color=("#FFE6E6", "#5A0000")) # Light Red / Dark Red
            self.error_icon_label.configure(text="❌")
        
        if is_retryable:
            self.retry_button.grid()
        else:
            self.retry_button.grid_remove()
        
        self.error_display_frame.grid() # Show error display

    def cancel_analysis_processing(self):
        """Cancel the ongoing analysis process."""
        self.logger.info("User initiated cancel processing.")
        if not self.is_processing:
            return
           
        # TODO: Here we'll later add code to signal the backend to stop processing (Task 4)
        
        self.is_processing = False # Crucial to stop simulated progress loops
        self.progress_bar.stop()
        self.progress_bar.set(0)
        self.status_label.configure(text="✖️ Analysis cancelled by user.")
        self.process_button.configure(text="Process Transcript", state="normal")
        self._check_process_button_state()
        self.cancel_button.grid_remove()
        self.time_estimate_frame.grid_remove()
        # Optionally show a message box or just update status label
        # CTkMessagebox(title="Cancelled", message="Analysis processing has been cancelled.", icon="info")

    def retry_analysis(self):
        """Retry the analysis after an error."""
        self.logger.info("Retrying analysis...")
        self._clear_error_message()
        # It's important that the Process button is enabled before calling start_analysis_processing
        # if it relies on the button's state or if start_analysis_processing checks its own conditions.
        self.start_analysis_processing()

    def _clear_error_message(self):
        """Clear and hide the error display."""
        self.error_display_frame.grid_remove()
        # Optionally reset status label if it's showing a generic error message
        if "failed" in self.status_label.cget("text").lower():
            self.status_label.configure(text="Ready")

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
        # self.progress_bar.grid_remove() # Keep it visible but at 0
        self.cancel_button.grid_remove()
        self.time_estimate_frame.grid_remove()
        self.error_display_frame.grid_remove()
        self._check_process_button_state() # Ensure process button is correctly set

if __name__ == "__main__":
    app = GrokApp()
    app.run() 