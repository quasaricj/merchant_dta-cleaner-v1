"""
This module contains the ColumnMapper widget, a reusable Tkinter component for
mapping columns from an input Excel file to the application's required fields.
"""
import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, List

import pandas as pd

from src.core.data_model import ColumnMapping
from src.core.config_manager import (save_column_mapping, load_column_mapping,
                                     MAPPING_PRESETS_DIR)


class ColumnMapper(tk.Frame):
    """A GUI component for mapping Excel columns to required data fields."""

    BLANK_OPTION = "<Do Not Map>"
    REQUIRED_FIELDS = {
        "merchant_name": "Merchant Name (mandatory)",
        "address": "Address (optional)",
        "city": "City (optional)",
        "country": "Country (optional)",
        "state": "State/Region (optional)",
    }

    def __init__(self, parent, on_mapping_update: Callable[[ColumnMapping], None], *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.on_mapping_update = on_mapping_update

        self.file_columns: List[str] = []
        self.column_vars: dict[str, tk.StringVar] = {}
        self.comboboxes: dict[str, ttk.Combobox] = {}
        self.save_button: ttk.Button
        self.load_button: ttk.Button

        self._create_widgets()
        self.disable()

    def load_file(self, filepath: str):
        """
        Loads column headers and a data preview from the selected file.
        Disables the component if the file is invalid or cannot be read.
        """
        if not filepath or not os.path.exists(filepath):
            self.disable()
            self._update_data_preview(pd.DataFrame())
            return

        try:
            df_preview = pd.read_excel(filepath, nrows=10)
            self.file_columns = sorted(list(df_preview.columns))
            self._update_data_preview(df_preview)
            self._clear_all_mappings()
            self._update_dropdown_options() # Set initial dropdown values
            self.enable()

        except (pd.errors.EmptyDataError, FileNotFoundError, ValueError) as e:
            messagebox.showerror("Error Reading File", f"Could not read the Excel file.\nError: {e}")
            self.file_columns = []
            self._update_data_preview(pd.DataFrame())
            self._update_dropdown_options()
            self.disable()

    def enable(self):
        """Enable all interactive widgets."""
        for cb in self.comboboxes.values():
            cb.config(state="readonly")
        if hasattr(self, 'save_button'): self.save_button.config(state="normal")
        if hasattr(self, 'load_button'): self.load_button.config(state="normal")

    def disable(self):
        """Disable all interactive widgets."""
        for cb in self.comboboxes.values():
            cb.config(state="disabled")
        if hasattr(self, 'save_button'): self.save_button.config(state="disabled")
        if hasattr(self, 'load_button'): self.load_button.config(state="disabled")

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
        for i, (field_key, field_label) in enumerate(self.REQUIRED_FIELDS.items()):
            ttk.Label(controls_frame, text=field_label).grid(row=i, column=0, sticky="w", padx=5, pady=2)
            var = tk.StringVar()
            var.trace_add("write", self._on_selection_change)
            self.column_vars[field_key] = var
            combobox = ttk.Combobox(controls_frame, textvariable=var, state="readonly")
            combobox.grid(row=i, column=1, sticky="ew", padx=5, pady=2)
            self.comboboxes[field_key] = combobox
        controls_frame.grid_columnconfigure(1, weight=1)

        preset_frame = ttk.Frame(controls_frame)
        preset_frame.grid(row=len(self.REQUIRED_FIELDS), column=0, columnspan=2, pady=10, sticky="ew")
        self.save_button = ttk.Button(preset_frame, text="Save Mapping...", command=self._save_mapping)
        self.save_button.pack(side="left", padx=5)
        self.load_button = ttk.Button(preset_frame, text="Load Mapping...", command=self._load_mapping)
        self.load_button.pack(side="left", padx=5)
        preset_frame.grid_columnconfigure(0, weight=1)

    def _update_data_preview(self, df: pd.DataFrame):
        """Populates the Treeview with a preview of the dataframe."""
        self.tree.delete(*self.tree.get_children())
        df_display = df.fillna('')
        self.tree["columns"] = list(df_display.columns)
        for col in df_display.columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor="w")
        for _, row in df_display.iterrows():
            self.tree.insert("", "end", values=list(row.astype(str)))

    def _update_dropdown_options(self):
        """Dynamically updates the list of available columns in each dropdown to prevent duplicates."""
        used_columns = {var.get() for var in self.column_vars.values() if var.get() and var.get() != self.BLANK_OPTION}
        for field_key, combobox in self.comboboxes.items():
            current_value = self.column_vars[field_key].get()
            available_options = sorted([col for col in self.file_columns if col not in used_columns or col == current_value])
            is_optional = field_key != "merchant_name"
            combobox["values"] = ([self.BLANK_OPTION] + available_options) if is_optional else available_options

    def _clear_all_mappings(self):
        """Resets all combobox selections."""
        for key, var in self.column_vars.items():
            var.set(self.BLANK_OPTION if key != "merchant_name" else "")

    def _on_selection_change(self, *_):
        """Validates selections, updates dropdowns, and notifies the parent."""
        self._update_dropdown_options()
        selections = [var.get() for var in self.column_vars.values() if var.get() and var.get() != self.BLANK_OPTION]
        style_name = "Duplicate.TCombobox"
        if style_name not in ttk.Style().element_names():
            ttk.Style().map(style_name, fieldbackground=[("readonly", "red")])
        for key, cb in self.comboboxes.items():
            value = self.column_vars[key].get()
            is_duplicate = value and value != self.BLANK_OPTION and selections.count(value) > 1
            cb.config(style=style_name if is_duplicate else "TCombobox")
        mapping_data = {key: (var.get() if var.get() != self.BLANK_OPTION else None) for key, var in self.column_vars.items()}
        current_mapping = ColumnMapping(**mapping_data)
        self.on_mapping_update(current_mapping)

    def _save_mapping(self):
        """Saves the current mapping to a preset file."""
        preset_name = filedialog.asksaveasfilename(initialdir=MAPPING_PRESETS_DIR, title="Save Mapping Preset", filetypes=[("JSON files", "*.json")], defaultextension=".json")
        if not preset_name: return
        mapping_data = {key: (var.get() if var.get() and var.get() != self.BLANK_OPTION else None) for key, var in self.column_vars.items()}
        if not mapping_data.get("merchant_name"):
            messagebox.showerror("Cannot Save", "Merchant Name must be mapped before saving.")
            return
        mapping = ColumnMapping(**mapping_data)
        try:
            filename = os.path.basename(preset_name); name_without_ext = os.path.splitext(filename)[0]
            save_column_mapping(mapping, name_without_ext)
            messagebox.showinfo("Success", f"Mapping '{name_without_ext}' saved successfully.")
        except IOError as e:
            messagebox.showerror("Error Saving", f"Could not save the mapping file.\nError: {e}")

    def _load_mapping(self):
        """Loads a mapping from a preset file."""
        preset_name = filedialog.askopenfilename(initialdir=MAPPING_PRESETS_DIR, title="Load Mapping Preset", filetypes=[("JSON files", "*.json")])
        if not preset_name: return
        try:
            filename = os.path.basename(preset_name); name_without_ext = os.path.splitext(filename)[0]
            mapping = load_column_mapping(name_without_ext)
            if mapping:
                for key, var in self.column_vars.items():
                    value = getattr(mapping, key, None)
                    if value and value in self.file_columns: var.set(value)
                    elif key != "merchant_name": var.set(self.BLANK_OPTION)
                    else: var.set("")
                messagebox.showinfo("Success", f"Mapping '{name_without_ext}' loaded.")
            else:
                messagebox.showerror("Error Loading", "Could not find or parse the mapping file.")
        except (IOError, json.JSONDecodeError) as e:
            messagebox.showerror("Error Loading", f"Could not load the mapping.\nError: {e}")