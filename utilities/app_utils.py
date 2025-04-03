import multiprocessing
from multiprocessing import Pool
from contextlib import contextmanager


class PoolManager:
    _pool = None

    @classmethod
    @contextmanager
    def get_pool(cls, processes):
        try:
            cls._pool = Pool(processes=processes)
            yield cls._pool
        finally:
            if cls._pool:
                cls._pool.terminate()
                cls._pool.join()
                cls._pool = None


def extract_and_save_examples_in_db(
    xml_dir, callback=None, stop_event=None, max_workers=4, year=None
):
    if stop_event and stop_event.is_set():
        if callback:
            callback("Stopping processing...")
        return

    # Use the pool manager instead of direct Pool creation
    with PoolManager.get_pool(processes=max_workers) as pool:
        try:
            # Your existing processing code here
            # ...existing code...

            # Add periodic stop checks
            if stop_event and stop_event.is_set():
                pool.terminate()
                if callback:
                    callback("Processing stopped by user")
                return

            # ...existing code...

        except Exception as e:
            if callback:
                callback(f"Error during processing: {str(e)}")
            pool.terminate()
            raise
