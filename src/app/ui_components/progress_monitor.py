# pylint: disable=too-many-instance-attributes
"""
This module contains the ProgressMonitor widget, a reusable Tkinter component
for displaying job progress and providing user controls like pause, resume, and stop.
"""
import tkinter as tk
from tkinter import ttk
from typing import Callable

class ProgressMonitor(tk.Frame):
    """A GUI component to display job progress and provide user controls."""

    def __init__(self, parent, pause_callback: Callable, resume_callback: Callable,
                 stop_callback: Callable, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.pause_callback = pause_callback
        self.resume_callback = resume_callback
        self.stop_callback = stop_callback

        self.status_label: ttk.Label
        self.progress_bar: ttk.Progressbar
        self.pause_button: ttk.Button
        self.resume_button: ttk.Button
        self.stop_button: ttk.Button

        self._create_widgets()

    def _create_widgets(self):
        """Creates and arranges the widgets."""
        self.grid_columnconfigure(0, weight=1)

        # --- Status Label ---
        self.status_label = ttk.Label(self, text="Status: Idle")
        self.status_label.grid(row=0, column=0, columnspan=3, sticky="w", padx=5, pady=2)

        # --- Progress Bar ---
        self.progress_bar = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=5)

        # --- Control Buttons ---
        button_frame = ttk.Frame(self)
        button_frame.grid(row=2, column=0, columnspan=3, pady=5)

        self.pause_button = ttk.Button(button_frame, text="Pause",
                                       command=self.pause_callback, state="disabled")
        self.pause_button.pack(side="left", padx=5)

        self.resume_button = ttk.Button(button_frame, text="Resume",
                                        command=self.resume_callback, state="disabled")
        self.resume_button.pack(side="left", padx=5)

        self.stop_button = ttk.Button(button_frame, text="Stop",
                                      command=self.stop_callback, state="disabled")
        self.stop_button.pack(side="left", padx=5)

    def update_progress(self, current_value: int, max_value: int, status_text: str):
        """Updates the progress bar and status label."""
        self.progress_bar["maximum"] = max_value
        self.progress_bar["value"] = current_value
        self.status_label.config(text=f"Status: {status_text} ({current_value} / {max_value})")
        self.update_idletasks()

    def job_started(self):
        """Configures the UI for a running job."""
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

    def job_finished(self, final_status: str):
        """Resets the UI to an idle state after job completion or failure."""
        self.status_label.config(text=f"Status: {final_status}")
        self.progress_bar["value"] = 0
        self.pause_button.config(state="disabled")
        self.resume_button.config(state="disabled")
        self.stop_button.config(state="disabled")

if __name__ == '__main__':
    import time

    def example_pause_job():
        """Dummy callback for example usage."""
        print("Pause button clicked")
        monitor_frame.job_paused()

    def example_resume_job():
        """Dummy callback for example usage."""
        print("Resume button clicked")
        monitor_frame.job_resumed()

    def example_stop_job():
        """Dummy callback for example usage."""
        print("Stop button clicked")
        monitor_frame.job_finished("Stopped by user")

    def simulate_job():
        """Simulates a job to demonstrate the progress monitor."""
        monitor_frame.job_started()
        max_val = 100
        for i in range(max_val + 1):
            if "Stopped" in monitor_frame.status_label.cget("text"):
                break
            if "Paused" not in monitor_frame.status_label.cget("text"):
                monitor_frame.update_progress(i, max_val, "Processing...")
                app_root.update()
                time.sleep(0.05)
            else:
                app_root.update()
                time.sleep(0.1)
        if "Stopped" not in monitor_frame.status_label.cget("text"):
            monitor_frame.job_finished("Completed")

    app_root = tk.Tk()
    app_root.title("Progress Monitor Example")
    app_root.geometry("400x150")

    monitor_frame = ProgressMonitor(app_root, example_pause_job, example_resume_job,
                                    example_stop_job, padx=10, pady=10)
    monitor_frame.pack(fill="x", expand=True)

    start_sim_button = ttk.Button(app_root, text="Start Simulation", command=simulate_job)
    start_sim_button.pack(pady=10)

    app_root.mainloop()