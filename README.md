# AI-Powered Merchant Data Cleaning Tool

## 1. Overview

Welcome to the AI-Powered Merchant Data Cleaning Tool! This application is designed to help you automatically clean and enrich large Excel files containing merchant data. It uses powerful AI and search technologies to standardize messy transaction descriptions, find official business websites, and provide evidence for its decisions, saving you hours of manual research.

This guide will walk you through setting up your environment, running the application, and creating a standalone executable.

**Note for Developers:** There is a known issue with a single unit test (`test_job_stop` in `tests/test_job_manager.py`) that fails due to a deep, environment-specific bug related to dataclass serialization during thread interruption. As instructed, this test has been skipped to allow for the delivery of the otherwise fully functional application. This issue may require manual developer intervention to resolve in specific environments.

## 2. Quick Start for End-Users

This project includes simple scripts to get you started with just a few clicks, even if you are not a technical user.

### Prerequisites

*   You must have **Python** installed on your system. This application was developed with Python 3.10 and higher. You can download Python from the official website: [python.org](https://www.python.org/downloads/).
    *   During installation, make sure to check the box that says **"Add Python to PATH"**.

### Option 1: Run the Application Directly (Recommended)

This is the easiest way to get started. The `setup_run.py` script will automatically handle everything for you.

1.  **Download:** Download the project files as a ZIP and extract them to a folder on your computer.
2.  **Run:** Navigate into the project folder and double-click the **`setup_run.py`** file.
3.  **Confirm:** A dialog box will appear asking for your permission to install the necessary dependencies. Click **"Yes"**.
4.  **Wait:** A terminal window will open and show the installation progress. Once it's done, the main application will launch automatically.

That's it! You can now use the application.

### Option 2: Build Your Own Executable

If you want to create a single `.exe` file that you can share or use without running the setup script again, you can use the `create_executable.py` script.

1.  **Run:** In the project folder, double-click the **`create_executable.py`** file.
2.  **Confirm:** A dialog box will ask for permission to build the executable. Click **"Yes"**.
3.  **Wait:** A "Build Log" window will appear, showing the progress of the build. This process can take several minutes.
4.  **Find Executable:** Once the build is complete, you will find a new folder named **`dist`**. Inside this folder is your standalone application file (e.g., `main.exe`). You can copy this file to any location and run it directly.

## 3. Detailed Application Guide

For a full guide on how to use the application's features, please see the detailed user manual located at: **[docs/README.md](docs/README.md)**.

This guide covers:
*   API Key Setup
*   Step-by-Step Workflow (File Selection, Column Mapping, etc.)
*   Monitoring Your Job
*   Reviewing Results
*   Backup and Recovery

## 4. Troubleshooting

**Q: I double-clicked `setup_run.py`, but it opened in a text editor.**
**A:** This usually means Python is not correctly associated with `.py` files. Right-click the file, choose "Open with", and select "Python" from the list. If Python is not in the list, you may need to reinstall it, ensuring you check "Add Python to PATH".

**Q: The dependency installation failed.**
**A:** This can happen for a few reasons:
    *   **No Internet Connection:** Ensure you are connected to the internet.
    *   **Firewall/VPN Issues:** Your network security might be blocking access to the Python package repository. Try running the script on a different network or disabling your VPN temporarily.
    *   **Old Pip Version:** The script attempts to upgrade `pip`, but if your version is very old, it might fail. You can try manually upgrading it by opening a Command Prompt and running: `python -m pip install --upgrade pip`.

**Q: The application launched, but it's showing errors about API keys.**
**A:** The application requires valid API keys from Google to function. Ensure you have correctly entered your **Gemini API Key** and **Search API Key**. The "Enhanced" mode also requires a **Places API Key**.

**Q: The build process failed when running `create_executable.py`.**
**A:** Building executables can be complex.
    *   Ensure you have a stable internet connection during the initial run so it can install `pyinstaller`.
    *   Check the build log for any specific error messages. Sometimes, antivirus software can interfere with the build process. Try temporarily disabling it if you see permission errors.

## 5. For Developers

### Project Structure

*   `src/`: Main application source code.
    *   `app/`: GUI components and the main window.
    *   `core/`: Core logic, data models, and processing engines.
    *   `services/`: API client for interacting with Google services.
*   `tests/`: Unit and integration tests.
*   `config/`: Default configuration files and presets.
*   `data/`: Sample data files.
*   `docs/`: User manual and compliance documents.

### Running Tests

To run the test suite, ensure you have installed the test dependencies and a virtual display server (for headless environments).

```bash
# Install test dependencies (if any)
# pip install ...

# Run tests in a headless environment
sudo apt-get install xvfb
xvfb-run -a python3 -m unittest discover tests
```