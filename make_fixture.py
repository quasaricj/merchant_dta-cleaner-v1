import pandas as pd
import os

def create_fixture_data():
    """Creates an Excel file with edge-case data for testing."""
    data = {
        "Business Name": [
            "Walmart",
            "Biz with no address",
            "  Leading/Trailing Spaces  ",
            "EMPTY_CITY_BIZ"
        ],
        "Street": [
            "123 Main St",
            "",
            "456 Spacing Rd",
            "789 NoCity Ave"
        ],
        "City": [
            "Anytown",
            "Metropolis",
            "Spacetown",
            ""
        ],
        "Country Code": [
            "USA",
            "USA",
            "USA",
            "USA"
        ]
    }

    df = pd.DataFrame(data)

    output_dir = "tests/fixtures"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_path = os.path.join(output_dir, "edge_case_data.xlsx")
    df.to_excel(output_path, index=False)
    print(f"Fixture data created at {output_path}")

if __name__ == "__main__":
    create_fixture_data()