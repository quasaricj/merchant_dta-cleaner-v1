"""
This module contains the ColumnMapper widget, a reusable Tkinter component for
mapping columns from an input Excel file to the application's required fields.
"""
import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, List, Dict, Optional

import pandas as pd

from src.core.data_model import ColumnMapping
from src.core.config_manager import (save_column_mapping, load_column_mapping,
                                     MAPPING_PRESETS_DIR)


class ColumnMapper(tk.Frame):
    """
    A GUI component for mapping Excel columns to required data fields.
    This component is now flexible and can be initialized with different sets
    of required fields for different application modes.
    """

    BLANK_OPTION = "<Do Not Map>"
    # Default fields for the main data enrichment feature
    DEFAULT_REQUIRED_FIELDS = {
        "merchant_name": "Merchant Name (mandatory)",
        "address": "Address (optional)",
        "city": "City (optional)",
        "country": "Country (optional)",
        "state": "State/Region (optional)",
    }

    def __init__(self, parent, on_mapping_update: Callable, required_columns: Optional[Dict[str, str]] = None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.on_mapping_update = on_mapping_update
        # Use custom required_columns if provided, otherwise use the default.
        self.required_fields = required_columns if required_columns is not None else self.DEFAULT_REQUIRED_FIELDS
        self.is_default_mode = (self.required_fields == self.DEFAULT_REQUIRED_FIELDS)

        self.file_columns: List[str] = []
        self.column_vars: Dict[str, tk.StringVar] = {}
        self.comboboxes: Dict[str, ttk.Combobox] = {}
        self.save_button: ttk.Button
        self.load_button: ttk.Button

        self._create_widgets()
        self.toggle_controls(False)

    def load_file(self, filepath: str) -> List[str]:
        """
        Loads column headers and a data preview from the selected file.
        Disables the component if the file is invalid or cannot be read.
        Returns the list of columns found.
        """
        if not filepath or not os.path.exists(filepath):
            self.toggle_controls(False)
            self._update_data_preview(pd.DataFrame())
            self.file_columns = []
            self._update_dropdown_options()
            return []

        try:
            df_preview = pd.read_excel(filepath, nrows=10, engine='openpyxl')
            self.file_columns = sorted(list(df_preview.columns))
            self._update_data_preview(df_preview)
            self._clear_all_mappings()
            self._update_dropdown_options()
            self.toggle_controls(True)
            return self.file_columns
        except (pd.errors.EmptyDataError, FileNotFoundError, ValueError, KeyError) as e:
            messagebox.showerror("Error Reading File", f"Could not read the Excel file.\nError: {e}")
            self.file_columns = []
            self._update_data_preview(pd.DataFrame())
            self._update_dropdown_options()
            self.toggle_controls(False)
        return []

    def toggle_controls(self, enabled: bool):
        """Disables or enables all interactive widgets in the mapper."""
        state = "readonly" if enabled else "disabled"
        for cb in self.comboboxes.values():
            cb.config(state=state)

        button_state = "normal" if enabled else "disabled"
        if hasattr(self, 'save_button'):
            self.save_button.config(state=button_state)
        if hasattr(self, 'load_button'):
            self.load_button.config(state=button_state)

    def get_mapping(self) -> Optional[ColumnMapping]:
        """Returns the current mapping as a ColumnMapping object. Returns None if invalid."""
        if not self.is_mapping_valid():
            return None
        mapping_data = self.get_mapping_as_dict()
        try:
            return ColumnMapping(**mapping_data)
        except TypeError:
            # This can happen if the required_fields do not match the ColumnMapping dataclass
            return None

    def get_mapping_as_dict(self) -> Dict[str, Optional[str]]:
        """Returns the current mapping as a simple dictionary."""
        return {key: (var.get() if var.get() != self.BLANK_OPTION else None) for key, var in self.column_vars.items()}

    def is_mapping_valid(self) -> bool:
        """Checks if all mandatory fields are mapped correctly."""
        selections = self.get_mapping_as_dict()
        for key, value in selections.items():
            # Check if a mandatory field is unmapped
            is_mandatory = "(mandatory)" in self.required_fields[key]
            if is_mandatory and not value:
                return False
        # Check for duplicate mappings
        valid_selections = [v for v in selections.values() if v]
        if len(valid_selections) != len(set(valid_selections)):
            return False # Duplicates exist
        return True

    def _create_widgets(self):
        """Creates and arranges the widgets for column mapping."""
        preview_frame = ttk.LabelFrame(self, text="Data Preview (First 10 Rows)", padding=10)
        preview_frame.pack(fill="both", expand=True, pady=5)
        self.tree = ttk.Treeview(preview_frame, show="headings")
        tree_scroll_y = ttk.Scrollbar(preview_frame, orient="vertical", command=self.tree.yview)
        tree_scroll_x = ttk.Scrollbar(preview_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        tree_scroll_y.pack(side="right", fill="y")
        tree_scroll_x.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

        controls_frame = ttk.LabelFrame(self, text="Map Your Columns", padding=10)
        controls_frame.pack(fill="x", pady=5)
        for i, (field_key, field_label) in enumerate(self.required_fields.items()):
            ttk.Label(controls_frame, text=field_label).grid(row=i, column=0, sticky="w", padx=5, pady=2)
            var = tk.StringVar()
            var.trace_add("write", self._on_selection_change)
            self.column_vars[field_key] = var
            combobox = ttk.Combobox(controls_frame, textvariable=var, state="disabled")
            combobox.grid(row=i, column=1, sticky="ew", padx=5, pady=2)
            self.comboboxes[field_key] = combobox
        controls_frame.grid_columnconfigure(1, weight=1)

        # Only show Save/Load functionality for the default (data enrichment) mode
        if self.is_default_mode:
            preset_frame = ttk.Frame(controls_frame)
            preset_frame.grid(row=len(self.required_fields), column=0, columnspan=2, pady=10, sticky="ew")
            self.save_button = ttk.Button(preset_frame, text="Save Mapping...", command=self._save_mapping, state="disabled")
            self.save_button.pack(side="left", padx=5)
            self.load_button = ttk.Button(preset_frame, text="Load Mapping...", command=self._load_mapping, state="disabled")
            self.load_button.pack(side="left", padx=5)
            preset_frame.grid_columnconfigure(0, weight=1)

    def _update_data_preview(self, df: pd.DataFrame):
        """Populates the Treeview with a preview of the dataframe."""
        for i in self.tree.get_children():
            self.tree.delete(i)
        df_display = df.fillna('')
        self.tree["columns"] = list(df_display.columns)
        for col in df_display.columns:
            self.tree.heading(col, text=col, anchor='w')
            self.tree.column(col, width=120, anchor="w", stretch=tk.NO)
        for _, row in df_display.iterrows():
            self.tree.insert("", "end", values=list(row.astype(str)))

    def _update_dropdown_options(self):
        """Dynamically updates the list of available columns in each dropdown."""
        used_columns = {var.get() for var in self.column_vars.values() if var.get() != self.BLANK_OPTION}
        for field_key, combobox in self.comboboxes.items():
            current_value = self.column_vars[field_key].get()
            # An option is available if it's not used by another dropdown, or if it's the current dropdown's value
            available_options = sorted([col for col in self.file_columns if col not in used_columns or col == current_value])
            is_optional = "(mandatory)" not in self.required_fields[field_key]
            combobox["values"] = ([self.BLANK_OPTION] + available_options) if is_optional else available_options

    def _clear_all_mappings(self):
        """Resets all combobox selections to their default state."""
        for key, var in self.column_vars.items():
            is_optional = "(mandatory)" not in self.required_fields[key]
            var.set(self.BLANK_OPTION if is_optional else "")

    def _on_selection_change(self, *_):
        """Validates selections, updates dropdowns, and notifies the parent."""
        self._update_dropdown_options()
        # Visual feedback for duplicates
        selections = [var.get() for var in self.column_vars.values() if var.get() and var.get() != self.BLANK_OPTION]
        style_name = "Duplicate.TCombobox"
        if "Duplicate.TCombobox" not in ttk.Style().element_names():
            style = ttk.Style()
            # Copy the existing theme's Combobox style and just change the fieldbackground
            # This is more robust across different themes (e.g., 'vista', 'clam')
            style.map(style_name, fieldbackground=[("readonly", "pink")])

        for key, cb in self.comboboxes.items():
            value = self.column_vars[key].get()
            is_duplicate = value and value != self.BLANK_OPTION and selections.count(value) > 1
            cb.config(style=style_name if is_duplicate else "TCombobox")

        # Notify the parent component of the change
        # The callback can decide how to interpret the mapping
        self.on_mapping_update(self.get_mapping())

    def _save_mapping(self):
        """Saves the current mapping to a preset file."""
        if not self.is_default_mode: return
        preset_name = filedialog.asksaveasfilename(initialdir=MAPPING_PRESETS_DIR, title="Save Mapping Preset", filetypes=[("JSON files", "*.json")], defaultextension=".json")
        if not preset_name: return

        mapping = self.get_mapping()
        if not mapping or not mapping.merchant_name:
            messagebox.showerror("Cannot Save", "Merchant Name must be mapped before saving.")
            return
        try:
            filename = os.path.basename(preset_name)
            name_without_ext = os.path.splitext(filename)[0]
            save_column_mapping(mapping, name_without_ext)
            messagebox.showinfo("Success", f"Mapping '{name_without_ext}' saved successfully.")
        except IOError as e:
            messagebox.showerror("Error Saving", f"Could not save the mapping file.\nError: {e}")

    def _load_mapping(self):
        """Loads a mapping from a preset file."""
        if not self.is_default_mode: return
        preset_name = filedialog.askopenfilename(initialdir=MAPPING_PRESETS_DIR, title="Load Mapping Preset", filetypes=[("JSON files", "*.json")])
        if not preset_name: return
        try:
            filename = os.path.basename(preset_name)
            name_without_ext = os.path.splitext(filename)[0]
            mapping = load_column_mapping(name_without_ext)
            if mapping:
                self._clear_all_mappings()
                for key, var in self.column_vars.items():
                    value = getattr(mapping, key, None)
                    if value and value in self.file_columns:
                        var.set(value)
                messagebox.showinfo("Success", f"Mapping '{name_without_ext}' loaded.")
            else:
                messagebox.showerror("Error Loading", "Could not find or parse the mapping file.")
        except (IOError, json.JSONDecodeError) as e:
            messagebox.showerror("Error Loading", f"Could not load the mapping.\nError: {e}")