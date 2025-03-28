import sqlite3
import time
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Context manager for database connections with retry logic"""

    def __init__(self, db_path, retries=3, retry_delay=1):
        self.db_path = db_path
        self.retries = retries
        self.retry_delay = retry_delay
        self.conn = None

    def __enter__(self):
        for attempt in range(self.retries):
            try:
                self.conn = sqlite3.connect(self.db_path, timeout=20)
                cursor = self.conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=10000")
                cursor.execute("BEGIN IMMEDIATE")
                return self.conn
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < self.retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                raise
            except Exception as e:
                if self.conn:
                    self.conn.rollback()
                raise
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()


def store_patent_examples(examples, db_path="db/patents.db"):
    conn = None
    retries = 3
    retry_delay = 1  # seconds

    for attempt in range(retries):
        try:
            conn = sqlite3.connect(db_path, timeout=20)  # Increase timeout
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")  # Use WAL mode
            cursor.execute("PRAGMA busy_timeout=10000")  # Set busy timeout
            cursor.execute("BEGIN IMMEDIATE")  # Get immediate lock

            # Update table schema with new columns
            cursor.execute("""CREATE TABLE IF NOT EXISTS patent_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patent_number TEXT NOT NULL,
                example_name TEXT,
                example_content TEXT NOT NULL,
                why_unknown TEXT,
                tense_breakdown TEXT
            );""")

            for patent_number, examples in examples.items():
                cursor.execute(
                    "SELECT patent_number FROM patent_examples WHERE patent_number = ?",
                    (patent_number,),
                )
                if cursor.fetchone() is None:
                    for idx, example in enumerate(examples, 1):
                        if len(example["content"]) > 0:
                            content_list = example["content"].copy()
                            content_list.insert(0, example["title"] + ".")
                            full_content = "".join(list(set(content_list)))

                            # Get additional tense info if available
                            why_unknown = example.get("why_unknown", "")
                            tense_breakdown = example.get("tense_breakdown", "")

                            cursor.execute(
                                """
                                INSERT OR REPLACE INTO patent_examples 
                                (patent_number, example_name, example_content, why_unknown, tense_breakdown) 
                                VALUES (?, ?, ?, ?, ?)
                            """,
                                (
                                    patent_number,
                                    example["number"],
                                    full_content.replace("\n\n", ""),
                                    why_unknown,
                                    tense_breakdown,
                                ),
                            )

            conn.commit()
            break  # Success - exit retry loop

        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < retries - 1:
                if conn:
                    conn.close()
                time.sleep(retry_delay)
                continue
            raise
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()


def store_patent_statistics(stats, db_path="db/patents.db", year=None):
    try:
        logger.info(f"Storing statistics for {len(stats)} patents")
        if year:
            logger.info(f"Using year: {year}")

        # Create db directory if it doesn't exist
        if not os.path.exists(os.path.dirname(db_path)):
            os.makedirs(os.path.dirname(db_path))

        with DatabaseConnection(db_path) as conn:
            cursor = conn.cursor()

            # Check if table exists
            cursor.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='patent_statistics'"
            )
            table_exists = cursor.fetchone()[0] > 0
            logger.info(f"Patent statistics table exists: {table_exists}")

            # Add year column and mixed_tense_percentage to the schema
            cursor.execute("""CREATE TABLE IF NOT EXISTS patent_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patent_number TEXT NOT NULL UNIQUE,
                year INTEGER,
                prophetic INTEGER,
                nonprophetic INTEGER,
                unknown INTEGER,
                mixed_tense_percentage REAL
            );""")

            # Count rows before insertion
            cursor.execute("SELECT COUNT(*) FROM patent_statistics")
            before_count = cursor.fetchone()[0]
            logger.info(f"Patent statistics rows before insertion: {before_count}")

            inserted_count = 0
            for patent_number, stat in stats.items():
                if "past" in stat and "present" in stat and "unknown" in stat:
                    # Get mixed tense percentage if available
                    mixed_tense_pct = stat.get("mixed_tense_percentage", 0.0)

                    cursor.execute(
                        """INSERT OR REPLACE INTO patent_statistics 
                        (patent_number, year, prophetic, nonprophetic, unknown, mixed_tense_percentage) 
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            patent_number,
                            year,
                            stat["present"],
                            stat["past"],
                            stat["unknown"],
                            mixed_tense_pct,
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
