# pylint: disable=too-many-instance-attributes
"""
This module defines the JobManager, a core class responsible for managing the
entire lifecycle of a data processing job. It handles threading, checkpointing,
and orchestrates the processing loop.
"""
import os
import json
import time
import threading
import copy
from typing import Callable, Optional, List
from dataclasses import asdict, is_dataclass

import pandas as pd

from src.core.data_model import JobSettings, MerchantRecord, ApiConfig, ColumnMapping
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

    def start(self):
        """Starts the processing job in a new thread."""
        if self._is_running:
            return

        self._is_running = True
        # Use a deep copy of settings for the thread to prevent state corruption
        thread_settings = copy.deepcopy(self.settings)
        self._thread = threading.Thread(target=self._run, args=(thread_settings,), daemon=True)
        self._thread.start()

    def pause(self):
        """Pauses the processing job."""
        self._is_paused = True

    def resume(self):
        """Resumes a paused job."""
        self._is_paused = False

    def stop(self):
        """Stops the job gracefully."""
        self._is_stopped = True

    def _run(self, thread_settings: JobSettings):
        """The main processing loop that runs in the background."""
        try:
            # 1. Load from checkpoint if it exists
            self._load_checkpoint()

            # 2. Initialize API client and processing engine
            api_client = GoogleApiClient(self.api_config)
            engine = ProcessingEngine(thread_settings, api_client)

            # 3. Read the input file
            df = pd.read_excel(thread_settings.input_filepath,
                               header=thread_settings.start_row - 2)

            total_rows_in_range = (thread_settings.end_row - self.start_from_row) + 1

            # 4. Main processing loop
            last_processed_absolute_row = 0
            for i, row in df.iloc[self.start_from_row - thread_settings.start_row:].iterrows():
                if self._is_stopped:
                    break

                while self._is_paused:
                    if self._is_stopped:
                        break
                    time.sleep(1)

                record = self._create_record_from_row(row, thread_settings.column_mapping)
                processed_record = engine.process_record(record)

                with self._lock:
                    self.processed_records.append(processed_record)
                    num_processed = len(self.processed_records)

                assert isinstance(i, int)
                last_processed_absolute_row = i + thread_settings.start_row
                self.status_callback(num_processed, total_rows_in_range, "Processing...")

                if num_processed % 50 == 0:
                    self._save_checkpoint(current_row=last_processed_absolute_row,
                                          settings_to_save=thread_settings)

            # 5. Finalize
            if self._is_stopped:
                if self.processed_records and last_processed_absolute_row > 0:
                    self._save_checkpoint(current_row=last_processed_absolute_row,
                                          settings_to_save=thread_settings)
                self.completion_callback("Job Stopped")
            else:
                self._write_output_file()
                self._cleanup_checkpoint()
                self.completion_callback("Job Completed Successfully")

        except (IOError, ValueError, KeyError) as e:
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
        # Force reconstruction of dataclass to prevent state corruption issues.
        if not is_dataclass(settings_to_save):
            settings_to_save = JobSettings(**vars(settings_to_save))
        if hasattr(settings_to_save, "column_mapping") and \
           not is_dataclass(settings_to_save.column_mapping):
            settings_to_save.column_mapping = ColumnMapping(**vars(settings_to_save.column_mapping))

        with self._lock:
            records_to_save = list(self.processed_records)

        checkpoint_data = {
            "last_processed_row": current_row,
            "job_settings": asdict(settings_to_save),
            "processed_records": [asdict(r) for r in records_to_save]
        }
        with open(self.checkpoint_path, 'w', encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=4)
        print(f"Checkpoint saved at row {current_row}")

    def _load_checkpoint(self):
        """Loads progress from a checkpoint file if it exists and is valid."""
        if not os.path.exists(self.checkpoint_path):
            return
        try:
            with open(self.checkpoint_path, 'r', encoding="utf-8") as f:
                checkpoint_data = json.load(f)
            saved_settings_dict = checkpoint_data.get("job_settings")
            if not saved_settings_dict or \
               saved_settings_dict.get("input_filepath") != self.settings.input_filepath:
                return
            saved_mapping_dict = saved_settings_dict.pop("column_mapping")
            saved_mapping = ColumnMapping(**saved_mapping_dict)
            with self._lock:
                self.settings = JobSettings(**saved_settings_dict, column_mapping=saved_mapping)
                self.start_from_row = checkpoint_data.get("last_processed_row",
                                                          self.settings.start_row - 1) + 1
                self.processed_records = [
                    MerchantRecord(**r) for r in checkpoint_data.get("processed_records", [])
                ]
                print(f"Resuming from checkpoint. Starting at row {self.start_from_row}.")
        except (IOError, json.JSONDecodeError) as e:
            print(f"Could not load checkpoint file. Starting from scratch. Error: {e}")
            self._cleanup_checkpoint()

    def _write_output_file(self):
        """Writes the processed records to the final output Excel file."""
        with self._lock:
            if not self.processed_records:
                return
            output_df = pd.DataFrame([asdict(r) for r in self.processed_records])
        other_data_df = output_df['other_data'].apply(pd.Series)
        output_df = pd.concat([output_df.drop('other_data', axis=1), other_data_df], axis=1)
        output_df.to_excel(self.settings.output_filepath, index=False)

    def _cleanup_checkpoint(self):
        """Removes the checkpoint file upon successful completion."""
        if os.path.exists(self.checkpoint_path):
            os.remove(self.checkpoint_path)
            print("Checkpoint file cleaned up.")