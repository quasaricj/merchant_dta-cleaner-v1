# pylint: disable=too-many-instance-attributes,broad-except-clause
"""
This module defines the JobManager, a core class responsible for managing the
entire lifecycle of a data processing job. It handles threading, checkpointing,
and orchestrates the processing loop.
"""
import os
import json
import time
import logging
import threading
import copy
from typing import Callable, Optional, List
from dataclasses import asdict, is_dataclass

import pandas as pd

from src.core.data_model import (JobSettings, MerchantRecord, ApiConfig,
                                  ColumnMapping, OutputColumnConfig)
from src.core.processing_engine import ProcessingEngine
from typing import Union, cast
from src.services.google_api_client import GoogleApiClient
from src.services.mock_google_api_client import MockGoogleApiClient
from src.core.logo_scraper import LogoScraper


class JobManager:
    """Manages the lifecycle of a data processing job."""

    def __init__(self, settings: JobSettings, api_config: ApiConfig,
                 status_callback: Callable, completion_callback: Callable,
                 logo_status_callback: Callable, logo_completion_callback: Callable,
                 view_text_website_func: Callable[[str], str]):
        self.settings = settings
        self.api_config = api_config
        self.status_callback = status_callback
        self.completion_callback = completion_callback
        self.logo_status_callback = logo_status_callback
        self.logo_completion_callback = logo_completion_callback
        self.view_text_website_func = view_text_website_func
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._is_running = False
        self._is_paused = False
        self._is_stopped = False
        self.processed_records: List[MerchantRecord] = []
        self.start_from_row = self.settings.start_row
        self.checkpoint_path = f"{self.settings.input_filepath}.checkpoint.json"
        self.api_client: Union[GoogleApiClient, MockGoogleApiClient]
        self.processing_engine: ProcessingEngine
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            log_file_path = os.path.abspath("job.log")
            file_handler = logging.FileHandler(log_file_path)
            file_handler.setFormatter(log_formatter)
            self.logger.addHandler(file_handler)
            self.logger.setLevel(logging.INFO)

    def start(self):
        """
        Performs comprehensive pre-flight checks and then starts the processing
        job in a new thread.
        """
        if self._is_running:
            return

        # --- Pre-flight Checks ---
        try:
            # Clear any old checkpoint to ensure a fresh start
            if os.path.exists(self.checkpoint_path):
                self.logger.info(f"Removing existing checkpoint file: {self.checkpoint_path}")
                os.remove(self.checkpoint_path)

            # 1. Validate essential files exist
            fallback_logo_path = os.path.abspath("data/image_for_logo_scraping_error.png")
            if not os.path.exists(fallback_logo_path):
                raise FileNotFoundError(f"Fallback logo not found at: {fallback_logo_path}")

            # 2. Validate output directory write permissions
            output_dir = os.path.dirname(self.settings.output_filepath)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            test_file = os.path.join(output_dir, f".permission_test_{os.getpid()}")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("test")
            os.remove(test_file)

            # 3. Validate API keys with a live check (skip in mock mode)
            if not self.settings.mock_mode:
                self.status_callback(0, 0, "Validating API keys...")
                temp_api_client = GoogleApiClient(self.api_config, self.settings.model_name)
                temp_api_client.validate_api_keys()
                self.status_callback(0, 0, "API keys validated.")
            else:
                self.status_callback(0, 0, "Mock Mode: Skipping API key validation.")

        except FileNotFoundError as e:
            raise RuntimeError(f"A critical file is missing: {e}") from e
        except PermissionError as e:
            raise PermissionError(f"Cannot write to output directory: {output_dir}. Please check permissions.") from e
        except ConnectionError as e:
            raise ConnectionError(f"API key validation failed. Please check your keys. Error: {e}") from e
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred during pre-flight checks: {e}") from e

        self._is_running = True
        thread_settings = copy.deepcopy(self.settings)
        self._thread = threading.Thread(target=self._run, args=(thread_settings,), daemon=True)
        self._thread.start()

    def pause(self):
        self.logger.info("Pause command received.")
        self._is_paused = True
    def resume(self):
        self.logger.info("Resume command received.")
        self._is_paused = False
    def stop(self):
        self.logger.info("Stop command received.")
        self._is_stopped = True

    def _run(self, thread_settings: JobSettings):
        """The main processing loop that runs in the background."""
        last_processed_absolute_row = 0
        try:
            self.logger.info(f"Starting job for file: {thread_settings.input_filepath}")
            self.status_callback(0, 0, "Loading checkpoint...")
            self._load_checkpoint()

            self.status_callback(0, 0, "Initializing API clients...")
            if thread_settings.mock_mode:
                self.logger.info("MOCK MODE ENABLED. Using MockGoogleApiClient.")
                self.api_client = MockGoogleApiClient(self.api_config, model_name=thread_settings.model_name)
            else:
                self.api_client = GoogleApiClient(self.api_config, model_name=thread_settings.model_name)
            self.processing_engine = ProcessingEngine(thread_settings, cast(GoogleApiClient, self.api_client), self.view_text_website_func)

            self.status_callback(0, 0, "Reading input file...")
            original_df = pd.read_excel(thread_settings.input_filepath, header=0, engine='openpyxl', keep_default_na=False)

            # --- REVISED AND CORRECTED SLICING LOGIC ---
            # Convert 1-based Excel row numbers (which are inclusive) to 0-based DataFrame indices (which are half-open).
            # A user selection of row 2 corresponds to index 0.
            start_index = thread_settings.start_row - 2
            # A user selection of rows 2-11 (10 rows) should slice from index 0 to 10 (exclusive).
            # The end row number is inclusive, so we subtract 1 to get the correct slice boundary.
            end_index = thread_settings.end_row -1

            # Clamp values to be within the dataframe's actual bounds.
            start_index = max(0, start_index)
            # The end index for .iloc is exclusive, so it can be at most len(df).
            end_index = min(len(original_df), end_index)

            # Handle checkpoint resumption. self.start_from_row is the 1-based Excel row to start FROM.
            current_run_start_index = self.start_from_row - 2
            current_run_start_index = max(start_index, current_run_start_index)

            # Final check to prevent invalid slices
            if current_run_start_index >= end_index:
                df_to_process = pd.DataFrame() # Process nothing if the range is invalid or already complete.
                self.logger.warning(f"Skipping processing: The start index ({current_run_start_index}) is not before the end index ({end_index}). This may be due to resuming a completed job.")
            else:
                df_to_process = original_df.iloc[current_run_start_index:end_index]

            total_rows_for_job = (thread_settings.end_row - thread_settings.start_row) + 1
            self.status_callback(len(self.processed_records), total_rows_for_job, "Processing...")

            for i, row in df_to_process.iterrows():
                if self._is_stopped: break
                while self._is_paused:
                    if self._is_stopped: break
                    time.sleep(1)

                try:
                    record = self._create_record_from_row(row, thread_settings.column_mapping)
                    processed_record = self.processing_engine.process_record(record)
                except Exception as row_error:
                    self.logger.error(f"Failed to process row {int(i) + 2}. Error: {row_error}", exc_info=True)
                    processed_record = self._create_record_from_row(row, thread_settings.column_mapping)
                    processed_record.remarks = f"FATAL_ERROR: {row_error}"
                    processed_record.evidence = f"The row could not be processed. Final error: {row_error}"
                    processed_record.cleaned_merchant_name = ""

                with self._lock:
                    self.processed_records.append(processed_record)

                last_processed_absolute_row = int(i) + 2
                self.status_callback(len(self.processed_records), total_rows_for_job, "Processing...")

                if len(self.processed_records) % 50 == 0:
                    self._save_checkpoint(current_row=int(last_processed_absolute_row), settings_to_save=thread_settings)

            if self._is_stopped:
                if self.processed_records:
                    self._write_output_file(original_df, thread_settings)
                self.logger.info("Job stopped by user. Partial results saved.")
                self.completion_callback("Job Stopped")
            else:
                self._write_output_file(original_df, thread_settings)
                self._cleanup_checkpoint()
                self.logger.info("Main data processing completed successfully.")
                self.completion_callback("Job Completed Successfully")
                self._start_logo_scraping()

        except Exception as e:
            self.logger.critical(f"An unexpected error occurred in the job thread: {e}", exc_info=True)
            if self.processed_records:
                self.logger.info("Attempting to save partial results via checkpoint before exiting due to error.")
                self._save_checkpoint(current_row=last_processed_absolute_row, settings_to_save=thread_settings)
            self.completion_callback(f"Job Failed: {e}")
        finally:
            self._is_running = False

    def _create_record_from_row(self, row: pd.Series, mapping: ColumnMapping) -> MerchantRecord:
        """Creates a MerchantRecord object from a pandas row and column mapping."""
        mapped_cols = asdict(mapping).values()
        return MerchantRecord(
            original_name=row.get(mapping.merchant_name, ""),
            original_address=row.get(mapping.address) if mapping.address else None,
            original_city=row.get(mapping.city) if mapping.city else None,
            original_country=row.get(mapping.country) if mapping.country else None,
            original_state=row.get(mapping.state) if mapping.state else None,
            other_data={str(col): val for col, val in row.items() if col not in mapped_cols}
        )

    def _save_checkpoint(self, current_row: int, settings_to_save: JobSettings):
        """Saves the current progress to a checkpoint file."""
        with self._lock:
            records_to_save = list(self.processed_records)
        checkpoint_data = {
            "last_processed_row": current_row,
            "job_settings": asdict(settings_to_save),
            "processed_records": [asdict(r) for r in records_to_save]
        }
        with open(self.checkpoint_path, 'w', encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=4)
        self.logger.info(f"Checkpoint saved at row {current_row}")

    def _load_checkpoint(self):
        """Loads progress from a checkpoint file if it exists and is valid."""
        if not os.path.exists(self.checkpoint_path): return
        try:
            with open(self.checkpoint_path, 'r', encoding="utf-8") as f:
                checkpoint_data = json.load(f)
            saved_settings_dict = checkpoint_data.get("job_settings")
            if not saved_settings_dict or saved_settings_dict.get("input_filepath") != self.settings.input_filepath: return

            saved_mapping = ColumnMapping(**saved_settings_dict.pop("column_mapping", {}))
            output_columns_data = saved_settings_dict.pop("output_columns", [])
            output_columns = [OutputColumnConfig(**data) for data in output_columns_data]

            with self._lock:
                self.settings = JobSettings(**saved_settings_dict, column_mapping=saved_mapping, output_columns=output_columns)
                self.start_from_row = checkpoint_data.get("last_processed_row", self.settings.start_row - 1) + 1
                self.processed_records = [MerchantRecord(**r) for r in checkpoint_data.get("processed_records", [])]
                self.logger.info(f"Resuming from checkpoint. Starting at row {self.start_from_row}.")
        except Exception as e:
            self.logger.error(f"Could not load checkpoint file. Starting from scratch. Error: {e}")
            self._cleanup_checkpoint()

    def _write_output_file(self, original_df: pd.DataFrame, thread_settings: JobSettings):
        """
        Writes the final results to an Excel file. It preserves the original file's
        contents and structure, updating only the rows within the selected range
        that were processed in the current job.
        """
        with self._lock:
            if not self.processed_records:
                self.logger.warning("No records were processed, output file will not be written.")
                return

            self.logger.info(f"Preparing to write {len(self.processed_records)} processed records to output file.")

            # This is the DataFrame with the new, processed data
            processed_df = pd.DataFrame([asdict(r) for r in self.processed_records])

            # Create a full copy of the original dataframe to modify. This is the foundation
            # of the output file, ensuring all non-processed rows are preserved.
            output_df = original_df.copy()

            # Determine the starting index for the update. This must account for both the
            # user's selected range and any checkpoint resumption.
            # We use the thread_settings here to get the original range selected by the user for this job.
            start_row_from_settings = thread_settings.start_row
            # self.start_from_row is the row we actually started on (could be from a checkpoint).
            actual_start_row = max(start_row_from_settings, self.start_from_row)
            update_start_index = actual_start_row - 2
            update_end_index = update_start_index + len(self.processed_records)

            self.logger.info(f"Updating output file from index {update_start_index} to {update_end_index-1}.")

            # Update the columns in the output_df slice.
            for col_config in self.settings.output_columns:
                if col_config.enabled and col_config.source_field in processed_df.columns:
                    # Ensure the target column exists in the output DataFrame before updating.
                    if col_config.output_header not in output_df.columns:
                        # Initialize with a default value that matches the source dtype if possible
                        output_df[col_config.output_header] = pd.Series(dtype=processed_df[col_config.source_field].dtype)

                    # Use .loc to update the specific slice. The indices of the slice must align
                    # with the indices of the source data. Using .values is crucial here as it
                    # ignores the index of the source (processed_df), preventing alignment errors.
                    output_df.loc[update_start_index:update_end_index-1, col_config.output_header] = processed_df[col_config.source_field].values

        try:
            # Fill any remaining NaN values from the merge with empty strings for a clean output
            # This is especially important for newly added columns outside the processed range.
            output_df.fillna('', inplace=True)
            output_df.to_excel(self.settings.output_filepath, index=False)
            self.logger.info(f"Successfully wrote {len(output_df)} total rows to {self.settings.output_filepath}")
        except (IOError, PermissionError) as e:
            raise IOError(f"Could not write to output file '{self.settings.output_filepath}'. Check permissions. Original error: {e}")

    def _cleanup_checkpoint(self):
        """Removes the checkpoint file upon successful completion."""
        if os.path.exists(self.checkpoint_path):
            os.remove(self.checkpoint_path)
            self.logger.info("Checkpoint file cleaned up.")

    def _start_logo_scraping(self):
        """Initializes and starts the logo scraping process in a background thread."""
        with self._lock:
            # Ensure we are using the records that were actually processed.
            records_for_scraping = list(self.processed_records)

        if not records_for_scraping:
            self.logger.info("No records to scrape logos for.")
            self.logo_completion_callback("Logo scraping skipped: no records processed.")
            return

        # Create the specific output directory for logos
        base_dir = os.path.dirname(self.settings.output_filepath)
        logo_dir_name = f"logos_of_range_{self.settings.start_row}-{self.settings.end_row}"
        logo_output_dir = os.path.join(base_dir, logo_dir_name)

        fallback_image = os.path.abspath("data/image_for_logo_scraping_error.png")

        scraper = LogoScraper(records_for_scraping, logo_output_dir, fallback_image)

        def scraping_task():
            try:
                self.logger.info(f"Starting logo scraping for {len(records_for_scraping)} records.")
                scraper.run(progress_callback=self.logo_status_callback)
                self.logger.info("Logo scraping finished successfully.")
                self.logo_completion_callback(f"Logo scraping complete. See folder: {logo_output_dir}")
            except Exception as e:
                self.logger.error(f"Logo scraping failed: {e}", exc_info=True)
                self.logo_completion_callback(f"Logo scraping failed: {e}")

        # Run the scraping task in a separate thread to not block the UI
        logo_thread = threading.Thread(target=scraping_task, daemon=True)
        logo_thread.start()