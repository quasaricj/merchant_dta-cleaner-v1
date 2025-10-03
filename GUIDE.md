# AI-Powered Merchant Data Cleaning Tool - User Guide

This guide provides step-by-step instructions on how to use the AI-Powered Merchant Data Cleaning Tool to clean and enrich your merchant data from Excel files.

## Table of Contents
1.  [First-Time Setup: API Keys](#1-first-time-setup-api-keys)
2.  [Step-by-Step Workflow](#2-step-by-step-workflow)
    *   [Step 1: Select Your Input File](#step-1-select-your-input-file)
    *   [Step 2: Map Your Input Columns](#step-2-map-your-input-columns)
    *   [Step 3: Select Row Range](#step-3-select-row-range)
    *   [Step 4: Configure Output Columns](#step-4-configure-output-columns)
    *   [Step 5: Configure and Run](#step-5-configure-and-run)
3.  [Managing a Running Job](#3-managing-a-running-job)
4.  [Reviewing Your Results](#4-reviewing-your-results)
5.  [Understanding the Output File](#5-understanding-the-output-file)

---

### 1. First-Time Setup: API Keys

Before you can use the tool, you need to provide API keys for the Google services it relies on. You will be prompted for these on first launch, but you can access them at any time from the **Settings > API Keys** menu.

**Required Keys:**
*   **Google Gemini API Key:** For accessing the AI model that cleans the merchant names.
*   **Google Search API Key:** For the Custom Search API.
*   **Google Search CSE ID:** Your Custom Search Engine ID.

**Optional Key:**
*   **Google Places API Key:** Required for "Enhanced" mode, which provides higher accuracy business verification.

Enter your keys in the dialog and click "Save". The application will store them securely for future use.

---

### 2. Step-by-Step Workflow

Follow these steps to process a file.

#### Step 1: Select Your Input File
-   Click the **Browse...** button.
-   Select the Excel file (`.xlsx`, `.xls`) containing your merchant data.
-   Once selected, the application will load a preview of the first 10 rows and enable the next steps.

#### Step 2: Map Your Input Columns
This step tells the application which columns in your file correspond to the required data fields.
-   **Merchant Name (mandatory):** You must select the column that contains the merchant names from the dropdown menu. The "Start Processing" button will not be enabled until this is mapped.
-   **Address, City, Country, State/Region (optional):** Mapping these fields is optional but highly recommended as it significantly improves the accuracy of the enrichment process.
-   For any optional field you don't have, you can leave the dropdown set to **`<Do Not Map>`**.

#### Step 3: Select Row Range
Specify which rows from your Excel file you want to process.
-   **Start Row / End Row:** Enter the row numbers for the range you wish to process. The tool assumes Row 1 is a header, so data processing typically starts from Row 2.
-   The tool will automatically detect the last row of your file.

#### Step 4: Configure Output Columns
This powerful feature allows you to customize the final output file exactly to your needs.
-   **Include:** Use the checkbox to enable or disable a column from appearing in the output file.
-   **Output Column Header:** Click on the text field to rename the header for any column.
-   **Reorder (▲/▼):** Use the up and down arrow buttons to change the order of the columns in the output file.
-   **Add Custom Column:** Click this button to add a new, blank column to your output file. This is useful for adding notes or other data downstream.
-   **Remove (✖):** You can only remove custom columns that you have added. Standard enriched columns can only be disabled.

#### Step 5: Configure and Run
-   **Processing Mode:**
    -   **Basic:** Uses Gemini AI and Google Search. This is the most cost-effective mode.
    -   **Enhanced:** Adds the Google Places API for higher-accuracy business verification. This mode costs more but provides better results.
-   **Estimated Cost:** The tool provides a real-time cost estimate based on the number of rows selected and the processing mode.
-   **Start Processing:** Once you have configured all the steps, this button will be enabled. Click it to begin the job.

---

### 3. Managing a Running Job
Once a job is running, you can monitor its progress in the "Job Progress" section at the bottom of the window.
-   **Progress Bar:** Shows the overall completion percentage.
-   **Status Text:** Provides real-time updates on the current operation (e.g., "Initializing...", "Processing Row 50/1000...").
-   **Pause/Resume:** You can pause a running job at any time and resume it later.
-   **Stop:** You can stop a job permanently. The application will save its progress in a checkpoint file, allowing you to resume from where you left off if you process the same input file again later.

---

### 4. Reviewing Your Results
When a job finishes (or is stopped), the progress area transforms into a results panel, giving you immediate access to your output.
-   **Final Status:** A clear message (e.g., "Job Completed Successfully", "Job Stopped", or "Job Failed") is displayed.
-   **Output File Path:** The full path to the generated Excel file is shown in a read-only text field.
-   **Copy Path:** Click this button to copy the file path to your clipboard.
-   **Open File:** Click this button to open the output file directly with your system's default application for Excel files (e.g., Microsoft Excel, LibreOffice Calc).

---

### 5. Understanding the Output File
-   The output file will be saved in the same directory as your input file with `_cleaned` appended to the filename.
-   The file will contain only the rows you selected for processing.
-   The columns will appear in the order you specified in the "Configure Output Columns" step.
-   Any columns you disabled will not be present.
-   Any custom columns you added will be present with blank values.
-   The original, unmapped columns from your input file will be preserved and appended after the enriched columns.