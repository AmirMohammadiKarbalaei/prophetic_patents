from utilities.utils_clean import (
    download_patents_pto,
    unzip_files,
    validate_year,
    validate_kind,
)
import argparse
import os


def validate_path(path):
    """Validate if the path exists or can be created."""
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Invalid path: {e}")


def main():
    default_year = 2015
    default_kind = "grant"

    parser = argparse.ArgumentParser(
        description="Download and unzip patent XML files from USPTO"
    )
    parser.add_argument(
        "--kind",
        type=validate_kind,
        default=default_kind,
        help="application or grant",
    )
    parser.add_argument(
        "--year",
        type=validate_year,
        default=default_year,
        help="Year to analyse (1976-2025)",
    )
    parser.add_argument(
        "--path",
        type=validate_path,
        help="Path to store downloaded files",
    )

    args = parser.parse_args()

    if args.path:
        base_path = args.path
    else:
        base_path = "data"
    zip_dir = f"{base_path}/temp/zipped_{args.kind}_files_{args.year}"
    extract_dir = f"{base_path}/patent_{args.kind}_{args.year}"
    os.makedirs(zip_dir, exist_ok=True)
    os.makedirs(extract_dir, exist_ok=True)
    try:
        print(f"Downloading XML files from USPTO for {args.year}")
        download_success = download_patents_pto(
            year=args.year,
            kind=args.kind,
            download_path=zip_dir,
        )

        if not download_success:
            print("Download failed")
            return

        print("Download complete. Unzipping files...")

        unzip_success = unzip_files(
            zip_dir,
            extract_dir,
        )

        if not unzip_success:
            print("Unzip failed")
            return

        print("Unzip complete")
    except Exception as e:
        print(f"Error during download/unzip: {e}")
        return


if __name__ == "__main__":
    main()
