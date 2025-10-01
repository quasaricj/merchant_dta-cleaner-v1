import pandas as pd
import os

def create_sample_data():
    """Creates a realistic sample Excel file for testing."""
    data = {
        "Transaction Description": [
            "SQ *O'MALLEYS TAVERN",
            "AMZ*Amazon Prime amzn.com/bill WA",
            "CHEVRON 0123 CITYVILLE",
            "STARBUCKS #54321",
            "UBER   EATS",
            "Parking Garage on 5th",
            "MCDONALDS F1122",
            "IN-N-OUT BURGER #123",
            "NETFLIX.COM",
            "Dr. Jane Smith, DDS"
        ],
        "Address": [
            "123 Main St",
            "",
            "456 Gas Rd",
            "789 Coffee Ave",
            "",
            "101 5th Ave",
            "321 Fastfood Ln",
            "456 Burger Blvd",
            "",
            "987 Dental Dr"
        ],
        "City": [
            "Anytown",
            "Seattle",
            "Cityville",
            "Metropolis",
            "New York",
            "Big City",
            "Foodville",
            "Flavor Town",
            "Los Gatos",
            "Healthville"
        ],
        "Region": [
            "CA",
            "WA",
            "TX",
            "NY",
            "NY",
            "IL",
            "FL",
            "CA",
            "CA",
            "MD"
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
        "Extra Data Column": [f"Info {i}" for i in range(10)]
    }

    df = pd.DataFrame(data)

    output_dir = "data"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_path = os.path.join(output_dir, "sample_merchant_data.xlsx")
    df.to_excel(output_path, index=False)
    print(f"Sample data created at {output_path}")

if __name__ == "__main__":
    create_sample_data()