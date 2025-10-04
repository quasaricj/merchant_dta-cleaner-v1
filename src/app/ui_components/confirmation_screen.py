"""
This module contains the ConfirmationScreen widget, a Toplevel window that
serves as a final confirmation dialog before a processing job is started.
"""
import os
import tkinter as tk
from tkinter import ttk
from src.core.data_model import JobSettings
from src.core.cost_estimator import CostEstimator

class ConfirmationScreen(tk.Toplevel):
    """A dialog window to confirm job settings before starting."""

    def __init__(self, parent, settings: JobSettings):
        super().__init__(parent)
        self.title("Confirm Job Settings")
        self.settings = settings
        self.result = False

        # Make the window modal
        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _create_widgets(self):
        """Creates and arranges the widgets in the dialog."""
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(fill="both", expand=True)

        # --- Summary Table ---
        summary_frame = ttk.LabelFrame(main_frame, text="Job Summary", padding="10")
        summary_frame.pack(fill="x", pady=5, expand=True)
        summary_frame.grid_columnconfigure(1, weight=1)

        num_rows = (self.settings.end_row - self.settings.start_row) + 1
        total_cost = CostEstimator.estimate_cost(num_rows, self.settings.mode, self.settings.model_name)

        summary_data = {
            "Input File": os.path.basename(self.settings.input_filepath),
            "Output File": os.path.basename(self.settings.output_filepath),
            "Processing Mode": self.settings.mode,
            "Row Range": f"{self.settings.start_row} to {self.settings.end_row}",
            "Total Rows to Process": f"{num_rows}",
            "Estimated Cost": f"₹{total_cost:.2f}"
        }

        for i, (key, value) in enumerate(summary_data.items()):
            ttk.Label(summary_frame, text=f"{key}:",
                      font=("Arial", 10, "bold")).grid(row=i, column=0, sticky="w", pady=2, padx=5)
            ttk.Label(summary_frame, text=value,
                      wraplength=350, anchor="w").grid(row=i, column=1, sticky="ew", pady=2, padx=5)

        # --- Column Mappings ---
        mapping_frame = ttk.LabelFrame(main_frame, text="Column Mappings", padding="10")
        mapping_frame.pack(fill="x", pady=5, expand=True)
        mapping_frame.grid_columnconfigure(1, weight=1)

        mappings = self.settings.column_mapping.__dict__
        for i, (key, value) in enumerate(mappings.items()):
            label = key.replace("_", " ").title()
            ttk.Label(mapping_frame, text=f"{label}:",
                      font=("Arial", 10, "bold")).grid(row=i, column=0, sticky="w", pady=2, padx=5)
            ttk.Label(mapping_frame, text=value if value else "Not Mapped",
                      foreground="gray" if not value else "black").grid(row=i, column=1,
                                                                        sticky="ew", pady=2, padx=5)

        # --- Buttons ---
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(15, 0))

        self.confirm_button = ttk.Button(button_frame, text="Confirm and Start",
                                         command=self._on_confirm)
        self.confirm_button.pack(side="right", padx=5)
        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self._on_cancel)
        self.cancel_button.pack(side="right")

        # Budget warning (FR13)
        if not CostEstimator.check_budget(total_cost, num_rows, self.settings.budget_per_row):
            warning_label = ttk.Label(
                main_frame,
                text=f"Warning: Estimated cost exceeds the budget of "
                     f"₹{self.settings.budget_per_row:.2f} per row.",
                foreground="red",
                wraplength=400
            )
            warning_label.pack(pady=(10, 0))

    def _on_confirm(self):
        self.result = True
        self.destroy()

    def _on_cancel(self):
        self.result = False
        self.destroy()

    def show(self) -> bool:
        """Shows the modal dialog and waits for user interaction."""
        self.wait_window()
        return self.result