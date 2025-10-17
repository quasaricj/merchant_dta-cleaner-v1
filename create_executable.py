import subprocess
import sys
import os
import tkinter as tk
from tkinter import messagebox, filedialog

def get_icon_path():
    """
    Opens a file dialog for the user to select an icon file.
    Returns the path to the icon or None if canceled.
    """
    if messagebox.askyesno("Icon Selection", "Do you want to add a custom icon to the executable?"):
        icon_path = filedialog.askopenfilename(
            title="Select Icon File",
            filetypes=[("Icon files", "*.ico"), ("All files", "*.*")]
        )
        if icon_path:
            return icon_path
        else:
            messagebox.showwarning("No Icon Selected", "No icon file was selected. The build will proceed with the default icon.")
            return None
    return None

def install_pyinstaller():
    """
    Checks if PyInstaller is installed and installs it if it's missing.
    """
    try:
        print(">>> Checking for PyInstaller...")
        # Try to import PyInstaller to check if it exists
        import PyInstaller
        print(">>> PyInstaller is already installed.")
        return True
    except ImportError:
        print(">>> PyInstaller not found. Attempting to install...")
        if messagebox.askyesno(
            "PyInstaller Not Found",
            "The 'pyinstaller' package is required to create an executable. "
            "Do you want to install it now?"
        ):
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
                print(">>> PyInstaller installed successfully.")
                return True
            except subprocess.CalledProcessError as e:
                messagebox.showerror(
                    "Installation Failed",
                    f"Could not install PyInstaller.\n\nError: {e}"
                )
                return False
        else:
            return False

def create_executable(icon_path=None):
    """
    Runs the PyInstaller command to build the standalone executable.
    """
    if not os.path.exists("src/main.py"):
        messagebox.showerror("Error", "Could not find the main entry point: src/main.py")
        return

    print("\n>>> Starting the build process. This may take several minutes...")

    # Define the command arguments for PyInstaller
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--add-data", "config/mapping_presets:config/mapping_presets",
        "--distpath", "./dist",
        "--workpath", "./build",
    ]

    # Add the icon argument if a path is provided
    if icon_path:
        command.extend(["--icon", icon_path])

    command.append("src/main.py")


    try:
        # Run the command and capture output
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')

        # Display output in a simple text box for user feedback
        show_build_log(process)

        if process.returncode == 0:
            messagebox.showinfo(
                "Build Successful",
                "The executable file has been created successfully in the 'dist' folder."
            )
        else:
            messagebox.showerror(
                "Build Failed",
                "The build process failed. Please see the log for details."
            )

    except Exception as e:
        messagebox.showerror("Build Error", f"An unexpected error occurred during the build.\n\nError: {e}")

def show_build_log(process):
    """
    Displays the live output of the build process in a Toplevel window.
    """
    log_window = tk.Toplevel()
    log_window.title("Build Log")
    log_window.geometry("600x400")

    text_widget = tk.Text(log_window, wrap="word", state="disabled")
    text_widget.pack(expand=True, fill="both")

    def update_log():
        """Reads from the process stdout and updates the text widget."""
        if process.stdout:
            line = process.stdout.readline()
            if line:
                text_widget.config(state="normal")
                text_widget.insert("end", line)
                text_widget.see("end")
                text_widget.config(state="disabled")

        if process.poll() is None:
            # If the process is still running, schedule the next update
            log_window.after(100, update_log)
        else:
            # Process finished
            log_window.title("Build Log (Completed)")

    log_window.after(100, update_log)
    # Make the main script wait until the log window is closed
    log_window.transient()
    log_window.grab_set()
    log_window.wait_window()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()

    if messagebox.askyesno(
        "Create Executable",
        "This script will package the application into a single executable file (.exe) "
        "in a 'dist' folder.\n\nThe process may take several minutes.\n\nDo you want to continue?"
    ):
        if install_pyinstaller():
            icon = get_icon_path()
            create_executable(icon_path=icon)

    root.destroy()