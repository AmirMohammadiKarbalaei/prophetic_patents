# USPTO Patent Analyser GUI Documentation

## Overview
The USPTO Patent Analyser is a graphical application that helps users download, process, and analyse patent data from the USPTO database. The application provides functionality for:
- Downloading patent files
- Unzipping downloaded files
- Processing patent data
- Viewing and analysing patent statistics
- Exporting data to CSV format

## Main Functions

### 1. Download Patents
**Function**: `download_patents_only()`  
**Purpose**: Downloads patent files from the USPTO database for specified years.  
**How to use**:
1. Select patent type (Grant or Application)
2. Choose year(s) to download (single year or range)
3. Set output directory
4. Click "Download Patents" button

### 2. Unzip Patent Files
**Function**: `unzip_patents_only()`  
**Purpose**: Extracts downloaded patent files from ZIP format.  
**How to use**:
1. Ensure patents are downloaded
2. Click "Unzip Patent Files" button
3. Files will be extracted to the specified output directory

### 3. Process Patent Data
**Function**: `process_patents_only()`  
**Purpose**: Analyses patent files to extract examples and statistics.  
**How to use**:
1. Ensure files are unzipped
2. Set number of concurrent files (1-8 recommended)
3. Click "Process Patent Data" button

### 4. Complete Process
**Function**: `download_patents()`  
**Purpose**: Executes all three steps (download, unzip, process) in sequence.  
**How to use**:
1. Configure all settings
2. Click "Run Complete Process" button

### 5. View Database Tables
**Function**: `view_database_tables()`  
**Purpose**: Displays processed patent data in a tabulated format.  
**How to use**:
1. Click "View Database Tables" button
2. Use tabs to switch between different data views
3. Double-click entries to view full details
4. Use pagination controls to navigate through data

## Key Features

### Data Navigation
- **Pagination**: Navigate through large datasets using page controls
- **Sorting**: Click column headers to sort data

### Data Export
**Function**: `export_to_csv()`  
**Purpose**: Exports table data to CSV format.  
**How to use**:
1. View database tables
2. Click "Export to CSV" button
3. Choose save location

### Tooltips
- Hover over column headers for descriptions
- Tooltips provide additional information about functionality

## Input Validation

### Year Validation
**Function**: `validate_year()`
- Accepts years between 1976 and 2025
- Validates both single years and ranges

### Patent Type Validation
**Function**: `validate_kind()`
- Accepts either "grant" or "application"
- Ensures proper USPTO database selection

### Concurrent Files Validation
- Accepts values between 1 and 16
- Recommended range: 1-8 files

## Error Handling
- Displays error messages in log window
- Prevents invalid operations
- Provides feedback for all operations

## Process Control
**Function**: `stop_operation()`  
**Purpose**: Safely stops running operations.  
**How to use**:
1. Click "Stop" button during any operation
2. Wait for current process to complete safely

## Interface Elements

### Main Controls
- Patent Type selection (Grant/Application)
- Year Selection (Single/Range)
- Output Directory setting
- Concurrent Files control
- Rows to Display setting

### Progress Monitoring
- Log window shows real-time progress
- Status messages for all operations
- Error reporting and feedback

### Data Viewing
- Table view with sortable columns
- Pagination controls
- Export functionality
- Detailed view for individual records

## Best Practices

1. **Resource Management**
   - Start with smaller date ranges for testing
   - Use recommended concurrent files range (1-8)
   - Monitor system resources during processing

2. **Data Organisation**
   - Use dedicated output directories
   - Maintain consistent naming conventions
   - Regular data exports for backup

3. **Error Recovery**
   - Check log messages for issues
   - Use stop button for safe process termination
   - Verify input parameters before long operations

## Technical Requirements
- Python 3.x
- Required libraries: tkinter, sqlite3, requests, beautifulsoup4
- Sufficient disk space for patent data
- Internet connection for downloads
