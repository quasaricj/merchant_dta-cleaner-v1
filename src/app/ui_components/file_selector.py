"""
This module contains the FileSelector widget, a reusable Tkinter component for
selecting an input Excel file and specifying an output file path.
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable

class FileSelector(tk.Frame):
    """A GUI component for selecting input and output files."""

    def __init__(self, parent, on_file_select: Callable[[str], None],
                 on_output_select: Callable[[str], None], *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.on_file_select = on_file_select
        self.on_output_select = on_output_select

        self.input_filepath = tk.StringVar()
        self.output_filepath = tk.StringVar()

        self.create_widgets()

    def create_widgets(self):
        """Creates and arranges the widgets in the frame."""
        self.grid_columnconfigure(0, weight=1)

        # --- Input File Selection ---
        ttk.Label(self, text="Input Excel File:", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(5,0))
        self.input_entry = ttk.Entry(self, textvariable=self.input_filepath, width=60, state="readonly")
        self.input_entry.grid(row=1, column=0, padx=5, pady=2, sticky="ew")
        self.browse_button = ttk.Button(self, text="Browse...", command=self.browse_input_file)
        self.browse_button.grid(row=1, column=1, padx=5, pady=2)

        # --- Output File Selection ---
        ttk.Label(self, text="Output Excel File:", font=("Arial", 10, "bold")).grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=(10,0))
        self.output_entry = ttk.Entry(self, textvariable=self.output_filepath, width=60, state="readonly")
        self.output_entry.grid(row=3, column=0, padx=5, pady=2, sticky="ew")
        self.output_browse_button = ttk.Button(self, text="Save As...", command=self.browse_output_file)
        self.output_browse_button.grid(row=3, column=1, padx=5, pady=2)

    def browse_input_file(self):
        """Opens a file dialog to select an input Excel file."""
        filepath = filedialog.askopenfilename(
            title="Select an Input File",
            filetypes=(("Excel files", "*.xlsx *.xls"), ("All files", "*.*"))
        )
        if filepath:
            self.input_filepath.set(filepath)
            self.on_file_select(filepath)
            # Auto-generate a default output path
            default_output = self._generate_default_output_path(filepath)
            self.output_filepath.set(default_output)
            self.on_output_select(default_output)

    def browse_output_file(self):
        """Opens a file dialog to specify the output file path."""
        if not self.input_filepath.get():
            messagebox.showwarning("Input File Required", "Please select an input file first.", parent=self)
            return

        filepath = filedialog.asksaveasfilename(
            title="Save Output File As",
            filetypes=(("Excel files", "*.xlsx"),),
            defaultextension=".xlsx",
            initialfile=os.path.basename(self.output_filepath.get())
        )
        if filepath:
            self.output_filepath.set(filepath)
            self.on_output_select(filepath)

    def _generate_default_output_path(self, input_path: str) -> str:
        """Generates a default output filepath based on the input."""
        directory, filename = os.path.split(input_path)
        name, ext = os.path.splitext(filename)
        return os.path.join(directory, f"{name}_cleaned{ext}")

    def set_output_path(self, path: str):
        """Allows the main window to set the output path externally if needed."""
        self.output_filepath.set(path)