
import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import glob
from urllib.parse import quote_plus

load_dotenv()

def get_db_engine():
    """Creates a database engine from environment variables."""
    db_user = os.getenv("DB_USER")
    raw_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")

    if not all([db_user, raw_password, db_host, db_port, db_name]):
        raise ValueError("One or more database credentials not found in .env file. Please check your configuration.")

    # URL-encode the password to handle special characters like '@'
    db_password = quote_plus(raw_password)

    engine = create_engine(
        f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )
    return engine

def load_csv_to_table(engine, csv_file_path, table_name):
    """Loads a single CSV file into a specified database table."""
    try:
        df = pd.read_csv(csv_file_path)
        print(f"Loading {len(df)} rows from {os.path.basename(csv_file_path)} into '{table_name}' table...")
        df.to_sql(table_name, engine, if_exists='append', index=False)
        print("Successfully loaded data.")
    except Exception as e:
        print(f"Error loading data from {csv_file_path}: {e}")

def main():
    """
    Main function to orchestrate loading all Synthea CSVs into PostgreSQL.
    """
    engine = get_db_engine()
    data_directory = 'synthea_sample_data_csv_nov2021/csv'
    
    table_mapping = {
        'patients': 'patients',
        'conditions': 'conditions',
        'encounters': 'encounters',
        'medications': 'medications',
        'organizations': 'organizations'
    }

    csv_files = glob.glob(os.path.join(data_directory, '*.csv'))
    
    if not csv_files:
        print(f"No CSV files found in '{data_directory}'. Please check the path.")
        return

    for csv_file in csv_files:
        file_name = os.path.basename(csv_file)
        table_key = os.path.splitext(file_name)[0]
        if table_key in table_mapping:
            table_name = table_mapping[table_key]
            load_csv_to_table(engine, csv_file, table_name)
        else:
            print(f"Skipping file {file_name} as it does not have a corresponding table mapping.")

if __name__ == "__main__":
    main()
