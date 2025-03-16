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
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")  # Start transaction
        cursor.execute("""CREATE TABLE IF NOT EXISTS patent_statistics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patent_number TEXT NOT NULL UNIQUE,
            prophetic INTEGER,
            nonprophetic INTEGER,
            unknown INTEGER);""")

        for patent_number, stats in stats.items():
            cursor.execute(
                """
                INSERT OR REPLACE INTO patent_statistics 
                (patent_number, prophetic, nonprophetic, unknown) 
                VALUES (?, ?, ?, ?)
            """,
                (patent_number, stats["past"], stats["present"], stats["unknown"]),
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
