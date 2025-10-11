# pylint: disable=too-few-public-methods,too-many-arguments,too-many-locals
"""
This module contains the LogoScraper class, responsible for downloading
logos from websites or social media pages.
"""
import os
import shutil
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple

from src.core.data_model import MerchantRecord

class LogoScraper:
    """
    Handles the logic for scraping logos from URLs, with fallback mechanisms.
    """
    def __init__(self, records: List[MerchantRecord], output_dir: str, fallback_image_path: str):
        self.records = records
        self.output_dir = output_dir
        self.fallback_image_path = fallback_image_path
        self.report_data = []

    def run(self, progress_callback: callable):
        """
        Executes the logo scraping process for all records.
        """
        os.makedirs(self.output_dir, exist_ok=True)
        for i, record in enumerate(self.records):
            progress_callback(i + 1, len(self.records), record.cleaned_merchant_name)
            if record.logo_filename:
                target_path = os.path.join(self.output_dir, record.logo_filename)
                source_url = record.website if record.website else (record.socials[0] if record.socials else None)

                if source_url:
                    try:
                        logo_url = self._find_logo_url(source_url)
                        if logo_url:
                            self._download_image(logo_url, target_path)
                            self.report_data.append((record.logo_filename, "scraped from URL", logo_url))
                        else:
                            self._use_fallback(target_path, "Logo not found on page")
                    except Exception as e:
                        self._use_fallback(target_path, f"Scrape failed: {e}")
                else:
                    self._use_fallback(target_path, "No URL available")
        self._generate_report()

    def _find_logo_url(self, page_url: str) -> Optional[str]:
        """
        Parses a webpage to find the most likely logo URL.
        This is a placeholder for a more sophisticated implementation.
        """
        # A more robust implementation would check for meta tags, specific classes, etc.
        # For now, we'll simulate a simple logic.
        response = requests.get(page_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Simple heuristic: find an image with 'logo' in its src
        logo_img = soup.find('img', src=lambda s: s and 'logo' in s.lower())
        if logo_img:
            return requests.compat.urljoin(page_url, logo_img['src'])

        return None

    def _download_image(self, url: str, target_path: str):
        """
        Downloads an image from a URL and saves it to the target path.
        """
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

    def _use_fallback(self, target_path: str, reason: str):
        """
        Copies the fallback image to the target path.
        """
        shutil.copy(self.fallback_image_path, target_path)
        self.report_data.append((os.path.basename(target_path), f"fallback used - {reason}", ""))

    def _generate_report(self):
        """
        Generates a CSV report of the scraping results.
        """
        report_path = os.path.join(self.output_dir, "scraping_report.csv")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("Logo Filename,Status,Source\\n")
            for row in self.report_data:
                f.write(f'"{row[0]}","{row[1]}","{row[2]}"\\n')