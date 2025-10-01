"""
This module contains the ModeSelector widget, a reusable Tkinter component for
selecting between "Basic" and "Enhanced" processing modes.
"""
import tkinter as tk
from tkinter import ttk
from typing import Callable

class ModeSelector(tk.Frame):
    """A GUI component for selecting the processing mode."""

    def __init__(self, parent, on_mode_change: Callable[[str], None], *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.on_mode_change = on_mode_change

        self.mode_var = tk.StringVar(value="Basic")
        self.basic_button: ttk.Radiobutton
        self.enhanced_button: ttk.Radiobutton

        self._create_widgets()
        self.disable()

    def _create_widgets(self):
        """Creates and arranges the widgets for mode selection."""
        ttk.Label(self, text="Processing Mode:",
                  font=("Arial", 10, "bold")).pack(side="left", padx=(0, 10))

        self.basic_button = ttk.Radiobutton(
            self,
            text="Basic (Gemini + Search)",
            variable=self.mode_var,
            value="Basic",
            command=self._on_change
        )
        self.basic_button.pack(side="left", padx=5)

        self.enhanced_button = ttk.Radiobutton(
            self,
            text="Enhanced (Gemini + Search + Places)",
            variable=self.mode_var,
            value="Enhanced",
            command=self._on_change
        )
        self.enhanced_button.pack(side="left", padx=5)

    def _on_change(self):
        """Calls the callback function when the mode changes."""
        selected_mode = self.mode_var.get()
        self.on_mode_change(selected_mode)

    def get_mode(self) -> str:
        """Returns the currently selected mode."""
        return self.mode_var.get()

    def enable(self):
        """Enables the radio buttons."""
        self.basic_button.config(state="normal")
        self.enhanced_button.config(state="normal")

    def disable(self):
        """Disables the radio buttons."""
        self.basic_button.config(state="disabled")
        self.enhanced_button.config(state="disabled")

if __name__ == '__main__':
    def handle_mode_change(mode):
        """Dummy callback for example usage."""
        print(f"Mode changed to: {mode}")

    app_root = tk.Tk()
    app_root.title("Mode Selector Example")
    app_root.geometry("450x100")

    selector_frame = ModeSelector(app_root, on_mode_change=handle_mode_change, padx=10, pady=10)
    selector_frame.pack(fill="x", expand=True)
    selector_frame.enable()

    app_root.mainloop()