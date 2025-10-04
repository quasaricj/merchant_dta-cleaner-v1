import pandas as pd

def create_srs_test_file():
    """
    Creates a challenging Excel file with diverse merchant data to test
    the application against the SRS requirements.
    """
    data = {
        "Merchant Name": [
            "Starbucks",  # Clean, well-known brand
            "SQ *SQ *THE COFFEE BEAN#5401",  # Messy, needs cleaning
            "MCDONALD'S #12345",  # Franchise
            "Nike Store", # Well-known brand, city but no street
            "Luigi's Pizza Palace", # Fictional local business with full address
            "City Lights Bookstore", # Real but less common business, only city
            "Totally Fake Biz Inc", # Unfindable merchant
            "Amazon Web Services", # Online business, no physical address
            "The Corner Deli", # Generic name, requires address to disambiguate
            "Uber Eats" # Aggregator, should be handled correctly
        ],
        "Address": [
            "1912 Pike Pl",
            "123 FAKE ST",
            "456 OAK AVE",
            "",
            "789 Pine Ln",
            "",
            "1 Nowhere St",
            "",
            "101 Maple Dr",
            ""
        ],
        "City": [
            "Seattle",
            "LOS ANGELES",
            "CHICAGO",
            "Beaverton", # Added city for Nike
            "New York",
            "San Francisco",
            "Nowhereville",
            "Seattle", # Added city for AWS
            "Anytown",
            ""
        ],
        "Country": [
            "USA",
            "USA",
            "USA",
            "USA",
            "USA",
            "USA",
            "USA",
            "USA",
            "USA",
            "USA"
        ],
        "Extra Info": [f"info_{i}" for i in range(10)] # A column that should be preserved
    }

    df = pd.DataFrame(data)

    output_filename = "srs_compliance_test_data.xlsx"
    df.to_excel(output_filename, index=False, engine='openpyxl')

    print(f"Test file '{output_filename}' created successfully.")

if __name__ == "__main__":
    create_srs_test_file()