import subprocess
import sys
import os
import tkinter as tk
from tkinter import messagebox

def install_dependencies():
    """
    Installs all required packages from requirements.txt using pip.
    """
    try:
        print(">>> Checking and installing dependencies...")
        # Ensure pip is up-to-date
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        # Install all packages from requirements.txt
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print(">>> Dependencies are all set.")
        return True
    except subprocess.CalledProcessError as e:
        messagebox.showerror(
            "Dependency Installation Failed",
            f"An error occurred while installing required packages.\n\n"
            f"Please ensure you have a working internet connection and that Python and pip are correctly installed.\n\n"
            f"Error: {e}"
        )
        return False

def launch_application():
    """
    Launches the main application window.
    """
    try:
        print(">>> Launching the application...")
        # We import here so that dependency installation can complete first
        from src.main import main
        main()
    except Exception as e:
        messagebox.showerror(
            "Application Failed to Launch",
            f"An unexpected error occurred while trying to start the application.\n\n"
            f"Error: {e}\n\n"
            f"Please see the README for troubleshooting steps."
        )

if __name__ == "__main__":
    # Hide the root Tkinter window for the setup phase
    root = tk.Tk()
    root.withdraw()

    if messagebox.askyesno(
        "Setup and Launch",
        "Welcome!\n\nThis script will install the necessary dependencies and then launch the "
        "AI-Powered Merchant Data Cleaning Tool.\n\nDo you want to proceed?"
    ):
        if install_dependencies():
            # Destroy the hidden root window before launching the main app
            root.destroy()
            launch_application()
        else:
            root.destroy()
    else:
        root.destroy()