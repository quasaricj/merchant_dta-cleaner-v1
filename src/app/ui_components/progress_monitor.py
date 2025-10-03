# pylint: disable=too-many-instance-attributes
"""
This module contains the ProgressMonitor widget, a reusable Tkinter component
for displaying job progress, providing controls, and showing final results.
"""
import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

class ProgressMonitor(tk.Frame):
    """A GUI component to display job progress, provide controls, and show results."""

    def __init__(self, parent, pause_callback: Callable, resume_callback: Callable,
                 stop_callback: Callable, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.pause_callback = pause_callback
        self.resume_callback = resume_callback
        self.stop_callback = stop_callback
        self.output_filepath: Optional[str] = None

        # --- Widgets ---
        self.status_label: ttk.Label
        self.progress_bar: ttk.Progressbar
        self.pause_button: ttk.Button
        self.resume_button: ttk.Button
        self.stop_button: ttk.Button
        self.results_frame: ttk.Frame
        self.filepath_entry: ttk.Entry
        self.copy_button: ttk.Button
        self.open_button: ttk.Button

        self._create_widgets()
        self.reset_to_idle()

    def _create_widgets(self):
        """Creates and arranges the widgets."""
        self.grid_columnconfigure(0, weight=1)

        # --- Status & Progress ---
        self.status_label = ttk.Label(self, text="Status: Idle")
        self.status_label.grid(row=0, column=0, columnspan=3, sticky="w", padx=5, pady=2)
        self.progress_bar = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=5)

        # --- Control Buttons ---
        self.button_frame = ttk.Frame(self)
        self.button_frame.grid(row=2, column=0, columnspan=3, pady=5)
        self.pause_button = ttk.Button(self.button_frame, text="Pause", command=self.pause_callback)
        self.pause_button.pack(side="left", padx=5)
        self.resume_button = ttk.Button(self.button_frame, text="Resume", command=self.resume_callback)
        self.resume_button.pack(side="left", padx=5)
        self.stop_button = ttk.Button(self.button_frame, text="Stop", command=self.stop_callback)
        self.stop_button.pack(side="left", padx=5)

        # --- Results Frame (initially hidden) ---
        self.results_frame = ttk.Frame(self)
        self.results_frame.grid(row=3, column=0, columnspan=3, pady=10, sticky="ew")
        self.results_frame.grid_remove() # Hide it initially

        ttk.Label(self.results_frame, text="Output File:").pack(side="left", padx=5)
        self.filepath_entry = ttk.Entry(self.results_frame, state="readonly")
        self.filepath_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.copy_button = ttk.Button(self.results_frame, text="Copy Path", command=self._copy_path)
        self.copy_button.pack(side="left", padx=5)
        self.open_button = ttk.Button(self.results_frame, text="Open File", command=self._open_file)
        self.open_button.pack(side="left", padx=5)

    def update_progress(self, current_value: int, max_value: int, status_text: str):
        """Updates the progress bar and status label."""
        if max_value > 0:
            self.progress_bar["maximum"] = max_value
            self.progress_bar["value"] = current_value
            self.status_label.config(text=f"Status: {status_text} ({current_value} / {max_value})")
        else:
            self.status_label.config(text=f"Status: {status_text}")
        self.update_idletasks()

    def job_started(self):
        """Configures the UI for a running job."""
        self.results_frame.grid_remove()
        self.button_frame.grid()
        self.progress_bar.grid()
        self.status_label.config(text="Status: Starting...")
        self.pause_button.config(state="normal")
        self.resume_button.config(state="disabled")
        self.stop_button.config(state="normal")

    def job_paused(self):
        """Configures the UI for a paused job."""
        current_text = self.status_label.cget("text")
        self.status_label.config(text=current_text.replace("Processing", "Paused"))
        self.pause_button.config(state="disabled")
        self.resume_button.config(state="normal")

    def job_resumed(self):
        """Configures the UI for a resumed job."""
        self.pause_button.config(state="normal")
        self.resume_button.config(state="disabled")

    def show_results(self, final_status: str, output_filepath: Optional[str]):
        """Shows the results panel with the final job status and output file path."""
        self.button_frame.grid_remove()
        self.progress_bar.grid_remove()
        self.status_label.config(text=f"Status: {final_status}")

        self.output_filepath = output_filepath
        if self.output_filepath and os.path.exists(self.output_filepath):
            self.results_frame.grid()
            self.filepath_entry.config(state="normal")
            self.filepath_entry.delete(0, tk.END)
            self.filepath_entry.insert(0, self.output_filepath)
            self.filepath_entry.config(state="readonly")
            self.open_button.config(state="normal")
        else:
            self.results_frame.grid_remove()

    def reset_to_idle(self):
        """Resets the entire component to its initial idle state."""
        self.status_label.config(text="Status: Idle")
        self.progress_bar.grid()
        self.progress_bar["value"] = 0
        self.button_frame.grid()
        self.pause_button.config(state="disabled")
        self.resume_button.config(state="disabled")
        self.stop_button.config(state="disabled")
        self.results_frame.grid_remove()

    def _copy_path(self):
        """Copies the output file path to the clipboard."""
        if self.output_filepath:
            self.clipboard_clear()
            self.clipboard_append(self.output_filepath)

    def _open_file(self):
        """Opens the output file with the default system application."""
        if not self.output_filepath or not os.path.exists(self.output_filepath):
            messagebox.showerror("Error", "Output file not found.", parent=self)
            return
        try:
            if sys.platform == "win32":
                os.startfile(self.output_filepath)
            elif sys.platform == "darwin": # macOS
                subprocess.run(["open", self.output_filepath], check=True)
            else: # Linux and other UNIX-like
                subprocess.run(["xdg-open", self.output_filepath], check=True)
        except (OSError, subprocess.CalledProcessError) as e:
            messagebox.showerror("Error Opening File", f"Could not open the file:\n{e}", parent=self)