# pylint: disable=too-many-instance-attributes,too-many-locals
"""
This module contains the OutputColumnConfigurator, a reusable Tkinter component
for configuring the output columns of a processing job.
"""
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from typing import List, Callable
from functools import partial

from src.core.data_model import OutputColumnConfig


class OutputColumnConfigurator(tk.Frame):
    """A GUI component for configuring output columns using a list-based editor."""

    def __init__(self, parent, on_update: Callable[[List[OutputColumnConfig]], None], *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.on_update = on_update
        self.columns: List[OutputColumnConfig] = []

        # Create a scrollable container
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Add a button at the bottom to add new columns
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
        ttk.Label(header_frame, text="Include", font=("Arial", 9, "bold"), width=7).pack(side="left", padx=(5,0))
        ttk.Label(header_frame, text="Output Column Header", font=("Arial", 9, "bold")).pack(side="left", padx=5)
        ttk.Separator(self.scrollable_frame, orient='horizontal').pack(fill='x', expand=True, pady=2)

        for i, col_config in enumerate(self.columns):
            row_frame = ttk.Frame(self.scrollable_frame)
            row_frame.pack(fill="x", expand=True, pady=2)

            # Checkbox for enabling/disabling
            enabled_var = tk.BooleanVar(value=col_config.enabled)
            enabled_check = ttk.Checkbutton(
                row_frame,
                variable=enabled_var,
                command=partial(self._update_enabled, i, enabled_var)
            )
            enabled_check.pack(side="left", padx=(15, 0), pady=0)

            # Entry for renaming
            header_var = tk.StringVar(value=col_config.output_header)
            header_entry = ttk.Entry(row_frame, textvariable=header_var, width=40)
            header_entry.pack(side="left", fill="x", expand=True, padx=5)
            header_entry.bind("<FocusOut>", partial(self._update_header, i, header_var))
            header_entry.bind("<Return>", partial(self._update_header, i, header_var))

            # Buttons for actions
            button_subframe = ttk.Frame(row_frame)
            button_subframe.pack(side="left", padx=5)

            up_button = ttk.Button(button_subframe, text="▲", width=3, command=partial(self._move_up, i))
            up_button.pack(side="left")
            if i == 0:
                up_button.config(state="disabled")

            down_button = ttk.Button(button_subframe, text="▼", width=3, command=partial(self._move_down, i))
            down_button.pack(side="left")
            if i == len(self.columns) - 1:
                down_button.config(state="disabled")

            if col_config.is_custom:
                remove_button = ttk.Button(button_subframe, text="✖", width=3, command=partial(self._remove_column, i))
                remove_button.pack(side="left")

        if self.columns:
            self.on_update(self.columns)

    def _update_enabled(self, index: int, var: tk.BooleanVar):
        if index < len(self.columns):
            self.columns[index].enabled = var.get()
            self.on_update(self.columns)

    def _update_header(self, index: int, var: tk.StringVar, event=None):
        if index < len(self.columns):
            new_header = var.get().strip()
            if new_header:
                self.columns[index].output_header = new_header
                self.on_update(self.columns)
            else:
                var.set(self.columns[index].output_header)

    def _add_column(self):
        """Adds a new custom, blank column."""
        new_name = simpledialog.askstring("Add Custom Column", "Enter header for new column:", parent=self)
        if new_name and new_name.strip():
            new_name = new_name.strip()
            source_field = f"custom_{new_name.lower().replace(' ', '_')}_{len(self.columns)}"
            new_col = OutputColumnConfig(
                source_field=source_field, output_header=new_name, enabled=True, is_custom=True
            )
            self.columns.append(new_col)
            self._populate_rows()

    def _remove_column(self, index: int):
        """Removes the selected column, only if it's a custom one."""
        if index < len(self.columns) and self.columns[index].is_custom:
            del self.columns[index]
            self._populate_rows()
        else:
            messagebox.showwarning(
                "Cannot Remove", "Standard enriched columns cannot be removed, only disabled.", parent=self
            )

    def _move_up(self, index: int):
        """Moves the selected column up in the order."""
        if index > 0:
            self.columns.insert(index - 1, self.columns.pop(index))
            self._populate_rows()

    def _move_down(self, index: int):
        """Moves the selected column down in the order."""
        if index < len(self.columns) - 1:
            self.columns.insert(index + 1, self.columns.pop(index))
            self._populate_rows()