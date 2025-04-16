import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font
import os
import threading
import queue
import sqlite3
import csv
import multiprocessing
from multiprocessing import freeze_support, Event as MPEvent
from utilities.app_utils import (
    download_patents_pto,
    unzip_files,
    extract_and_save_examples_in_db,
    validate_year,
    validate_kind,
)

# Add freeze_support call at module level
freeze_support()


def process_year(year, kind, base_path, status_callback=None, stop_event=None):
    """Process a single year of patent data."""
    try:
        # Unpack stop events if provided as tuple
        thread_event = None
        mp_event = None
        if isinstance(stop_event, tuple):
            thread_event, mp_event = stop_event
        elif isinstance(stop_event, (threading.Event, multiprocessing.Event)):
            thread_event = stop_event

        # Check stop events
        if (thread_event and thread_event.is_set()) or (mp_event and mp_event.is_set()):
            if status_callback:
                status_callback("Operation stopped by user")
            return False

        # Pass thread event to download
        downloaded, download_path = download_patents_pto(
            year=year,
            kind=kind,
            callback=status_callback,
            stop_event=thread_event,  # Only pass thread event
        )

        # Check stop events after download
        if (thread_event and thread_event.is_set()) or (mp_event and mp_event.is_set()):
            if status_callback:
                status_callback("Operation stopped by user")
            return False

        if downloaded:
            unzip_path = os.path.join(base_path, f"patent_{kind}s_{year}")
            # Pass thread event to unzip
            if not unzip_files(
                download_path,
                unzip_path,
                callback=status_callback,
                stop_event=thread_event,  # Only pass thread event
            ):
                return False

            # Check stop events after unzip
            if (thread_event and thread_event.is_set()) or (
                mp_event and mp_event.is_set()
            ):
                if status_callback:
                    status_callback("Operation stopped by user")
                return False

            # Set multiprocessing start method
            if multiprocessing.get_start_method(allow_none=True) != "spawn":
                multiprocessing.set_start_method("spawn", force=True)

            # Pass both events to processing function
            extract_and_save_examples_in_db(
                unzip_path,
                callback=status_callback,
                stop_event=mp_event,  # Pass MP event
                max_workers=4,
                year=year,
            )

            if (thread_event and thread_event.is_set()) or (
                mp_event and mp_event.is_set()
            ):
                if status_callback:
                    status_callback("Operation stopped by user")
                return False

            if status_callback:
                status_callback(f"Processing complete for year {year}")
            return True
        else:
            if status_callback:
                status_callback(f"Failed to download patents for {year}")
            return False
    except Exception as e:
        if status_callback:
            status_callback(f"Error processing year {year}: {str(e)}")
        return False


class PatentDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("USPTO Patent Analyser")
        self.root.geometry("700x600")  # Increased height to accommodate new buttons
        self.root.configure(bg="#f0f0f0")

        # Create styles for ttk widgets
        style = ttk.Style()
        style.configure("TFrame", background="#f0f0f0")
        style.configure("TLabel", background="#f0f0f0")
        style.configure("TRadiobutton", background="#f0f0f0")

        # Main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)

        # Log frame (moved to row 11 to make room for new buttons)
        log_frame = ttk.LabelFrame(main_frame, text="Log Messages", padding="5")
        log_frame.grid(
            row=11, column=0, columnspan=2, sticky=(tk.N, tk.S, tk.E, tk.W), pady=5
        )
        main_frame.grid_rowconfigure(11, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame, height=10, width=80, wrap=tk.WORD, bg="#ffffff", fg="#000000"
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(
            log_frame, orient=tk.VERTICAL, command=self.log_text.yview
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # Patent Type
        ttk.Label(main_frame, text="Patent Type:").grid(
            row=0, column=0, sticky=tk.E, pady=5
        )
        self.kind_var = tk.StringVar(value="grant")
        kind_frame = ttk.Frame(main_frame)
        kind_frame.grid(row=0, column=1, sticky=tk.W)
        ttk.Radiobutton(
            kind_frame, text="Grant", variable=self.kind_var, value="grant"
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            kind_frame, text="Application", variable=self.kind_var, value="application"
        ).pack(side=tk.LEFT)

        # Year Selection
        ttk.Label(main_frame, text="Year Selection:").grid(
            row=1, column=0, sticky=tk.E, pady=5
        )
        year_frame = ttk.LabelFrame(main_frame, text="Choose Year Option", padding="5")
        year_frame.grid(row=1, column=1, sticky=tk.W, pady=5)

        self.year_type = tk.StringVar(value="single")
        ttk.Radiobutton(
            year_frame,
            text="Single Year",
            variable=self.year_type,
            value="single",
            command=self.toggle_year_inputs,
        ).pack(anchor=tk.W)
        ttk.Radiobutton(
            year_frame,
            text="Year Range",
            variable=self.year_type,
            value="range",
            command=self.toggle_year_inputs,
        ).pack(anchor=tk.W)

        # Year Input Fields
        self.year_input_frame = ttk.Frame(main_frame)
        self.year_input_frame.grid(row=2, column=1, sticky=tk.W, pady=5)

        self.single_year_var = tk.StringVar()
        self.start_year_var = tk.StringVar()
        self.end_year_var = tk.StringVar()

        self.single_year_frame = ttk.Frame(self.year_input_frame)
        ttk.Label(self.single_year_frame, text="Year:").pack(side=tk.LEFT)
        ttk.Entry(
            self.single_year_frame, textvariable=self.single_year_var, width=6
        ).pack(side=tk.LEFT)

        self.range_year_frame = ttk.Frame(self.year_input_frame)
        ttk.Label(self.range_year_frame, text="From:").pack(side=tk.LEFT)
        ttk.Entry(
            self.range_year_frame, textvariable=self.start_year_var, width=6
        ).pack(side=tk.LEFT)
        ttk.Label(self.range_year_frame, text="To:").pack(side=tk.LEFT)
        ttk.Entry(self.range_year_frame, textvariable=self.end_year_var, width=6).pack(
            side=tk.LEFT
        )

        # Output Directory
        ttk.Label(main_frame, text="Output Directory:").grid(
            row=3, column=0, sticky=tk.E, pady=5
        )
        dir_frame = ttk.Frame(main_frame)
        dir_frame.grid(row=3, column=1, sticky=tk.W)
        self.output_dir = tk.StringVar(value="data")
        ttk.Entry(dir_frame, textvariable=self.output_dir, width=40).pack(side=tk.LEFT)
        ttk.Button(dir_frame, text="Browse", command=self.browse_directory).pack(
            side=tk.LEFT, padx=5
        )

        # Progress
        # self.progress_var = tk.StringVar(value="Ready")
        # ttk.Label(main_frame, textvariable=self.progress_var).grid(
        #     row=4, column=0, columnspan=2, pady=10, sticky=tk.N + tk.S + tk.E + tk.W
        # )

        # Operation Buttons - Download, Unzip, Process separately
        ttk.Button(
            main_frame, text="Download Patents", command=self.download_patents_only
        ).grid(row=5, column=0, columnspan=2, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

        ttk.Button(
            main_frame, text="Unzip Patent Files", command=self.unzip_patents_only
        ).grid(row=6, column=0, columnspan=2, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

        ttk.Button(
            main_frame, text="Process Patent Data", command=self.process_patents_only
        ).grid(row=7, column=0, columnspan=1, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

        # Stop Button
        ttk.Button(main_frame, text="Stop", command=self.stop_operation).grid(
            row=7, column=1, columnspan=1, pady=5, sticky=tk.N + tk.S + tk.E + tk.W
        )

        # Add concurrent files control before the log frame
        concurrency_frame = ttk.Frame(main_frame)
        concurrency_frame.grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Label(concurrency_frame, text="Concurrent Files:").pack(side=tk.LEFT)
        self.concurrent_files = tk.StringVar(value="4")  # Default to 4
        ttk.Entry(concurrency_frame, textvariable=self.concurrent_files, width=5).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Label(concurrency_frame, text="(1-8 recommended)").pack(side=tk.LEFT)

        # Full Operation Button (all steps at once)
        ttk.Button(
            main_frame, text="Run Complete Process", command=self.download_patents
        ).grid(row=9, column=0, columnspan=2, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

        # Add disclaimer text below the Run Complete Process button
        disclaimer_text = "Note: Processing each year of patent data can take between 3 to 12 hours\ndepending on your hardware. Multiple years will take proportionally longer."
        disclaimer_label = ttk.Label(
            main_frame,
            text=disclaimer_text,
            foreground="darkred",
            justify=tk.CENTER,
            wraplength=600,
        )
        disclaimer_label.grid(row=10, column=0, columnspan=2, pady=(0, 10))

        # Add a new button to view database tables
        ttk.Button(
            main_frame, text="View Database Tables", command=self.view_database_tables
        ).grid(
            row=12, column=0, columnspan=2, pady=10, sticky=tk.N + tk.S + tk.E + tk.W
        )

        # Add Export All Tables button
        ttk.Button(
            main_frame, text="Export All Tables to CSV", command=self.export_all_tables
        ).grid(row=13, column=0, columnspan=2, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

        # Add an entry to set the number of rows to display
        ttk.Label(main_frame, text="Rows to Display:").grid(
            row=14, column=0, sticky=tk.E, pady=5
        )
        self.rows_to_display = tk.StringVar(value="10")
        ttk.Entry(main_frame, textvariable=self.rows_to_display, width=6).grid(
            row=14, column=1, sticky=tk.W, pady=5
        )

        self.log_queue = queue.Queue()
        self.error_occurred = False  # Track if an error has occurred
        self.stop_event = threading.Event()  # Event to signal stopping the download
        self.mp_stop_event = MPEvent()  # Event for multiprocessing operations
        self.root.after(100, self.process_log_queue)

        # Track state of each operation
        self.downloaded_data = {}  # Store year: download_path pairs
        self.unzipped_data = {}  # Store year: unzip_path pairs

        self.toggle_year_inputs()
        self.active_thread = None  # Track the active operation thread

        # Track pagination state for each table
        self.pagination_states = {}

    def update_log(self, message):
        """Add log message to the queue"""
        if "ERROR" in message:
            if self.error_occurred:
                self.log_text.delete(
                    "end-2l", "end-1l"
                )  # Remove the last error message
            self.error_occurred = True
        else:
            self.error_occurred = False
        self.log_queue.put(message)

    def process_log_queue(self):
        """Process log messages from the queue"""
        while not self.log_queue.empty():
            message = self.log_queue.get()
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
        self.root.after(100, self.process_log_queue)

    def toggle_year_inputs(self):
        if self.year_type.get() == "single":
            self.range_year_frame.pack_forget()
            self.single_year_frame.pack()
        else:
            self.single_year_frame.pack_forget()
            self.range_year_frame.pack()

    def browse_directory(self):
        directory = filedialog.askdirectory(initialdir=self.output_dir.get())
        if directory:
            self.output_dir.set(directory)

    def stop_operation(self):
        """Stop all running operations."""
        if not self.active_thread or not self.active_thread.is_alive():
            return

        self.update_log("Stopping all operations...")
        self.stop_event.set()  # Signal thread operations to stop
        self.mp_stop_event.set()  # Signal multiprocessing operations to stop

        # Force stop any active multiprocessing pools
        from utilities.app_utils import PoolManager

        if PoolManager._pool:
            PoolManager._pool.terminate()
            PoolManager._pool.join()
            PoolManager._pool = None

        def check_thread():
            if self.active_thread.is_alive():
                # Still running, update GUI and check again in 100ms
                self.root.update_idletasks()  # Keep GUI responsive
                self.root.after(100, check_thread)
            else:
                # Thread stopped
                self.update_log("All operations stopped successfully.")
                self.stop_event.clear()
                self.mp_stop_event = MPEvent()  # Create new MP event
                self.active_thread = None

        # Start periodic checks
        check_thread()
        self.update_log("Initiated stop operation - please wait...")

    def validate_inputs(self):
        """Validate user inputs with proper error handling."""
        try:
            # Remove the disclaimer popup and directly validate inputs

            # Validate year inputs
            if self.year_type.get() == "single":
                year_str = self.single_year_var.get().strip()
                if not year_str:
                    raise ValueError("Please enter a year")
                try:
                    year = int(year_str)
                    validate_year(year)
                except ValueError:
                    raise ValueError("Invalid year format")
            else:
                start_str = self.start_year_var.get().strip()
                end_str = self.end_year_var.get().strip()

                if not start_str or not end_str:
                    raise ValueError("Please enter both start and end years")

                try:
                    start_year = int(start_str)
                    end_year = int(end_str)
                    validate_year(start_year)
                    validate_year(end_year)

                    if start_year > end_year:
                        raise ValueError(
                            "Start year must be less than or equal to end year"
                        )
                except ValueError as e:
                    if "between 1976 and 2025" in str(e):
                        raise ValueError("Years must be between 1976 and 2025")
                    else:
                        raise ValueError("Invalid year format")

            # Validate kind
            kind = self.kind_var.get()
            validate_kind(kind)

            # Validate concurrent files
            try:
                concurrent = int(self.concurrent_files.get())
                if concurrent < 1:
                    raise ValueError("Concurrent files must be at least 1")
                if concurrent > 16:  # Set a reasonable upper limit
                    raise ValueError("Maximum 16 concurrent files allowed")
            except ValueError as e:
                if "concurrent files" in str(e):
                    raise
                raise ValueError("Invalid concurrent files value")

            return True

        except ValueError as e:
            self.update_log(f"ERROR: {str(e)}")
            return False
        except Exception as e:
            self.update_log(f"ERROR: An unexpected error occurred: {str(e)}")
            return False

    def download_patents_only(self):
        """Handle only the patent download process."""
        if not self.validate_inputs():
            return

        def run_download():
            try:
                self.log_queue.put("Clearing previous log")
                self.log_text.delete(1.0, tk.END)  # Clear previous log
                self.stop_event.clear()  # Clear the stop event before starting
                self.downloaded_data.clear()  # Clear previous download data

                years_to_process = self._get_years_to_process()
                if not years_to_process:
                    return

                kind = self.kind_var.get()
                base_path = self.output_dir.get()
                success_count = 0

                for year in years_to_process:
                    if self.stop_event.is_set():
                        break

                    self.log_queue.put(f"Downloading patents for year {year}")
                    downloaded, download_path = download_patents_pto(
                        year=year,
                        kind=kind,
                        callback=self.update_log,
                        stop_event=self.stop_event,
                    )

                    if downloaded:
                        self.downloaded_data[year] = download_path
                        self.log_queue.put(
                            f"Successfully downloaded patents for year {year}"
                        )
                        success_count += 1
                    else:
                        self.log_queue.put(
                            f"Failed to download patents for year {year}"
                        )

                if not self.stop_event.is_set():
                    if success_count > 0:
                        self.log_queue.put(
                            f"Download process completed successfully! Downloaded {success_count} year(s)."
                        )
                    else:
                        self.log_queue.put(
                            "Download process completed with no successful downloads."
                        )
                else:
                    self.log_queue.put("Download process stopped by user.")

            except Exception as e:
                self.log_queue.put(
                    f"ERROR: An error occurred during download: {str(e)}"
                )

        self.active_thread = threading.Thread(target=run_download)
        self.active_thread.start()

    def unzip_patents_only(self):
        """Handle only the patent unzipping process."""
        if not self.validate_inputs():
            return

        def run_unzip():
            try:
                self.stop_event.clear()
                self.unzipped_data.clear()  # Clear previous unzip data

                years_to_process = self._get_years_to_process()
                if not years_to_process:
                    return

                kind = self.kind_var.get()
                base_path = self.output_dir.get()
                success_count = 0

                for year in years_to_process:
                    if self.stop_event.is_set():
                        break

                    # Check if download exists
                    download_path = self._find_download_path(year, kind)

                    if download_path and os.path.exists(download_path):
                        unzip_path = os.path.join(base_path, f"patent_{kind}s_{year}")
                        self.log_queue.put(f"Unzipping patents for year {year}")

                        unzip_files(download_path, unzip_path, callback=self.update_log)

                        if os.path.exists(unzip_path):
                            self.unzipped_data[year] = unzip_path
                            self.log_queue.put(
                                f"Successfully unzipped patents for year {year}"
                            )
                            success_count += 1
                        else:
                            self.log_queue.put(
                                f"Failed to unzip patents for year {year}"
                            )
                    else:
                        self.log_queue.put(
                            f"No download found for year {year}. Please download first."
                        )

                if not self.stop_event.is_set():
                    if success_count > 0:
                        self.log_queue.put(
                            f"Unzip process completed successfully! Unzipped {success_count} year(s)."
                        )
                    else:
                        self.log_queue.put(
                            "Unzip process completed with no successful unzips."
                        )
                else:
                    self.log_queue.put("Unzip process stopped by user.")

            except Exception as e:
                self.log_queue.put(
                    f"ERROR: An error occurred during unzipping: {str(e)}"
                )

        self.active_thread = threading.Thread(target=run_unzip)
        self.active_thread.start()

    def process_patents_only(self):
        """Handle only the patent processing process."""
        if not self.validate_inputs():
            return

        def run_processing():
            try:
                self.stop_event.clear()
                self.mp_stop_event = MPEvent()  # Reset MP event at start

                years_to_process = self._get_years_to_process()
                if not years_to_process:
                    return

                kind = self.kind_var.get()
                base_path = self.output_dir.get()
                success_count = 0

                for year in years_to_process:
                    if self.stop_event.is_set() or self.mp_stop_event.is_set():
                        break

                    # Check if unzip path exists
                    unzip_path = self._find_unzip_path(year, kind)

                    if unzip_path and os.path.exists(unzip_path):
                        self.log_queue.put(f"Processing patents for year {year}")
                        try:
                            extract_and_save_examples_in_db(
                                unzip_path,
                                callback=self.update_log,
                                stop_event=(
                                    self.stop_event,
                                    self.mp_stop_event,
                                ),  # Pass both events
                                max_workers=int(self.concurrent_files.get()),
                                year=year,
                            )
                            self.log_queue.put(f"Processing complete for year {year}")
                            success_count += 1
                        except Exception as e:
                            self.log_queue.put(
                                f"Failed to process patents for year {year}: {str(e)}"
                            )
                    else:
                        self.log_queue.put(
                            f"No unzipped data found for year {year}. Please unzip first."
                        )

                if not self.stop_event.is_set() and not self.mp_stop_event.is_set():
                    if success_count > 0:
                        self.log_queue.put(
                            f"Processing completed successfully! Processed {success_count} year(s)."
                        )
                    else:
                        self.log_queue.put(
                            "Processing completed with no successful operations."
                        )
                else:
                    self.log_queue.put("Processing stopped by user.")

            except Exception as e:
                self.log_queue.put(
                    f"ERROR: An error occurred during processing: {str(e)}"
                )

        self.active_thread = threading.Thread(target=run_processing)
        self.active_thread.start()

    def _get_years_to_process(self):
        """Get the list of years to process based on user input."""
        years = []
        if self.year_type.get() == "single":
            try:
                year = int(self.single_year_var.get().strip())
                years = [year]
            except ValueError:
                self.log_queue.put("ERROR: Invalid year format")
                return []
        else:
            try:
                start_year = int(self.start_year_var.get().strip())
                end_year = int(self.end_year_var.get().strip())
                years = list(range(start_year, end_year + 1))
            except ValueError:
                self.log_queue.put("ERROR: Invalid year format")
                return []

        return years

    def _find_download_path(self, year, kind):
        """Find the download path for a year, either from tracked downloads or by guessing."""
        # First check if we have tracked this download
        if year in self.downloaded_data:
            return self.downloaded_data[year]

        # Try to guess the path
        base_path = self.output_dir.get()

        # Check if base_path itself is the file
        if os.path.isfile(base_path):
            if os.path.basename(base_path).startswith(f"patent_{kind}_{year}"):
                return base_path

        # Common formats to check - updated with correct naming pattern
        possible_paths = [
            # Try direct in the base path
            os.path.join(base_path, f"patent_{kind}_{year}_zip"),
            # Try in a data subdirectory
            os.path.join(base_path, "data", f"patent_{kind}_{year}_zip"),
            # Try with 's' suffix on kind
            os.path.join(base_path, f"patent_{kind}s_{year}_zip"),
            os.path.join(base_path, "data", f"patent_{kind}s_{year}_zip"),
            # Check with parent directory if base_path is already 'data'
            os.path.join(os.path.dirname(base_path), f"patent_{kind}_{year}_zip"),
            os.path.join(os.path.dirname(base_path), f"patent_{kind}s_{year}_zip"),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        # Debug log to show what paths were checked
        self.log_queue.put("DEBUG: Checked the following paths for downloads:")
        for path in possible_paths:
            self.log_queue.put(f"  - {path}")

        return None

    def _find_unzip_path(self, year, kind):
        """Find the unzip path for a year, either from tracked unzips or by guessing."""
        # First check if we have tracked this unzip
        if year in self.unzipped_data:
            return self.unzipped_data[year]

        # Try to guess the path
        base_path = self.output_dir.get()

        # Common paths to check
        possible_paths = [
            # Try direct in the base path
            os.path.join(base_path, f"patent_{kind}s_{year}"),
            # Try in a data subdirectory
            os.path.join(base_path, "data", f"patent_{kind}s_{year}"),
            # Try without 's' suffix
            os.path.join(base_path, f"patent_{kind}_{year}"),
            os.path.join(base_path, "data", f"patent_{kind}_{year}"),
            # Check with parent directory if base_path is already 'data'
            os.path.join(os.path.dirname(base_path), f"patent_{kind}s_{year}"),
            os.path.join(os.path.dirname(base_path), f"patent_{kind}_{year}"),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        # Debug log to show what paths were checked
        self.log_queue.put("DEBUG: Checked the following paths for unzipped data:")
        for path in possible_paths:
            self.log_queue.put(f"  - {path}")

        return None

    def download_patents(self):
        """Handle the complete patent process (download, unzip, process)."""
        if not self.validate_inputs():
            return

        def run_download():
            try:
                # Reset stop events at start of operation
                self.stop_event.clear()
                self.mp_stop_event = MPEvent()

                self.log_queue.put("Clearing previous log")
                self.log_text.delete(1.0, tk.END)  # Clear previous log

                years_to_process = self._get_years_to_process()
                if not years_to_process:
                    return

                kind = self.kind_var.get()
                base_path = self.output_dir.get()
                success_count = 0

                for year in years_to_process:
                    if self.stop_event.is_set() or self.mp_stop_event.is_set():
                        self.log_queue.put("Operation stopped by user.")
                        break

                    self.log_queue.put(f"Processing year {year}")

                    if process_year(
                        year,
                        kind,
                        base_path,
                        status_callback=self.update_log,
                        stop_event=(
                            self.stop_event,
                            self.mp_stop_event,
                        ),  # Pass both events
                    ):
                        success_count += 1

                    if self.stop_event.is_set() or self.mp_stop_event.is_set():
                        break

                if not self.stop_event.is_set() and not self.mp_stop_event.is_set():
                    if success_count > 0:
                        self.log_queue.put(
                            f"Complete process finished successfully! Processed {success_count} year(s)."
                        )
                    else:
                        self.log_queue.put(
                            "Process completed but no years were successfully processed."
                        )
                else:
                    self.log_queue.put("Process stopped by user.")

            except Exception as e:
                self.log_queue.put(f"ERROR: An error occurred: {str(e)}")
            finally:
                if self.stop_event.is_set() or self.mp_stop_event.is_set():
                    self.stop_event.clear()  # Reset stop event
                    self.mp_stop_event = MPEvent()  # Reset multiprocessing event

        self.active_thread = threading.Thread(target=run_download)
        self.active_thread.start()

    def view_database_tables(self):
        """Open a new window to view database tables."""
        try:
            # First verify database connection and tables
            with sqlite3.connect("./db/patents.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                print(f"Tables in database: {tables}")  # Debug info

                # Check if patent_statistics exists and has data
                for table in ["patent_examples", "patent_statistics"]:
                    cursor.execute(
                        f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{table}'"
                    )
                    exists = cursor.fetchone()[0] > 0
                    print(f"Table {table} exists: {exists}")

                    if exists:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        print(f"Table {table} has {count} rows")

                        # Show sample data
                        if count > 0:
                            cursor.execute(f"SELECT * FROM {table} LIMIT 1")
                            sample = cursor.fetchone()
                            print(f"Sample from {table}: {sample}")

            # Now create the GUI
            db_window = tk.Toplevel(self.root)
            db_window.title("Database Tables")
            db_window.geometry("800x600")

            notebook = ttk.Notebook(db_window)
            notebook.pack(fill=tk.BOTH, expand=True)

            # Create frames for each table
            examples_frame = ttk.Frame(notebook)
            statistics_frame = ttk.Frame(notebook)

            notebook.add(examples_frame, text="Patent Examples")
            notebook.add(statistics_frame, text="Patent Statistics")

            # Add treeviews to display tables
            self.create_table_view(examples_frame, "patent_examples")
            self.create_table_view(statistics_frame, "patent_statistics")

        except Exception as e:
            self.log_queue.put(f"Error viewing database: {str(e)}")
            import traceback

            traceback.print_exc()

    def create_table_view(self, parent_frame, table_name):
        """Create a styled treeview to display a database table."""
        # Create frame for treeview and scrollbarss
        frame = ttk.Frame(parent_frame)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create treeview with scrollbars
        tree = ttk.Treeview(frame)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid layout for treeview and scrollbars
        tree.grid(column=0, row=0, sticky="nsew")
        vsb.grid(column=1, row=0, sticky="ns")
        hsb.grid(column=0, row=1, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        # Add double-click event binding for viewing full data
        tree.bind(
            "<Double-1>", lambda event: self.view_full_data(event, tree, table_name)
        )

        # Enhanced style configuration
        style = ttk.Style()
        style.configure(
            "Treeview",
            rowheight=30,  # Increased row height
            font=("Helvetica", 10),  # Default font for content
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
            padding=5,
        )
        style.configure(
            "Treeview.Heading",
            font=("Helvetica", 10, "bold"),  # Bold headers
            relief="raised",
            padding=5,
            background="#E8E8E8",  # Light gray background for headers
        )
        style.map(
            "Treeview",
            background=[("selected", "#0078D7")],
            foreground=[("selected", "#FFFFFF")],
        )

        # Connect to database and fetch data
        with sqlite3.connect("./db/patents.db") as conn:
            cursor = conn.cursor()

            # Get column info and set up treeview columns
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            tree["columns"] = columns
            tree["show"] = "headings"  # Hide the first empty column

            # Configure columns with better spacing and alignment based on content type
            for col in columns:
                tree.heading(
                    col,
                    text=col.replace("_", " ").title(),
                    anchor="center",  # Center-align headers
                    command=lambda c=col: self.sort_treeview(tree, c, False),
                )

                # Set initial column width and alignment based on content type
                if col in ["id", "year"]:
                    tree.column(col, width=80, anchor="center")
                elif "percentage" in col.lower():
                    tree.column(col, width=120, anchor="center")
                elif col in ["patent_number"]:
                    tree.column(col, width=150, anchor="w")  # Left-align
                elif col in ["example_content", "tense_breakdown"]:
                    tree.column(
                        col, width=400, anchor="w"
                    )  # Left-align, wider for text
                else:
                    tree.column(
                        col, width=200, anchor="w"
                    )  # Default width and left-align

                self.add_heading_tooltip(tree, col, col.replace("_", " ").title())

            # Fetch and insert data with user-defined page size
            try:
                rows_to_display = max(1, int(self.rows_to_display.get()))
            except ValueError:
                rows_to_display = 10  # Default if invalid input

            # Get total row count for pagination
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            total_rows = cursor.fetchone()[0]

            # Initialize/update pagination state for this table
            if table_name not in self.pagination_states:
                self.pagination_states[table_name] = {
                    "current_page": 0,
                    "total_pages": max(
                        1, (total_rows + rows_to_display - 1) // rows_to_display
                    ),
                    "page_size": rows_to_display,  # Store the page size
                }
            else:
                # Update existing pagination state with new page size
                self.pagination_states[table_name]["page_size"] = rows_to_display
                self.pagination_states[table_name]["total_pages"] = max(
                    1, (total_rows + rows_to_display - 1) // rows_to_display
                )

            # Create pagination frame
            pagination_frame = ttk.Frame(parent_frame)
            pagination_frame.pack(fill=tk.X, padx=5, pady=5)

            # Each button captures the current tree and table_name
            ttk.Button(
                pagination_frame,
                text="<<",
                command=lambda t=tree, tn=table_name: self.change_page(tn, t, 0),
            ).pack(side=tk.LEFT, padx=5)

            ttk.Button(
                pagination_frame,
                text="<",
                command=lambda t=tree, tn=table_name: self.change_page(
                    tn, t, self.pagination_states[tn]["current_page"] - 1
                ),
            ).pack(side=tk.LEFT, padx=5)

            # Store label in pagination state for updates
            page_label = ttk.Label(
                pagination_frame,
                text=f"Page 1 of {self.pagination_states[table_name]['total_pages']}",
            )
            page_label.pack(side=tk.LEFT, padx=5)
            self.pagination_states[table_name]["label"] = page_label

            ttk.Button(
                pagination_frame,
                text=">",
                command=lambda t=tree, tn=table_name: self.change_page(
                    tn, t, self.pagination_states[tn]["current_page"] + 1
                ),
            ).pack(side=tk.LEFT, padx=5)

            ttk.Button(
                pagination_frame,
                text=">>",
                command=lambda t=tree, tn=table_name: self.change_page(
                    tn, t, self.pagination_states[tn]["total_pages"] - 1
                ),
            ).pack(side=tk.LEFT, padx=5)

            # Add export button to pagination frame
            ttk.Button(
                pagination_frame,
                text="Export to CSV",
                command=lambda: self.export_to_csv(table_name),
            ).pack(side=tk.RIGHT, padx=5)

            # Load initial data
            self.load_table_data(table_name, tree, 0, rows_to_display)

            # Configure row colors
            tree.tag_configure("oddrow", background="#F5F5F5")  # Lighter gray
            tree.tag_configure("evenrow", background="#FFFFFF")  # White

    def view_full_data(self, event, tree, table_name):
        """Display full data for the selected row in a new window."""
        # Get the selected item
        item = tree.selection()[0] if tree.selection() else None
        if not item:
            return

        # Get the item values
        values = tree.item(item, "values")
        if not values:
            return

        # Get column names
        columns = tree.config("columns")[-1]

        # Create new window for displaying full data
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"Full Data View - {table_name}")
        detail_window.geometry("800x600")

        # Add a frame with scrollbars
        frame = ttk.Frame(detail_window)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create a notebook for different view options
        notebook = ttk.Notebook(frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Tab for formatted view (key-value pairs)
        formatted_frame = ttk.Frame(notebook)
        notebook.add(formatted_frame, text="Formatted View")

        # Tab for raw text view
        raw_frame = ttk.Frame(notebook)
        notebook.add(raw_frame, text="Raw Text")

        # Find text column with longest content
        main_content_col = None
        max_length = 0
        for i, col in enumerate(columns):
            if isinstance(values[i], str) and len(values[i]) > max_length:
                max_length = len(values[i])
                main_content_col = i

        # Formatted view with fields
        canvas = tk.Canvas(formatted_frame)
        scroll_y = ttk.Scrollbar(
            formatted_frame, orient="vertical", command=canvas.yview
        )
        scroll_x = ttk.Scrollbar(
            formatted_frame, orient="horizontal", command=canvas.xview
        )

        canvas.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        formatted_frame.grid_rowconfigure(0, weight=1)
        formatted_frame.grid_columnconfigure(0, weight=1)

        content_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=content_frame, anchor="nw")

        # Add fields to the content frame
        row = 0
        for i, col in enumerate(columns):
            # Create a frame for each field
            field_frame = ttk.Frame(content_frame)
            field_frame.grid(row=row, column=0, sticky="ew", pady=5)

            # Label for field name
            label = ttk.Label(
                field_frame,
                text=f"{col.replace('_', ' ').title()}:",
                font=("TkDefaultFont", 10, "bold"),
            )
            label.grid(row=0, column=0, sticky="nw", padx=5)

            # Special handling for long text fields
            if isinstance(values[i], str) and len(values[i]) > 100:
                # Text widget for long content
                text_widget = tk.Text(field_frame, wrap="word", height=10, width=80)
                text_widget.grid(row=1, column=0, sticky="nsew", padx=5)
                text_widget.insert("1.0", values[i])
                text_widget.config(state="disabled")

                # Add scrollbar for the text widget
                text_scroll = ttk.Scrollbar(field_frame, command=text_widget.yview)
                text_widget.config(yscrollcommand=text_scroll.set)
                text_scroll.grid(row=1, column=1, sticky="ns")

                # Copy button
                copy_btn = ttk.Button(
                    field_frame,
                    text="Copy to Clipboard",
                    command=lambda v=values[i]: self.copy_to_clipboard(v),
                )
                copy_btn.grid(row=2, column=0, sticky="nw", padx=5, pady=2)
            else:
                # Simple label for short content
                value_label = ttk.Label(
                    field_frame, text=str(values[i]), wraplength=700
                )
                value_label.grid(row=1, column=0, sticky="nw", padx=5)

            field_frame.grid_columnconfigure(0, weight=1)
            row += 1

        # Raw text view - just a text widget with all data
        raw_text = tk.Text(raw_frame, wrap="word")
        raw_text.pack(fill=tk.BOTH, expand=True)

        # Add all data to the raw text view
        raw_data = ""
        for i, col in enumerate(columns):
            raw_data += f"{col.replace('_', ' ').title()}: {values[i]}\n\n"

        raw_text.insert("1.0", raw_data)
        raw_text.config(state="disabled")

        # Add scrollbar for raw text
        raw_scroll = ttk.Scrollbar(raw_frame, command=raw_text.yview)
        raw_text.config(yscrollcommand=raw_scroll.set)
        raw_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Button frame at the bottom
        button_frame = ttk.Frame(detail_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        # Copy all button
        copy_all_btn = ttk.Button(
            button_frame,
            text="Copy All Data",
            command=lambda: self.copy_to_clipboard(raw_data),
        )
        copy_all_btn.pack(side=tk.LEFT, padx=5)

        # Close button
        close_btn = ttk.Button(
            button_frame, text="Close", command=detail_window.destroy
        )
        close_btn.pack(side=tk.RIGHT, padx=5)

        # Update the canvas scrollregion
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

    def copy_to_clipboard(self, text):
        """Copy text to clipboard and show confirmation."""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

        # Show a small confirmation tooltip
        x, y = self.root.winfo_pointerxy()
        tooltip = tk.Toplevel(self.root)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{x + 10}+{y + 10}")
        tooltip.wm_attributes("-topmost", True)

        label = ttk.Label(
            tooltip,
            text="Copied to clipboard!",
            background="#FFFFEA",
            relief="solid",
            borderwidth=1,
            font=("TkDefaultFont", 9, "normal"),
            padding=(5, 3),
        )
        label.pack()

        # Close the tooltip after 1.5 seconds
        tooltip.after(1500, tooltip.destroy)

    def create_header_tooltip(self, tree, column, text):
        """
        DEPRECATED: This method was causing errors with unsupported events.
        Use add_heading_tooltip instead.
        """
        pass  # Keep this for compatibility but don't use it

    def add_heading_tooltip(self, tree, column, text):
        """Add tooltip for column headers using a better approach."""

        # Initialize the active_tooltip attribute if it doesn't exist
        if not hasattr(tree, "active_tooltip"):
            tree.active_tooltip = None

        def show_tooltip(event):
            # Get the column the mouse is over
            region = tree.identify_region(event.x, event.y)
            if region == "heading":
                column = tree.identify_column(event.x)
                if column:
                    # Show tooltip near the cursor
                    x, y = event.x_root + 10, event.y_root + 10
                    tip = tk.Toplevel(tree)
                    tip.wm_overrideredirect(True)
                    tip.wm_geometry(f"+{x}+{y}")
                    label = ttk.Label(
                        tip,
                        text=text,
                        justify="left",
                        background="#FFFFEA",
                        relief="solid",
                        borderwidth=1,
                        font=("TkDefaultFont", 9, "normal"),
                    )
                    label.pack(padx=3, pady=2)

                    # Safely destroy existing tooltip before creating new one
                    if (
                        hasattr(tree, "active_tooltip")
                        and tree.active_tooltip is not None
                    ):
                        try:
                            tree.active_tooltip.destroy()
                        except:
                            pass

                    tree.active_tooltip = tip

                    # Auto-close tooltip after 3 seconds
                    tree.after(3000, lambda: self.safely_destroy_tooltip(tip))

        def hide_tooltip(event):
            # Safely destroy tooltip if it exists
            if hasattr(tree, "active_tooltip") and tree.active_tooltip is not None:
                self.safely_destroy_tooltip(tree.active_tooltip)
                tree.active_tooltip = None

        # Use <Motion> event which is supported
        tree.bind("<Motion>", show_tooltip)
        tree.bind("<Leave>", hide_tooltip)

    def safely_destroy_tooltip(self, tooltip):
        """Safely destroy a tooltip window if it exists and is valid."""
        try:
            if tooltip and tooltip.winfo_exists():
                tooltip.destroy()
        except:
            pass  # Ignore any errors during tooltip destruction

    def load_table_data(self, table_name, tree, page, page_size=None):
        """Load a specific page of data into the treeview."""
        # Clear existing rows
        for item in tree.get_children():
            tree.delete(item)

        # Use the current page size from pagination state if not specified
        if page_size is None and table_name in self.pagination_states:
            page_size = self.pagination_states[table_name]["page_size"]
        elif page_size is None:
            try:
                page_size = max(1, int(self.rows_to_display.get()))
            except ValueError:
                page_size = 10

        offset = page * page_size

        # Connect to database and fetch data
        try:
            with sqlite3.connect("./db/patents.db") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT * FROM {table_name} LIMIT {page_size} OFFSET {offset}"
                )
                rows = cursor.fetchall()

                # Format and insert rows with improved visual clarity
                for i, row in enumerate(rows):
                    # Format values based on column type
                    formatted_row = []
                    for val in row:
                        if isinstance(val, (int, float)):
                            if isinstance(val, float):
                                formatted_row.append(f"{val:.2f}")  # Format floats
                            else:
                                formatted_row.append(str(val))  # Format integers
                        elif val is None:
                            formatted_row.append("")  # Empty string for NULL values
                        else:
                            formatted_row.append(str(val))  # String values as-is

                    tag = "evenrow" if i % 2 == 0 else "oddrow"
                    tree.insert("", tk.END, values=formatted_row, tags=(tag,))

            # Update page label and state
            if table_name in self.pagination_states:
                state = self.pagination_states[table_name]
                state["current_page"] = page

                if "label" in state:
                    state["label"].config(
                        text=f"Page {page + 1} of {state['total_pages']}"
                    )

                # self.log_queue.put(f"Changed to page {page + 1} for {table_name}")
        except Exception as e:
            self.log_queue.put(f"Error loading table data: {str(e)}")
            import traceback

            traceback.print_exc()

    def change_page(self, table_name, tree, page):
        """Navigate to a specific page of data."""
        if table_name in self.pagination_states:
            state = self.pagination_states[table_name]
            if 0 <= page < state["total_pages"]:
                self.load_table_data(table_name, tree, page, state["page_size"])

    def export_to_csv(self, table_name):
        """Export table data to CSV file."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"{table_name}.csv",
        )

        if not file_path:
            return

        try:
            with sqlite3.connect("./db/patents.db") as conn:
                cursor = conn.cursor()

                # Get column names
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = [col[1] for col in cursor.fetchall()]

                # Get all data
                cursor.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()

                # Write to CSV
                import csv

                with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(columns)  # Write header
                    writer.writerows(rows)  # Write data

                self.update_log(f"Data exported successfully to {file_path}")

        except Exception as e:
            self.update_log(f"Error exporting data: {str(e)}")

    def export_all_tables(self):
        """Export all database tables to CSV files."""
        try:
            # Ask for directory to save files
            save_dir = filedialog.askdirectory(
                title="Select Directory to Save CSV Files"
            )
            if not save_dir:
                return

            tables = ["patent_examples", "patent_statistics"]
            with sqlite3.connect("./db/patents.db") as conn:
                cursor = conn.cursor()

                for table_name in tables:
                    file_path = os.path.join(save_dir, f"{table_name}.csv")

                    # Get column names
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = [col[1] for col in cursor.fetchall()]

                    # Get all data
                    cursor.execute(f"SELECT * FROM {table_name}")
                    rows = cursor.fetchall()

                    # Write to CSV
                    with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(columns)  # Write header
                        writer.writerows(rows)  # Write data

                    self.update_log(f"Exported {table_name} to {file_path}")

            self.update_log("All tables exported successfully!")
            messagebox.showinfo(
                "Success", "All tables have been exported successfully!"
            )

        except Exception as e:
            error_msg = f"Error exporting tables: {str(e)}"
            self.update_log(error_msg)
            messagebox.showerror("Error", error_msg)

    def sort_treeview(self, tree, column, reverse):
        """Sort treeview data by a column."""
        data = [(tree.set(item, column), item) for item in tree.get_children("")]

        # Check if data is numeric
        try:
            data.sort(key=lambda x: float(x[0]), reverse=reverse)
        except ValueError:
            data.sort(reverse=reverse)

        # Rearrange items in sorted order
        for index, (val, item) in enumerate(data):
            tree.move(item, "", index)

        # Switch sort order for next sort operation
        tree.heading(
            column, command=lambda: self.sort_treeview(tree, column, not reverse)
        )


class ToolTip:
    """Create tooltips for treeview headers."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        label = ttk.Label(
            self.tooltip,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
        )
        label.pack()

    def leave(self, event):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


def main():
    # Add freeze support here as well
    multiprocessing.freeze_support()
    root = tk.Tk()
    app = PatentDownloaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
