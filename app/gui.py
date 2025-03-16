import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font  # Add font here
import os
import threading
import queue
import sqlite3  # Add this import
from utilities.app_utils import (
    download_patents_pto,
    unzip_files,
    extract_and_save_examples_in_db,
    validate_year,
    validate_kind,
)


def process_year(year, kind, base_path, status_callback=None, stop_event=None):
    """Process a single year of patent data."""
    try:
        if stop_event and stop_event.is_set():
            return False
        downloaded, download_path = download_patents_pto(
            year=year, kind=kind, callback=status_callback, stop_event=stop_event
        )
        if stop_event and stop_event.is_set():
            return False
        if downloaded:
            unzip_path = os.path.join(base_path, f"patent_{kind}s_{year}")
            unzip_files(
                download_path,
                unzip_path,
                callback=status_callback,
                stop_event=stop_event,
            )
            if stop_event and stop_event.is_set():
                return False
            extract_and_save_examples_in_db(
                unzip_path, callback=status_callback, stop_event=stop_event
            )
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

        # Log frame (moved to row 9 to make room for new buttons)
        log_frame = ttk.LabelFrame(main_frame, text="Log Messages", padding="5")
        log_frame.grid(
            row=9, column=0, columnspan=2, sticky=(tk.N, tk.S, tk.E, tk.W), pady=5
        )
        main_frame.grid_rowconfigure(9, weight=1)
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
        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(main_frame, textvariable=self.progress_var).grid(
            row=4, column=0, columnspan=2, pady=10, sticky=tk.N + tk.S + tk.E + tk.W
        )

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

        # Full Operation Button (all steps at once)
        ttk.Button(
            main_frame, text="Run Complete Process", command=self.download_patents
        ).grid(row=8, column=0, columnspan=2, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

        # Add a new button to view database tables
        ttk.Button(
            main_frame, text="View Database Tables", command=self.view_database_tables
        ).grid(
            row=10, column=0, columnspan=2, pady=10, sticky=tk.N + tk.S + tk.E + tk.W
        )

        # Add an entry to set the number of rows to display
        ttk.Label(main_frame, text="Rows to Display:").grid(
            row=11, column=0, sticky=tk.E, pady=5
        )
        self.rows_to_display = tk.StringVar(value="10")
        ttk.Entry(main_frame, textvariable=self.rows_to_display, width=6).grid(
            row=11, column=1, sticky=tk.W, pady=5
        )

        self.log_queue = queue.Queue()
        self.error_occurred = False  # Track if an error has occurred
        self.stop_event = threading.Event()  # Event to signal stopping the download
        self.root.after(100, self.process_log_queue)

        # Track state of each operation
        self.downloaded_data = {}  # Store year: download_path pairs
        self.unzipped_data = {}  # Store year: unzip_path pairs

        self.toggle_year_inputs()
        self.active_thread = None  # Track the active operation thread

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
        if self.active_thread and self.active_thread.is_alive():
            self.update_log("Stopping all operations...")
            self.stop_event.set()  # Signal all processes to stop

            # Wait for a short time for the thread to stop gracefully
            self.active_thread.join(timeout=2.0)

            # If thread is still alive after timeout, show a message
            if self.active_thread.is_alive():
                self.update_log("Operation is taking longer to stop. Please wait...")
                self.active_thread.join()  # Wait for complete stop

            self.update_log("All operations stopped.")
            # Reset stop event for future operations
            self.stop_event.clear()

    def validate_inputs(self):
        """Validate user inputs with proper error handling."""
        try:
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

                years_to_process = self._get_years_to_process()
                if not years_to_process:
                    return

                kind = self.kind_var.get()
                base_path = self.output_dir.get()
                success_count = 0

                for year in years_to_process:
                    if self.stop_event.is_set():
                        break

                    # Check if unzip path exists
                    unzip_path = self._find_unzip_path(year, kind)

                    if unzip_path and os.path.exists(unzip_path):
                        self.log_queue.put(f"Processing patents for year {year}")
                        try:
                            extract_and_save_examples_in_db(
                                unzip_path,
                                callback=self.update_log,
                                stop_event=self.stop_event,  # Add this line
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

                if not self.stop_event.is_set():
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
                self.log_queue.put("Clearing previous log")
                self.log_text.delete(1.0, tk.END)  # Clear previous log
                self.stop_event.clear()  # Clear the stop event before starting

                years_to_process = self._get_years_to_process()
                if not years_to_process:
                    return

                kind = self.kind_var.get()
                base_path = self.output_dir.get()
                success_count = 0

                for year in years_to_process:
                    if self.stop_event.is_set():
                        break

                    self.log_queue.put(f"Processing year {year}")

                    # Download phase
                    downloaded, download_path = download_patents_pto(
                        year=year,
                        kind=kind,
                        callback=self.update_log,
                        stop_event=self.stop_event,
                    )

                    if not downloaded or self.stop_event.is_set():
                        self.log_queue.put(
                            f"Failed to download patents for year {year}"
                        )
                        continue

                    # Unzip phase
                    unzip_path = os.path.join(base_path, f"patent_{kind}s_{year}")
                    try:
                        unzip_files(
                            download_path,
                            unzip_path,
                            callback=self.update_log,
                            stop_event=self.stop_event,
                        )
                    except Exception as e:
                        self.log_queue.put(
                            f"Failed to unzip files for year {year}: {str(e)}"
                        )
                        continue

                    if self.stop_event.is_set():
                        continue

                    # Process and store in database
                    try:
                        extract_and_save_examples_in_db(
                            unzip_path,
                            callback=self.update_log,
                            stop_event=self.stop_event,
                        )
                        success_count += 1
                        self.log_queue.put(
                            f"Successfully processed and stored data for year {year}"
                        )
                    except Exception as e:
                        self.log_queue.put(
                            f"Failed to process data for year {year}: {str(e)}"
                        )
                        continue

                if not self.stop_event.is_set():
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

        self.active_thread = threading.Thread(target=run_download)
        self.active_thread.start()

    def view_database_tables(self):
        """Open a new window to view database tables."""
        db_window = tk.Toplevel(self.root)
        db_window.title("Database Tables")
        db_window.geometry("800x600")

        # Store window reference for refreshing
        self.db_window = db_window

        notebook = ttk.Notebook(db_window)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Create frames for each table
        examples_frame = ttk.Frame(notebook)
        self.statistics_frame = ttk.Frame(notebook)  # Store reference for refreshing

        notebook.add(examples_frame, text="Patent Examples")
        notebook.add(self.statistics_frame, text="Patent Statistics")

        # Store notebook reference
        self.db_notebook = notebook

        # Add treeviews to display tables
        self.create_table_view(examples_frame, "patent_examples")
        self.create_table_view(self.statistics_frame, "patent_statistics")

    def create_table_view(self, parent_frame, table_name):
        """Create a styled treeview to display a database table."""
        # Create frame for treeview and scrollbars
        frame = ttk.Frame(parent_frame)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Ensure db directory exists
        os.makedirs("./db", exist_ok=True)

        # Check if the table exists before trying to display it
        if not self.check_table_exists(table_name):
            # Display a message indicating the table doesn't exist
            message_frame = ttk.Frame(frame)
            message_frame.pack(fill=tk.BOTH, expand=True)

            message = f"The table '{table_name}' doesn't exist in the database yet.\n\n"
            if table_name == "patent_statistics":
                message += "This table will be created after running statistics analysis on patent data."
            else:
                message += "Please ensure you've processed patent data before viewing this table."

            message_label = ttk.Label(
                message_frame,
                text=message,
                font=("TkDefaultFont", 11),
                wraplength=600,
                justify=tk.CENTER,
            )
            message_label.pack(expand=True, pady=50)

            # Add a button to create the statistics table if it's the statistics table
            if table_name == "patent_statistics":
                ttk.Button(
                    message_frame,
                    text="Generate Statistics",
                    command=lambda: self.generate_statistics(
                        parent_frame
                    ),  # Pass frame for refresh
                ).pack(pady=10)

            return

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

        # Style configuration
        style = ttk.Style()
        style.configure("Treeview", rowheight=25)
        style.configure("Treeview.Heading", font=("Helvetica", 10, "bold"))
        style.map("Treeview", background=[("selected", "#0078D7")])

        # Create font for measurements
        default_font = tk.font.nametofont("TkDefaultFont")

        # Connect to database and fetch data
        with sqlite3.connect("./db/patents.db") as conn:
            cursor = conn.cursor()

            # Get column info and set up treeview columns
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            tree["columns"] = columns
            tree["show"] = "headings"  # Hide the first empty column

            # Configure columns
            for col in columns:
                tree.heading(
                    col,
                    text=col.replace("_", " ").title(),
                    command=lambda c=col: self.sort_treeview(tree, c, False),
                )
                tree.column(col, width=0)  # Start with 0 width to calculate later

            # Fetch and insert data
            try:
                rows_to_display = max(1, min(1000, int(self.rows_to_display.get())))
            except ValueError:
                rows_to_display = 10

            # Get total row count for pagination
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            total_rows = cursor.fetchone()[0]
            self.current_page = 0
            self.page_size = rows_to_display
            self.total_pages = (total_rows // rows_to_display) + (
                1 if total_rows % rows_to_display > 0 else 0
            )

            # Create pagination frame
            pagination_frame = ttk.Frame(parent_frame)
            pagination_frame.pack(fill=tk.X, padx=5, pady=5)

            ttk.Button(
                pagination_frame,
                text="<<",
                command=lambda: self.change_page(table_name, tree, 0),
            ).pack(side=tk.LEFT, padx=5)
            ttk.Button(
                pagination_frame,
                text="<",
                command=lambda: self.change_page(
                    table_name, tree, self.current_page - 1
                ),
            ).pack(side=tk.LEFT, padx=5)

            self.page_label = ttk.Label(
                pagination_frame, text=f"Page 1 of {self.total_pages}"
            )
            self.page_label.pack(side=tk.LEFT, padx=5)

            ttk.Button(
                pagination_frame,
                text=">",
                command=lambda: self.change_page(
                    table_name, tree, self.current_page + 1
                ),
            ).pack(side=tk.LEFT, padx=5)
            ttk.Button(
                pagination_frame,
                text=">>",
                command=lambda: self.change_page(
                    table_name, tree, self.total_pages - 1
                ),
            ).pack(side=tk.LEFT, padx=5)

            # Add search feature
            search_frame = ttk.Frame(parent_frame)
            search_frame.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)
            self.search_var = tk.StringVar()
            search_entry = ttk.Entry(
                search_frame, textvariable=self.search_var, width=30
            )
            search_entry.pack(side=tk.LEFT, padx=5)
            ttk.Button(
                search_frame,
                text="Search",
                command=lambda: self.search_table(table_name, tree, columns),
            ).pack(side=tk.LEFT, padx=5)
            ttk.Button(
                search_frame,
                text="Clear",
                command=lambda: self.clear_search(table_name, tree),
            ).pack(side=tk.LEFT, padx=5)

            # Add export button
            ttk.Button(
                search_frame,
                text="Export to CSV",
                command=lambda: self.export_to_csv(table_name),
            ).pack(side=tk.RIGHT, padx=5)

            # Load initial data
            self.load_table_data(table_name, tree, 0, rows_to_display)

            # Configure row colors
            tree.tag_configure("oddrow", background="#F0F0F8")
            tree.tag_configure("evenrow", background="#FFFFFF")

            # Auto-adjust column widths based on content
            for col in columns:
                max_width = (
                    max(
                        default_font.measure(str(tree.set(item, col)))
                        for item in tree.get_children()
                    )
                    + 20
                )  # Add padding
                header_width = default_font.measure(tree.heading(col)["text"]) + 20
                tree.column(col, width=min(300, max(100, max_width, header_width)))

        # Add tooltips for column headers - REPLACE THIS SECTION
        for col in columns:
            self.setup_column_tooltip(tree, col, col.replace("_", " ").title())

    def check_table_exists(self, table_name):
        """Check if a table exists in the database."""
        try:
            # Ensure the database directory exists
            os.makedirs("./db", exist_ok=True)

            # Get absolute path to database
            db_path = os.path.abspath("./db/patents.db")
            self.update_log(f"Checking for table {table_name} in database at {db_path}")

            # Check if database file exists
            if not os.path.isfile(db_path):
                self.update_log(f"Database file does not exist at {db_path}")
                return False

            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                )
                result = cursor.fetchone() is not None
                self.update_log(
                    f"Table {table_name} {'exists' if result else 'does not exist'} in database"
                )
                return result
        except sqlite3.Error as e:
            self.update_log(f"SQLite error checking for table {table_name}: {str(e)}")
            return False
        except Exception as e:
            self.update_log(f"Error checking for table {table_name}: {str(e)}")
            return False

    def generate_statistics(self, parent_frame=None):
        """Generate statistics for patent data and create the statistics table."""
        # Check if patent_examples table exists
        db_path = os.path.abspath("./db/patents.db")
        self.update_log(f"Using database at {db_path}")

        if not self.check_table_exists("patent_examples"):
            messagebox.showinfo(
                "No Data",
                "No patent examples found in database.\nPlease process patent data first before generating statistics.",
            )
            return

        # Ask for confirmation
        confirm = messagebox.askyesno(
            "Generate Statistics",
            "This will analyze the patent data and generate statistics.\nThis process may take some time. Continue?",
        )

        if not confirm:
            return

        # Start a thread to generate statistics
        def run_statistics():
            try:
                self.log_queue.put("Generating patent statistics...")
                self.stop_event.clear()

                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()

                    # First drop the table if it already exists to refresh data
                    cursor.execute("DROP TABLE IF EXISTS patent_statistics")

                    # Create the patent_statistics table
                    cursor.execute("""
                    CREATE TABLE IF NOT EXISTS patent_statistics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        year INTEGER,
                        kind TEXT,
                        total_patents INTEGER,
                        avg_claims_count REAL,
                        avg_example_length REAL,
                        most_common_words TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """)
                    conn.commit()

                    # Get years with data
                    cursor.execute(
                        "SELECT DISTINCT year FROM patent_examples ORDER BY year"
                    )
                    years = [row[0] for row in cursor.fetchall()]

                    if not years:
                        self.log_queue.put("No patent data found to analyze")
                        return

                    # Process each year
                    for year in years:
                        if self.stop_event.is_set():
                            break

                        self.log_queue.put(f"Analyzing patent data for year {year}...")

                        # Calculate statistics for this year
                        cursor.execute(
                            """
                        SELECT kind, COUNT(*) as total,
                               AVG(LENGTH(example_text)) as avg_length
                        FROM patent_examples 
                        WHERE year = ?
                        GROUP BY kind
                        """,
                            (year,),
                        )

                        stats_by_kind = cursor.fetchall()

                        for kind, total, avg_length in stats_by_kind:
                            # Insert into statistics table
                            cursor.execute(
                                """
                            INSERT INTO patent_statistics 
                            (year, kind, total_patents, avg_example_length)
                            VALUES (?, ?, ?, ?)
                            """,
                                (year, kind, total, avg_length),
                            )

                    conn.commit()

                    # Verify the table was created and has data
                    cursor.execute("SELECT COUNT(*) FROM patent_statistics")
                    count = cursor.fetchone()[0]
                    self.log_queue.put(
                        f"Added {count} statistics records to the database"
                    )

                    if not self.stop_event.is_set():
                        self.log_queue.put(
                            "Statistics generation completed successfully!"
                        )

                        # Refresh the statistics view in the main thread
                        self.root.after(
                            0, lambda: self.refresh_statistics_view(parent_frame)
                        )

            except Exception as e:
                self.log_queue.put(f"ERROR: Failed to generate statistics: {str(e)}")
                messagebox.showerror(
                    "Error", f"Failed to generate statistics: {str(e)}"
                )

        self.active_thread = threading.Thread(target=run_statistics)
        self.active_thread.start()

    def refresh_statistics_view(self, parent_frame):
        """Refresh the statistics view after generation."""
        try:
            # Clear the parent frame
            for widget in parent_frame.winfo_children():
                widget.destroy()

            # Recreate the table view
            self.create_table_view(parent_frame, "patent_statistics")

            # Show success message
            messagebox.showinfo(
                "Success",
                "Patent statistics have been generated.\nThe view has been refreshed with the new data.",
            )
        except Exception as e:
            self.update_log(f"Error refreshing statistics view: {str(e)}")
            messagebox.showerror("Error", f"Error refreshing view: {str(e)}")

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

    def setup_column_tooltip(self, tree, column, tooltip_text):
        """Set up tooltips for treeview column headers using direct bindings."""
        tooltip = None  # Variable to keep track of the current tooltip

        def show_tooltip(event):
            nonlocal tooltip
            # Check if the mouse is over a column header
            region = tree.identify_region(event.x, event.y)
            if region == "heading":
                # Get the column the mouse is over
                column_id = tree.identify_column(event.x)
                if column_id:
                    # Get the column name from the column id (e.g., '#1' -> first column)
                    col_idx = int(column_id[1:]) - 1
                    if (
                        col_idx >= 0
                        and col_idx < len(tree["columns"])
                        and tree["columns"][col_idx] == column
                    ):
                        # Show tooltip if mouse is over the target column
                        x, y = event.x_root, event.y_root
                        tooltip = tk.Toplevel(tree)
                        tooltip.wm_overrideredirect(True)
                        tooltip.wm_geometry(f"+{x + 10}+{y + 10}")
                        tooltip.wm_attributes("-topmost", True)
                        label = ttk.Label(
                            tooltip,
                            text=tooltip_text,
                            justify="left",
                            background="#FFFFEA",
                            relief="solid",
                            borderwidth=1,
                            font=("TkDefaultFont", 9, "normal"),
                            padding=(5, 3),
                        )
                        label.pack()

        def hide_tooltip(event):
            nonlocal tooltip
            if tooltip:
                tooltip.destroy()
                tooltip = None

        def on_motion(event):
            nonlocal tooltip
            # Hide tooltip if mouse moves away from the column header
            region = tree.identify_region(event.x, event.y)
            if region != "heading":
                hide_tooltip(event)
            else:
                # Check if mouse moved to a different column
                column_id = tree.identify_column(event.x)
                if column_id:
                    col_idx = int(column_id[1:]) - 1
                    if (
                        col_idx < 0
                        or col_idx >= len(tree["columns"])
                        or tree["columns"][col_idx] != column
                    ):
                        hide_tooltip(event)

        # Bind events to the treeview
        tree.bind("<Motion>", on_motion)
        tree.bind("<Enter>", show_tooltip)
        tree.bind("<Leave>", hide_tooltip)

    def load_table_data(self, table_name, tree, page, page_size):
        """Load a specific page of data into the treeview."""
        # Clear existing rows
        for item in tree.get_children():
            tree.delete(item)

        offset = page * page_size

        # Connect to database and fetch data
        with sqlite3.connect("./db/patents.db") as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {table_name} LIMIT {page_size} OFFSET {offset}"
            )
            rows = cursor.fetchall()

            # Insert rows with alternating colors
            for i, row in enumerate(rows):
                tag = "evenrow" if i % 2 == 0 else "oddrow"
                tree.insert("", tk.END, values=row, tags=(tag,))

        # Update page label
        self.current_page = page
        if hasattr(self, "page_label"):
            self.page_label.config(text=f"Page {page + 1} of {self.total_pages}")

    def change_page(self, table_name, tree, page):
        """Navigate to a specific page of data."""
        if 0 <= page < self.total_pages:
            self.load_table_data(table_name, tree, page, self.page_size)

    def search_table(self, table_name, tree, columns):
        """Search for data in the table."""
        search_term = self.search_var.get().strip()
        if not search_term:
            self.clear_search(table_name, tree)
            return

        # Clear existing rows
        for item in tree.get_children():
            tree.delete(item)

        # Construct WHERE clause for each column
        where_clauses = [f"{col} LIKE ?" for col in columns]
        search_params = [f"%{search_term}%" for _ in columns]

        # Connect to database and fetch matching data
        with sqlite3.connect("./db/patents.db") as conn:
            cursor = conn.cursor()
            query = f"SELECT * FROM {table_name} WHERE {' OR '.join(where_clauses)} LIMIT 1000"
            cursor.execute(query, search_params)
            rows = cursor.fetchall()

            # Insert rows with alternating colors
            for i, row in enumerate(rows):
                tag = "evenrow" if i % 2 == 0 else "oddrow"
                tree.insert("", tk.END, values=row, tags=(tag,))

        # Update status
        if hasattr(self, "page_label"):
            self.page_label.config(text=f"Search results: {len(rows)} items")

    def clear_search(self, table_name, tree):
        """Clear search and return to normal pagination."""
        if hasattr(self, "search_var"):
            self.search_var.set("")
        self.load_table_data(table_name, tree, 0, self.page_size)

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
    root = tk.Tk()
    app = PatentDownloaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
