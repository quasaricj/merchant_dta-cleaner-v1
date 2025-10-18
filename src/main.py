"""
This is the main entry point for the J Cleans application.
It sets up logging, initializes the main window, and starts the Tkinter event loop.
"""
import logging
import os
from src.app.main_window import MainWindow

# --- Basic Logging Setup ---
# Create a logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure logging to write to a file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='logs/app.log',
    filemode='a' # Append to the log file
)

# Also create a console handler for printing to the terminal
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)


def main():
    """
    Initializes and runs the main application window.
    """
    try:
        logging.info("Application starting...")
        app = MainWindow()
        app.mainloop()
        logging.info("Application closed.")
    except Exception as e:
        logging.critical("A fatal error occurred: %s", e, exc_info=True)
        # Optionally, show a simple Tkinter error dialog as a last resort
        # This is helpful if the main app's error handling fails to initialize
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Fatal Error", f"A fatal error occurred and the application must close.\n\nDetails: {e}\n\nPlease check the logs/app.log file for more information.")
        root.destroy()

if __name__ == '__main__':
    main()