# Frame.io CLI

A command-line interface for interacting with the Frame.io API.

## Installation

```bash
pip install frame-io-v4-cli
```

## Configuration

1. Create a `.env` file in your home directory with your Frame.io API credentials:
```bash
FRAME_CLIENT_ID=your_client_id
FRAME_CLIENT_SECRET=your_client_secret
```

2. Initialize the CLI:
```bash
fio init
```

## Usage

### Authentication and Setup

```bash
fio init                    # Initialize the CLI with your credentials
fio accounts                # List available accounts
fio set-account <id>        # Set default account
fio workspaces              # List workspaces
fio set-workspace <id>      # Set default workspace
fio projects                # List projects
fio set-project <id>        # Set default project
```

### Navigation

```bash
fio cd <folder_id>          # Change to a specific folder
fio cd ..                   # Move up one level
fio cd /                    # Go to root folder
fio pwd                     # Show current folder path
fio ls                      # List contents of current folder
```

### File Operations

#### Upload Files
```bash
# Upload a single file
fio upload file.jpg

# Upload multiple files with wildcards
fio upload "*.jpg"          # Upload all JPG files
fio upload "*.mp4"          # Upload all MP4 files
fio upload *                # Upload all files

# Upload files from a directory
fio upload folder/*         # Upload all files in a folder
fio upload folder/          # Upload all files in a folder

# Upload with metadata extraction
fio upload --md file.jpg    # Upload and extract metadata
fio upload --md "*.jpg"     # Upload all JPGs with metadata
fio upload --md *           # Upload all files with metadata

# Debug mode for troubleshooting
fio upload --debug file.jpg # Show detailed API requests
```

#### Download Files
```bash
fio download <file_id>      # Download a file
fio download <file_id> -o custom_name.jpg  # Download with custom name
```

#### File Management
```bash
fio mv <file_id> <folder_id>  # Move file to another folder
fio cp <file_id> <folder_id>  # Copy file to another folder
fio rm <file_id>              # Delete a file
fio rename <file_id> <name>   # Rename a file
```

### Folder Operations

```bash
fio mkdir <name>            # Create a new folder
fio rmdir <folder_id>       # Delete a folder
fio rename-folder <folder_id> <name>  # Rename a folder
```

### Metadata Operations

```bash
fio mdlist <file_id>        # List all metadata fields for a file
fio mdset <file_id> <field_id> <value>  # Set metadata field value
```

### Rate Limiting

The CLI includes configurable rate limiting to prevent overwhelming the API:

```bash
fio rate-limit 20           # Set rate limit to 20 requests per minute
fio show-rate-limit         # Show current rate limit setting
```

Default rate limit is 10 requests per minute. This is particularly useful when:
- Uploading multiple files in parallel
- Making bulk metadata updates
- Working with large numbers of files

### Advanced Features

#### Parallel Uploads
The upload command automatically uses parallel processing to speed up multiple file uploads:
- Uses 5 worker threads by default
- Maintains rate limiting across all parallel uploads
- Shows real-time progress for each file
- Provides a summary of successful and failed uploads

#### Metadata Extraction
When using the `--md` flag, the CLI will:
1. Upload the file
2. Extract metadata from the file
3. Map the metadata to Frame.io fields
4. Update the file's metadata automatically

#### Debug Mode
Use `--debug` flag to see:
- Detailed API requests and responses
- Rate limiting information
- Upload progress details
- Error messages and stack traces

## Development

### Project Structure
```
frame-io-v4-cli/
├── fio/
│   ├── __init__.py
│   ├── cli.py              # CLI command definitions
│   ├── config.py           # Configuration management
│   ├── auth.py             # Authentication handling
│   └── commands/
│       ├── __init__.py
│       ├── accounts.py     # Account management
│       ├── workspaces.py   # Workspace operations
│       ├── projects.py     # Project and file operations
│       └── metadata.py     # Metadata handling
├── tests/                  # Test suite
├── setup.py               # Package configuration
└── README.md             # This file
```

### Running Tests
```bash
pytest
```

### Building the Package
```bash
python setup.py sdist bdist_wheel
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
