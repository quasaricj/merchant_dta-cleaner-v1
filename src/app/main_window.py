# pylint: disable=too-many-instance-attributes,too-many-locals,too-many-statements
"""
This module contains the MainWindow class, which is the main entry point and
container for the entire GUI application. It orchestrates all UI components
and manages the overall application state.
"""
import os
import socket
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, List

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
        self.start_button_tooltip: Optional[Tooltip] = None
        self.available_models: List[str] = []
        self.api_keys_validated = False
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
        progress_frame = ttk.LabelFrame(root_frame, text="Job Progress", padding="10")
        progress_frame.pack(side="bottom", fill="x", pady=10)
        self.progress_monitor = ProgressMonitor(progress_frame, self.pause_job, self.resume_job, self.stop_job, self._run_diagnostics)
        self.progress_monitor.pack(fill='x', expand=True)
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
        self._create_config_widgets(self.config_frame)

    def _create_config_widgets(self, parent):
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
        ttk.Label(controls_frame, text="Processing Mode:").grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.mode_selector = ModeSelector(controls_frame, on_mode_change=self.handle_mode_change)
        self.mode_selector.grid(row=0, column=1, sticky='w', padx=5)
        ttk.Label(controls_frame, text="AI Model:").grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.model_selector = ttk.Combobox(controls_frame, state="disabled", values=[])
        self.model_selector.grid(row=1, column=1, sticky='ew', padx=5)
        self.model_selector.bind("<<ComboboxSelected>>", self._on_model_select)
        self.cost_label = ttk.Label(controls_frame, text="Estimated Cost: ₹0.00", font=("Arial", 10, "italic"))
        self.cost_label.grid(row=2, column=0, columnspan=2, pady=5)
        self.start_button = ttk.Button(controls_frame, text="Start Processing", command=self.start_processing, state="disabled")
        self.start_button.grid(row=3, column=0, columnspan=2, pady=10, ipadx=10, ipady=5)
        self.start_button_tooltip = Tooltip(self.start_button, "Please configure API keys and select a file to enable.")

    def _on_model_select(self, event=None):
        if self.job_settings: self.job_settings.model_name = self.model_selector.get().split(" ")[0]
        self.validate_for_processing()
        self.update_cost_estimate()

    def handle_file_selection(self, filepath: str):
        self.reset_ui_for_new_file()
        self.job_settings = JobSettings(input_filepath=filepath, output_filepath="", column_mapping=ColumnMapping(merchant_name="<not_mapped>"), start_row=2, end_row=-1, mode="Basic")
        if self.api_keys_validated and self.available_models:
            self.job_settings.model_name = self.model_selector.get().split(" ")[0]
        self.column_mapper.load_file(filepath)
        self.output_column_configurator.set_columns(self.job_settings.output_columns)
        self._update_row_range_selector(filepath)
        self.mode_selector.enable()
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
        if not self.job_settings or self.job_settings.end_row < self.job_settings.start_row or not self.job_settings.model_name:
            self.cost_label.config(text="Estimated Cost: ₹0.00", foreground="black")
            return
        num_rows = (self.job_settings.end_row - self.job_settings.start_row) + 1
        total_cost = CostEstimator.estimate_cost(num_rows, self.job_settings.mode, self.job_settings.model_name)
        self.cost_label.config(text=f"Estimated Cost: ₹{total_cost:.2f}")
        self.cost_label.config(foreground="red" if not CostEstimator.check_budget(total_cost, num_rows, self.job_settings.budget_per_row) else "black")

    def validate_for_processing(self):
        is_ready = self.api_keys_validated and self.job_settings and self.job_settings.output_filepath and self.job_settings.column_mapping.merchant_name and self.job_settings.column_mapping.merchant_name != "<not_mapped>" and self.job_settings.model_name
        tooltip_text = ""
        if not self.api_keys_validated: tooltip_text = "API Keys are not validated. Please configure them in Settings."
        elif not self.job_settings: tooltip_text = "Please select an input file."
        elif not self.job_settings.output_filepath: tooltip_text = "Please specify an output file path."
        elif not self.job_settings.column_mapping.merchant_name or self.job_settings.column_mapping.merchant_name == "<not_mapped>": tooltip_text = "Please map the 'Merchant Name (mandatory)' column."
        elif not self.job_settings.model_name: tooltip_text = "Please select an AI Model to use."
        else: tooltip_text = "Ready to start processing."
        self.start_button.config(state="normal" if is_ready else "disabled")
        if self.start_button_tooltip: self.start_button_tooltip.update_text(tooltip_text)

    def start_processing(self):
        if not self.job_settings: messagebox.showerror("Error", "Job settings are not configured."); return
        if not self.api_keys_validated: messagebox.showerror("API Keys Invalid", "Please configure and validate your API keys via the Settings > API Keys menu."); self.open_api_key_dialog(); return
        if not self.job_settings.model_name: messagebox.showerror("Model Not Selected", "Please select an AI model from the dropdown before starting."); return
        confirmation_dialog = ConfirmationScreen(self, self.job_settings)
        if not confirmation_dialog.show(): return
        self.toggle_config_widgets(enabled=False)
        self.progress_monitor.job_started()
        self.job_manager = JobManager(self.job_settings, self.api_config, self.handle_status_update, self.handle_completion)
        self.job_manager.start()

    def pause_job(self):
        if self.job_manager: self.job_manager.pause(); self.progress_monitor.job_paused()

    def resume_job(self):
        if self.job_manager: self.job_manager.resume(); self.progress_monitor.job_resumed()

    def stop_job(self):
        if self.job_manager and messagebox.askyesno("Confirm Stop", "Are you sure you want to stop the job? Progress will be saved."): self.job_manager.stop()

    def handle_status_update(self, current: int, total: int, status: str): self.after(0, self.progress_monitor.update_progress, current, total, status)
    def handle_completion(self, final_status: str): self.after(0, self._finalize_job_ui, final_status)

    def _finalize_job_ui(self, final_status: str):
        output_path = self.job_settings.output_filepath if self.job_settings else None
        self.progress_monitor.show_results(final_status, output_path)
        self.toggle_config_widgets(enabled=True)
        self.job_manager = None
        if "Successfully" in final_status: messagebox.showinfo("Job Complete", f"The job finished with status: {final_status}")
        elif "Failed" in final_status: messagebox.showerror("Job Failed", f"The job ended with an error: {final_status}")

    def toggle_config_widgets(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for child in self.config_frame.winfo_children():
            if isinstance(child, (ttk.LabelFrame, ttk.Frame)):
                for sub_child in child.winfo_children():
                    try: sub_child.config(state=state)
                    except tk.TclError: pass
        self.file_selector.browse_button.config(state=state)
        self.start_button.config(state=state if enabled else "disabled")
        if self.api_keys_validated: self.model_selector.config(state="readonly" if enabled else "disabled")
        else: self.model_selector.config(state="disabled")

    def reset_ui_for_new_file(self):
        self.job_settings = None
        self.column_mapper.load_file("")
        self.output_column_configurator.set_columns([])
        self.row_range_selector.disable()
        self.mode_selector.disable()
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
        if self.api_config.is_valid(): self._validate_api_and_load_models()
        else: messagebox.showinfo("API Key Setup", "Welcome! Please enter your API keys to begin."); self.open_api_key_dialog()

    def _validate_api_and_load_models(self):
        gemini_key = self.api_config.gemini_api_key
        messagebox.showinfo("Validating", "Validating API Key and fetching available models...", parent=self, icon=messagebox.INFO)
        self.update_idletasks()
        models = GoogleApiClient.validate_and_list_models(gemini_key)
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

    def open_api_key_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("API Key Configuration"); dialog.geometry("400x250"); dialog.resizable(False, False)
        tk.Label(dialog, text="Google Gemini API Key:").pack(pady=5)
        gemini_entry = tk.Entry(dialog, show='*', width=50); gemini_entry.pack(); gemini_entry.insert(0, self.api_config.gemini_api_key or "")
        tk.Label(dialog, text="Google Search API Key:").pack(pady=5)
        search_key_entry = tk.Entry(dialog, show='*', width=50); search_key_entry.pack(); search_key_entry.insert(0, self.api_config.search_api_key or "")
        tk.Label(dialog, text="Google Search CSE ID:").pack(pady=5)
        cse_id_entry = tk.Entry(dialog, show='*', width=50); cse_id_entry.pack(); cse_id_entry.insert(0, self.api_config.search_cse_id or "")
        tk.Label(dialog, text="Google Places API Key (Optional):").pack(pady=5)
        places_entry = tk.Entry(dialog, show='*', width=50); places_entry.pack(); places_entry.insert(0, self.api_config.places_api_key or "")
        def save_keys():
            gemini_key = gemini_entry.get().strip(); search_key = search_key_entry.get().strip(); cse_id = cse_id_entry.get().strip(); places_key = places_entry.get().strip()
            if gemini_key and search_key and cse_id:
                self.api_config = ApiConfig(gemini_key, search_key, cse_id, places_key or None); save_api_config(self.api_config)
                dialog.destroy()
                self._validate_api_and_load_models()
            else: messagebox.showwarning("Incomplete", "Gemini Key, Search Key, and CSE ID are required.", parent=dialog)
        save_button = ttk.Button(dialog, text="Save and Validate", command=save_keys); save_button.pack(pady=10)
        dialog.transient(self); dialog.grab_set(); self.wait_window(dialog)

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