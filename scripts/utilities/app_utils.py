import requests
import os
import zipfile
from lxml import etree
from tqdm import tqdm
import re
from .nlp_processing import dic_to_dic_w_tense_test
from .database_utils import store_patent_examples, store_patent_statistics
from .utils_clean import (
    remove_duplicate_docs,
)
import argparse
import time
import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import aiofiles
from .patent_processor import PatentProcessor
import multiprocessing  # Add this import


# Add PoolManager class
class PoolManager:
    _pool = None

    @classmethod
    def get_pool(cls, max_workers=None):
        if cls._pool is None:
            cls._pool = ProcessPoolExecutor(max_workers=max_workers)
        return cls._pool

    @classmethod
    def shutdown(cls):
        if cls._pool:
            cls._pool.shutdown()
            cls._pool = None


# Custom tqdm class that reports progress to a callback function
class TqdmCallback(tqdm):
    def __init__(self, *args, **kwargs):
        # Extract callback before passing to parent
        self.callback = kwargs.pop("callback", None)
        self.last_update_time = time.time()
        self.update_interval = 0.5  # Update GUI every 0.5 seconds to avoid flooding
        super().__init__(*args, **kwargs)

    def display(self, msg=None, pos=None):
        # Call the parent class display method
        super().display(msg, pos)

        # Only send updates to GUI at a reasonable interval
        current_time = time.time()
        if (
            self.callback
            and current_time - self.last_update_time >= self.update_interval
        ):
            progress_msg = f"Progress: {self.n}/{self.total} {self.desc} [{int(self.n / self.total * 100)}%]"
            self.callback(progress_msg)
            self.last_update_time = current_time


def validate_kind(value, callback=None):
    """Validate if the kind is either 'application' or 'grant'."""
    try:
        if value not in ["application", "grant"]:
            if callback:
                callback(
                    f"Invalid kind value: {value}. Must be 'application' or 'grant'"
                )
            raise argparse.ArgumentTypeError(
                "Kind must be either 'application' or 'grant'"
            )
        if callback:
            callback(f"Valid kind selected: {value}")
        return value
    except Exception as e:
        if callback:
            callback(f"Validation error: {str(e)}")
        raise


def validate_year(year, callback=None):
    """Validate if the year is between 1976 and 2025."""
    try:
        year = int(year)
        if 1976 <= year <= 2025:
            if callback:
                callback(f"Valid year: {year}")
            return year
        if callback:
            callback(f"Invalid year: {year}. Must be between 1976 and 2025")
        raise ValueError
    except ValueError:
        if callback:
            callback(f"Invalid year format or value: {year}")
        raise argparse.ArgumentTypeError("Year must be between 1976 and 2025")


def get_latest_versions(urls, kind="g"):
    """
    Function to extract the latest versions of files based on a regex pattern.

    Args:
    - urls (dict): A dictionary where keys are years and values are lists of filenames.

    Returns:
    - latest_files (dict): A dictionary where keys are years and values are lists of the latest versions of the files for that year.
    """
    # Initialize the result dictionary to store the latest versions for each year
    latest_files = {}

    if kind == "g":
        pattern = re.compile(r"(ipg\d{6})(?:_r(\d+))?\.zip")
    elif kind == "a":
        pattern = re.compile(r"(ipa\d{6})(?:_r(\d+))?\.zip")

    # Process each year in the input dictionary

    latest_versions = {}  # Holds the latest version of files for the current year
    for file in urls:
        match = pattern.match(file)
        if match:
            base_name, revision = match.groups()
            revision = int(revision) if revision else 0  # Default to 0 if no revision

            # Extract the current highest revision number for the base_name
            current_revision_match = re.search(
                r"_r(\d+)", latest_versions.get(base_name, "")
            )
            current_revision = (
                int(current_revision_match.group(1)) if current_revision_match else 0
            )

            # Update if the new file has a higher revision
            if base_name not in latest_versions or revision > current_revision:
                latest_versions[base_name] = file

    # Get the final list of unique latest versions sorted by file name
    latest_files = sorted(latest_versions.values())

    return latest_files


def download_patents_pto(
    year, kind="application", download_path=None, callback=None, stop_event=None
):
    """Download patent files with progress updates."""
    try:
        if download_path is None:
            download_path = f"./data/patent_{kind}_{year}_zip"
        # if callback:
        #     callback(f"Starting download for year {year}...")

        url = f"https://bulkdata.uspto.gov/data/patent/{kind}/redbook/fulltext/{year}/"
        if callback:
            callback("Connecting to USPTO server...")

        rp = requests.get(url, timeout=10)
        root = etree.fromstring(rp.text.encode(), etree.XMLParser(recover=True))
        href_values = root.findall(".//a[@href]")
        urls = [
            href.get("href")
            for href in href_values
            if href.get("href").endswith(".zip")
        ]

        if callback:
            callback(f"Found {len(urls)} zip files for {year}")

        url_no_dup = get_latest_versions(urls, kind[0])
        # if callback:
        #     callback(f"Downloading {len(url_no_dup)} unique patent files...")

        download_files(url, download_path, url_no_dup, callback, stop_event)
        return True, download_path

    except requests.exceptions.RequestException as e:
        if callback:
            callback(f"Error during download: {e}")
        return False, ""


def download_files(url, download_path, files, callback=None, stop_event=None):
    """Download files with progress updates."""
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    for index, file_name in enumerate(files):
        if stop_event and stop_event.is_set():
            if callback:
                callback("Download stopped by user.")
            break

        if callback:
            callback(f"Downloading file {index + 1} of {len(files)}: {file_name}")

        url_ = url + file_name
        zip_file_path = os.path.join(download_path, file_name)

        response = requests.get(url_, stream=True, timeout=10)
        with open(zip_file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)


def unzip_files(download_path, unzip_path, callback=None, stop_event=None):
    """Unzip files with progress updates."""
    if not os.path.exists(unzip_path):
        os.makedirs(unzip_path)
    try:
        files = [f for f in os.listdir(download_path) if f.endswith(".zip")]
        if callback:
            callback(f"Found {len(files)} zip files to extract")

        for file_name in files:
            if stop_event and stop_event.is_set():
                if callback:
                    callback("Unzip process stopped by user.")
                return False

            if callback:
                callback(f"Extracting {file_name}...")

            zip_file_path = os.path.join(download_path, file_name)
            with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                zip_ref.extractall(unzip_path)

        if callback:
            callback(f"Finished extracting all files to {unzip_path}")
        return True
    except Exception as e:
        if callback:
            callback(f"Error during unzip: {e}")
        return False


def process_xml_chunk(chunk):
    """Process a chunk of XML in a separate process."""
    try:
        root = etree.fromstring(chunk.encode(), etree.XMLParser(recover=True))
        if root is not None:
            return chunk
    except Exception:
        pass
    return None


async def process_xml_in_executor(executor, chunk):
    """Run XML processing in process pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, process_xml_chunk, chunk)


async def process_file_async(file_info, folder_path, callback=None, stop_event=None):
    """Process a single XML file asynchronously."""
    i, file = file_info
    file_path = os.path.join(folder_path, file)
    loop = asyncio.get_running_loop()

    # Check stop event
    if stop_event and stop_event.is_set():
        if callback:
            callback("Operation stopped by user")
        return file, 0, []

    if callback:
        callback(f"Processing file {i + 1}: {file}")

    try:
        # Create process pool for CPU-intensive work
        process_pool = ProcessPoolExecutor(max_workers=1)
        thread_pool = ThreadPoolExecutor(max_workers=2)

        # Read file in chunks asynchronously
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()

        # Check stop event after file read
        if stop_event and stop_event.is_set():
            if callback:
                callback("Operation stopped by user")
            return file, 0, []

        if '<?xml version="1.0" encoding="UTF-8"?>' not in content:
            if callback:
                callback(f"Warning: Invalid XML structure in {file}")
            return file, 0, []

        # Split and process parts concurrently
        parts = content.split('<?xml version="1.0" encoding="UTF-8"?>')
        valid_parts = []

        # Process XML chunks in parallel
        tasks = []
        for part in parts:
            if stop_event and stop_event.is_set():
                break
            if part.strip():
                task = process_xml_in_executor(process_pool, part)
                tasks.append(task)

        if stop_event and stop_event.is_set():
            if callback:
                callback("Operation stopped by user")
            return file, 0, []

        # Gather results
        results = await asyncio.gather(*tasks)
        valid_parts = [r for r in results if r is not None]

        # Close process pool
        process_pool.shutdown()

        if not valid_parts:
            if callback:
                callback(f"No valid XML parts found in {file}")
            return file, 0, []

        # Remove duplicates asynchronously
        xml_no_dup = await loop.run_in_executor(
            thread_pool, remove_duplicate_docs, valid_parts
        )

        current_file_patents = len(xml_no_dup)

        # Clean up thread pool
        thread_pool.shutdown()

        return file, current_file_patents, xml_no_dup

    except Exception as e:
        if callback:
            callback(f"Error processing {file}: {str(e)}")
        return file, 0, []


async def process_files_parallel(
    folder_path, callback=None, max_workers=4, year=None, stop_event=None
):
    """Process multiple XML files using concurrent pipelines."""
    start_time = time.time()

    # Initialize
    file_names = [f for f in os.listdir(folder_path) if f.endswith(".xml")]
    processor = PatentProcessor(max_workers=4)
    grand_total = 0

    if callback:
        callback(
            f"\nStarting parallel processing with {max_workers} concurrent pipelines"
        )
        callback(f"Found {len(file_names)} files to process")

    # Process files in batches of max_workers
    for i in range(0, len(file_names), max_workers):
        # Check stop event at start of each batch
        if stop_event and stop_event.is_set():
            if callback:
                callback("Operation stopped by user")
            break

        batch = file_names[i : i + max_workers]
        current_tasks = []

        # Create concurrent pipelines for each file in batch
        for j, file in enumerate(batch):
            pipeline = create_processing_pipeline(
                (i + j, file), folder_path, processor, callback, year, stop_event
            )
            current_tasks.append(pipeline)

        # Execute all pipelines concurrently
        batch_results = await asyncio.gather(*current_tasks)

        # Aggregate results
        for patents_found in batch_results:
            if patents_found and patents_found > 0:
                grand_total += patents_found
                if callback:
                    callback(f"Current total patents with examples: {grand_total}")

        # Allow other operations
        await asyncio.sleep(0)

    # Calculate and display total time
    end_time = time.time()
    elapsed_time = end_time - start_time
    hours = int(elapsed_time // 3600)
    minutes = int((elapsed_time % 3600) // 60)
    seconds = int(elapsed_time % 60)

    if callback:
        if stop_event and stop_event.is_set():
            callback("\nProcessing stopped by user")
        else:
            callback(f"\nProcessing complete!")
        callback(f"Total patents with examples found: {grand_total}")
        callback(f"Total time taken: {hours}h {minutes}m {seconds}s")

    return grand_total, []


async def create_processing_pipeline(
    file_info, folder_path, processor, callback, year=None, stop_event=None
):
    """Create a complete processing pipeline for a single file."""
    try:
        # Check stop event at start
        if stop_event and stop_event.is_set():
            return 0

        # Stage 1: Extract patents from XML
        file_result = await process_file_async(
            file_info, folder_path, callback, stop_event
        )
        if not isinstance(file_result, tuple) or not file_result[2]:
            return 0

        # Check stop event after extraction
        if stop_event and stop_event.is_set():
            return 0

        file_name, count, xml_parts = file_result
        if callback:
            callback(f"\nProcessing {count} patents from {file_name}")

        # Extract year from filename if not provided
        file_year = year
        if not file_year:
            if file_name.startswith("ipg"):
                year_match = re.match(r"ipg(\d{2})\d{4}\.xml", file_name)
            elif file_name.startswith("ipa"):
                year_match = re.match(r"ipa(\d{2})\d{4}\.xml", file_name)
            if year_match:
                two_digit_year = int(year_match.group(1))
                file_year = (
                    2000 + two_digit_year
                    if two_digit_year < 50
                    else 1900 + two_digit_year
                )

        # Check stop event before processing
        if stop_event and stop_event.is_set():
            return 0

        # Stage 2: Process patents
        doc_w_exp = await processor.process_batch(xml_parts, callback, stop_event)
        if not doc_w_exp:
            return 0

        # Check stop event before classification
        if stop_event and stop_event.is_set():
            return 0

        # Stage 3: Classify and store results
        classification_workers = min(len(doc_w_exp), max(2, processor.max_workers * 2))
        with ThreadPoolExecutor(max_workers=classification_workers) as executor:
            loop = asyncio.get_running_loop()

            # Classify examples
            with_tense = await loop.run_in_executor(
                executor, dic_to_dic_w_tense_test, doc_w_exp
            )

            # Check stop event before storage
            if stop_event and stop_event.is_set():
                return 0

            # Store results
            with ThreadPoolExecutor(
                max_workers=processor.max_workers
            ) as storage_executor:
                await asyncio.gather(
                    loop.run_in_executor(
                        storage_executor, store_patent_examples, doc_w_exp
                    ),
                    loop.run_in_executor(
                        storage_executor,
                        lambda: store_patent_statistics(with_tense, year=file_year),
                    ),
                )

            if callback:
                callback(
                    f"Saved {len(doc_w_exp)} patents with examples into db from {file_name}"
                )

            return len(doc_w_exp)

    except Exception as e:
        if callback:
            callback(f"Error in pipeline for {file_info[1]}: {str(e)}")
        return 0


async def process_batch(batch, callback=None):
    """Process a batch of patents asynchronously."""
    processor = PatentProcessor(max_workers=2)
    doc_w_exp = await processor.process_batch(batch, callback)
    return doc_w_exp


def extract_and_save_examples_in_db(
    folder_path, callback=None, stop_event=None, max_workers=4, year=None
):
    """Extract and save examples with progress updates."""
    if callback:
        callback("Starting example extraction process...")
        if year:
            callback(f"Using year {year} from user input")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Handle stop_event being a tuple of events
        if isinstance(stop_event, tuple):
            thread_event, mp_event = stop_event
            stop_event = mp_event  # Use the MP event for processing
        elif stop_event is None:
            stop_event = multiprocessing.Event()

        # Check if the event is already set before starting
        if stop_event.is_set():
            if callback:
                callback("Operation stopped by user")
            return

        total_num_of_patents, _ = loop.run_until_complete(
            process_files_parallel(
                folder_path,
                callback,
                max_workers,
                year,
                stop_event,
            )
        )

        if callback:
            if stop_event.is_set():
                callback("Processing stopped by user")
            else:
                callback(
                    f"Processing complete. Total patents processed: {total_num_of_patents}"
                )

    except Exception as e:
        if callback:
            callback(f"Error during parallel processing: {str(e)}")
            import traceback

            traceback.print_exc()
    finally:
        loop.close()

        # Clean up any remaining process pools
        from .patent_processor import PatentProcessor

        if hasattr(PatentProcessor, "process_pool"):
            try:
                PatentProcessor.process_pool.shutdown(wait=False)
            except:
                pass
