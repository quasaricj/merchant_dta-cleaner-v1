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
from src.services.google_api_client import GoogleApiClient


class JobManager:
    """Manages the lifecycle of a data processing job."""

    def __init__(self, settings: JobSettings, api_config: ApiConfig,
                 status_callback: Callable, completion_callback: Callable):
        self.settings = settings
        self.api_config = api_config
        self.status_callback = status_callback
        self.completion_callback = completion_callback
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._is_running = False
        self._is_paused = False
        self._is_stopped = False
        self.processed_records: List[MerchantRecord] = []
        self.start_from_row = self.settings.start_row
        self.checkpoint_path = f"{self.settings.input_filepath}.checkpoint.json"
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            log_file_path = os.path.abspath("job.log")
            file_handler = logging.FileHandler(log_file_path)
            file_handler.setFormatter(log_formatter)
            self.logger.addHandler(file_handler)
            self.logger.setLevel(logging.INFO)

    def start(self):
        """Starts the processing job in a new thread."""
        if self._is_running: return
        self._is_running = True
        thread_settings = copy.deepcopy(self.settings)
        self._thread = threading.Thread(target=self._run, args=(thread_settings,), daemon=True)
        self._thread.start()

    def pause(self): self._is_paused = True
    def resume(self): self._is_paused = False
    def stop(self): self._is_stopped = True

    def _run(self, thread_settings: JobSettings):
        """The main processing loop that runs in the background."""
        last_processed_absolute_row = 0
        try:
            self.logger.info(f"Starting job for file: {thread_settings.input_filepath}")
            self.status_callback(0, 0, "Loading checkpoint...")
            self._load_checkpoint()

            self.status_callback(0, 0, "Initializing API clients...")
            api_client = GoogleApiClient(self.api_config, model_name=thread_settings.model_name)
            engine = ProcessingEngine(thread_settings, api_client)

            self.status_callback(0, 0, "Reading input file...")
            df = pd.read_excel(thread_settings.input_filepath, header=0, engine='openpyxl', keep_default_na=False)

            # Determine the full slice for the entire job based on original settings.
            # This is crucial for correctly aligning data when writing the output file.
            full_job_start_index = thread_settings.start_row - 2
            full_job_end_index = thread_settings.end_row - 1
            full_original_slice = df.iloc[full_job_start_index:full_job_end_index]
            total_rows_for_job = len(full_original_slice)

            # Determine the slice for the *current* processing run, which may be a partial
            # run if resuming from a checkpoint. self.start_from_row is updated by _load_checkpoint.
            current_run_start_index = self.start_from_row - 2
            df_to_process = df.iloc[current_run_start_index:full_job_end_index]

            self.status_callback(len(self.processed_records), total_rows_for_job, "Processing...")

            for i, row in df_to_process.iterrows():
                if self._is_stopped: break
                while self._is_paused:
                    if self._is_stopped: break
                    time.sleep(1)

                record = self._create_record_from_row(row, thread_settings.column_mapping)
                processed_record = engine.process_record(record)
                with self._lock:
                    self.processed_records.append(processed_record)

                last_processed_absolute_row = i + 2
                self.status_callback(len(self.processed_records), total_rows_for_job, "Processing...")

                if len(self.processed_records) % 50 == 0:
                    self._save_checkpoint(current_row=last_processed_absolute_row, settings_to_save=thread_settings)

            # --- Finalization ---
            if self._is_stopped:
                if self.processed_records:
                    self._write_output_file(full_original_slice)
                self.logger.info("Job stopped by user. Partial results saved.")
                self.completion_callback("Job Stopped")
            else:
                self._write_output_file(full_original_slice)
                self._cleanup_checkpoint()
                self.logger.info("Job completed successfully.")
                self.completion_callback("Job Completed Successfully")

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

    def _write_output_file(self, original_data_df: pd.DataFrame):
        """
        Writes the final results to an Excel file by combining the original data
        with the new, processed data.
        """
        with self._lock:
            if not self.processed_records:
                self.logger.warning("No records were processed, output file will not be written.")
                return

            # Make a copy to avoid SettingWithCopyWarning
            final_df = original_data_df.copy()

            # Convert the list of processed record objects into a DataFrame
            processed_df = pd.DataFrame([asdict(r) for r in self.processed_records])

            # Reset index on both DataFrames to ensure alignment when adding columns
            final_df.reset_index(drop=True, inplace=True)
            processed_df.reset_index(drop=True, inplace=True)

        # Iterate through the user-defined output columns and add them to the final DataFrame
        for col_config in self.settings.output_columns:
            if col_config.enabled:
                if col_config.is_custom:
                    # Add a blank column if it's a custom user-defined one
                    final_df[col_config.output_header] = ""
                elif hasattr(processed_df, col_config.source_field):
                    # Check if the source field exists in the processed data
                    if col_config.source_field in processed_df.columns:
                        final_df[col_config.output_header] = processed_df[col_config.source_field]
                    else:
                        # If the source field is valid but missing (e.g., optional field), add a blank column
                        final_df[col_config.output_header] = ""

        try:
            # Save the combined DataFrame to the output file
            final_df.to_excel(self.settings.output_filepath, index=False, na_rep='')
            self.logger.info(f"Successfully wrote output to {self.settings.output_filepath}")
        except (IOError, PermissionError) as e:
            # Raise a specific, informative error if the file can't be written
            raise IOError(f"Could not write to output file '{self.settings.output_filepath}'. Check permissions. Original error: {e}")

    def _cleanup_checkpoint(self):
        """Removes the checkpoint file upon successful completion."""
        if os.path.exists(self.checkpoint_path):
            os.remove(self.checkpoint_path)
            self.logger.info("Checkpoint file cleaned up.")