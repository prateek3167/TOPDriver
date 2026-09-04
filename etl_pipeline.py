import os
import sys
import logging
from datetime import datetime
import pandas as pd
from sqlalchemy import text
from db_engine import get_engine

# Configure logging
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "etl_pipeline.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

COLUMN_MAPPING = {
    'Ticket Id': 'ticket_id',
    'Created Time (Ticket)': 'created_time',
    'Closed Time': 'closed_time',
    'Created By (Ticket)': 'created_by',
    'Product': 'product',
    'Campaigns': 'campaigns',
    'Category (Ticket)': 'category',
    'Sub Category': 'sub_category',
    'Sub Category Classification': 'sub_category_classification',
    'Subject': 'subject',
    'Classifications': 'classifications',
    'Ticket Owner': 'ticket_owner',
    'Category+SubCategory': 'category_subcategory',
    'Category+SubCategory+Sub Category Classification': 'full_category_hierarchy'
}

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Cleans, normalizes, and casts columns before loading into MySQL."""
    logging.info("Validating and normalizing extracted dataframe...")
    
    # Rename columns
    df = df.rename(columns=COLUMN_MAPPING)
    
    # Replace whitespace and dash placeholders with None/NULL
    df = df.replace(r'^\s*-\s*$', None, regex=True)
    df = df.replace(r'^\s*$', None, regex=True)
    
    # Clean text columns
    str_cols = [
        'created_by', 'product', 'campaigns', 'category', 
        'sub_category', 'sub_category_classification', 
        'subject', 'classifications', 'ticket_owner', 
        'category_subcategory', 'full_category_hierarchy'
    ]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace({'None': None, 'nan': None, '<NA>': None})
            
    # Datetime conversions
    df['created_time'] = pd.to_datetime(df['created_time'], errors='coerce')
    df['closed_time'] = pd.to_datetime(df['closed_time'], errors='coerce')
    
    # Validate primary key integrity
    initial_count = len(df)
    df = df.dropna(subset=['ticket_id', 'created_time'])
    df['ticket_id'] = pd.to_numeric(df['ticket_id'], errors='coerce').astype('int64')
    
    # Drop in-file duplicates if any (keeps latest)
    df = df.drop_duplicates(subset=['ticket_id'], keep='last')
    
    dropped = initial_count - len(df)
    if dropped > 0:
        logging.warning(f"Discarded {dropped} invalid or in-file duplicate rows.")
        
    return df

def run_etl(file_path: str, chunksize: int = 50000):
    """Orchestrates the ingestion, staging, and upsert logic."""
    if not os.path.exists(file_path):
        logging.error(f"Target Excel file not found: {file_path}")
        return

    engine = get_engine()
    logging.info(f"Starting ETL execution for: {file_path}")
    start_time = datetime.now()

    try:
        # 1. Load Excel file
        logging.info("Reading Excel sheet 'Raw'...")
        df_raw = pd.read_excel(file_path, sheet_name="Raw")
        logging.info(f"Loaded {len(df_raw)} records from sheet.")

        # 2. Clean & Normalize
        df_clean = clean_dataframe(df_raw)

        # 3. Process to MySQL in Staging & Upsert
        with engine.begin() as conn:
            # Create isolated staging table
            conn.execute(text("DROP TABLE IF EXISTS staging_tickets;"))
            conn.execute(text("""
                CREATE TABLE staging_tickets (
                    ticket_id BIGINT PRIMARY KEY,
                    created_time DATETIME NOT NULL,
                    closed_time DATETIME NULL,
                    created_by VARCHAR(100),
                    product VARCHAR(100),
                    campaigns VARCHAR(100),
                    category VARCHAR(100),
                    sub_category VARCHAR(150),
                    sub_category_classification VARCHAR(150),
                    subject VARCHAR(500),
                    classifications VARCHAR(50),
                    ticket_owner VARCHAR(100),
                    category_subcategory VARCHAR(255),
                    full_category_hierarchy VARCHAR(300)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """))
            logging.info("Created temporary staging table.")

            # Load into staging in chunks
            logging.info(f"Pushing {len(df_clean)} records to staging in batches...")
            df_clean.to_sql(
                name='staging_tickets',
                con=conn,
                if_exists='append',
                index=False,
                chunksize=chunksize,
                method='multi'
            )

            # Atomic Upsert from Staging into Production
            logging.info("Executing atomic ON DUPLICATE KEY UPDATE...")
            upsert_query = text("""
                INSERT INTO support_tickets (
                    ticket_id, created_time, closed_time, created_by, product,
                    campaigns, category, sub_category, sub_category_classification,
                    subject, classifications, ticket_owner, category_subcategory,
                    full_category_hierarchy
                )
                SELECT 
                    ticket_id, created_time, closed_time, created_by, product,
                    campaigns, category, sub_category, sub_category_classification,
                    subject, classifications, ticket_owner, category_subcategory,
                    full_category_hierarchy
                FROM staging_tickets
                ON DUPLICATE KEY UPDATE
                    closed_time = VALUES(closed_time),
                    ticket_owner = VALUES(ticket_owner),
                    classifications = VALUES(classifications),
                    category = VALUES(category),
                    sub_category = VALUES(sub_category),
                    sub_category_classification = VALUES(sub_category_classification),
                    subject = VALUES(subject);
            """)
            conn.execute(upsert_query)
            
            # Clean up staging table
            conn.execute(text("DROP TABLE IF EXISTS staging_tickets;"))

        elapsed = (datetime.now() - start_time).total_seconds()
        logging.info(f"ETL completed successfully in {elapsed:.2f} seconds.")

    except Exception as e:
        logging.exception(f"Fatal error during ETL run: {str(e)}")
        raise

if __name__ == "__main__":
    # Point this to your target Excel file path
    RAW_EXCEL_PATH = "July, Aug, Sept 2026 Raw.xlsx"
    run_etl(RAW_EXCEL_PATH)