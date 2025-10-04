# pylint: disable=too-many-instance-attributes,too-many-locals
"""
This module contains the OutputColumnConfigurator, a reusable Tkinter component
for configuring the output columns of a processing job.
"""
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from typing import List, Callable, Dict
from functools import partial

from src.core.data_model import OutputColumnConfig, MerchantRecord


class OutputColumnConfigurator(tk.Frame):
    """A GUI component for configuring output columns using a list-based editor."""

    # These are the available data fields from the backend that can be mapped to output columns.
    AVAILABLE_SOURCE_FIELDS: Dict[str, str] = {
        "cleaned_merchant_name": "Cleaned Merchant Name",
        "website": "Website",
        "socials": "Social(s)",
        "evidence": "Evidence",
        "evidence_links": "Evidence Links",
        "cost_per_row": "Cost per Row",
        "logo_filename": "Logo Filename",
        "remarks": "Remarks",
    }

    def __init__(self, parent, on_update: Callable[[List[OutputColumnConfig]], None], *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.on_update = on_update
        self.columns: List[OutputColumnConfig] = []

        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        add_button_frame = ttk.Frame(self)
        add_button_frame.pack(fill="x", pady=5, side="bottom")
        add_button = ttk.Button(add_button_frame, text="Add Custom Column", command=self._add_column)
        add_button.pack()

    def set_columns(self, columns: List[OutputColumnConfig]):
        """Loads the list of columns into the configurator UI."""
        self.columns = columns
        self._populate_rows()

    def _populate_rows(self):
        """Clears and repopulates the frame with configuration rows."""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Create header
        header_frame = ttk.Frame(self.scrollable_frame)
        header_frame.pack(fill="x", expand=True, pady=(0, 5))
        ttk.Label(header_frame, text="Source Field", font=("Arial", 9, "bold")).pack(side="left", padx=5, expand=True, fill='x')
        ttk.Label(header_frame, text="Output Header", font=("Arial", 9, "bold")).pack(side="left", padx=5, expand=True, fill='x')
        ttk.Label(header_frame, text="Actions", font=("Arial", 9, "bold"), width=15).pack(side="left", padx=5)
        ttk.Separator(self.scrollable_frame, orient='horizontal').pack(fill='x', expand=True, pady=2)

        used_sources = {col.source_field for col in self.columns if not col.is_custom}

        for i, col_config in enumerate(self.columns):
            row_frame = ttk.Frame(self.scrollable_frame)
            row_frame.pack(fill="x", expand=True, pady=2)

            # Dropdown for source field
            source_var = tk.StringVar(value=self.AVAILABLE_SOURCE_FIELDS.get(col_config.source_field, col_config.source_field))
            available_sources = sorted([v for k, v in self.AVAILABLE_SOURCE_FIELDS.items() if k not in used_sources or k == col_config.source_field])

            source_dropdown = ttk.Combobox(row_frame, textvariable=source_var, values=available_sources, state="readonly" if not col_config.is_custom else "disabled")
            source_dropdown.pack(side="left", padx=5, expand=True, fill='x')
            if not col_config.is_custom:
                source_dropdown.bind("<<ComboboxSelected>>", partial(self._update_source, i, source_var))
            else:
                source_var.set("Custom/Blank")

            # Entry for renaming
            header_var = tk.StringVar(value=col_config.output_header)
            header_entry = ttk.Entry(row_frame, textvariable=header_var)
            header_entry.pack(side="left", padx=5, expand=True, fill='x')
            header_entry.bind("<FocusOut>", partial(self._update_header, i, header_var))

            # Buttons for actions
            button_subframe = ttk.Frame(row_frame, width=15)
            button_subframe.pack(side="left", padx=5)
            up_button = ttk.Button(button_subframe, text="▲", width=3, command=partial(self._move_up, i))
            up_button.pack(side="left"); up_button.config(state="disabled" if i == 0 else "normal")
            down_button = ttk.Button(button_subframe, text="▼", width=3, command=partial(self._move_down, i))
            down_button.pack(side="left"); down_button.config(state="disabled" if i == len(self.columns) - 1 else "normal")
            remove_button = ttk.Button(button_subframe, text="✖", width=3, command=partial(self._remove_column, i))
            remove_button.pack(side="left")

        if self.columns:
            self.on_update(self.columns)

    def _update_source(self, index: int, var: tk.StringVar, event=None):
        if index < len(self.columns):
            selected_display_name = var.get()
            # Find the internal key for the selected display name
            new_source_key = next((k for k, v in self.AVAILABLE_SOURCE_FIELDS.items() if v == selected_display_name), None)
            if new_source_key:
                self.columns[index].source_field = new_source_key
                self._populate_rows() # Repopulate to update dropdowns

    def _update_header(self, index: int, var: tk.StringVar, event=None):
        if index < len(self.columns):
            new_header = var.get().strip()
            if new_header: self.columns[index].output_header = new_header; self.on_update(self.columns)
            else: var.set(self.columns[index].output_header)

    def _add_column(self):
        new_name = simpledialog.askstring("Add Custom Column", "Enter header for new column:", parent=self)
        if new_name and new_name.strip():
            new_name = new_name.strip()
            source_field = f"custom_{new_name.lower().replace(' ', '_')}_{len(self.columns)}"
            new_col = OutputColumnConfig(source_field=source_field, output_header=new_name, enabled=True, is_custom=True)
            self.columns.append(new_col)
            self._populate_rows()

    def _remove_column(self, index: int):
        """Removes the selected column, only if it's a custom one."""
        if index < len(self.columns):
            if self.columns[index].is_custom:
                del self.columns[index]
                self._populate_rows()
            else:
                messagebox.showwarning(
                    "Cannot Remove",
                    "Standard enriched columns cannot be removed, only disabled.",
                    parent=self
                )

    def _move_up(self, index: int):
        if index > 0:
            self.columns.insert(index - 1, self.columns.pop(index))
            self._populate_rows()

    def _move_down(self, index: int):
        if index < len(self.columns) - 1:
            self.columns.insert(index + 1, self.columns.pop(index))
            self._populate_rows()