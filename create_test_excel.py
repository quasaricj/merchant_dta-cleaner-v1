import pandas as pd
import numpy as np
import sys

def create_test_file(num_rows: int):
    """
    Creates a challenging Excel file with diverse merchant data to test
    the application against the SRS requirements.
    """
    base_data = {
        "Merchant Name": [
            "Starbucks", "SQ *SQ *THE COFFEE BEAN#5401", "MCDONALD'S #12345",
            "Nike Store", "Luigi's Pizza Palace", "City Lights Bookstore",
            "Totally Fake Biz Inc", "Amazon Web Services", "The Corner Deli", "Uber Eats",
            "FORCE_FAIL_MERCHANT" # This record will be used to test row-level error handling
        ],
        "Address": [
            "1912 Pike Pl", "123 FAKE ST", "456 OAK AVE", "", "789 Pine Ln",
            "", "1 Nowhere St", "", "101 Maple Dr", "", "123 Fail St"
        ],
        "City": [
            "Seattle", "LOS ANGELES", "CHICAGO", "Beaverton", "New York",
            "San Francisco", "Nowhereville", "Seattle", "Anytown", "", "Fail City"
        ],
        "Country": ["USA"] * 11,
    }

    # Repeat the base data to reach the desired number of rows
    num_repeats = (num_rows // len(base_data["Merchant Name"])) + 1

    data = {}
    for key, values in base_data.items():
        data[key] = np.tile(values, num_repeats)[:num_rows]

    # Add a unique identifier to ensure data is not identical
    data["Extra Info"] = [f"info_{i}" for i in range(num_rows)]

    df = pd.DataFrame(data)

    output_filename = f"large_test_data_{num_rows}.xlsx"
    df.to_excel(output_filename, index=False, engine='openpyxl')

    print(f"Test file '{output_filename}' with {num_rows} rows created successfully.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python create_test_excel.py <number_of_rows>")
        sys.exit(1)

    try:
        rows = int(sys.argv[1])
        if rows <= 0:
            print("Number of rows must be a positive integer.")
            sys.exit(1)
        create_test_file(rows)
    except ValueError:
        print("Invalid number format. Please provide an integer for the number of rows.")
        sys.exit(1)