"""
This module contains the FileSelector widget, a reusable Tkinter component for
selecting an input Excel file.
"""
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Callable

class FileSelector(tk.Frame):
    """A GUI component for selecting an input file."""

    def __init__(self, parent, on_file_select: Callable[[str], None], *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.on_file_select = on_file_select

        self.filepath = tk.StringVar()

        self.create_widgets()

    def create_widgets(self):
        """Creates and arranges the widgets in the frame."""
        ttk.Label(self, text="Input Excel File:",
                  font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", padx=5, pady=5)

        self.entry = ttk.Entry(self, textvariable=self.filepath, width=60, state="readonly")
        self.entry.grid(row=1, column=0, padx=5, pady=2, sticky="ew")

        self.browse_button = ttk.Button(self, text="Browse...", command=self.browse_file)
        self.browse_button.grid(row=1, column=1, padx=5, pady=2)

        self.grid_columnconfigure(0, weight=1)

    def browse_file(self):
        """Opens a file dialog to select an Excel file."""
        filetypes = (
            ("Excel files", "*.xlsx *.xls"),
            ("All files", "*.*")
        )

        filepath = filedialog.askopenfilename(
            title="Select an Input File",
            filetypes=filetypes
        )

        if filepath:
            self.filepath.set(filepath)
            self.on_file_select(filepath)

if __name__ == '__main__':
    # Example usage
    def handle_file_selection(path):
        """Dummy callback for example usage."""
        print(f"File selected: {path}")

    root = tk.Tk()
    root.title("File Selector Example")
    root.geometry("500x100")

    file_selector_frame = FileSelector(root, on_file_select=handle_file_selection,
                                       padx=10, pady=10)
    file_selector_frame.pack(fill="x", expand=True)

    root.mainloop()