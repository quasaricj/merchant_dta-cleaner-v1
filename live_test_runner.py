import os
import sys
import time
import threading

# Ensure the src directory is in the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.core.job_manager import JobManager
from src.core.data_model import JobSettings, ApiConfig, ColumnMapping, get_default_output_columns

# --- Configuration ---
# IMPORTANT: These are the live API keys for testing.
API_KEY_GEMINI = "AIzaSyAKhZMr8YSrLMA9ibvQKvKnnskefAHPDKA"
API_KEY_SEARCH = "AIzaSyB5kDmEk0lze4iZZgI3KPKBNmu-id6ivfA"
CSE_ID = "b54a78356ae6441e9"

INPUT_FILE = "srs_compliance_test_data.xlsx"
OUTPUT_FILE = "live_test_output.xlsx"

# This event will signal when the job is complete
job_finished_event = threading.Event()

def run_live_test():
    """
    Configures and runs a live data processing job using the JobManager.
    This test uses real API calls and does not mock the processing engine.
    """
    print("--- Starting Live End-to-End Test ---")

    # 1. Configure API keys
    api_config = ApiConfig(
        gemini_api_key=API_KEY_GEMINI,
        search_api_key=API_KEY_SEARCH,
        search_cse_id=CSE_ID
    )

    # 2. Configure Column Mapping
    column_mapping = ColumnMapping(
        merchant_name="Merchant Name",
        address="Address",
        city="City",
        country="Country"
    )

    # 3. Configure Job Settings
    job_settings = JobSettings(
        input_filepath=INPUT_FILE,
        output_filepath=OUTPUT_FILE,
        column_mapping=column_mapping,
        start_row=2,
        end_row=12,
        mode="Basic",
        model_name="models/gemini-flash-latest",
        output_columns=get_default_output_columns()
    )

    # 4. Define Callbacks
    def status_callback(processed, total, message):
        print(f"Status: {message} | Progress: {processed}/{total}")

    def completion_callback(message):
        print(f"\n--- Job Finished ---")
        print(f"Completion message: {message}")
        if "success" in message.lower():
            print(f"Output file should be available at: {OUTPUT_FILE}")
        else:
            print("Job did not complete successfully. Check logs for details.")
        job_finished_event.set()

    # 5. Initialize and Start the Job Manager
    print("Initializing Job Manager...")
    manager = JobManager(job_settings, api_config, status_callback, completion_callback)

    print("Starting job...")
    manager.start()

    print("Job is running in the background. Waiting for completion signal...")
    finished_in_time = job_finished_event.wait(timeout=600) # 10 minute timeout
    if not finished_in_time:
        print("ERROR: Job timed out after 10 minutes.")
        manager.stop()
        job_finished_event.set()

    print("\n--- Live Test Script Finished ---")

if __name__ == "__main__":
    run_live_test()