# pylint: disable=too-many-instance-attributes,too-many-locals,too-many-statements
"""
This module contains the MainWindow class, which is the main entry point and
container for the entire GUI application. It orchestrates all UI components
and manages the overall application state.
"""
import os
import socket
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, List
import logging
import threading

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
from src.services.google_api_client import GoogleApiClient
from src.tools import view_text_website


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
    def enter(self, event=None): self.schedule()
    def leave(self, event=None): self.unschedule(); self.hidetip()
    def schedule(self): self.unschedule(); self.id = self.widget.after(500, self.showtip)
    def unschedule(self): id = self.id; self.id = None; self.widget.after_cancel(id) if id else None
    def showtip(self, event=None):
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tw, text=self.text, justify='left', background="#ffffe0", relief='solid', borderwidth=1, font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)
    def hidetip(self): tw = self.tw; self.tw = None; tw.destroy() if tw else None
    def update_text(self, new_text): self.text = new_text


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
        self.model_selector: ttk.Combobox
        self.cost_label: ttk.Label
        self.start_button: ttk.Button
        self.progress_monitor: ProgressMonitor
        self.logo_progress_frame: ttk.Frame
        self.logo_progress_bar: ttk.Progressbar
        self.logo_status_label: ttk.Label
        self.validation_progress_bar: ttk.Progressbar
        self.start_button_tooltip: Optional[Tooltip] = None
        self.available_models: List[str] = []
        self.api_keys_validated = False
        self.mock_mode = tk.BooleanVar(value=False)
        self.logger = logging.getLogger(__name__)
        self.create_menu()
        self.create_widgets()
        self.check_api_keys()

    def create_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="API Keys", command=self.open_api_key_dialog)

    def create_widgets(self):
        root_frame = ttk.Frame(self, padding="10")
        root_frame.pack(fill="both", expand=True)

        # Bottom frame for progress bar and controls
        progress_frame = ttk.LabelFrame(root_frame, text="Job Progress", padding="10")
        progress_frame.pack(side="bottom", fill="x", pady=10)

        # API Validation progress bar (initially hidden)
        self.validation_progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')

        self.progress_monitor = ProgressMonitor(progress_frame, self.pause_job, self.resume_job, self.stop_job, self._run_diagnostics)
        self.progress_monitor.pack(fill='x', expand=True)

        # Logo scraping progress section (initially hidden)
        self.logo_progress_frame = ttk.Frame(progress_frame)
        ttk.Label(self.logo_progress_frame, text="Logo Scraping:", font=("Arial", 10, "bold")).pack(side="left", padx=(5,0))
        self.logo_status_label = ttk.Label(self.logo_progress_frame, text="Idle", width=40, anchor='w')
        self.logo_status_label.pack(side="left", fill='x', padx=5)
        self.logo_progress_bar = ttk.Progressbar(self.logo_progress_frame, orient='horizontal', mode='determinate', length=100)
        self.logo_progress_bar.pack(side="left", fill='x', expand=True, padx=5)

        credit_label = ttk.Label(progress_frame, text="made by jeeban", font=("Arial", 8, "italic"), foreground="gray")
        credit_label.pack(side="right", padx=5, pady=5)

        # Top frame for configuration options, with a scrollbar
        scroll_container = ttk.Frame(root_frame)
        scroll_container.pack(fill="both", expand=True)
        canvas = tk.Canvas(scroll_container)
        scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        self.config_frame = ttk.Frame(canvas)
        self.config_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=self.config_frame, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- Inlined _create_config_widgets ---
        parent = self.config_frame
        file_selector_frame = ttk.LabelFrame(parent, text="Step 1: Select Input & Output Files", padding="10")
        file_selector_frame.pack(fill="x", pady=5)
        self.file_selector = FileSelector(file_selector_frame, on_file_select=self.handle_file_selection, on_output_select=self.handle_output_file_selection)
        self.file_selector.pack(fill="x", expand=True)
        column_mapper_frame = ttk.LabelFrame(parent, text="Step 2: Map Columns", padding="10")
        column_mapper_frame.pack(fill="both", expand=True, pady=5)
        self.column_mapper = ColumnMapper(column_mapper_frame, on_mapping_update=self.handle_mapping_update)
        self.column_mapper.pack(fill="both", expand=True)
        row_range_frame = ttk.LabelFrame(parent, text="Step 3: Select Rows", padding="10")
        row_range_frame.pack(fill="x", pady=5)
        self.row_range_selector = RowRangeSelector(row_range_frame, on_range_update=self.handle_range_update)
        self.row_range_selector.pack(fill='x', expand=True)
        output_config_frame = ttk.LabelFrame(parent, text="Step 4: Configure Output Columns", padding="10")
        output_config_frame.pack(fill="both", expand=True, pady=5)
        self.output_column_configurator = OutputColumnConfigurator(output_config_frame, on_update=self.handle_output_column_update)
        self.output_column_configurator.pack(fill='both', expand=True)
        controls_frame = ttk.LabelFrame(parent, text="Step 5: Configure and Run", padding="10")
        controls_frame.pack(fill="x", pady=10)
        controls_frame.columnconfigure(1, weight=1)

        mock_mode_check = ttk.Checkbutton(
            controls_frame,
            text="Enable Mock/Data-Only Mode (No External API)",
            variable=self.mock_mode,
            command=self._on_mock_mode_toggle
        )
        mock_mode_check.grid(row=0, column=0, columnspan=2, sticky='w', padx=5, pady=(0, 10))

        ttk.Label(controls_frame, text="Processing Mode:").grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.mode_selector = ModeSelector(controls_frame, on_mode_change=self.handle_mode_change)
        self.mode_selector.grid(row=1, column=1, sticky='w', padx=5)
        ttk.Label(controls_frame, text="AI Model:").grid(row=2, column=0, sticky='w', padx=5, pady=2)
        self.model_selector = ttk.Combobox(controls_frame, state="disabled", values=[])
        self.model_selector.grid(row=2, column=1, sticky='ew', padx=5)
        self.model_selector.bind("<<ComboboxSelected>>", self._on_model_select)
        self.cost_label = ttk.Label(controls_frame, text="Estimated Cost: $0.00", font=("Arial", 10, "italic"))
        self.cost_label.grid(row=3, column=0, columnspan=2, pady=5)
        self.start_button = ttk.Button(controls_frame, text="Start Processing", command=self.start_processing, state="disabled")
        self.start_button.grid(row=4, column=0, columnspan=2, pady=10, ipadx=10, ipady=5)
        self.start_button_tooltip = Tooltip(self.start_button, "Please configure API keys and select a file to enable.")

    def _on_mock_mode_toggle(self):
        """Handles the logic when the mock mode checkbox is toggled."""
        if self.mock_mode.get():
            # Entering mock mode
            self.api_keys_validated = True  # Pretend keys are valid
            self.available_models = ["mock-model-v1", "mock-model-v2"]
            model_display_list = [f"{m} (~$0.0000/req)" for m in self.available_models]
            self.model_selector.config(values=model_display_list, state="readonly")
            self.model_selector.set(model_display_list[0])
            if self.job_settings:
                self.job_settings.model_name = self.available_models[0]
            self.cost_label.config(text="Est. Max Cost: $0.00 total ($0.0000/row) - MOCK MODE")
            messagebox.showinfo("Mock Mode Enabled", "Mock mode is now active. No real API calls will be made.")
        else:
            # Exiting mock mode
            self.api_keys_validated = False
            self.available_models = []
            self.model_selector.config(values=[], state="disabled")
            self.model_selector.set("")
            if self.job_settings:
                self.job_settings.model_name = ""
            self.cost_label.config(text="Estimated Cost: $0.00")
            # Re-validate real keys
            self.check_api_keys()

        self.validate_for_processing()

    def _on_model_select(self, event=None):
        if self.job_settings: self.job_settings.model_name = self.model_selector.get().split(" ")[0]
        self.validate_for_processing()
        self.update_cost_estimate()

    def handle_file_selection(self, filepath: str):
        self.reset_ui_for_new_file()
        self.job_settings = JobSettings(input_filepath=filepath, output_filepath="", column_mapping=ColumnMapping(merchant_name="<not_mapped>"), start_row=2, end_row=-1, mode="Basic")
        if self.api_keys_validated and self.available_models:
            self.job_settings.model_name = self.model_selector.get().split(" ")[0]
        file_columns = self.column_mapper.load_file(filepath)
        self.output_column_configurator.set_available_columns(file_columns)
        self.output_column_configurator.set_columns(self.job_settings.output_columns)
        self._update_row_range_selector(filepath)
        self.mode_selector.toggle_controls(True)
        if self.api_keys_validated: self.model_selector.config(state="readonly")
        self.validate_for_processing()

    def handle_output_file_selection(self, filepath: str):
        if self.job_settings:
            self.job_settings.output_filepath = filepath
        self.validate_for_processing()

    def handle_mapping_update(self, new_mapping: ColumnMapping):
        if self.job_settings: self.job_settings.column_mapping = new_mapping
        self.validate_for_processing()

    def handle_output_column_update(self, updated_columns: List[OutputColumnConfig]):
        if self.job_settings: self.job_settings.output_columns = updated_columns

    def handle_range_update(self, start_row: int, end_row: int):
        if self.job_settings: self.job_settings.start_row = start_row; self.job_settings.end_row = end_row
        self.update_cost_estimate()

    def handle_mode_change(self, mode: str):
        if self.job_settings: self.job_settings.mode = mode
        self.update_cost_estimate()

    def update_cost_estimate(self):
        """
        Updates the cost estimation label in the UI. This is triggered by changes
        to row range, processing mode, or AI model selection.
        The cost is now displayed in USD and uses the "maximum expected" model.
        """
        if (not self.job_settings or
                self.job_settings.end_row < self.job_settings.start_row or
                not self.job_settings.model_name):
            self.cost_label.config(text="Estimated Cost: $0.00", foreground="black")
            return

        num_rows = (self.job_settings.end_row - self.job_settings.start_row) + 1
        total_cost = CostEstimator.estimate_cost(num_rows, self.job_settings.mode, self.job_settings.model_name)
        cost_per_row = total_cost / num_rows if num_rows > 0 else 0

        # Update label text to use USD and show both total and per-row cost
        cost_text = (f"Est. Max Cost: ${total_cost:.2f} total "
                     f"(${cost_per_row:.4f}/row)")
        self.cost_label.config(text=cost_text)

        # Change color if budget is exceeded
        is_over_budget = not CostEstimator.check_budget(total_cost, num_rows, self.job_settings.budget_per_row)
        self.cost_label.config(foreground="red" if is_over_budget else "black")

    def validate_for_processing(self):
        is_mock_mode = self.mock_mode.get()
        # In mock mode, we don't need to check for API key validation.
        keys_ok = self.api_keys_validated or is_mock_mode

        is_ready = keys_ok and self.job_settings and self.job_settings.output_filepath and self.job_settings.column_mapping.merchant_name and self.job_settings.column_mapping.merchant_name != "<not_mapped>" and self.job_settings.model_name
        tooltip_text = ""
        if not keys_ok: tooltip_text = "API Keys are not validated. Please configure them in Settings or enable Mock Mode."
        elif not self.job_settings: tooltip_text = "Please select an input file."
        elif not self.job_settings.output_filepath: tooltip_text = "Please specify an output file path."
        elif not self.job_settings.column_mapping.merchant_name or self.job_settings.column_mapping.merchant_name == "<not_mapped>": tooltip_text = "Please map the 'Merchant Name (mandatory)' column."
        elif not self.job_settings.model_name: tooltip_text = "Please select an AI Model to use."
        else: tooltip_text = "Ready to start processing."
        self.start_button.config(state="normal" if is_ready else "disabled")
        if self.start_button_tooltip: self.start_button_tooltip.update_text(tooltip_text)

    def start_processing(self):
        if not self.job_settings: messagebox.showerror("Error", "Job settings are not configured."); return

        is_mock_mode = self.mock_mode.get()
        if not is_mock_mode and not self.api_keys_validated:
             messagebox.showerror("API Keys Invalid", "Please configure and validate your API keys via the Settings > API Keys menu, or enable Mock Mode for offline testing.");
             self.open_api_key_dialog()
             return
        if not self.job_settings.model_name:
            messagebox.showerror("Model Not Selected", "Please select an AI model from the dropdown before starting."); return

        self.job_settings.mock_mode = is_mock_mode

        confirmation_dialog = ConfirmationScreen(self, self.job_settings)
        if not confirmation_dialog.show(): return
        self.toggle_config_widgets(enabled=False)
        self.progress_monitor.job_started()
        self.job_manager = JobManager(
            self.job_settings, self.api_config,
            self.handle_status_update, self.handle_completion,
            self.handle_logo_status_update, self.handle_logo_completion,
            view_text_website
        )
        self.job_manager.start()

    def pause_job(self):
        if self.job_manager: self.job_manager.pause(); self.progress_monitor.job_paused()

    def resume_job(self):
        if self.job_manager: self.job_manager.resume(); self.progress_monitor.job_resumed()

    def stop_job(self):
        if self.job_manager and messagebox.askyesno("Confirm Stop", "Are you sure you want to stop the job? Progress will be saved."): self.job_manager.stop()

    def handle_status_update(self, current: int, total: int, status: str): self.after(0, self.progress_monitor.update_progress, current, total, status)
    def handle_completion(self, final_status: str): self.after(0, self._finalize_job_ui, final_status)

    def handle_logo_status_update(self, current: int, total: int, name: str):
        self.after(0, self._update_logo_progress_ui, current, total, name)

    def _update_logo_progress_ui(self, current: int, total: int, name: str):
        if total > 0:
            self.logo_progress_bar['value'] = current
            self.logo_progress_bar['maximum'] = total
        self.logo_status_label.config(text=f"Scraping {current}/{total}: {name[:35]}...")

    def handle_logo_completion(self, final_status: str):
        self.after(0, self._finalize_logo_scraping_ui, final_status)

    def _finalize_logo_scraping_ui(self, final_status: str):
        messagebox.showinfo("Logo Scraping Complete", final_status)
        self.logo_progress_frame.pack_forget()
        self.toggle_config_widgets(enabled=True)
        self.job_manager = None # Fully release the manager now

    def _finalize_job_ui(self, final_status: str):
        output_path = self.job_settings.output_filepath if self.job_settings else None
        self.progress_monitor.show_results(final_status, output_path)

        if "Stopped" in final_status or "Failed" in final_status:
            self.toggle_config_widgets(enabled=True)
            self.job_manager = None
            if "Stopped" in final_status:
                if output_path and os.path.exists(output_path):
                    self._show_stopped_dialog(output_path)
                else:
                    messagebox.showinfo("Job Stopped", "The job was stopped, but no output file was generated.")
            else: # Failed
                messagebox.showerror("Job Failed", f"The job ended with an error: {final_status}")
        elif "Successfully" in final_status:
            messagebox.showinfo("Processing Complete", "Main data processing is complete. Now starting logo scraping...")
            self.logo_progress_frame.pack(fill='x', expand=True, pady=5)
            self.toggle_config_widgets(enabled=False) # Keep UI frozen

    def _show_stopped_dialog(self, output_path: str):
        """Shows a custom dialog with options for the stopped job's output file."""
        dialog = tk.Toplevel(self)
        dialog.title("Job Stopped")

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill="both", expand=True)

        message = "The job was stopped. Partial results have been saved to the output file."
        ttk.Label(main_frame, text=message, wraplength=300).pack(pady=(0, 15))

        ttk.Label(main_frame, text="Output File:").pack(anchor='w')
        path_entry = ttk.Entry(main_frame, width=60)
        path_entry.insert(0, output_path)
        path_entry.config(state="readonly")
        path_entry.pack(fill='x', expand=True, pady=(0, 10))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=5, anchor="e")

        def open_file():
            try:
                if sys.platform == "win32":
                    os.startfile(output_path)
                elif sys.platform == "darwin":
                    subprocess.run(["open", output_path], check=True)
                else:
                    subprocess.run(["xdg-open", output_path], check=True)
            except (OSError, subprocess.CalledProcessError) as e:
                messagebox.showerror("Error Opening File", f"Could not open the file:\n{e}", parent=dialog)

        def copy_path():
            self.clipboard_clear()
            self.clipboard_append(output_path)
            messagebox.showinfo("Copied", "File path copied to clipboard.", parent=dialog)

        open_button = ttk.Button(button_frame, text="Open Output File", command=open_file)
        open_button.pack(side="left", padx=5)

        copy_button = ttk.Button(button_frame, text="Copy File Path", command=copy_path)
        copy_button.pack(side="left", padx=5)

        ok_button = ttk.Button(button_frame, text="OK", command=dialog.destroy)
        ok_button.pack(side="right", padx=5)

        dialog.transient(self)
        dialog.grab_set()
        self.wait_window(dialog)

    def toggle_config_widgets(self, enabled: bool):
        """
        Disables or enables all user-configurable widgets in the main interface
        to prevent changes during a processing job.
        """
        state = "normal" if enabled else "disabled"
        # Explicitly toggle each major component
        self.file_selector.toggle_controls(enabled)
        self.column_mapper.toggle_controls(enabled)
        self.row_range_selector.toggle_controls(enabled)
        self.output_column_configurator.toggle_controls(enabled)
        self.mode_selector.toggle_controls(enabled)

        # Toggle the Start button separately
        self.start_button.config(state="normal" if enabled else "disabled")

        # Handle the AI model selector state
        if self.api_keys_validated:
            self.model_selector.config(state="readonly" if enabled else "disabled")
        else:
            self.model_selector.config(state="disabled")

    def reset_ui_for_new_file(self):
        self.job_settings = None
        self.column_mapper.load_file("")
        self.output_column_configurator.set_columns([])
        self.row_range_selector.toggle_controls(False)
        self.mode_selector.toggle_controls(False)
        self.model_selector.set('')
        if not self.api_keys_validated: self.model_selector.config(state="disabled")
        self.update_cost_estimate()
        self.validate_for_processing()
        self.progress_monitor.reset_to_idle()

    def _update_row_range_selector(self, filepath: str):
        try:
            workbook = openpyxl.load_workbook(filepath, read_only=True); sheet = workbook.active
            if sheet is None: raise ValueError("The Excel file does not contain any active sheets.")
            total_data_rows = sheet.max_row - 1
            if total_data_rows > 0:
                self.row_range_selector.set_file_properties(total_rows=total_data_rows)
                if self.job_settings: self.job_settings.end_row = total_data_rows + 1
                self.update_cost_estimate()
            else: self.row_range_selector.disable(); messagebox.showwarning("Empty File", "Could not find any data rows.")
        except (IOError, ValueError) as e: self.row_range_selector.disable(); messagebox.showerror("Error Reading File", f"Could not determine file length.\nError: {e}")

    def check_api_keys(self):
        if self.mock_mode.get():
            self.logger.info("Starting in Mock Mode. Skipping initial API key validation.")
            self._on_mock_mode_toggle() # Refresh UI for mock mode
        elif self.api_config.is_valid():
            self._start_api_validation_thread()
        else:
            if not self.mock_mode.get():
                 messagebox.showinfo("API Key Setup", "Welcome! Please enter your API keys to begin, or enable Mock Mode for offline testing.")
                 self.open_api_key_dialog()

    def _start_api_validation_thread(self):
        """Starts the API validation process in a background thread."""
        self.validation_progress_bar.pack(fill='x', expand=True, pady=5)
        self.validation_progress_bar.start()
        self.progress_monitor.update_status("Validating API keys...")

        validation_thread = threading.Thread(target=self._validate_api_and_load_models, daemon=True)
        validation_thread.start()

        # Set a timeout to check if the thread is still alive
        self.after(30000, self._check_validation_timeout, validation_thread)

    def _check_validation_timeout(self, thread: threading.Thread):
        """Checks if the validation thread is still running after a timeout."""
        if thread.is_alive():
            self.validation_progress_bar.stop()
            self.validation_progress_bar.pack_forget()
            self.progress_monitor.reset_to_idle()
            messagebox.showwarning(
                "Validation Timeout",
                "API validation is taking too long. Please check your internet connection and API keys. "
                "You can also use Mock Mode for offline testing."
            )
            self.api_keys_validated = False
            self.validate_for_processing()

    def _validate_api_and_load_models_complete(self, models: Optional[List[str]]):
        """
        This method is called on the main thread with the result from the
        background validation task.
        """
        self.validation_progress_bar.stop()
        self.validation_progress_bar.pack_forget()
        self.progress_monitor.reset_to_idle()

        if models:
            self.available_models = sorted(models)
            model_display_list = [f"{m} (~${CostEstimator.get_model_cost(m):.4f}/req)" for m in self.available_models]
            self.api_keys_validated = True
            self.model_selector.config(values=model_display_list, state="readonly")
            if model_display_list: self.model_selector.set(model_display_list[0])
            if self.job_settings: self.job_settings.model_name = self.model_selector.get().split(" ")[0]
            messagebox.showinfo("Success", "API Key is valid. Please select a model.", parent=self)
        else:
            self.api_keys_validated = False
            self.model_selector.config(values=[], state="disabled"); self.model_selector.set("")
            messagebox.showerror("Validation Failed", "The Gemini API Key is invalid or no models could be fetched. Please check your key and internet connection.", parent=self)

        self.validate_for_processing()

    def _validate_api_and_load_models(self):
        """
        Worker function that runs in a background thread to validate the API key.
        The result is then passed to the main thread via `after`.
        """
        gemini_key = self.api_config.gemini_api_key
        try:
            models = GoogleApiClient.validate_and_list_models(gemini_key)
            self.after(0, self._validate_api_and_load_models_complete, models)
        except Exception as e:
            self.logger.error(f"Unhandled exception in API validation thread: {e}", exc_info=True)
            self.after(0, self._validate_api_and_load_models_complete, None)

    def open_api_key_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("API Key Configuration")
        dialog.geometry("550x300")
        dialog.resizable(False, False)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill="both", expand=True)

        def create_key_entry(parent, label_text, key_name, initial_value):
            frame = ttk.Frame(parent)
            frame.pack(fill='x', pady=2)
            ttk.Label(frame, text=label_text, width=25).pack(side='left', anchor='w')
            entry = ttk.Entry(frame, show='*', width=40)
            entry.pack(side='left', fill='x', expand=True, padx=5)
            entry.insert(0, initial_value or "")
            help_button = ttk.Button(frame, text="?", width=2, command=lambda: self._show_key_help(key_name))
            help_button.pack(side='left')
            return entry

        gemini_entry = create_key_entry(main_frame, "Google Gemini API Key:", "Gemini", self.api_config.gemini_api_key)
        search_key_entry = create_key_entry(main_frame, "Google Search API Key:", "Search", self.api_config.search_api_key)
        cse_id_entry = create_key_entry(main_frame, "Google Search CSE ID:", "Search", self.api_config.search_cse_id)
        places_entry = create_key_entry(main_frame, "Google Places API Key (Opt.):", "Places", self.api_config.places_api_key)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        def save_keys():
            gemini_key = gemini_entry.get().strip()
            search_key = search_key_entry.get().strip()
            cse_id = cse_id_entry.get().strip()
            places_key = places_entry.get().strip()

            if gemini_key and search_key and cse_id:
                self.api_config = ApiConfig(gemini_key, search_key, cse_id, places_key or None)
                save_api_config(self.api_config)
                dialog.destroy()
                self._start_api_validation_thread()
            else:
                messagebox.showwarning("Incomplete", "Gemini Key, Search Key, and CSE ID are required.", parent=dialog)

        save_button = ttk.Button(button_frame, text="Save and Validate", command=save_keys)
        save_button.pack(side="left", padx=10)

        cancel_button = ttk.Button(button_frame, text="Cancel", command=dialog.destroy)
        cancel_button.pack(side="left")

        dialog.transient(self)
        dialog.grab_set()
        self.wait_window(dialog)

    def _show_key_help(self, key_name: str):
        """Displays a help message for a specific API key."""
        help_messages = {
            "Gemini": "To get a Gemini API Key:\n\n"
                      "1. Go to Google AI Studio: https://aistudio.google.com/\n"
                      "2. Sign in with your Google account.\n"
                      "3. Click on 'Get API Key' in the top left corner.\n"
                      "4. Create a new API key in a new or existing project.\n"
                      "5. Copy the generated key and paste it here.",
            "Search": "To get a Google Search API Key and CSE ID:\n\n"
                      "1. Go to the Google Cloud Console: https://console.cloud.google.com/\n"
                      "2. Create a new project.\n"
                      "3. Enable the 'Custom Search API' for your project.\n"
                      "4. Go to 'Credentials' and create a new 'API Key'. Copy it.\n"
                      "5. Go to the Programmable Search Engine control panel: https://programmablesearchengine.google.com/controlpanel/all\n"
                      "6. Create a new search engine. For 'Sites to search', enter 'www.google.com'.\n"
                      "7. In the search engine settings, find the 'Search engine ID' and copy it.",
            "Places": "To get a Google Places API Key (Optional):\n\n"
                      "1. Go to the Google Cloud Console (the same project as your Search API).\n"
                      "2. Enable the 'Places API' for your project.\n"
                      "3. Your existing Search API Key should work for Places as well. If not, create a new one."
        }
        messagebox.showinfo(f"How to get {key_name} Key", help_messages.get(key_name, "No help available."), parent=self)


    def _run_diagnostics(self):
        """Runs a series of checks to help the user diagnose a failed job."""
        report = "Diagnostics Report:\n\n"
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            report += "✅ Internet Connectivity: Connection successful.\n\n"
        except OSError:
            report += "❌ Internet Connectivity: No internet connection detected.\n   ➡️ Fix: Please connect to the internet and try again.\n\n"
            messagebox.showinfo("Diagnostics Report", report, parent=self); return
        if not self.api_config.is_valid():
            report += "❌ API Keys: One or more required API keys are missing.\n   ➡️ Fix: Go to Settings > API Keys and ensure all required fields are filled.\n\n"
        else:
            report += "✅ API Keys: All required keys are present.\n\n"
            report += "⏳ Checking Gemini API Key validity...\n"
            self.update_idletasks()
            models = GoogleApiClient.validate_and_list_models(self.api_config.gemini_api_key)
            if models:
                report += "✅ Gemini API Key: Successfully connected and fetched available models.\n"
                selected_model = self.model_selector.get().split(" ")[0] if self.model_selector.get() else ""
                if not selected_model: report += "❌ AI Model: No AI model was selected.\n   ➡️ Fix: Please select a model from the AI Model dropdown.\n\n"
                elif selected_model not in models: report += f"❌ AI Model: The selected model '{selected_model}' is not valid for this API key.\n   ➡️ Fix: Please select a valid model from the dropdown.\n\n"
                else: report += f"✅ AI Model: '{selected_model}' is a valid selection.\n\n"
            else:
                report += "❌ Gemini API Key: Validation failed. Key is likely incorrect, expired, or lacks permissions.\n   ➡️ Fix: Go to Settings > API Keys and enter a valid Gemini API Key.\n\n"
        if self.job_settings:
            input_path = self.job_settings.input_filepath; output_path = self.job_settings.output_filepath; output_dir = os.path.dirname(output_path)
            report += f"ℹ️ Input File: {input_path}\n"
            if not os.path.exists(input_path): report += "❌ Input File: Does not exist.\n   ➡️ Fix: Please select a valid input file.\n\n"
            elif not os.access(input_path, os.R_OK): report += "❌ Input File: Cannot read the file. Check permissions.\n\n"
            else: report += "✅ Input File: Exists and is readable.\n\n"
            report += f"ℹ️ Output Directory: {output_dir}\n"
            if not os.path.isdir(output_dir): report += "❌ Output Directory: Does not exist.\n\n"
            elif not os.access(output_dir, os.W_OK): report += "❌ Output Directory: Cannot write to this directory. Check permissions.\n\n"
            else: report += "✅ Output Directory: Exists and is writable.\n\n"
        else: report += "ℹ️ File Paths: No job has been configured, skipping file path checks.\n"
        messagebox.showinfo("Diagnostics Report", report, parent=self)

if __name__ == '__main__':
    app = MainWindow()
    app.mainloop()