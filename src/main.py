"""
This is the main entry point for the application.
Running this script will launch the Tkinter GUI.
"""
from src.app.main_window import MainWindow

def main():
    """The main entry point for the application."""
    app = MainWindow()
    app.mainloop()

if __name__ == "__main__":
    main()
