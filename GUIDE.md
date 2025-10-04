# AI-Powered Merchant Data Cleaning Tool - User Guide

This guide provides step-by-step instructions on how to use the AI-Powered Merchant Data Cleaning Tool to clean and enrich your merchant data from Excel files.

## Table of Contents
1.  [First-Time Setup: API Keys & Validation](#1-first-time-setup-api-keys--validation)
2.  [Step-by-Step Workflow](#2-step-by-step-workflow)
    *   [Step 1: Select Your Input File](#step-1-select-your-input-file)
    *   [Step 2: Map Your Input Columns](#step-2-map-your-input-columns)
    *   [Step 3: Select Row Range](#step-3-select-row-range)
    *   [Step 4: Configure Output Columns](#step-4-configure-output-columns)
    *   [Step 5: Configure and Run](#step-5-configure-and-run)
3.  [Managing a Running Job](#3-managing-a-running-job)
4.  [Reviewing Results & Troubleshooting](#4-reviewing-results--troubleshooting)
5.  [Understanding the Output File](#5-understanding-the-output-file)

---

### 1. First-Time Setup: API Keys & Validation

Before you can use the tool, you need to provide and validate API keys for the Google services it relies on. You will be prompted for these on first launch, but you can access them at any time from the **Settings > API Keys** menu.

**Required Keys:**
*   **Google Gemini API Key:** For accessing the AI models.
*   **Google Search API Key:** For the Custom Search API.
*   **Google Search CSE ID:** Your Custom Search Engine ID.

**Optional Key:**
*   **Google Places API Key:** Required for "Enhanced" mode.

When you click **"Save and Validate"**, the application will:
1.  Save your keys securely.
2.  Attempt to connect to the Google Gemini API to validate your key and fetch a list of available AI models.

If validation is successful, a success message will appear, and the "AI Model" dropdown in Step 5 will be enabled. If it fails, you will receive an error message, and the "Start Processing" button will remain disabled until the keys are corrected.

---

### 2. Step-by-Step Workflow

#### Step 1: Select Your Input File
-   Click the **Browse...** button to select the Excel file (`.xlsx`, `.xls`) containing your merchant data.
-   The application will load a preview of the first 10 rows and enable the subsequent steps.

#### Step 2: Map Your Input Columns
This step tells the application which columns in your file correspond to the required data fields.
-   **Dropdown Menus:** Use the dropdown for each field to select the corresponding column from your file.
-   **Duplicate Prevention:** Once a column is assigned to a field, it will be removed from the list of options for all other fields to prevent errors.
-   **Merchant Name (mandatory):** You must map this field to enable processing.
-   **Optional Fields:** For any optional field you don't have, leave the dropdown set to **`<Do Not Map>`**.

#### Step 3: Select Row Range
Specify which rows from your Excel file you want to process. By default, the tool selects all rows.

#### Step 4: Configure Output Columns
This powerful feature allows you to customize the final output file exactly to your needs.
-   **Source Field:** Choose the data you want to include in this output column. You can select any of the enriched fields (like "Cleaned Merchant Name", "Website", etc.) or a custom/blank field. Once a source field is used, it cannot be selected again.
-   **Output Column Header:** Enter the exact name you want for the column header in the final Excel file.
-   **Reorder (▲/▼):** Use the up and down arrow buttons to change the order of the columns.
-   **Add Custom Column:** Click this button to add a new, blank column to your output file. This is useful for adding notes or other data downstream.
-   **Remove (✖):** You can remove any column from the output configuration.

#### Step 5: Configure and Run
-   **Processing Mode:**
    -   **Basic:** Uses Gemini AI and Google Search.
    -   **Enhanced:** Adds the Google Places API for higher-accuracy business verification.
-   **AI Model:** Select a validated AI model from the dropdown. The list includes the estimated cost per request for each model, helping you make an informed decision. The application defaults to the lowest-cost model.
-   **Estimated Cost:** The tool provides a real-time cost estimate based on the number of rows, processing mode, and the selected AI model.
-   **Start Processing:** Once all mandatory configurations are complete, this button will be enabled. Click it to begin the job.

---

### 3. Managing a Running Job
The "Job Progress" section provides real-time feedback.
-   **Status Text:** Provides updates on the current operation (e.g., "Initializing...", "Processing Row 50/1000...").
-   **Pause/Resume/Stop:** You can pause, resume, or stop the job at any time. If stopped, progress is saved in a checkpoint file.

---

### 4. Reviewing Results & Troubleshooting
When a job finishes, the progress area transforms into a results panel.
-   **If Successful:**
    -   A **"Job Completed Successfully"** message is displayed.
    -   The full path to the output file is shown.
    -   **Copy Path:** Copies the file path to your clipboard.
    -   **Open File:** Opens the output file with your system's default application.
-   **If Failed:**
    -   A **"Job Failed"** message is displayed with a summary of the error.
    -   A **"Diagnose Problem"** button appears. Clicking this runs a series of checks (Internet, API Keys, File Permissions, etc.) and provides a detailed report with recommended fixes to help you resolve the issue.

---

### 5. Understanding the Output File
-   The output file is saved in the same directory as your input file with `_cleaned` appended to the filename.
-   It contains only the rows you selected for processing.
-   The columns appear in the order you specified in the "Configure Output Columns" step.
-   The original, unmapped columns from your input file are preserved and appended after the enriched columns.