import argparse
import os
from utilities.test_dataset_utils import create_test_dataset_from_freilich
from utilities.utils_clean import download_patents_pto, unzip_files, validate_year
# python test_dataset_creator.py --year 2015 --freilich-path Freilich.Data.Compressed.xlsb --download


def validate_file_path(path):
    """Validate if the file exists."""
    if os.path.exists(path):
        return path
    raise argparse.ArgumentTypeError(f"File {path} does not exist")


def main():
    default_freilich_path = "Freilich.Data.Compressed.xlsb"
    default_xml_path = "patent_grants_2015"
    default_year = 2015

    parser = argparse.ArgumentParser(
        description="Create test dataset from Freilich data"
    )
    parser.add_argument(
        "--year",
        type=validate_year,
        default=default_year,
        help="Year to analyse (1976-2025)",
    )
    parser.add_argument(
        "--freilich-path",
        type=str,
        default=default_freilich_path,
        help="Path to Freilich dataset",
    )
    parser.add_argument(
        "--xml-path",
        type=str,
        default=default_xml_path,
        help="Directory containing XML files for the chosen year",
    )
    parser.add_argument(
        "--download",
        action="store_true",  # Changed from type=bool
        help="Download XML files from USPTO",
    )

    args = parser.parse_args()

    if not args.xml_path:
        args.xml_path = "temp/data"

    if args.download:
        try:
            print(f"Downloading XML files from USPTO for the year {args.year}")
            download_success = download_patents_pto(
                year=args.year,
                kind="grant",
                download_path=f"zipped_files_{args.year}",
            )

            if not download_success:
                print("Download failed")
                return

            print("Download complete. Unzipping files...")
            # Wait for unzip to complete and show progress
            unzip_success = unzip_files(
                f"zipped_files_{args.year}", f"patent_grants_{args.year}"
            )

            if not unzip_success:
                print("Unzip failed")
                return

            print("Unzip complete")
            args.xml_path = f"patent_grants_{args.year}"
        except Exception as e:
            print(f"Error during download/unzip: {e}")
            return

    try:
        freilich_path = validate_file_path(args.freilich_path)
        xml_path = validate_file_path(args.xml_path)
    except argparse.ArgumentTypeError as e:
        print(f"Error: {e}")
        return

    print(f"Processing year: {args.year}")
    print(f"Using Freilich data from: {freilich_path}")
    print(f"Using XML files from: {xml_path}")

    try:
        test_dataset = create_test_dataset_from_freilich(
            year=args.year,
            freilich_data_path=freilich_path,
            path_to_all_xmls_for_chosen_year=xml_path,
        )
        print(f"Number of patents extracted: {len(test_dataset)}")
        print("Sample document numbers:", list(test_dataset.keys())[:5])
    except Exception as e:
        print(f"Error creating test dataset: {e}")


if __name__ == "__main__":
    main()
