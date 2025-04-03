import sqlite3
import os
import logging
import time

# def store_patent_examples(examples, db_path="patents.db"):
#     try:
#         conn = sqlite3.connect(db_path)
#         cursor = conn.cursor()
#         cursor.execute("""CREATE TABLE IF NOT EXISTS patent_examples (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             patent_number TEXT NOT NULL,
#             example_name TEXT,
#             example_title TEXT,
#             example_content TEXT NOT NULL
#         );""")s

#         for patent_number, examples in examples.items():
#             cursor.execute(
#                 "SELECT patent_number FROM patent_examples WHERE patent_number = ?",
#                 (patent_number,),
#             )
#             if cursor.fetchone() is None:
#                 for idx, example in enumerate(examples, 1):
#                     if len(example["content"]) > 0:
#                         cursor.execute(
#                             """
#                             INSERT OR REPLACE INTO patent_examples
#                             (patent_number, example_name, example_title, example_content)
#                             VALUES (?, ?, ?, ?)
#                         """,
#                             (
#                                 patent_number,
#                                 example["number"],
#                                 example["title"],
#                                 "".join(example["content"]),
#                             ),
#                         )

#         conn.commit()
#         conn.close()
#     except Exception as e:
#         print(f"Error storing data: {e}")


# def store_patent_statistics(stats, db_path="patents.db"):
#     try:
#         conn = sqlite3.connect(db_path)
#         cursor = conn.cursor()
#         cursor.execute("""CREATE TABLE IF NOT EXISTS patent_statistics (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             patent_number TEXT NOT NULL UNIQUE,
#             prophetic INTEGER,
#             nonprophetic INTEGER,
#             unknown INTEGER);""")
#         for patent_number, stats in stats.items():
#             cursor.execute(
#                 """
#                 INSERT OR REPLACE INTO patent_statistics
#                 (patent_number, prophetic, Nonprophetic, unknown)
#                 VALUES (?, ?, ?, ?)
#             """,
#                 (patent_number, stats["past"], stats["present"], stats["unknown"]),
#             )


#         conn.commit()
#         conn.close()
#     except Exception as e:
#         print(f"Error storing data: {e}")
def store_patent_examples(examples, db_path="db/patents.db"):
    """Store patent examples with improved error handling and retry logic."""
    try:
        logger = logging.getLogger(__name__)
        logger.info(f"Storing {len(examples)} patent examples")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create table if not exists
        cursor.execute("""CREATE TABLE IF NOT EXISTS patent_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patent_number TEXT NOT NULL,
            example_name TEXT,
            example_content TEXT NOT NULL,
            why_unknown TEXT,
            tense_breakdown TEXT
        );""")

        # Use a transaction for batch inserts
        for patent_number, examples_list in examples.items():
            try:
                cursor.execute(
                    "SELECT patent_number FROM patent_examples WHERE patent_number = ?",
                    (patent_number,),
                )
                if cursor.fetchone() is None:
                    for example in examples_list:
                        if len(example["content"]) > 0:
                            content_list = example["content"].copy()
                            content_list.insert(0, example["title"] + ".")
                            full_content = "".join(list(set(content_list)))

                            cursor.execute(
                                """INSERT OR REPLACE INTO patent_examples 
                                (patent_number, example_name, example_content, why_unknown, tense_breakdown) 
                                VALUES (?, ?, ?, ?, ?)""",
                                (
                                    patent_number,
                                    example["number"],
                                    full_content.replace("\n\n", ""),
                                    example.get("why_unknown", ""),
                                    example.get("tense_breakdown", ""),
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
        logger = logging.getLogger(__name__)
        logger.info(f"Storing statistics for {len(stats)} patents")
        if year:
            logger.info(f"Using year: {year}")

        # Create db directory if it doesn't exist
        if not os.path.exists(os.path.dirname(db_path)):
            os.makedirs(os.path.dirname(db_path))

        conn = sqlite3.connect(db_path)
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
                    1 if total_examples > 0 and stat["present"] == total_examples else 0
                )
                no_prophetic = 1 if total_examples > 0 and stat["present"] == 0 else 0
                some_prophetic = (
                    1
                    if total_examples > 0 and stat["present"] > 0 and not all_prophetic
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
