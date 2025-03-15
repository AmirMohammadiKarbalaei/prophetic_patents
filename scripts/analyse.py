from utilities.utils_clean import (
    download_patents_pto,
    unzip_files,
    extract_and_save_examples_in_db,
    validate_year,
    validate_default_kind,
)
import os
import argparse
## usage: python analyse.py --year 2015 --kind grant --path data
## usage: python analyse.py --year-range 2015 2017 --kind grant --path data


def validate_path(path):
    """Validate if the path exists or can be created."""
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Invalid path: {e}")


def process_year(year, kind, base_path):
    """Process a single year of patent data."""
    downloaded, download_path = download_patents_pto(year=year, default_kind=kind)
    if downloaded:
        unzip_path = os.path.join(base_path, f"patent_{kind}s_{year}")
        unzip_files(download_path, unzip_path)
        print(f"Patents for {year} downloaded and unzipped")
        return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Download and unzip patent XML files from USPTO"
    )
    parser.add_argument(
        "--kind",
        type=validate_default_kind,
        default="grant",
        help="application or grant",
    )
    year_group = parser.add_mutually_exclusive_group(required=True)
    year_group.add_argument(
        "--year",
        type=validate_year,
        help="Single year to analyse (1976-2025)",
    )
    year_group.add_argument(
        "--year-range",
        nargs=2,
        type=validate_year,
        metavar=("START_YEAR", "END_YEAR"),
        help="Year range to analyse (1976-2025)",
    )
    parser.add_argument(
        "--path",
        type=validate_path,
        default="data",
        help="Path to store downloaded files",
    )

    args = parser.parse_args()

    # Process single year or year range
    if args.year:
        process_year(args.year, args.kind, args.path)
        print(f"Download and unzipping complete for the year {args.year}")
    else:
        start_year, end_year = args.year_range
        if start_year <= end_year:
            for year in range(start_year, end_year + 1):
                process_year(year, args.kind, args.path)
            print("Download and unzipping complete for the year range")
        else:
            print(
                "Invalid year range: start year must be less than or equal to end year"
            )

    # Process extracted files
    if os.path.exists(args.path):
        files = os.listdir(args.path)
        for file in files:
            if not file.endswith(".zip"):
                file_path = os.path.join(args.path, file)
                extract_and_save_examples_in_db(file_path)


if __name__ == "__main__":
    main()
