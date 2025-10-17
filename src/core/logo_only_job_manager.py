# pylint: disable=too-many-instance-attributes,broad-except-clause
"""
This module defines the LogoOnlyJobManager, a class dedicated to running
the logo scraping process as a standalone feature.
"""
import os
import logging
import threading
from typing import Callable, Optional, List, Dict

import pandas as pd

from src.core.data_model import MerchantRecord
from src.core.logo_scraper import LogoScraper


class LogoOnlyJobManager:
    """Manages the lifecycle of a logo-only scraping job."""

    def __init__(self,
                 input_filepath: str,
                 column_mapping: Dict[str, str],
                 status_callback: Callable,
                 completion_callback: Callable):
        self.input_filepath = input_filepath
        self.column_mapping = column_mapping
        self.status_callback = status_callback
        self.completion_callback = completion_callback
        self._thread: Optional[threading.Thread] = None
        self._is_stopped = False
        self.logger = logging.getLogger(__name__)

    def start(self):
        """Starts the logo scraping job in a new thread."""
        if self._thread and self._thread.is_alive():
            return
        self._is_stopped = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Signals the running job to stop."""
        self.logger.info("Stop command received for logo-only job.")
        self._is_stopped = True

    def _run(self):
        """The main processing loop for the logo scraping job."""
        try:
            self.logger.info(f"Starting logo-only job for file: {self.input_filepath}")
            self.status_callback(0, 0, "Reading input file...")

            # Read the necessary columns from the Excel file
            df = pd.read_excel(self.input_filepath, header=0, engine='openpyxl', keep_default_na=False)

            # Validate that all mapped columns exist in the dataframe
            for key, col_name in self.column_mapping.items():
                if col_name not in df.columns:
                    raise ValueError(f"Required column '{col_name}' (mapped to '{key}') not found in the input file.")

            records_to_scrape: List[MerchantRecord] = []
            for _, row in df.iterrows():
                # The logo scraper relies on these specific fields in the MerchantRecord
                # The 'socials' field expects a list of strings.
                social_link = row.get(self.column_mapping.get("social_media_links"), "")
                socials_list = [social_link] if social_link else []

                record = MerchantRecord(
                    original_name=row.get(self.column_mapping["cleaned_merchant_name"], ""), # Use cleaned name as original for this mode
                    cleaned_merchant_name=row.get(self.column_mapping["cleaned_merchant_name"], ""),
                    website=row.get(self.column_mapping["website"], ""),
                    socials=socials_list,
                    logo_filename=row.get(self.column_mapping["logo_filename"], "")
                )
                records_to_scrape.append(record)

            if not records_to_scrape:
                self.completion_callback("Job finished: No records found to scrape.")
                return

            # Prepare for scraping
            base_dir = os.path.dirname(self.input_filepath)
            input_filename = os.path.splitext(os.path.basename(self.input_filepath))[0]
            logo_dir_name = f"logos_from_{input_filename}"
            logo_output_dir = os.path.join(base_dir, logo_dir_name)
            fallback_image = os.path.abspath("data/image_for_logo_scraping_error.png")

            if not os.path.exists(fallback_image):
                 raise FileNotFoundError("Fallback logo image 'data/image_for_logo_scraping_error.png' not found.")

            scraper = LogoScraper(records_to_scrape, logo_output_dir, fallback_image)

            # Define a wrapper for the progress callback to check for the stop flag
            def progress_wrapper(current, total, name):
                if self._is_stopped:
                    # Returning False from the callback signals the scraper to stop
                    return False
                self.status_callback(current, total, name)
                return True # Continue scraping

            self.logger.info(f"Starting logo scraping for {len(records_to_scrape)} records.")
            scraper.run(progress_callback=progress_wrapper)

            if self._is_stopped:
                 self.logger.info("Logo scraping job stopped by user.")
                 self.completion_callback("Job Stopped")
            else:
                self.logger.info("Logo scraping finished successfully.")
                self.completion_callback(f"Logo scraping complete. See folder: {logo_output_dir}")

        except Exception as e:
            self.logger.critical(f"An unexpected error occurred in the logo-only job thread: {e}", exc_info=True)
            self.completion_callback(f"Job Failed: {e}")