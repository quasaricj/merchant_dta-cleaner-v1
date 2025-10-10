"""
A script to perform a large-scale stress test on the JobManager to verify
its checkpointing and recovery capabilities.
"""
import os
import time
import pandas as pd
import shutil
from unittest.mock import patch

from src.core.job_manager import JobManager
from src.core.data_model import JobSettings, ApiConfig, ColumnMapping, OutputColumnConfig
from src.services.mock_google_api_client import MockGoogleApiClient

# --- Configuration ---
INPUT_FILE = "large_test_data_5000.xlsx" # Using the smaller, targeted test file
OUTPUT_DIR = "stress_test_output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "large_test_data_5000_processed.xlsx")
CHECKPOINT_FILE = f"{INPUT_FILE}.checkpoint.json"

def run_test(simulate_interruption: bool):
    """
    Runs the stress test.

    Args:
        simulate_interruption: If True, stops the job after a short time.
                               If False, lets the job run to completion (or from checkpoint).
    """
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file '{INPUT_FILE}' not found. Please generate it first.")
        return

    # --- Setup Callbacks ---
    def status_callback(processed, total, message):
        if processed % 1000 == 0 or processed == total: # Log less frequently
            print(f"Status: {processed}/{total} - {message}")

    def completion_callback(message):
        print(f"\nCompletion: {message}\n")

    # --- Setup Config ---
    api_config = ApiConfig("fake_gemini", "fake_search", "fake_cse")
    column_mapping = ColumnMapping(merchant_name="Merchant Name", country="Country")
    job_settings = JobSettings(
        input_filepath=INPUT_FILE,
        output_filepath=OUTPUT_FILE,
        column_mapping=column_mapping,
        start_row=2,
        end_row=5001, # 5k rows + header
        mode="Basic",
        model_name="mock-model",
        output_columns=[
            OutputColumnConfig(source_field='cleaned_merchant_name', output_header='Cleaned Merchant Name', enabled=True),
            OutputColumnConfig(source_field='website', output_header='Website', enabled=True),
            OutputColumnConfig(source_field='socials', output_header='Social media links', enabled=True),
            OutputColumnConfig(source_field='evidence', output_header='Evidence', enabled=True),
            OutputColumnConfig(source_field='evidence_links', output_header='Evidence Links', enabled=True),
            OutputColumnConfig(source_field='cost_per_row', output_header='Cost per row', enabled=True),
            OutputColumnConfig(source_field='logo_filename', output_header='Logo Filename', enabled=True),
            OutputColumnConfig(source_field='remarks', output_header='Remarks', enabled=True),
        ]
    )

    with patch('src.core.job_manager.GoogleApiClient', MockGoogleApiClient):
        manager = JobManager(
            settings=job_settings,
            api_config=api_config,
            status_callback=status_callback,
            completion_callback=completion_callback,
            logo_status_callback=lambda *args: None,
            logo_completion_callback=lambda *args: None,
            view_text_website_func=lambda url: "<html>mock content</html>"
        )

        print("--- Starting Job ---")
        manager.start()

        start_time = time.time()

        if simulate_interruption:
            print("\n>>> Simulating interruption. Will stop the job in a few seconds...")
            time.sleep(15)
            manager.stop()
            print(">>> Stop signal sent.")

        if manager._thread:
            manager._thread.join()
        print(f"--- Job Finished in {time.time() - start_time:.2f} seconds ---")


def verify_results():
    """Checks the final output file for data integrity."""
    print("\n--- Verifying Results ---")
    if not os.path.exists(OUTPUT_FILE):
        print("FAILURE: Output file was not created.")
        return

    try:
        df = pd.read_excel(OUTPUT_FILE)
        num_rows = len(df)
        print(f"Output file found with {num_rows} rows.")

        if num_rows != 5000:
            print(f"FAILURE: Expected 5,000 rows, but found {num_rows}.")
            return

        failed_rows = df[df['Remarks'].str.contains("FATAL_ERROR", na=False)]
        num_failed = len(failed_rows)
        print(f"Found {num_failed} rows that failed as expected.")

        if num_failed == 0:
            print("FAILURE: Did not find any rows marked with FATAL_ERROR. The test did not run correctly.")
            return

        print("SUCCESS: Job completed, and row-level errors were handled correctly without crashing.")

    except Exception as e:
        print(f"An error occurred during verification: {e}")


if __name__ == "__main__":
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

    print("--- Running Interruption Test ---")
    run_test(simulate_interruption=True)

    print("\n\n--- Running Recovery Test ---")
    run_test(simulate_interruption=False)

    verify_results()