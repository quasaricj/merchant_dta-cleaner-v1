"""
This module contains the RowRangeSelector widget, a reusable Tkinter component
for selecting a start and end row for processing.
"""
import tkinter as tk
from tkinter import ttk
from typing import Callable

class RowRangeSelector(tk.Frame):
    """A GUI component for selecting a range of rows to process."""

    def __init__(self, parent, on_range_update: Callable[[int, int], None], *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.on_range_update = on_range_update

        self.total_rows = 0
        self.start_row_var = tk.StringVar()
        self.end_row_var = tk.StringVar()

        self.start_entry: ttk.Entry
        self.end_entry: ttk.Entry
        self.info_label: ttk.Label

        self._create_widgets()
        self.disable()

    def _create_widgets(self):
        """Creates and arranges the widgets for row range selection."""
        self.grid_columnconfigure((1, 3), weight=1)

        # --- Labels and Entries ---
        ttk.Label(self, text="Start Row:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.start_entry = ttk.Entry(self, textvariable=self.start_row_var, width=10)
        self.start_entry.grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Label(self, text="End Row:").grid(row=0, column=2, sticky="w", padx=5)
        self.end_entry = ttk.Entry(self, textvariable=self.end_row_var, width=10)
        self.end_entry.grid(row=0, column=3, sticky="ew", padx=5)

        # --- Info Label ---
        self.info_label = ttk.Label(self, text="Selected: 0 rows")
        self.info_label.grid(row=0, column=4, sticky="w", padx=10)

        # --- Bind validation ---
        self.start_row_var.trace_add("write", self._validate_and_update)
        self.end_row_var.trace_add("write", self._validate_and_update)

    def set_file_properties(self, total_rows: int):
        """Sets the total number of rows from the file and updates defaults."""
        self.total_rows = total_rows
        # Assuming row 1 is header, so data starts at 2
        self.start_row_var.set("2")
        self.end_row_var.set(str(total_rows + 1))
        self.enable()
        self._validate_and_update()

    def _validate_and_update(self, *args):
        """Validates the input and calls the update callback."""
        del args  # Unused, but required by trace_add callback signature
        start_str = self.start_row_var.get()
        end_str = self.end_row_var.get()

        try:
            start = int(start_str) if start_str else 2
            end = int(end_str) if end_str else self.total_rows + 1
        except ValueError:
            self.info_label.config(text="Invalid number", foreground="red")
            return

        is_valid = True
        # Validation logic (FR5A)
        if start < 2:
            is_valid = False
        if end > self.total_rows + 1:
            is_valid = False
        if start > end:
            is_valid = False

        if is_valid:
            selected_count = end - start + 1
            self.info_label.config(text=f"Selected: {selected_count} rows", foreground="black")
            self.on_range_update(start, end)
        else:
            self.info_label.config(text="Invalid range", foreground="red")

    def toggle_controls(self, enabled: bool):
        """Disables or enables the entry widgets."""
        state = "normal" if enabled else "disabled"
        self.start_entry.config(state=state)
        self.end_entry.config(state=state)
        if not enabled:
            # When disabling, also clear the values for a clean state
            self.start_row_var.set("")
            self.end_row_var.set("")
            self.info_label.config(text="Selected: 0 rows", foreground="black")

    def enable(self):
        """Kept for backward compatibility if needed, redirects to new method."""
        self.toggle_controls(True)

    def disable(self):
        """Kept for backward compatibility, redirects to new method."""
        self.toggle_controls(False)

if __name__ == '__main__':
    def handle_range_update(start, end):
        """Dummy callback for example usage."""
        print(f"Range updated: Start={start}, End={end}")

    app_root = tk.Tk()
    app_root.title("Row Range Selector Example")
    app_root.geometry("600x100")

    selector_frame = RowRangeSelector(app_root, on_range_update=handle_range_update,
                                      padx=10, pady=10)
    selector_frame.pack(fill="x", expand=True)

    # Simulate loading a file with 1000 data rows (+1 header)
    selector_frame.set_file_properties(total_rows=1000)

    app_root.mainloop()