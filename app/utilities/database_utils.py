import sqlite3


def store_patent_examples(examples, db_path="db/patents.db"):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")  # Start transaction
        cursor.execute("""CREATE TABLE IF NOT EXISTS patent_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patent_number TEXT NOT NULL,
            example_name TEXT,
            example_title TEXT,
            example_content TEXT NOT NULL
        );""")

        for patent_number, examples in examples.items():
            cursor.execute(
                "SELECT patent_number FROM patent_examples WHERE patent_number = ?",
                (patent_number,),
            )
            if cursor.fetchone() is None:
                for idx, example in enumerate(examples, 1):
                    if len(example["content"]) > 0:
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO patent_examples 
                            (patent_number, example_name, example_title, example_content) 
                            VALUES (?, ?, ?, ?)
                        """,
                            (
                                patent_number,
                                example["number"],
                                example["title"],
                                "".join(example["content"]),
                            ),
                        )

        conn.commit()  # Commit transaction
    except Exception as e:
        if conn:
            conn.rollback()  # Rollback on error
        print(f"Error storing data: {e}")
        raise
    finally:
        if conn:
            conn.close()


def store_patent_statistics(stats, db_path="db/patents.db"):
    conn = None
    try:
        print(f"Storing statistics for {len(stats)} patents")
        # Check if db file exists
        import os

        if not os.path.exists(os.path.dirname(db_path)):
            os.makedirs(os.path.dirname(db_path))

        # Print a sample of the stats data to verify structure
        if stats:
            sample_key = next(iter(stats.keys()))
            sample_data = stats[sample_key]
            print(f"Sample statistics data: {sample_key}: {sample_data}")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='patent_statistics'"
        )
        table_exists = cursor.fetchone()[0] > 0
        print(f"Patent statistics table exists: {table_exists}")

        cursor.execute("BEGIN TRANSACTION")
        cursor.execute("""CREATE TABLE IF NOT EXISTS patent_statistics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patent_number TEXT NOT NULL UNIQUE,
            prophetic INTEGER,
            nonprophetic INTEGER,
            unknown INTEGER);""")

        # Count rows before insertion
        cursor.execute("SELECT COUNT(*) FROM patent_statistics")
        before_count = cursor.fetchone()[0]
        print(f"Patent statistics rows before insertion: {before_count}")

        inserted_count = 0
        for patent_number, stat in stats.items():
            if "past" in stat and "present" in stat and "unknown" in stat:
                cursor.execute(
                    """INSERT OR REPLACE INTO patent_statistics 
                    (patent_number, prophetic, nonprophetic, unknown) 
                    VALUES (?, ?, ?, ?)""",
                    (patent_number, stat["past"], stat["present"], stat["unknown"]),
                )
                inserted_count += 1
            else:
                print(
                    f"Warning: Invalid stat format for patent {patent_number}: {stat}"
                )

        # Count rows after insertion
        cursor.execute("SELECT COUNT(*) FROM patent_statistics")
        after_count = cursor.fetchone()[0]
        print(
            f"Patent statistics rows after insertion: {after_count} (inserted {inserted_count})"
        )

        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error storing data: {e}")
        raise
    finally:
        if conn:
            conn.close()
