# Prophetic Patents Analysis Tool

## Overview
This tool provides both a graphical user interface (GUI) and command-line interface (CLI) for analysing and processing Patents from United States Patent and Trademark Office (USPTO). It is designed to help researchers and analysts work with patent datasets efficiently.

## Features
- Interactive GUI for patent data analysis and visualisation
- Command-line interface for batch processing and automation
- Patent data extraction and processing and classification

## Components

### [GUI Application (USPTO_Patent_Analyser.py)](https://drive.google.com/file/d/1Dx9eSOApGypDGTTVP4plUuvdMd44mXK-/view?usp=sharing)
The graphical interface provides:
- Interactive application for patent analysis and processing
- Automated yearly patent file downloading and unzipping from USPTO
- Patent text processing and  example extraction
- Advanced tense classification and comprehensive patent statistics

### Command Line Tool (`patents_cli`)
The CLI tool enables:
- Batch processing of patent data
- Automated data extraction
- Script-based workflows
- Integration with other tools

## Installation


### Prerequisites
- Python 3.7+
- Required Python packages (install via pip):
  ```
  pip install -r requirements.txt
  ```

### Setup
1. Clone the repository
2. Install dependencies
3. Configure data directories

## Usage

### USPTO_Patent_Analyser
The applciation can be accessed from: [USPTO_Patent_Analyser](https://drive.google.com/file/d/1Dx9eSOApGypDGTTVP4plUuvdMd44mXK-/view?usp=sharing)

### GUI Application
To launch the GUI:
```bash
python gui.py
```

### CLI Tool
Basic command structure:
```bash
python patents_cli [options] [command]
```

## Data Management
- Patent data files are stored in the `patents_data` directory
- Processed data is saved in appropriate formats
- Temporary files are automatically cleaned up

## Documentation
The project includes detailed documentation for both the GUI application and CLI tool:

### GUI Documentation
- **User Guide**: Comprehensive walkthrough of the GUI features
- **Download Instructions**: Steps for downloading and processing USPTO patent files
- **Analysis Guide**: Instructions for patent analysis and classification

### CLI Documentation
- **Command Reference**: Complete list of available commands and options
- **Batch Processing**: Guide for automated patent processing

For detailed documentation, please refer to the following resources:
- [GUI Documentation](docs/gui_documentation.md)
- [CLI Tool Documentation](docs/patent_cli.md)
