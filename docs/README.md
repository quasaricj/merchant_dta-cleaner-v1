# AI-Powered Merchant Data Cleaning Tool - User Manual

## 1. Overview

Welcome to the AI-Powered Merchant Data Cleaning Tool! This application is designed to help you automatically clean and enrich large Excel files containing merchant data. It uses powerful AI and search technologies to standardize messy transaction descriptions, find official business websites, and provide evidence for its decisions, saving you hours of manual research.

This guide will walk you through how to install and use every feature of the application.

## 2. Installation

This application is designed to be incredibly simple to set up. It is a standalone executable, which means you do not need to install Python or any other technical dependencies.

1.  **Download:** Download the provided `.exe` file to your Windows computer.
2.  **Place:** Move the `.exe` file to any folder you like (e.g., your Desktop or a new folder called "Merchant Tool").
3.  **Run:** Double-click the `.exe` file to launch the application. That's it!

## 3. Getting Started: API Key Setup

The first time you launch the application, you will be prompted to enter your API keys. These are necessary for the tool to connect to the AI and search services that power its features.

1.  **Gemini API Key:** Enter your Google Gemini API key. This is **required** for the AI-powered name cleaning.
2.  **Search API Key:** Enter your Google Custom Search API key. This is **required** for web searches. You will also need a **Custom Search Engine ID (CX ID)**.
3.  **Places API Key (Optional):** Enter your Google Places API key. This is **optional** but enables the "Enhanced" processing mode for higher accuracy results.

These keys will be stored securely on your local computer and can be changed later if needed.

## 4. Step-by-Step Workflow

The application guides you through a simple, 4-step process to clean your data.

### Step 1: Select Your File

-   Click the **"Browse..."** button.
-   An "Open" dialog will appear. Navigate to and select the Excel file (`.xlsx` or `.xls`) you want to process.
-   Once selected, the file path will appear in the text box, and the next step will become active.

### Step 2: Map Your Columns

This is a critical step where you tell the application which columns in your Excel file contain which pieces of information.

-   **Data Preview:** A preview of the first 10 rows of your file is shown to help you identify the columns.
-   **Mapping Dropdowns:** For each required field (like "Merchant Name"), click the dropdown menu and select the corresponding column header from your file.
    -   **Merchant Name** is mandatory. The application cannot run without it.
    -   Address, City, Country, and State are optional but highly recommended for better results.
-   **Validation:** The application will automatically highlight any duplicate mappings in red. You must resolve these conflicts before proceeding.
-   **Save/Load Mappings:**
    -   If you frequently work with files that have the same layout, you can click **"Save Mapping..."** to save your current setup as a template.
    -   Click **"Load Mapping..."** to load a previously saved template for a new file.

### Step 3: Select Which Rows to Process

You have full control over which part of the file you want to process.

-   **Start Row / End Row:** Enter the row numbers you wish to process. By default, it will select the entire file (starting from row 2, assuming row 1 is a header).
-   **Live Validation:** The tool will show you how many total rows you have selected and will prevent you from entering an invalid range (e.g., a start row that is after the end row).

### Step 4: Configure and Run

This is the final step before processing begins.

-   **Processing Mode:**
    -   **Basic:** Uses AI and standard Google Search. This is faster and lower cost.
    -   **Enhanced:** Adds the Google Places API for business verification. This provides higher accuracy but is slower and costs more.
-   **Estimated Cost:** A real-time cost estimate is displayed based on the number of rows and the processing mode you have selected. If the cost is likely to exceed the budget (₹3.00/row), a warning will be shown.
-   **Start Processing:** Once the "Merchant Name" column is mapped, the **"Start Processing"** button will become active. Click it to proceed.

### A Note on How Results are Found

The application's AI is governed by a strict set of rules based on `rules.md`. Its primary function is to analyze search results and find explicit, text-based evidence for a merchant's official name and website.

The app will only output a cleaned name or website if the AI can find direct, supporting text in a search result's title or snippet. If no such evidence is found after all search attempts, the output fields for that row will be left blank, and the `Evidence` column will explain why. This rule-based approach ensures that you can trust the data in the output file, as every result is backed by a clear, auditable trail.

### Final Confirmation

-   A final confirmation window will appear summarizing all your selected settings.
-   Review everything carefully.
-   Click **"Confirm and Start"** to begin the job, or **"Cancel"** to go back and make changes.

## 5. Monitoring Your Job

Once a job is running, the "Job Progress" section becomes active.

-   **Progress Bar:** Shows the overall progress of the job.
-   **Status Label:** Gives you real-time updates (e.g., "Processing... (52 / 1000)").
-   **Controls:**
    -   **Pause:** Temporarily pause the job.
    -   **Resume:** Continue a paused job.
    -   **Stop:** Abort the job completely. If you stop a job, your progress up to that point is saved in a `.checkpoint` file, and the job can be resumed later by simply starting it again with the same input file.

## 6. Reviewing the Results

-   When the job is complete, a confirmation message will appear.
-   A new Excel file will be created in the same directory as your input file, with `_cleaned` added to the name (e.g., `MyData_cleaned.xlsx`).
-   This new file contains all of your original data plus the new columns added by the tool:
    -   `Cleaned Merchant Name`
    -   `Website`
    -   `Socials`
    -   `Evidence` (explains how the data was found)
    -   `Evidence Links`
    -   `Cost per row`
    -   `Remarks` (contains notes from the cleaning process)

## 7. Backup and Recovery

The application automatically saves your progress.

-   **Checkpoints:** During a long job, a `.checkpoint.json` file is created. If the application crashes or is stopped, you can simply re-run the same job, and it will automatically resume from the last checkpoint.
-   **API Keys:** Your API keys are stored in `config/app_settings.json`. To back them up, simply copy this file to a safe location. To restore, place the backup file back in the `config` directory.

---
Thank you for using the AI-Powered Merchant Data Cleaning Tool!