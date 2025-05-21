import customtkinter as ctk
from .output_display.error_display import ErrorDisplayFrame
from .output_display.json_view import JsonViewFrame
from .output_display.chat_view import ChatViewFrame
from typing import List, Dict, Any, Optional # Added for type hinting

class OutputDisplayFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_rowconfigure(0, weight=0) # TabView row (or main content area if no explicit toggle frame)
        self.grid_rowconfigure(1, weight=0) # Truncation controls row
        self.grid_columnconfigure(0, weight=1)

        # self.current_view_mode = "json" # This will be managed per tab if tabs have their own views
        self.current_data_list: Optional[List[Dict[str, Any]]] = None # Store the list of results
        self.active_tab_name: Optional[str] = None

        # Store references to view instances within each tab: {tab_name: {'json_view': ..., 'chat_view': ...}}
        self.tab_views_widgets: Dict[str, Dict[str, Any]] = {}

        # Main content will now be a TabView
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10,5))
        # If no tabs initially, provide a placeholder message
        # self.tab_view.add("placeholder_tab") # Add a placeholder if needed or handle empty state
        # self.tab_view.set("placeholder_tab")
        # ctk.CTkLabel(self.tab_view.tab("placeholder_tab"), text="No analysis results to display.").pack(expand=True)
        self._show_no_results_placeholder() # Call method to handle initial empty state

        # The old toggle frame for JSON/Chat is removed as this will be per-tab or managed differently.
        # self.toggle_frame = ctk.CTkFrame(self, fg_color="transparent") ...
        # self.json_button = ctk.CTkButton(self.toggle_frame, ...) ...
        # self.chat_button = ctk.CTkButton(self.toggle_frame, ...) ...

        # The old single content_frame is replaced by the TabView's tabs.
        # self.content_frame = ctk.CTkFrame(self, fg_color="transparent") ...
        # self.json_view = JsonViewFrame(self.content_frame) # Old single instance
        # self.chat_view = ChatViewFrame(self.content_frame) # Old single instance

        # Bottom: Truncation Controls Frame 
        self.truncation_controls_frame = ctk.CTkFrame(self, fg_color="transparent", height=30)
        self.truncation_controls_frame.grid(row=1, column=0, padx=10, pady=(0,5), sticky="ew")
        self.truncation_status_label = ctk.CTkLabel(self.truncation_controls_frame, text="")
        self.view_full_json_button = ctk.CTkButton(self.truncation_controls_frame, text="Save Full JSON", command=self._save_full_json_active_tab)
        self.save_full_chat_button = ctk.CTkButton(self.truncation_controls_frame, text="Save Full Chat", command=self._save_full_chat_active_tab)
        self.truncation_controls_frame.grid_remove() # Initially hidden

        # Error Display Frame (overlays content when active)
        self.error_display = ErrorDisplayFrame(self)
        # Error display will now be on top of the tab_view (row 0) and truncation controls (row 1)
        self.error_display.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=10, pady=10)
        self.error_display.grid_remove() # Hide it initially

        # self._update_button_states() # This is likely obsolete or needs rework for per-tab controls
        # self.switch_view(self.current_view_mode) # Old call, tabs manage their own views
        self._update_truncation_controls() # Initial check (will be empty)

    def _show_no_results_placeholder(self):
        try:
            self.tab_view.add("status_tab")
            self.tab_view.set("status_tab") # Make it active
        except Exception:
             # If tab exists, just get it
            if "status_tab" not in self.tab_view._name_list:
                 # This case should ideally not be reached if logic is correct
                 # but as a fallback, try to delete and re-add if something is weird
                try: self.tab_view.delete("status_tab") 
                except Exception: pass
                self.tab_view.add("status_tab")
        
        placeholder_label = ctk.CTkLabel(self.tab_view.tab("status_tab"), text="No analysis results to display.", font=ctk.CTkFont(size=14))
        placeholder_label.pack(expand=True, padx=20, pady=20)
        # Ensure this placeholder label is tracked if we need to remove it later
        if "status_tab" not in self.tab_views_widgets:
            self.tab_views_widgets["status_tab"] = {}
        self.tab_views_widgets["status_tab"]['placeholder_label'] = placeholder_label

    def _clear_tabs(self):
        # Clear stored widget references
        self.tab_views_widgets.clear()
        # Delete all existing tabs from the tab_view
        for tab_name in list(self.tab_view._name_list): # Iterate over a copy of the list
            try:
                self.tab_view.delete(tab_name)
            except Exception as e:
                print(f"Error deleting tab {tab_name}: {e}") # Log error but continue
        self.active_tab_name = None

    def show_loading_message(self, message: str = "Processing, please wait..."):
        """Displays a loading message, hiding other content."""
        self.tab_view.grid_remove()
        self.truncation_controls_frame.grid_remove()
        # Use the existing show_error with a "generic" type for loading
        self.error_display.show_error(
            error_type="generic",
            details={"custom_title": "Loading", "custom_message": message},
            icon="⏳" # Hourglass icon for loading
        )
        # No retry command for loading messages
        if self.error_display.retry_button.winfo_ismapped():
            self.error_display.retry_button.pack_forget()
        
        # Ensure copy button is also hidden for a simple loading message
        if self.error_display.copy_button.winfo_ismapped():
            self.error_display.copy_button.pack_forget()
            
        self.error_display.grid()

    def hide_loading_message(self):
        """Hides the loading message and restores content view."""
        self.error_display.clear_error() 
        self.error_display.grid_remove()
        # self.content_frame.grid() # Old: content_frame is gone
        self.tab_view.grid() # Ensure tab_view is visible
        self._update_truncation_controls()

    def _save_full_json_active_tab(self):
        active_tab = self.tab_view.get()
        if active_tab and active_tab in self.tab_views_widgets and self.tab_views_widgets[active_tab].get('json_view'):
            self.tab_views_widgets[active_tab]['json_view']._view_full_output()

    def _save_full_chat_active_tab(self):
        active_tab = self.tab_view.get()
        if active_tab and active_tab in self.tab_views_widgets and self.tab_views_widgets[active_tab].get('chat_view'):
            self.tab_views_widgets[active_tab]['chat_view'].save_full_chat_data_to_file()

    def _update_truncation_controls(self):
        self.truncation_status_label.pack_forget()
        self.view_full_json_button.pack_forget()
        self.save_full_chat_button.pack_forget()
        self.truncation_controls_frame.grid_remove() # Hide if not needed

        active_tab_name = self.tab_view.get() # Get current active tab name
        if not active_tab_name or active_tab_name not in self.tab_views_widgets or active_tab_name == "status_tab":
            return # No active or valid tab, or it's the placeholder

        tab_widgets = self.tab_views_widgets[active_tab_name]
        current_view_mode_for_tab = tab_widgets.get('current_view_mode', 'json') # Default to json
        json_view_instance = tab_widgets.get('json_view')
        chat_view_instance = tab_widgets.get('chat_view')

        show_bar = False
        status_text = ""

        if current_view_mode_for_tab == "json" and json_view_instance and json_view_instance.is_truncated:
            status_text = json_view_instance.status_label.cget("text")
            self.view_full_json_button.pack(side="right", padx=5)
            show_bar = True
        elif current_view_mode_for_tab == "chat" and chat_view_instance and chat_view_instance.is_truncated:
            total_msgs = len(chat_view_instance.full_chat_data) if chat_view_instance.full_chat_data else 0
            displayed_msgs = len(chat_view_instance._message_widgets) # Accessing protected member, consider getter
            status_text = f"Chat truncated. Displaying {displayed_msgs} of {total_msgs} messages."
            self.save_full_chat_button.pack(side="right", padx=5)
            show_bar = True
        
        if show_bar:
            self.truncation_status_label.configure(text=status_text)
            self.truncation_status_label.pack(side="left", padx=5)
            self.truncation_controls_frame.grid() 
        else:
            self.truncation_controls_frame.grid_remove()
    
    def _create_view_controls_for_tab(self, tab_frame: ctk.CTkFrame, tab_name: str):
        """Creates JSON/Chat toggle buttons for a specific tab."""
        toggle_frame = ctk.CTkFrame(tab_frame, fg_color="transparent") # Parent is the tab_frame
        toggle_frame.pack(pady=(5,0), padx=5, fill="x") # Pack at the top of the tab content

        json_button = ctk.CTkButton(toggle_frame, text="JSON View", 
                                    command=lambda t_name=tab_name: self._switch_tab_view(t_name, "json"))
        json_button.pack(side="left", padx=(0,5))

        chat_button = ctk.CTkButton(toggle_frame, text="Chat View", 
                                    command=lambda t_name=tab_name: self._switch_tab_view(t_name, "chat"))
        chat_button.pack(side="left", padx=0)
        
        self.tab_views_widgets[tab_name]['json_button'] = json_button
        self.tab_views_widgets[tab_name]['chat_button'] = chat_button
        self.tab_views_widgets[tab_name]['current_view_mode'] = 'json' # Default view for new tabs

    def _switch_tab_view(self, tab_name: str, mode: str):
        """Switches the view (JSON/Chat) within a specific tab."""
        if tab_name not in self.tab_views_widgets:
            return

        tab_data = self.tab_views_widgets[tab_name]
        tab_data['current_view_mode'] = mode

        json_view = tab_data.get('json_view')
        chat_view = tab_data.get('chat_view')

        if json_view: json_view.grid_remove()
        if chat_view: chat_view.grid_remove()

        if mode == "json" and json_view:
            json_view.grid(row=0, column=0, sticky="nsew")
        elif mode == "chat" and chat_view:
            chat_view.grid(row=0, column=0, sticky="nsew")
        
        self._update_tab_button_states(tab_name)
        if self.tab_view.get() == tab_name: # If this is the active tab
            self._update_truncation_controls() # Update truncation controls based on new view mode

    def _update_tab_button_states(self, tab_name: str):
        if tab_name not in self.tab_views_widgets:
            return
        
        tab_data = self.tab_views_widgets[tab_name]
        json_button = tab_data.get('json_button')
        chat_button = tab_data.get('chat_button')
        current_mode = tab_data.get('current_view_mode')

        if not json_button or not chat_button:
            return

        # Use theme colors for consistency
        default_fg = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        hover_fg = ctk.ThemeManager.theme["CTkButton"]["hover_color"] # Or a specific "active" color
        
        if current_mode == "json":
            json_button.configure(fg_color=default_fg) # Active view button
            chat_button.configure(fg_color=hover_fg) # Inactive view button
        elif current_mode == "chat":
            json_button.configure(fg_color=hover_fg)
            chat_button.configure(fg_color=default_fg)

    def set_data(self, data_list: Optional[List[Dict[str, Any]]]):
        self.current_data_list = data_list
        self._clear_tabs()
        self.error_display.grid_remove() # Clear any previous errors
        self.tab_view.grid() # Ensure tab_view is visible

        if not data_list:
            self._show_no_results_placeholder()
            self._update_truncation_controls()
            return

        first_tab_display_name = None # Store the display name for CTkTabview.set()
        for i, result_item in enumerate(data_list):
            profile_name = result_item.get("profile_name", f"Result {i+1}")
            # This unique_tab_key is for our internal tracking in self.tab_views_widgets
            unique_tab_key = f"tab_{profile_name.replace(' ','_').lower()}_{result_item.get('profile_id', i)}" 
            
            if i == 0: 
                first_tab_display_name = profile_name # This is what CTkTabview.add() uses

            current_tab_frame = self.tab_view.add(profile_name) # Use profile_name for display
            self.tab_views_widgets[unique_tab_key] = {} # Initialize dict for this tab using our unique key

            # Get the status for this profile
            status = result_item.get("status", "unknown")
            
            if status == "success":
                # Create view controls (JSON/Chat buttons) for successful results
                self._create_view_controls_for_tab(current_tab_frame, unique_tab_key)
                
                # Create a content area within the tab (below toggles)
                tab_content_area = ctk.CTkFrame(current_tab_frame, fg_color="transparent")
                tab_content_area.pack(expand=True, fill="both", padx=0, pady=0)
                tab_content_area.grid_rowconfigure(0, weight=1)
                tab_content_area.grid_columnconfigure(0, weight=1)
                
                # Create JsonView and ChatView instances for this tab
                json_view = JsonViewFrame(tab_content_area)
                chat_view = ChatViewFrame(tab_content_area)
                self.tab_views_widgets[unique_tab_key]['json_view'] = json_view
                self.tab_views_widgets[unique_tab_key]['chat_view'] = chat_view
                
                # Get result data from the appropriate field
                result_data = result_item.get("result_data", {})
                
                # Extract JSON and chat data from result_data
                json_data = result_data.get("json_data") if result_data else None
                chat_data = result_data.get("chat_data") if result_data else None
                
                # Populate views with data
                json_view.set_json_data(json_data)
                chat_view.set_chat_data(chat_data)
                
                # Set initial view for the tab (default to JSON)
                self._switch_tab_view(unique_tab_key, self.tab_views_widgets[unique_tab_key].get('current_view_mode', 'json'))
            
            elif status == "error":
                # For error state, display error message without JSON/Chat toggle
                error_data = result_item.get("error_data", {})
                error_message = "An error occurred during analysis."
                
                if isinstance(error_data, dict):
                    error_message = error_data.get("message", error_message)
                elif isinstance(error_data, str):
                    error_message = error_data
                
                error_frame = ctk.CTkFrame(current_tab_frame, fg_color=("gray95", "gray20"))
                error_frame.pack(expand=True, fill="both", padx=10, pady=10)
                
                error_icon = ctk.CTkLabel(error_frame, text="⚠️", font=ctk.CTkFont(size=24))
                error_icon.pack(pady=(20, 5))
                
                error_label = ctk.CTkLabel(error_frame, text=error_message, 
                                         wraplength=500, font=ctk.CTkFont(size=14))
                error_label.pack(pady=10, padx=20)
                
                # Store reference to error components
                self.tab_views_widgets[unique_tab_key]['error_frame'] = error_frame
                self.tab_views_widgets[unique_tab_key]['error_message'] = error_message
            
            elif status == "loading":
                # For loading state, display a loading indicator
                loading_frame = ctk.CTkFrame(current_tab_frame, fg_color="transparent")
                loading_frame.pack(expand=True, fill="both", padx=10, pady=10)
                
                loading_icon = ctk.CTkLabel(loading_frame, text="⏳", font=ctk.CTkFont(size=24))
                loading_icon.pack(pady=(40, 5))
                
                loading_label = ctk.CTkLabel(loading_frame, text="Processing...", 
                                           font=ctk.CTkFont(size=16))
                loading_label.pack(pady=10)
                
                # Store reference to loading components
                self.tab_views_widgets[unique_tab_key]['loading_frame'] = loading_frame
            
            else:
                # For unknown status, display a generic message
                unknown_frame = ctk.CTkFrame(current_tab_frame, fg_color="transparent")
                unknown_frame.pack(expand=True, fill="both", padx=10, pady=10)
                
                unknown_label = ctk.CTkLabel(unknown_frame, text=f"Status: {status}", 
                                          font=ctk.CTkFont(size=14))
                unknown_label.pack(pady=20)
                
                # Store reference
                self.tab_views_widgets[unique_tab_key]['unknown_frame'] = unknown_frame
        
        if first_tab_display_name:
            self.tab_view.set(first_tab_display_name) # Activate the first tab using its display name
            # Need to find our unique_tab_key that corresponds to first_tab_display_name if results are not empty
            if data_list: 
                first_result_item = data_list[0]
                first_profile_name = first_result_item.get("profile_name", f"Result 1")
                self.active_tab_name = f"tab_{first_profile_name.replace(' ','_').lower()}_{first_result_item.get('profile_id', 0)}"
        
        self.tab_view.configure(command=self._on_tab_change) # Update truncation on tab change
        self._update_truncation_controls()

    def _on_tab_change(self):
        # When a tab is changed by the user clicking on it, CTkTabview.get() returns the display name.
        # We need to find our internal unique_tab_key that corresponds to this display name.
        current_display_name = self.tab_view.get()
        found_key = None
        for key, widgets_dict in self.tab_views_widgets.items():
            # This check assumes profile_name used for adding tab is somewhat recoverable or stored.
            # A more robust way would be to store a mapping: display_name -> unique_tab_key when adding tabs.
            # For now, let's try to reconstruct based on the `tab_` prefix and profile name part of our key.
            # This is becoming fragile. Let's simplify: self.active_tab_name will be set by our internal logic (_switch_tab_view, set_data)
            # For _on_tab_change, we need to find the unique_tab_key from the display_name given by tab_view.get()
            
            # Simplified assumption: profile_name in the tab_view is unique enough for this lookup
            # More robust: When adding tabs, store {profile_name_display: unique_tab_key}
            # Let's assume for now the first part of unique_tab_key after "tab_" and before the ID is the profile_name used for adding.
            # This is not perfectly robust if profile names have underscores or numbers matching the ID part.
            
            # Iterating to find which unique_tab_key corresponds to current_display_name
            # This is inefficient. A direct mapping would be better.
            # For now, a quick and dirty way if profile_name is within the key for self.tab_views_widgets
            # Example: unique_tab_key = "tab_profile_alpha_id123", display_name = "Profile Alpha"
            # We need to match current_display_name with the name used in `self.tab_view.add(profile_name)`

            # To make this work correctly, we need to iterate through the original data_list 
            # and find the item whose profile_name matches current_display_name, then reconstruct its unique_tab_key.
            if self.current_data_list:
                for i, item_data in enumerate(self.current_data_list):
                    profile_name_from_data = item_data.get("profile_name", f"Result {i+1}")
                    if profile_name_from_data == current_display_name:
                        found_key = f"tab_{profile_name_from_data.replace(' ','_').lower()}_{item_data.get('profile_id', i)}"
                        break
            if found_key:
                break
        
        if found_key:
            self.active_tab_name = found_key
        else:
            # Fallback or error if we can't map display name back to our key
            # This might happen with "status_tab"
            if current_display_name == "status_tab" and "status_tab" in self.tab_views_widgets:
                self.active_tab_name = "status_tab"
            else:
                 print(f"Warning: Could not map tab display name '{current_display_name}' back to a unique_tab_key.")
                 self.active_tab_name = None # Or the first key in self.tab_views_widgets as a guess

        self._update_truncation_controls()

    def show_analysis_error(self, error_type: str, details: dict, retry_command=None):
        # self.content_frame.grid_remove() # Old
        self.tab_view.grid_remove() # Hide tab view on error
        self.truncation_controls_frame.grid_remove()
        self.error_display.show_error(error_type=error_type, details=details, retry_command=retry_command)
        self.error_display.grid() # Ensure error display is visible

    def clear_output(self):
        self.current_data_list = None
        self._clear_tabs()
        self._show_no_results_placeholder() # Show placeholder after clearing
        
        self.error_display.clear_error()
        self.error_display.grid_remove()
        # self.content_frame.grid() # Old
        self.tab_view.grid() # Ensure tab_view is visible
        self._update_truncation_controls()
        
    def show_content(self):
        """Ensures the tab view is visible and any overlay displays are hidden."""
        self.error_display.clear_error()
        self.error_display.grid_remove()
        self.tab_view.grid()
        self._update_truncation_controls()
    
    def refresh_profile_outputs(self):
        """
        Refreshes the content of all tabs based on the current state data in self.current_data_list.
        Unlike set_data, this method tries to update existing tabs rather than recreating everything.
        This is useful when the underlying data changes but tab structure remains the same.
        """
        if not self.current_data_list:
            # Nothing to refresh, show placeholder
            self._clear_tabs()
            self._show_no_results_placeholder()
            return
            
        # Track which profile_ids we've processed to identify tabs to remove later
        processed_profile_ids = set()
        
        for result_item in self.current_data_list:
            profile_id = result_item.get("profile_id")
            profile_name = result_item.get("profile_name", f"Result {profile_id}")
            status = result_item.get("status", "unknown")
            
            # Skip if no profile_id (should not happen with our design)
            if not profile_id:
                continue
                
            processed_profile_ids.add(profile_id)
            
            # Generate the unique_tab_key for this profile
            unique_tab_key = f"tab_{profile_name.replace(' ','_').lower()}_{profile_id}"
            
            # Check if we already have a tab for this profile
            tab_exists = False
            tab_display_name = None
            
            # Find if this profile has a tab by checking tab_views_widgets keys
            for key in self.tab_views_widgets.keys():
                if key == unique_tab_key:
                    tab_exists = True
                    break
            
            # Find the display name used in tab_view for this profile_id
            for display_name in self.tab_view._name_list:
                for result in self.current_data_list:
                    if result.get("profile_id") == profile_id and result.get("profile_name") == display_name:
                        tab_display_name = display_name
                        break
                if tab_display_name:
                    break
            
            if not tab_exists:
                # This is a new profile, create a new tab
                # Similar to what we do in set_data
                current_tab_frame = self.tab_view.add(profile_name)
                self.tab_views_widgets[unique_tab_key] = {}
                tab_display_name = profile_name
            else:
                # Tab exists, get its frame
                current_tab_frame = self.tab_view.tab(tab_display_name)
                # Clear existing content
                for widget in current_tab_frame.winfo_children():
                    widget.destroy()
                # Reset the widgets dict for this tab but preserve the key
                self.tab_views_widgets[unique_tab_key] = {}
            
            # Now populate the tab based on status (similar to set_data)
            if status == "success":
                # Create view controls (JSON/Chat buttons) for successful results
                self._create_view_controls_for_tab(current_tab_frame, unique_tab_key)
                
                # Create a content area within the tab (below toggles)
                tab_content_area = ctk.CTkFrame(current_tab_frame, fg_color="transparent")
                tab_content_area.pack(expand=True, fill="both", padx=0, pady=0)
                tab_content_area.grid_rowconfigure(0, weight=1)
                tab_content_area.grid_columnconfigure(0, weight=1)
                
                # Create JsonView and ChatView instances for this tab
                json_view = JsonViewFrame(tab_content_area)
                chat_view = ChatViewFrame(tab_content_area)
                self.tab_views_widgets[unique_tab_key]['json_view'] = json_view
                self.tab_views_widgets[unique_tab_key]['chat_view'] = chat_view
                
                # Get result data from the appropriate field
                result_data = result_item.get("result_data", {})
                
                # Extract JSON and chat data from result_data
                json_data = result_data.get("json_data") if result_data else None
                chat_data = result_data.get("chat_data") if result_data else None
                
                # Populate views with data
                json_view.set_json_data(json_data)
                chat_view.set_chat_data(chat_data)
                
                # Set initial view for the tab (default to JSON)
                self._switch_tab_view(unique_tab_key, self.tab_views_widgets[unique_tab_key].get('current_view_mode', 'json'))
            
            elif status == "error":
                # For error state, display error message without JSON/Chat toggle
                error_data = result_item.get("error_data", {})
                error_message = "An error occurred during analysis."
                
                if isinstance(error_data, dict):
                    error_message = error_data.get("message", error_message)
                elif isinstance(error_data, str):
                    error_message = error_data
                
                error_frame = ctk.CTkFrame(current_tab_frame, fg_color=("gray95", "gray20"))
                error_frame.pack(expand=True, fill="both", padx=10, pady=10)
                
                error_icon = ctk.CTkLabel(error_frame, text="⚠️", font=ctk.CTkFont(size=24))
                error_icon.pack(pady=(20, 5))
                
                error_label = ctk.CTkLabel(error_frame, text=error_message, 
                                         wraplength=500, font=ctk.CTkFont(size=14))
                error_label.pack(pady=10, padx=20)
                
                # Store reference to error components
                self.tab_views_widgets[unique_tab_key]['error_frame'] = error_frame
                self.tab_views_widgets[unique_tab_key]['error_message'] = error_message
            
            elif status == "loading":
                # For loading state, display a loading indicator
                loading_frame = ctk.CTkFrame(current_tab_frame, fg_color="transparent")
                loading_frame.pack(expand=True, fill="both", padx=10, pady=10)
                
                loading_icon = ctk.CTkLabel(loading_frame, text="⏳", font=ctk.CTkFont(size=24))
                loading_icon.pack(pady=(40, 5))
                
                loading_label = ctk.CTkLabel(loading_frame, text="Processing...", 
                                           font=ctk.CTkFont(size=16))
                loading_label.pack(pady=10)
                
                # Store reference to loading components
                self.tab_views_widgets[unique_tab_key]['loading_frame'] = loading_frame
            
            else:
                # For unknown status, display a generic message
                unknown_frame = ctk.CTkFrame(current_tab_frame, fg_color="transparent")
                unknown_frame.pack(expand=True, fill="both", padx=10, pady=10)
                
                unknown_label = ctk.CTkLabel(unknown_frame, text=f"Status: {status}", 
                                          font=ctk.CTkFont(size=14))
                unknown_label.pack(pady=20)
                
                # Store reference
                self.tab_views_widgets[unique_tab_key]['unknown_frame'] = unknown_frame
        
        # Remove tabs for profiles that are no longer in the current_data_list
        tabs_to_remove = []
        for key in self.tab_views_widgets.keys():
            if key == "status_tab":
                continue # Skip the status tab
                
            # Extract profile_id from unique_tab_key
            # Format: tab_profilename_profileid
            parts = key.split('_')
            if len(parts) > 2:  # At least "tab" + "profile" + "id"
                profile_id = parts[-1]  # Last part should be the ID
                if profile_id not in processed_profile_ids:
                    tabs_to_remove.append(key)
        
        # Now remove the tabs that are no longer needed
        for key in tabs_to_remove:
            # Find the display name for this tab
            display_name_to_remove = None
            for display_name in self.tab_view._name_list:
                # This is a simplistic approach; a more robust solution would maintain a mapping
                for result in self.current_data_list:
                    if result.get("profile_name") == display_name:
                        display_name_to_remove = display_name
                        break
            
            if display_name_to_remove:
                try:
                    self.tab_view.delete(display_name_to_remove)
                except Exception as e:
                    print(f"Error removing tab {display_name_to_remove}: {e}")
            
            # Remove from our tracking dict
            self.tab_views_widgets.pop(key, None)
        
        # Show placeholder if no tabs left
        if not self.tab_views_widgets or len(self.tab_views_widgets) == 0:
            self._show_no_results_placeholder()
        
        # Update truncation controls for currently active tab
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
        app.after(1000, lambda: output_display.set_data([
            {"profile_id": "p1", "profile_name": "Profile Alpha", "json_data": {"status": "Retried successfully!", "result": "Some new data"}, "chat_data": [{"sender":"System", "text":"Retry successful. Displaying new data."}]},
            {"profile_id": "p2", "profile_name": "Profile Beta (Large JSON)", "json_data": {f"item_{i}": f"Main display large string for item {i}. " * 5 for i in range(30)}, "chat_data": [{"sender":f"Msg{i}", "text":f"Message {i} in main display test for chat truncation.", "is_user": i % 2 == 0} for i in range(20)]},
            {"profile_id": "p3", "profile_name": "Profile Gamma (Large Chat)", "json_data": {"key1": "value1", "key2": list(range(10)), "nested": {"a":1, "b": "hello world "*10}}, "chat_data": [{
                "sender":f"Msg{i}", 
                "text":f"Message {i} in main display test for chat truncation.", 
                "is_user": i % 2 == 0
            } for i in range(20)]}
        ]))

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
        output_display.set_data([
            {"profile_id": "p1", "profile_name": "Profile Alpha", "json_data": sample_json_data, "chat_data": sample_chat_data},
            {"profile_id": "p2", "profile_name": "Profile Beta (Large JSON)", "json_data": large_json_for_main_test, "chat_data": sample_chat_data},
            {"profile_id": "p3", "profile_name": "Profile Gamma (Large Chat)", "json_data": sample_json_data, "chat_data": large_chat_for_main_test}
        ])

    def load_large_json_data(): # Test JSON truncation - Now loads into the multi-set_data
        # output_display.switch_view("json") # Old concept
        output_display.set_data([
            {"profile_id": "large_json_test", "profile_name": "Large JSON Test", "json_data": large_json_for_main_test, "chat_data": sample_chat_data}
        ])
        # To specifically test truncation, we might need to ensure this tab is active
        # and its view is set to JSON. For now, set_data activates the first tab by default.
        # If testing a specific tab's truncation, might need: 
        # output_display.tab_view.set("tab_large_json_test_large_json_test") # or whatever the generated name is
        # output_display._switch_tab_view("tab_large_json_test_large_json_test", "json")

    def load_large_chat_data(): # Test Chat truncation
        # output_display.switch_view("chat") # Old concept
        output_display.set_data([
            {"profile_id": "large_chat_test", "profile_name": "Large Chat Test", "json_data": sample_json_data, "chat_data": large_chat_for_main_test}
        ])

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