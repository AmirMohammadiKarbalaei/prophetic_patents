import argparse
import os
import multiprocessing
from utilities.app_utils import (
    download_patents_pto,
    unzip_files,
    extract_and_save_examples_in_db,
    validate_year,
    validate_kind,
)
import pandas as pd
from sqlalchemy import create_engine, text

# # Process a single year
# python patent_cli.py --year 2020 --kind grant

# # Process a range of years
# python patent_cli.py --year-range 2018 2020 --kind grant

# # Download only
# python patent_cli.py --year 2020 --kind grant --download-only

# # Unzip only
# python patent_cli.py --year 2020 --kind grant --unzip-only

# # Process existing files
# python patent_cli.py --input-dir ./my_patents --process-only

# # Specify output directory and number of workers
# python patent_cli.py --year 2020 --output-dir ./patent_data --workers 6


def save_to_csv(output_dir, year=None):
    """Save database tables to CSV files."""
    engine = create_engine("sqlite:///patent_database.db")
    tables = ["patents", "claims", "descriptions"]

    csv_dir = os.path.join(output_dir, "csv_exports")
    os.makedirs(csv_dir, exist_ok=True)

    year_suffix = f"_{year}" if year else ""
    for table in tables:
        query = f"SELECT * FROM {table}"
        if year:
            query += f" WHERE year = {year}"
        df = pd.read_sql(query, engine)
        csv_path = os.path.join(csv_dir, f"{table}{year_suffix}.csv")
        df.to_csv(csv_path, index=False)


def process_year(year, kind, base_path, status_callback=None, stop_event=None):
    """Process a single year of patent data."""
    try:
        # Validate inputs
        year = validate_year(year)
        kind = validate_kind(kind)

        if status_callback:
            status_callback(f"\nProcessing year {year}")

        # Download patents
        downloaded, download_path = download_patents_pto(
            year=year,
            kind=kind,
            download_path=os.path.join(base_path, f"patent_{kind}_{year}_zip"),
            callback=status_callback,
            stop_event=stop_event,
        )

        if not downloaded:
            if status_callback:
                status_callback(f"Failed to download patents for {year}")
            return False

        # Unzip files
        unzip_path = os.path.join(base_path, f"patent_{kind}s_{year}")
        if not unzip_files(
            download_path, unzip_path, callback=status_callback, stop_event=stop_event
        ):
            return False

        # Process and analyze patents
        extract_and_save_examples_in_db(
            unzip_path,
            callback=status_callback,
            stop_event=stop_event,
            max_workers=4,
            year=year,
        )

        # Save to CSV after processing
        if status_callback:
            status_callback(f"Saving data to CSV files for year {year}")
        save_to_csv(base_path, year)

        if status_callback:
            status_callback(f"Processing complete for year {year}")
        return True

    except Exception as e:
        if status_callback:
            status_callback(f"Error processing year {year}: {str(e)}")
        return False


def print_status(message):
    """Print status messages to console."""
    print(message)


def main():
    parser = argparse.ArgumentParser(
        description="USPTO Patent Processor Command Line Tool"
    )

    # Main operation mode
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--year", type=int, help="Single year to process")
    group.add_argument(
        "--year-range",
        type=int,
        nargs=2,
        metavar=("START", "END"),
        help="Year range to process (e.g., 2010 2015)",
    )
    group.add_argument(
        "--input-dir", help="Process existing patent files from directory"
    )

    # Optional arguments
    parser.add_argument(
        "--kind",
        choices=["application", "grant"],
        default="grant",
        help="Patent type (default: grant)",
    )
    parser.add_argument(
        "--output-dir",
        default="./data",
        help="Output directory for downloads and processing (default: ./data)",
    )
    parser.add_argument(
        "--workers", type=int, default=4, help="Number of worker processes (default: 4)"
    )

    # Operation flags
    parser.add_argument(
        "--download-only", action="store_true", help="Only download patent files"
    )
    parser.add_argument(
        "--unzip-only", action="store_true", help="Only unzip downloaded files"
    )
    parser.add_argument(
        "--process-only", action="store_true", help="Only process/analyze patents"
    )

    args = parser.parse_args()

    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)

    # Initialize stop event
    stop_event = multiprocessing.Event()

    try:
        # Determine years to process
        years_to_process = []
        if args.year:
            years_to_process = [args.year]
        elif args.year_range:
            start, end = args.year_range
            if start > end:
                print("Error: Start year must be less than or equal to end year")
                return
            years_to_process = range(start, end + 1)

        # Process existing directory
        if args.input_dir:
            if not os.path.exists(args.input_dir):
                print(f"Error: Input directory {args.input_dir} does not exist")
                return

            print(f"Processing files from {args.input_dir}")
            extract_and_save_examples_in_db(
                args.input_dir,
                callback=print_status,
                stop_event=stop_event,
                max_workers=args.workers,
            )
            print("Saving all data to CSV files")
            save_to_csv(args.output_dir)
            return

        # Process years
        for year in years_to_process:
            if args.download_only:
                # Download only
                downloaded, download_path = download_patents_pto(
                    year=year,
                    kind=args.kind,
                    download_path=os.path.join(
                        args.output_dir, f"patent_{args.kind}_{year}_zip"
                    ),
                    callback=print_status,
                    stop_event=stop_event,
                )
                if not downloaded:
                    print(f"Failed to download patents for {year}")
                    continue

            elif args.unzip_only:
                # Unzip only
                download_path = os.path.join(
                    args.output_dir, f"patent_{args.kind}_{year}_zip"
                )
                unzip_path = os.path.join(
                    args.output_dir, f"patent_{args.kind}s_{year}"
                )
                if not unzip_files(
                    download_path,
                    unzip_path,
                    callback=print_status,
                    stop_event=stop_event,
                ):
                    print(f"Failed to unzip patents for {year}")
                    continue

            elif args.process_only:
                # Process only
                input_path = os.path.join(
                    args.output_dir, f"patent_{args.kind}s_{year}"
                )
                if not os.path.exists(input_path):
                    print(f"Error: Input directory {input_path} does not exist")
                    continue
                extract_and_save_examples_in_db(
                    input_path,
                    callback=print_status,
                    stop_event=stop_event,
                    max_workers=args.workers,
                    year=year,
                )

            else:
                # Full process
                process_year(year, args.kind, args.output_dir, print_status, stop_event)

    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
        stop_event.set()
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        # Cleanup
        if hasattr(multiprocessing, "get_context"):
            mp_context = multiprocessing.get_context("spawn")
            if hasattr(mp_context, "_pool"):
                mp_context._pool.terminate()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
