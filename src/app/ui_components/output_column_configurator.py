# pylint: disable=too-many-instance-attributes,too-many-locals
"""
This module contains the OutputColumnConfigurator, a reusable Tkinter component
for configuring the output columns of a processing job.
"""
import tkinter as tk
from tkinter import ttk, simpledialog
from typing import List, Callable

from src.core.data_model import OutputColumnConfig


class OutputColumnConfigurator(tk.Frame):
    """A GUI component for configuring output columns."""

    def __init__(self, parent, on_update: Callable[[List[OutputColumnConfig]], None], *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.on_update = on_update
        self.columns: List[OutputColumnConfig] = []

        self._create_widgets()

    def set_columns(self, columns: List[OutputColumnConfig]):
        """Loads the list of columns into the configurator UI."""
        self.columns = columns
        self._populate_tree()

    def _create_widgets(self):
        """Creates and arranges the widgets for the configurator."""
        # --- Treeview for column list ---
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("enabled", "output_header"),
            show="headings"
        )
        self.tree.heading("enabled", text="Include")
        self.tree.heading("output_header", text="Output Column Header")
        self.tree.column("enabled", width=60, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.bind("<Double-1>", self._on_double_click)

        # --- Control Buttons ---
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", pady=5)

        add_button = ttk.Button(button_frame, text="Add Custom Column", command=self._add_column)
        add_button.pack(side="left", padx=5)
        remove_button = ttk.Button(button_frame, text="Remove Column", command=self._remove_column)
        remove_button.pack(side="left", padx=5)
        move_up_button = ttk.Button(button_frame, text="Move Up", command=self._move_up)
        move_up_button.pack(side="left", padx=5)
        move_down_button = ttk.Button(button_frame, text="Move Down", command=self._move_down)
        move_down_button.pack(side="left", padx=5)

    def _populate_tree(self):
        """Clears and repopulates the treeview with current column data."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        for i, col in enumerate(self.columns):
            enabled_char = "✔" if col.enabled else "☐"
            self.tree.insert("", "end", iid=str(i), values=(enabled_char, col.output_header))

    def _on_double_click(self, event):
        """Handles double-click events on the treeview for editing."""
        item_id = self.tree.identify_row(event.y)
        column_id = self.tree.identify_column(event.x)
        if not item_id:
            return

        col_index = int(item_id)
        if column_id == "#1":  # "Enabled" column
            self.columns[col_index].enabled = not self.columns[col_index].enabled
        elif column_id == "#2":  # "Output Header" column
            new_name = simpledialog.askstring(
                "Rename Column",
                "Enter the new header name:",
                initialvalue=self.columns[col_index].output_header,
                parent=self
            )
            if new_name:
                self.columns[col_index].output_header = new_name

        self._populate_tree()
        self.on_update(self.columns)

    def _add_column(self):
        """Adds a new custom, blank column."""
        new_name = simpledialog.askstring("Add Custom Column", "Enter header for new column:", parent=self)
        if new_name:
            # Create a unique source_field for this custom column
            source_field = f"custom_{new_name.lower().replace(' ', '_')}_{len(self.columns)}"
            new_col = OutputColumnConfig(
                source_field=source_field,
                output_header=new_name,
                enabled=True,
                is_custom=True
            )
            self.columns.append(new_col)
            self._populate_tree()
            self.on_update(self.columns)

    def _remove_column(self):
        """Removes the selected column, only if it's a custom one."""
        selected_item = self.tree.focus()
        if not selected_item:
            return

        col_index = int(selected_item)
        if self.columns[col_index].is_custom:
            del self.columns[col_index]
            self._populate_tree()
            self.on_update(self.columns)
        else:
            tk.messagebox.showwarning(
                "Cannot Remove",
                "Standard enriched columns cannot be removed, only disabled.",
                parent=self
            )

    def _move_up(self):
        """Moves the selected column up in the order."""
        selected_item = self.tree.focus()
        if not selected_item:
            return

        col_index = int(selected_item)
        if col_index > 0:
            self.columns.insert(col_index - 1, self.columns.pop(col_index))
            self._populate_tree()
            # Reselect the item after moving
            self.tree.selection_set(str(col_index - 1))
            self.tree.focus(str(col_index - 1))
            self.on_update(self.columns)

    def _move_down(self):
        """Moves the selected column down in the order."""
        selected_item = self.tree.focus()
        if not selected_item:
            return

        col_index = int(selected_item)
        if col_index < len(self.columns) - 1:
            self.columns.insert(col_index + 1, self.columns.pop(col_index))
            self._populate_tree()
            # Reselect the item after moving
            self.tree.selection_set(str(col_index + 1))
            self.tree.focus(str(col_index + 1))
            self.on_update(self.columns)