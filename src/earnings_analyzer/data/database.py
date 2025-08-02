import sqlite3
from sqlite3 import Error
import os
import logging
from pathlib import Path
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Determine the absolute path for the database file
# Prioritize EARNINGS_ANALYZER_DB environment variable
# Otherwise, default to ~/.earnings_analyzer/earnings_analyzer.db
if os.getenv("EARNINGS_ANALYZER_DB"):
    DATABASE_FILE = os.getenv("EARNINGS_ANALYZER_DB")
else:
    try:
        app_data_dir = Path.home() / ".earnings_analyzer"
        app_data_dir.mkdir(parents=True, exist_ok=True)
        DATABASE_FILE = str(app_data_dir / "earnings_analyzer.db")
    except PermissionError as e:
        logging.error(f"Permission denied creating database directory: {e}")
        # Fallback to current directory
        DATABASE_FILE = "earnings_analyzer.db"
        logging.warning(f"Using fallback database location: {DATABASE_FILE}")
    except OSError as e:
        logging.error(f"OS error creating database directory: {e}")
        DATABASE_FILE = "earnings_analyzer.db"
        logging.warning(f"Using fallback database location: {DATABASE_FILE}")

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
    FOREIGN KEY (ticker) REFERENCES companies (ticker),
    UNIQUE(ticker, quarter, year)
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

def _validate_column_name(column_name):
    """
    Validates column name to prevent SQL injection.
    
    Args:
        column_name (str): Column name to validate
        
    Returns:
        bool: True if column name is safe, False otherwise
    """
    # Allow only alphanumeric characters and underscores
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', column_name):
        return False
    
    # Check against SQL reserved words (basic list)
    reserved_words = {
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'TABLE', 'INDEX', 'WHERE', 'FROM', 'JOIN', 'UNION', 'ORDER', 'GROUP'
    }
    
    if column_name.upper() in reserved_words:
        return False
        
    return True

def create_connection(db_file):
    """Create a database connection to the SQLite database specified by db_file."""
    conn = None
    try:
        conn = sqlite3.connect(db_file, timeout=30.0)
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except Error as e:
        logging.error(f"Error connecting to database {db_file}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error connecting to database {db_file}: {e}")
    return conn

def create_table(conn, create_table_sql):
    """Create a table from the create_table_sql statement."""
    if not conn:
        logging.error("No database connection provided")
        return False
        
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
        conn.commit()
        return True
    except Error as e:
        logging.error(f"Error creating table: {e}")
        return False
    finally:
        if c:
            c.close()

def setup_database():
    """Create the database and all necessary tables if they don't exist, and add new columns if missing."""
    conn = create_connection(DATABASE_FILE)

    if conn is not None:
        try:
            # Create all tables
            success = True
            success &= create_table(conn, sql_create_companies_table)
            success &= create_table(conn, sql_create_earnings_calls_table)
            success &= create_table(conn, sql_create_sentiment_analysis_table)
            success &= create_table(conn, sql_create_stock_performance_table)

            if not success:
                logging.error("Failed to create one or more database tables")
                return False

            # Add new columns to sentiment_analysis table if they don't exist
            try:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(sentiment_analysis);")
                columns = [col[1] for col in cursor.fetchall()]
                
                columns_to_add = [
                    ('model_name', 'TEXT'),
                    ('qualitative_assessment', 'TEXT')
                ]
                
                for column_name, column_type in columns_to_add:
                    if column_name not in columns:
                        if _validate_column_name(column_name):
                            cursor.execute(f"ALTER TABLE sentiment_analysis ADD COLUMN {column_name} {column_type};")
                            logging.info(f"Added '{column_name}' column to sentiment_analysis table.")
                        else:
                            logging.error(f"Invalid column name: {column_name}")
                
                conn.commit()
                
            except Error as e:
                logging.error(f"Error altering sentiment_analysis table: {e}")
                return False
            finally:
                if cursor:
                    cursor.close()
                    
            return True
            
        except Exception as e:
            logging.error(f"Unexpected error during database setup: {e}")
            return False
        finally:
            conn.close()
    else:
        logging.error("Error! Cannot create the database connection.")
        return False

def insert_company(conn, company_data):
    """Insert a new company into the companies table."""
    if not conn:
        logging.error("No database connection provided")
        return None
        
    sql = ''' INSERT OR IGNORE INTO companies(ticker, company_name, sector)
              VALUES(?,?,?) '''
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(sql, company_data)
        conn.commit()
        return cursor.lastrowid
    except Error as e:
        logging.error(f"Error inserting company data: {e}")
        conn.rollback()
        return None
    except Exception as e:
        logging.error(f"Unexpected error inserting company data: {e}")
        conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()

def select_company_by_ticker(conn, ticker):
    """Query companies by ticker."""
    if not conn:
        logging.error("No database connection provided")
        return None
        
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM companies WHERE ticker=?", (ticker,))
        rows = cursor.fetchall()
        return rows
    except Error as e:
        logging.error(f"Error selecting company by ticker {ticker}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error selecting company by ticker {ticker}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def insert_earnings_call(conn, earnings_call_data):
    """Insert a new earnings call into the earnings_calls table."""
    if not conn:
        logging.error("No database connection provided")
        return None
        
    sql = ''' INSERT OR IGNORE INTO earnings_calls(ticker, call_date, quarter, year, transcript_text, filing_url)
              VALUES(?,?,?,?,?,?) '''
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(sql, earnings_call_data)
        conn.commit()
        
        # Check if we actually inserted (not ignored due to duplicate)
        if cursor.rowcount == 0:
            # Find the existing record
            cursor.execute("""SELECT id FROM earnings_calls 
                            WHERE ticker=? AND quarter=? AND year=?""", 
                          (earnings_call_data[0], earnings_call_data[2], earnings_call_data[3]))
            existing_row = cursor.fetchone()
            if existing_row:
                logging.info(f"Earnings call already exists for {earnings_call_data[0]} {earnings_call_data[2]} {earnings_call_data[3]}")
                return existing_row[0]
        
        return cursor.lastrowid
    except Error as e:
        logging.error(f"Error inserting earnings call data: {e}")
        conn.rollback()
        return None
    except Exception as e:
        logging.error(f"Unexpected error inserting earnings call data: {e}")
        conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()

def insert_sentiment_analysis(conn, sentiment_data):
    """Insert a new sentiment analysis result.
    sentiment_data should be a tuple: (earnings_call_id, overall_sentiment_score, confidence_level, key_themes, model_name, qualitative_assessment)
    """
    if not conn:
        logging.error("No database connection provided")
        return None
        
    sql = ''' INSERT INTO sentiment_analysis(earnings_call_id, overall_sentiment_score, confidence_level, key_themes, model_name, qualitative_assessment)
              VALUES(?,?,?,?,?,?) '''
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(sql, sentiment_data)
        conn.commit()
        return cursor.lastrowid
    except Error as e:
        logging.error(f"Error inserting sentiment analysis data: {e}")
        conn.rollback()
        return None
    except Exception as e:
        logging.error(f"Unexpected error inserting sentiment analysis data: {e}")
        conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()

def insert_stock_performance(conn, stock_performance_data):
    """Insert a new stock performance record."""
    if not conn:
        logging.error("No database connection provided")
        return None
        
    sql = ''' INSERT INTO stock_performance(earnings_call_id, price_at_call, price_1_week, price_1_month, price_3_month, performance_1_week, performance_1_month, performance_3_month)
              VALUES(?,?,?,?,?,?,?,?) '''
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(sql, stock_performance_data)
        conn.commit()
        return cursor.lastrowid
    except Error as e:
        logging.error(f"Error inserting stock performance data: {e}")
        conn.rollback()
        return None
    except Exception as e:
        logging.error(f"Unexpected error inserting stock performance data: {e}")
        conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()

def select_earnings_calls_by_ticker(conn, ticker):
    """Query earnings calls by ticker, returning call_date, quarter, year, and transcript_text."""
    if not conn:
        logging.error("No database connection provided")
        return None
        
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT
            ec.ticker,
            ec.call_date,
            ec.quarter,
            ec.year,
            ec.filing_url,
            ec.transcript_text,
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
        rows = cursor.fetchall()
        return rows
    except Error as e:
        logging.error(f"Error selecting earnings calls by ticker {ticker}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error selecting earnings calls by ticker {ticker}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def select_earnings_call_by_ticker_quarter_year(conn, ticker, quarter, year):
    """Query a specific earnings call by ticker, quarter, and year, joining all related tables."""
    if not conn:
        logging.error("No database connection provided")
        return None
        
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT
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
        row = cursor.fetchone()
        return row
    except Error as e:
        logging.error(f"Error selecting earnings call by ticker, quarter, and year for {ticker}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error selecting earnings call by ticker, quarter, and year for {ticker}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def select_all_earnings_calls(conn):
    """Query all earnings calls from the earnings_calls table, including transcript_text."""
    if not conn:
        logging.error("No database connection provided")
        return None
        
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT
            ec.ticker,
            ec.call_date,
            ec.quarter,
            ec.year,
            ec.filing_url,
            ec.transcript_text,
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
        rows = cursor.fetchall()
        return rows
    except Error as e:
        logging.error(f"Error selecting all earnings calls: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error selecting all earnings calls: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def close_connection(conn):
    """Safely close a database connection."""
    if conn:
        try:
            conn.close()
            logging.debug("Database connection closed successfully")
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")

def get_database_stats(conn):
    """Get basic statistics about the database contents."""
    if not conn:
        logging.error("No database connection provided")
        return None
        
    cursor = None
    try:
        cursor = conn.cursor()
        
        # Count companies
        cursor.execute("SELECT COUNT(*) FROM companies")
        company_count = cursor.fetchone()[0]
        
        # Count earnings calls
        cursor.execute("SELECT COUNT(*) FROM earnings_calls")
        calls_count = cursor.fetchone()[0]
        
        # Count sentiment analyses
        cursor.execute("SELECT COUNT(*) FROM sentiment_analysis")
        sentiment_count = cursor.fetchone()[0]
        
        # Count stock performance records
        cursor.execute("SELECT COUNT(*) FROM stock_performance")
        performance_count = cursor.fetchone()[0]
        
        return {
            'companies': company_count,
            'earnings_calls': calls_count,
            'sentiment_analyses': sentiment_count,
            'stock_performance_records': performance_count
        }
        
    except Error as e:
        logging.error(f"Error getting database statistics: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error getting database statistics: {e}")
        return None
    finally:
        if cursor:
            cursor.close()