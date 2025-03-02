import argparse
import os
from test_dataset_utils import create_test_dataset_from_freilich


# use case: python test_dataset_creator.py --year 2015 --freilich-path Freilich.Data.Compressed.xlsb --xml-path patent_grants_2015
def validate_year(year):
    """Validate if the year is between 1976 and 2025."""
    try:
        year = int(year)
        if 1976 <= year <= 2025:
            return year
        raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError("Year must be between 1976 and 2025")


def validate_file_path(path):
    """Validate if the file exists."""
    if os.path.exists(path):
        return path
    raise argparse.ArgumentTypeError(f"File {path} does not exist")


def main():
    default_freilich_path = "Freilich.Data.Compressed.xlsb"
    default_xml_path = "patent_grants_2015"
    default_year = 2015

    # Set up argument parser
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

    args = parser.parse_args()

    # Validate file paths
    try:
        freilich_path = validate_file_path(args.freilich_path)
        xml_path = validate_file_path(args.xml_path)
    except argparse.ArgumentTypeError as e:
        print(f"Error: {e}")
        return

    print(f"Processing year: {args.year}")
    print(f"Using Freilich data from: {freilich_path}")
    print(f"Using XML files from: {xml_path}")

    test_dataset = create_test_dataset_from_freilich(
        year=args.year,
        freilich_data_path=freilich_path,
        path_to_all_xmls_for_chosen_year=xml_path,
    )

    print(f"Number of patents extracted: {len(test_dataset)}")
    print("Sample document numbers:", list(test_dataset.keys())[:5])


if __name__ == "__main__":
    main()
