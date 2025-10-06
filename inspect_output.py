import pandas as pd

# Set pandas display options to show all columns and prevent line wrapping
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)

try:
    # Read the generated Excel file
    df = pd.read_excel("live_test_output.xlsx", engine='openpyxl')
    # Print the DataFrame to the console
    print(df.to_string())
except FileNotFoundError:
    print("Error: 'live_test_output.xlsx' not found.")
except Exception as e:
    print(f"An error occurred: {e}")