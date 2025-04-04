import sqlite3
import time
import os
import logging
import random
from contextlib import contextmanager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConnection:
    def __init__(self, db_path, max_retries=5, initial_delay=1, max_delay=30):
        self.db_path = db_path
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.conn = None

    def __enter__(self):
        retry_count = 0
        last_error = None
        delay = self.initial_delay

        while retry_count < self.max_retries:
            try:
                # Add random jitter to avoid multiple processes retrying at exact same time
                jitter = random.uniform(0, 0.1 * delay)
                self.conn = sqlite3.connect(self.db_path, timeout=20)
                cursor = self.conn.cursor()

                # Database optimization settings
                cursor.execute(
                    "PRAGMA journal_mode=WAL"
                )  # Write-Ahead Logging for better concurrency
                cursor.execute(
                    "PRAGMA synchronous=NORMAL"
                )  # Better performance with slight durability trade-off
                cursor.execute(
                    "PRAGMA busy_timeout=30000"
                )  # Wait up to 30 seconds when database is locked
                cursor.execute(
                    "PRAGMA temp_store=MEMORY"
                )  # Store temp tables in memory
                cursor.execute("BEGIN IMMEDIATE")  # Get write lock immediately

                return self.conn

            except sqlite3.OperationalError as e:
                last_error = e
                if "database is locked" in str(e):
                    retry_count += 1
                    if retry_count < self.max_retries:
                        time.sleep(delay + jitter)
                        # Exponential backoff with max delay
                        delay = min(delay * 2, self.max_delay)
                        continue
                raise
            except Exception as e:
                if self.conn:
                    self.conn.rollback()
                raise

        raise sqlite3.OperationalError(
            f"Failed after {self.max_retries} retries. Last error: {last_error}"
        )

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            try:
                if exc_type is None:
                    self.conn.commit()
                else:
                    self.conn.rollback()
            finally:
                self.conn.close()


@contextmanager
def database_operation_with_retry(db_path, operation_name, max_retries=5):
    """Context manager for database operations with retry logic."""
    retry_count = 0
    delay = 1

    while True:
        try:
            with DatabaseConnection(db_path) as conn:
                yield conn
                break  # Success - exit the retry loop
        except sqlite3.OperationalError as e:
            retry_count += 1
            if retry_count >= max_retries or "database is locked" not in str(e):
                logger.error(
                    f"Failed {operation_name} after {retry_count} retries: {e}"
                )
                raise

            jitter = random.uniform(0, 0.1 * delay)
            wait_time = delay + jitter
            logger.warning(
                f"{operation_name} failed (attempt {retry_count}), retrying in {wait_time:.1f}s..."
            )
            time.sleep(wait_time)
            delay = min(delay * 2, 30)  # Exponential backoff up to 30 seconds


def store_patent_examples(examples, db_path="db/patents.db"):
    """Store patent examples with improved error handling and retry logic."""
    try:
        with database_operation_with_retry(db_path, "store_patent_examples") as conn:
            cursor = conn.cursor()

            cursor.execute("""CREATE TABLE IF NOT EXISTS patent_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patent_number TEXT NOT NULL,
                example_name TEXT,
                example_content TEXT NOT NULL,
                tense TEXT,
                past_percentage REAL,
                present_percentage REAL,
                unknown_percentage REAL,
                why_unknown TEXT,
                tense_breakdown TEXT
            );""")

            for patent_number, examples_list in examples.items():
                try:
                    cursor.execute(
                        "SELECT patent_number FROM patent_examples WHERE patent_number = ?",
                        (patent_number,),
                    )
                    if cursor.fetchone() is None and isinstance(examples_list, list):
                        for example in examples_list:
                            if not isinstance(example, dict):
                                continue

                            content = example.get("content", [])
                            title = example.get("title", "")

                            if not isinstance(content, list):
                                content = [str(content)]

                            content_list = content.copy()
                            if title:
                                content_list.insert(0, str(title) + ".")

                            full_content = "".join(str(item) for item in content_list)

                            cursor.execute(
                                """INSERT OR REPLACE INTO patent_examples 
                                (patent_number, example_name, example_content, tense, past_percentage,
                                present_percentage, unknown_percentage, why_unknown, tense_breakdown) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    patent_number,
                                    example.get("number", ""),
                                    full_content.replace("\n\n", ""),
                                    example.get("tense", ""),
                                    example.get("past_percentage", 0.0),
                                    example.get("present_percentage", 0.0),
                                    example.get("unknown_percentage", 0.0),
                                    example.get("why_unknown", ""),
                                    example.get("tense_breakdown", "")
                                    if example.get("tense") != "unknown"
                                    else "",
                                ),
                            )
                except Exception as e:
                    logger.error(f"Error processing patent {patent_number}: {str(e)}")
                    continue

    except Exception as e:
        logger.error(f"Error storing patent examples: {str(e)}")
        raise


def store_patent_statistics(stats, db_path="db/patents.db", year=None):
    """Store patent statistics with improved error handling and retry logic."""
    try:
        logger.info(f"Storing statistics for {len(stats)} patents")
        if year:
            logger.info(f"Using year: {year}")

        # Create db directory if it doesn't exist
        if not os.path.exists(os.path.dirname(db_path)):
            os.makedirs(os.path.dirname(db_path))

        with database_operation_with_retry(db_path, "store_patent_statistics") as conn:
            cursor = conn.cursor()

            # Modified schema with new binary columns
            cursor.execute("""CREATE TABLE IF NOT EXISTS patent_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patent_number TEXT NOT NULL UNIQUE,
                year INTEGER,
                prophetic INTEGER,
                nonprophetic INTEGER,
                unknown INTEGER,
                mixed_tense_percentage REAL,
                all_prophetic INTEGER DEFAULT 0,
                some_prophetic INTEGER DEFAULT 0,
                no_prophetic INTEGER DEFAULT 0
            );""")

            # Count rows before insertion
            cursor.execute("SELECT COUNT(*) FROM patent_statistics")
            before_count = cursor.fetchone()[0]
            logger.info(f"Patent statistics rows before insertion: {before_count}")

            inserted_count = 0
            for patent_number, stat in stats.items():
                if "past" in stat and "present" in stat and "unknown" in stat:
                    # Calculate prophetic indicators
                    total_examples = stat["past"] + stat["present"] + stat["unknown"]
                    all_prophetic = (
                        1
                        if total_examples > 0 and stat["present"] == total_examples
                        else 0
                    )
                    no_prophetic = (
                        1 if total_examples > 0 and stat["present"] == 0 else 0
                    )
                    some_prophetic = (
                        1
                        if total_examples > 0
                        and stat["present"] > 0
                        and not all_prophetic
                        else 0
                    )

                    mixed_tense_pct = stat.get("mixed_tense_percentage", 0.0)

                    cursor.execute(
                        """INSERT OR REPLACE INTO patent_statistics 
                        (patent_number, year, prophetic, nonprophetic, unknown, 
                        mixed_tense_percentage, all_prophetic, some_prophetic, no_prophetic) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            patent_number,
                            year,
                            stat["present"],
                            stat["past"],
                            stat["unknown"],
                            mixed_tense_pct,
                            all_prophetic,
                            some_prophetic,
                            no_prophetic,
                        ),
                    )
                    inserted_count += 1
                else:
                    logger.warning(
                        f"Warning: Invalid stat format for patent {patent_number}: {stat}"
                    )

            # Count rows after insertion
            cursor.execute("SELECT COUNT(*) FROM patent_statistics")
            after_count = cursor.fetchone()[0]
            logger.info(
                f"Patent statistics rows after insertion: {after_count} (inserted {inserted_count})"
            )
        return True
    except Exception as e:
        logger.error(f"Error storing patent statistics: {str(e)}")
        return False
