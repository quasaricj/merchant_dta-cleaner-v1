# pylint: disable=too-many-instance-attributes
"""
This module contains the MainWindow class, which is the main entry point and
container for the entire GUI application. It orchestrates all UI components
and manages the overall application state.
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.simpledialog import askstring
from typing import Optional

import openpyxl

from src.app.ui_components.file_selector import FileSelector
from src.app.ui_components.column_mapper import ColumnMapper
from src.app.ui_components.output_column_configurator import OutputColumnConfigurator
from src.app.ui_components.row_range_selector import RowRangeSelector
from src.app.ui_components.mode_selector import ModeSelector
from src.app.ui_components.progress_monitor import ProgressMonitor
from src.app.ui_components.confirmation_screen import ConfirmationScreen
from src.core.data_model import JobSettings, ColumnMapping, ApiConfig, OutputColumnConfig
from src.core.cost_estimator import CostEstimator
from src.core.job_manager import JobManager
from src.core.config_manager import load_api_config, save_api_config


class Tooltip:
    """Create a tooltip for a given widget."""

    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tw, text=self.text, justify='left',
                       background="#ffffe0", relief='solid', borderwidth=1,
                       font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()

    def update_text(self, new_text):
        self.text = new_text


class MainWindow(tk.Tk):
    """The main application window."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title("AI-Powered Merchant Data Cleaning Tool v1.1")
        self.geometry("800x800")

        self.job_settings: Optional[JobSettings] = None
        self.api_config: ApiConfig = load_api_config() or ApiConfig()
        self.job_manager: Optional[JobManager] = None

        self.config_frame: ttk.Frame
        self.file_selector: FileSelector
        self.column_mapper: ColumnMapper
        self.output_column_configurator: OutputColumnConfigurator
        self.row_range_selector: RowRangeSelector
        self.mode_selector: ModeSelector
        self.cost_label: ttk.Label
        self.start_button: ttk.Button
        self.progress_monitor: ProgressMonitor
        self.start_button_tooltip: Optional[Tooltip] = None

        self.create_menu()
        self.create_widgets()
        self.check_api_keys()

    def create_menu(self):
        """Creates the main application menu."""
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="API Keys", command=self.open_api_key_dialog)

    def create_widgets(self):
        """Create and layout the main widgets."""
        root_frame = ttk.Frame(self, padding="10")
        root_frame.pack(fill="both", expand=True)

        # --- Progress & Job Management Frame (at the bottom) ---
        progress_frame = ttk.LabelFrame(root_frame, text="Job Progress", padding="10")
        progress_frame.pack(side="bottom", fill="x", pady=10)
        self.progress_monitor = ProgressMonitor(
            progress_frame,
            pause_callback=self.pause_job,
            resume_callback=self.resume_job,
            stop_callback=self.stop_job
        )
        self.progress_monitor.pack(fill='x', expand=True)

        # --- Scrollable container for the configuration widgets ---
        scroll_container = ttk.Frame(root_frame)
        scroll_container.pack(fill="both", expand=True)

        canvas = tk.Canvas(scroll_container)
        scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        self.config_frame = ttk.Frame(canvas)  # This frame holds the config widgets

        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        self.config_frame.bind("<Configure>", on_frame_configure)

        canvas_window = canvas.create_window((0, 0), window=self.config_frame, anchor="nw")

        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)

        canvas.bind("<Configure>", on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._create_config_widgets(self.config_frame)

    def _create_config_widgets(self, parent):
        """Creates all the widgets for the configuration section."""
        file_selector_frame = ttk.LabelFrame(parent, text="Step 1: Select File", padding="10")
        file_selector_frame.pack(fill="x", pady=5)
        self.file_selector = FileSelector(file_selector_frame,
                                          on_file_select=self.handle_file_selection)
        self.file_selector.pack(fill="x", expand=True)

        column_mapper_frame = ttk.LabelFrame(parent, text="Step 2: Map Columns", padding="10")
        column_mapper_frame.pack(fill="both", expand=True, pady=5)
        self.column_mapper = ColumnMapper(column_mapper_frame,
                                          on_mapping_update=self.handle_mapping_update)
        self.column_mapper.pack(fill="both", expand=True)

        row_range_frame = ttk.LabelFrame(parent, text="Step 3: Select Rows", padding="10")
        row_range_frame.pack(fill="x", pady=5)
        self.row_range_selector = RowRangeSelector(row_range_frame,
                                                   on_range_update=self.handle_range_update)
        self.row_range_selector.pack(fill='x', expand=True)

        output_config_frame = ttk.LabelFrame(parent, text="Step 4: Configure Output Columns", padding="10")
        output_config_frame.pack(fill="both", expand=True, pady=5)
        self.output_column_configurator = OutputColumnConfigurator(
            output_config_frame,
            on_update=self.handle_output_column_update
        )
        self.output_column_configurator.pack(fill='both', expand=True)

        controls_frame = ttk.LabelFrame(parent, text="Step 5: Configure and Run", padding="10")
        controls_frame.pack(fill="x", pady=10)
        self.mode_selector = ModeSelector(controls_frame, on_mode_change=self.handle_mode_change)
        self.mode_selector.pack(pady=5)
        self.cost_label = ttk.Label(controls_frame, text="Estimated Cost: ₹0.00",
                                    font=("Arial", 10, "italic"))
        self.cost_label.pack(pady=5)
        self.start_button = ttk.Button(controls_frame, text="Start Processing",
                                       command=self.start_processing, state="disabled")
        self.start_button.pack(pady=10, ipadx=10, ipady=5)
        self.start_button_tooltip = Tooltip(
            self.start_button,
            "Please select a file and map the Merchant Name column to enable processing."
        )

    def handle_file_selection(self, filepath: str):
        """Callback for when a file is selected."""
        self.reset_ui_for_new_file()
        self.job_settings = JobSettings(
            input_filepath=filepath,
            output_filepath=self._generate_output_path(filepath),
            column_mapping=ColumnMapping(merchant_name="<not_mapped>"),
            start_row=2,
            end_row=-1,
            mode="Basic"
        )
        self.column_mapper.load_file(filepath)
        self.output_column_configurator.set_columns(self.job_settings.output_columns)
        self._update_row_range_selector(filepath)
        self.mode_selector.enable()
        self.validate_for_processing()

    def handle_mapping_update(self, new_mapping: ColumnMapping):
        """Callback for when the column mapping is updated."""
        if self.job_settings:
            self.job_settings.column_mapping = new_mapping
        self.validate_for_processing()

    def handle_output_column_update(self, updated_columns: List[OutputColumnConfig]):
        """Callback for when the output column configuration is updated."""
        if self.job_settings:
            self.job_settings.output_columns = updated_columns

    def handle_range_update(self, start_row: int, end_row: int):
        """Callback for when the row range is updated."""
        if self.job_settings:
            self.job_settings.start_row = start_row
            self.job_settings.end_row = end_row
        self.update_cost_estimate()

    def handle_mode_change(self, mode: str):
        """Callback for when the processing mode is changed."""
        if self.job_settings:
            self.job_settings.mode = mode
        self.update_cost_estimate()

    def update_cost_estimate(self):
        """Updates the cost estimate label using the CostEstimator."""
        if not self.job_settings or self.job_settings.end_row < self.job_settings.start_row:
            self.cost_label.config(text="Estimated Cost: ₹0.00", foreground="black")
            return
        num_rows = (self.job_settings.end_row - self.job_settings.start_row) + 1
        total_cost = CostEstimator.estimate_cost(num_rows, self.job_settings.mode)
        self.cost_label.config(text=f"Estimated Cost: ₹{total_cost:.2f}")
        if not CostEstimator.check_budget(total_cost, num_rows,
                                          self.job_settings.budget_per_row):
            self.cost_label.config(foreground="red")
        else:
            self.cost_label.config(foreground="black")

    def validate_for_processing(self):
        """Checks if all conditions are met to enable the start button."""
        is_ready = (self.job_settings and self.job_settings.column_mapping and
                    self.job_settings.column_mapping.merchant_name and
                    self.job_settings.column_mapping.merchant_name != "<not_mapped>")

        if is_ready:
            self.start_button.config(state="normal")
            if self.start_button_tooltip:
                self.start_button_tooltip.update_text("Ready to start processing.")
        else:
            self.start_button.config(state="disabled")
            if self.start_button_tooltip:
                tooltip_text = "Please select a file and map the 'Merchant Name (mandatory)' column."
                self.start_button_tooltip.update_text(tooltip_text)

    def start_processing(self):
        """Handler for the 'Start Processing' button."""
        if not self.job_settings:
            messagebox.showerror("Error", "Job settings are not configured.")
            return
        if not self.api_config.is_valid():
            messagebox.showerror("API Keys Missing",
                                 "Please configure all required API keys via the "
                                 "Settings > API Keys menu before starting.")
            self.open_api_key_dialog()
            return

        # Show confirmation screen (FR2E)
        confirmation_dialog = ConfirmationScreen(self, self.job_settings)
        if not confirmation_dialog.show():
            return  # User cancelled

        self.toggle_config_widgets(enabled=False)
        self.progress_monitor.job_started()

        self.job_manager = JobManager(
            settings=self.job_settings,
            api_config=self.api_config,
            status_callback=self.handle_status_update,
            completion_callback=self.handle_completion
        )
        self.job_manager.start()

    def pause_job(self):
        """Sends the 'pause' signal to the job manager."""
        if self.job_manager:
            self.job_manager.pause()
            self.progress_monitor.job_paused()

    def resume_job(self):
        """Sends the 'resume' signal to the job manager."""
        if self.job_manager:
            self.job_manager.resume()
            self.progress_monitor.job_resumed()

    def stop_job(self):
        """Sends the 'stop' signal to the job manager after user confirmation."""
        if self.job_manager:
            if messagebox.askyesno("Confirm Stop",
                                     "Are you sure you want to stop the job? "
                                     "Progress will be saved."):
                self.job_manager.stop()

    def handle_status_update(self, current: int, total: int, status: str):
        """Thread-safe method to update the progress monitor from the job manager."""
        self.after(0, self.progress_monitor.update_progress, current, total, status)

    def handle_completion(self, final_status: str):
        """Thread-safe method to handle job completion."""
        self.after(0, self._finalize_job_ui, final_status)

    def _finalize_job_ui(self, final_status: str):
        """Updates the UI after a job has finished, failed, or been stopped."""
        self.progress_monitor.job_finished(final_status)
        self.toggle_config_widgets(enabled=True)
        self.job_manager = None
        if "Successfully" in final_status and self.job_settings:
            messagebox.showinfo("Job Complete",
                                  f"The job finished successfully. Output saved to:\n"
                                  f"{self.job_settings.output_filepath}")
        else:
            messagebox.showerror("Job Status", f"The job ended with status: {final_status}")

    def toggle_config_widgets(self, enabled: bool):
        """Enables or disables all configuration widgets."""
        state = "normal" if enabled else "disabled"
        # This is a bit broad, but effective for this UI structure.
        for child in self.config_frame.winfo_children():
            if isinstance(child, (ttk.LabelFrame, ttk.Frame)):
                for sub_child in child.winfo_children():
                    try:
                        sub_child.config(state=state)  # type: ignore[attr-defined]
                    except tk.TclError:
                        # Some widgets like Labels don't have a 'state'
                        pass
        self.file_selector.browse_button.config(state=state)
        self.start_button.config(state=state if enabled else "disabled")

    def reset_ui_for_new_file(self):
        """Resets the UI state when a new file is selected."""
        self.job_settings = None
        self.column_mapper.load_file("")
        self.output_column_configurator.set_columns([])
        self.row_range_selector.disable()
        self.mode_selector.disable()
        self.update_cost_estimate()
        self.validate_for_processing()
        self.progress_monitor.job_finished("Idle")

    def _generate_output_path(self, input_path: str) -> str:
        """Generates a default output filepath based on the input."""
        directory, filename = os.path.split(input_path)
        name, ext = os.path.splitext(filename)
        return os.path.join(directory, f"{name}_cleaned{ext}")

    def _update_row_range_selector(self, filepath: str):
        """Gets total rows and updates the row range selector."""
        try:
            # A more robust way to get row count without loading the whole file
            workbook = openpyxl.load_workbook(filepath, read_only=True)
            sheet = workbook.active
            if sheet is None:
                raise ValueError("The Excel file does not contain any active sheets.")
            total_data_rows = sheet.max_row - 1

            if total_data_rows > 0:
                self.row_range_selector.set_file_properties(total_rows=total_data_rows)
                if self.job_settings:
                    self.job_settings.end_row = total_data_rows + 1
                self.update_cost_estimate()
            else:
                self.row_range_selector.disable()
                messagebox.showwarning("Empty File", "Could not find any data rows.")
        except (IOError, ValueError) as e:
            self.row_range_selector.disable()
            messagebox.showerror("Error Reading File",
                                 f"Could not determine file length.\nError: {e}")

    def check_api_keys(self):
        """Checks if API keys exist and prompts the user if they don't."""
        if not self.api_config.is_valid():
            messagebox.showinfo("API Key Setup",
                                "Welcome! Please enter your API keys to begin.")
            self.open_api_key_dialog()

    def open_api_key_dialog(self):
        """A custom dialog to get all required API keys."""
        dialog = tk.Toplevel(self)
        dialog.title("API Key Configuration")
        dialog.geometry("400x250")
        dialog.resizable(False, False)

        tk.Label(dialog, text="Google Gemini API Key:").pack(pady=5)
        gemini_entry = tk.Entry(dialog, show='*', width=50)
        gemini_entry.pack()
        gemini_entry.insert(0, self.api_config.gemini_api_key or "")

        tk.Label(dialog, text="Google Search API Key:").pack(pady=5)
        search_key_entry = tk.Entry(dialog, show='*', width=50)
        search_key_entry.pack()
        search_key_entry.insert(0, self.api_config.search_api_key or "")

        tk.Label(dialog, text="Google Search CSE ID:").pack(pady=5)
        cse_id_entry = tk.Entry(dialog, show='*', width=50)
        cse_id_entry.pack()
        cse_id_entry.insert(0, self.api_config.search_cse_id or "")

        tk.Label(dialog, text="Google Places API Key (Optional):").pack(pady=5)
        places_entry = tk.Entry(dialog, show='*', width=50)
        places_entry.pack()
        places_entry.insert(0, self.api_config.places_api_key or "")

        def save_keys():
            gemini_key = gemini_entry.get().strip()
            search_key = search_key_entry.get().strip()
            cse_id = cse_id_entry.get().strip()
            places_key = places_entry.get().strip()

            if gemini_key and search_key and cse_id:
                self.api_config = ApiConfig(gemini_key, search_key, cse_id, places_key or None)
                save_api_config(self.api_config)
                messagebox.showinfo("Success", "API keys saved successfully.", parent=dialog)
                dialog.destroy()
            else:
                messagebox.showwarning("Incomplete",
                                         "Gemini Key, Search Key, and CSE ID are required.",
                                         parent=dialog)

        save_button = ttk.Button(dialog, text="Save", command=save_keys)
        save_button.pack(pady=10)

        dialog.transient(self)
        dialog.grab_set()
        self.wait_window(dialog)

if __name__ == '__main__':
    app = MainWindow()
    app.mainloop()