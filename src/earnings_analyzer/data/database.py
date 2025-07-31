import sqlite3
from sqlite3 import Error
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

import os
from pathlib import Path

# Determine the absolute path for the database file
# Prioritize EARNINGS_ANALYZER_DB environment variable
# Otherwise, default to ~/.earnings_analyzer/earnings_analyzer.db
if os.getenv("EARNINGS_ANALYZER_DB"):
    DATABASE_FILE = os.getenv("EARNINGS_ANALYZER_DB")
else:
    app_data_dir = Path.home() / ".earnings_analyzer"
    app_data_dir.mkdir(parents=True, exist_ok=True)
    DATABASE_FILE = str(app_data_dir / "earnings_analyzer.db")

sql_create_companies_table = """
CREATE TABLE IF NOT EXISTS companies (
    ticker TEXT PRIMARY KEY,
    company_name TEXT,
    sector TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

sql_create_earnings_calls_table = """
CREATE TABLE IF NOT EXISTS earnings_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    call_date DATE,
    quarter TEXT,
    year INTEGER,
    transcript_text TEXT,
    filing_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticker) REFERENCES companies (ticker)
);
"""

sql_create_sentiment_analysis_table = """
CREATE TABLE IF NOT EXISTS sentiment_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    earnings_call_id INTEGER,
    overall_sentiment_score REAL,
    confidence_level REAL,
    key_themes TEXT,
    model_name TEXT,
    qualitative_assessment TEXT,
    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (earnings_call_id) REFERENCES earnings_calls (id)
);
"""

sql_create_stock_performance_table = """
CREATE TABLE IF NOT EXISTS stock_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    earnings_call_id INTEGER,
    price_at_call REAL,
    price_1_week REAL,
    price_1_month REAL,
    price_3_month REAL,
    performance_1_week REAL,
    performance_1_month REAL,
    performance_3_month REAL,
    FOREIGN KEY (earnings_call_id) REFERENCES earnings_calls (id)
);
"""

def create_connection(db_file):
    """Create a database connection to the SQLite database specified by db_file."""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        logging.error(f"Error connecting to database {db_file}: {e}")
    return conn

def create_table(conn, create_table_sql):
    """Create a table from the create_table_sql statement."""
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except Error as e:
        logging.error(f"Error creating table: {e}")

def setup_database():
    """Create the database and all necessary tables if they don't exist, and add new columns if missing."""
    conn = create_connection(DATABASE_FILE)

    if conn is not None:
        create_table(conn, sql_create_companies_table)
        create_table(conn, sql_create_earnings_calls_table)
        create_table(conn, sql_create_sentiment_analysis_table)
        create_table(conn, sql_create_stock_performance_table)

        # Add new columns to sentiment_analysis table if they don't exist
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sentiment_analysis);")
            columns = [col[1] for col in cursor.fetchall()]
            if 'model_name' not in columns:
                cursor.execute("ALTER TABLE sentiment_analysis ADD COLUMN model_name TEXT;")
                logging.info("Added 'model_name' column to sentiment_analysis table.")
            if 'qualitative_assessment' not in columns:
                cursor.execute("ALTER TABLE sentiment_analysis ADD COLUMN qualitative_assessment TEXT;")
                logging.info("Added 'qualitative_assessment' column to sentiment_analysis table.")
            conn.commit()
        except Error as e:
            logging.error(f"Error altering sentiment_analysis table: {e}")

        conn.close()
    else:
        logging.error("Error! cannot create the database connection.")

def insert_company(conn, company_data):
    """Insert a new company into the companies table."""
    sql = ''' INSERT OR IGNORE INTO companies(ticker, company_name, sector)
              VALUES(?,?,?) '''
    try:
        cur = conn.cursor()
        cur.execute(sql, company_data)
        conn.commit()
        return cur.lastrowid
    except Error as e:
        logging.error(f"Error inserting company data: {e}")
        return None

def select_company_by_ticker(conn, ticker):
    """Query companies by ticker."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM companies WHERE ticker=?", (ticker,))
        rows = cur.fetchall()
        return rows
    except Error as e:
        logging.error(f"Error selecting company by ticker {ticker}: {e}")
        return None

def insert_earnings_call(conn, earnings_call_data):
    """Insert a new earnings call into the earnings_calls table."""
    sql = ''' INSERT INTO earnings_calls(ticker, call_date, quarter, year, transcript_text, filing_url)
              VALUES(?,?,?,?,?,?) '''
    try:
        cur = conn.cursor()
        cur.execute(sql, earnings_call_data)
        conn.commit()
        return cur.lastrowid
    except Error as e:
        logging.error(f"Error inserting earnings call data: {e}")
        return None

def insert_sentiment_analysis(conn, sentiment_data):
    """Insert a new sentiment analysis result.
    sentiment_data should be a tuple: (earnings_call_id, overall_sentiment_score, confidence_level, key_themes, model_name, qualitative_assessment)
    """
    sql = ''' INSERT INTO sentiment_analysis(earnings_call_id, overall_sentiment_score, confidence_level, key_themes, model_name, qualitative_assessment)
              VALUES(?,?,?,?,?,?) '''
    try:
        cur = conn.cursor()
        cur.execute(sql, sentiment_data)
        conn.commit()
        return cur.lastrowid
    except Error as e:
        logging.error(f"Error inserting sentiment analysis data: {e}")
        return None

def insert_stock_performance(conn, stock_performance_data):
    """Insert a new stock performance record."""
    sql = ''' INSERT INTO stock_performance(earnings_call_id, price_at_call, price_1_week, price_1_month, price_3_month, performance_1_week, performance_1_month, performance_3_month)
              VALUES(?,?,?,?,?,?,?,?) '''
    try:
        cur = conn.cursor()
        cur.execute(sql, stock_performance_data)
        conn.commit()
        return cur.lastrowid
    except Error as e:
        logging.error(f"Error inserting stock performance data: {e}")
        return None

def select_earnings_calls_by_ticker(conn, ticker):
    """Query earnings calls by ticker, returning call_date, quarter, and year."""
    try:
        cur = conn.cursor()
        cur.execute("""SELECT
            ec.ticker,
            ec.call_date,
            ec.quarter,
            ec.year,
            ec.filing_url,
            sa.overall_sentiment_score,
            sa.confidence_level,
            sa.model_name,
            sa.qualitative_assessment,
            sa.key_themes
        FROM
            earnings_calls ec
        JOIN
            sentiment_analysis sa ON ec.id = sa.earnings_call_id
        WHERE
            ec.ticker = ?
        ORDER BY
            ec.call_date DESC""", (ticker,))
        rows = cur.fetchall()
        return rows
    except Error as e:
        logging.error(f"Error selecting earnings calls by ticker {ticker}: {e}")
        return None

def select_earnings_call_by_ticker_quarter_year(conn, ticker, quarter, year):
    """Query a specific earnings call by ticker, quarter, and year, joining all related tables."""
    try:
        cur = conn.cursor()
        cur.execute("""SELECT
            c.ticker, c.company_name, c.sector,
            ec.call_date, ec.quarter, ec.year, ec.filing_url,
            sa.overall_sentiment_score, sa.confidence_level, sa.key_themes, sa.model_name, sa.qualitative_assessment,
            sp.price_at_call, sp.price_1_week, sp.price_1_month, sp.price_3_month,
            sp.performance_1_week, sp.performance_1_month, sp.performance_3_month
        FROM companies c
        JOIN earnings_calls ec ON c.ticker = ec.ticker
        LEFT JOIN sentiment_analysis sa ON ec.id = sa.earnings_call_id
        LEFT JOIN stock_performance sp ON ec.id = sp.earnings_call_id
        WHERE c.ticker = ? AND ec.quarter = ? AND ec.year = ?
        """, (ticker, quarter, year))
        row = cur.fetchone()
        return row
    except Error as e:
        logging.error(f"Error selecting earnings call by ticker, quarter, and year for {ticker}: {e}")
        return None

def select_all_earnings_calls(conn):
    """Query all earnings calls from the earnings_calls table."""
    try:
        cur = conn.cursor()
        cur.execute("""SELECT
            ec.ticker,
            ec.call_date,
            ec.quarter,
            ec.year,
            ec.filing_url,
            sa.overall_sentiment_score,
            sa.confidence_level,
            sa.model_name,
            sa.qualitative_assessment,
            sa.key_themes
        FROM
            earnings_calls ec
        JOIN
            sentiment_analysis sa ON ec.id = sa.earnings_call_id
        ORDER BY
            ec.call_date DESC""")
        rows = cur.fetchall()
        return rows
    except Error as e:
        logging.error(f"Error selecting all earnings calls: {e}")
        return None

