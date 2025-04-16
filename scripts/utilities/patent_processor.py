from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import asyncio
from bs4 import BeautifulSoup
import re
import multiprocessing
from .utils_clean import (
    remove_leadiong_zeros,
    find_doc_number,
    extract_experiments_w_heading,
    extract_examples_start_w_word_all,
)


class PatentProcessor:
    def __init__(self, max_workers=None):
        if max_workers is None:
            max_workers = max(1, multiprocessing.cpu_count() - 1)
        self.max_workers = max_workers
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.process_pool = ProcessPoolExecutor(max_workers=max_workers)

    async def process_patent(self, xml, callback=None, stop_event=None):
        """Process a single patent document asynchronously."""
        try:
            # Check stop event
            if stop_event and stop_event.is_set():
                return None

            if len(xml) <= 2000:
                return None

            loop = asyncio.get_running_loop()

            # Fast pre-check for examples section
            if all(i not in xml.upper() for i in ["EXAMPLES", "EXPERIMENTS", "TESTS"]):
                return None

            # Check stop event before heavy processing
            if stop_event and stop_event.is_set():
                return None

            # Check for sequence listings
            has_sequences = await loop.run_in_executor(
                self.thread_pool,
                lambda: bool(re.findall(r"<s\d+>.*?</s\d+>", xml))
                or '<sequence-cwu id="SEQLST-0">' in xml
                or "<!DOCTYPE sequence-cwu" in xml,
            )
            if has_sequences:
                return None

            # Check stop event before processing heading
            if stop_event and stop_event.is_set():
                return None

            # Process heading and examples asynchronously
            heading = await loop.run_in_executor(
                self.thread_pool, extract_experiments_w_heading, xml
            )

            examples = []
            if heading and len(heading) == 1:
                examples = await loop.run_in_executor(
                    self.thread_pool,
                    extract_examples_start_w_word_all,
                    heading[0].find_next_siblings(),
                )
                if not examples:
                    soup = BeautifulSoup(xml, "xml")
                    siblings = soup.find_all(["heading", "p"])
                    examples = await loop.run_in_executor(
                        self.thread_pool, extract_examples_start_w_word_all, siblings
                    )
            else:
                soup = BeautifulSoup(xml, "xml")
                siblings = soup.find_all(["heading", "p"])
                examples = await loop.run_in_executor(
                    self.thread_pool, extract_examples_start_w_word_all, siblings
                )

            # Check stop event before finalizing
            if stop_event and stop_event.is_set():
                return None

            if examples:
                doc_nums = await loop.run_in_executor(
                    self.thread_pool, find_doc_number, xml
                )
                if doc_nums:
                    doc_num = remove_leadiong_zeros(doc_nums[0])
                    return (doc_num, examples)

            return None

        except Exception as e:
            if callback:
                callback(f"Error processing patent: {str(e)}")
            return None

    async def process_batch(self, patents, callback=None, stop_event=None):
        """Process a batch of patents using multiple CPU cores."""
        batch_size = min(200, len(patents))
        total_results = {}
        total_patents = len(patents)
        processed = 0
        found = 0

        # Create processing pools
        loop = asyncio.get_running_loop()

        # Process patents in parallel batches
        for i in range(0, len(patents), batch_size):
            # Check stop event at start of each batch
            if stop_event and stop_event.is_set():
                if callback:
                    callback("Operation stopped by user")
                break

            batch = patents[i : i + batch_size]
            tasks = []

            # Create concurrent tasks for the batch
            for patent in batch:
                task = asyncio.create_task(
                    self.process_patent(patent, callback, stop_event)
                )
                tasks.append(task)

            # Process batch results
            results = await asyncio.gather(*tasks)

            valid_results = []
            for result in results:
                processed += 1
                if isinstance(result, tuple) and result[0] is not None:
                    doc_num, examples = result
                    total_results[doc_num] = examples
                    found += 1

                if processed % 500 == 0 and callback:
                    callback(
                        f"Processed {processed}/{total_patents} patents - Found {found} with examples"
                    )

            # Check stop event after batch processing
            if stop_event and stop_event.is_set():
                if callback:
                    callback("Operation stopped by user")
                break

            await asyncio.sleep(0)  # Allow other tasks to run

        return total_results

    def __del__(self):
        self.thread_pool.shutdown()
        self.process_pool.shutdown()
