"""
CLI module for Frame.io CLI
"""
import click
import logging
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from .commands.accounts import list_accounts, set_default_account
from .commands.workspaces import list_workspaces, set_default_workspace, delete_workspace
from .commands.projects import list_projects, set_default_project, get_project_details, show_project_details, change_directory, show_folder_contents, create_folder, delete_folder, rename_folder, upload_file, delete_file, get_file_metadata, update_file_metadata, list_file_metadata_fields, set_metadata_field_mapping
from .commands.custom_actions import add_custom_action, list_custom_actions, delete_custom_action
from .config import get_default_account, get_default_workspace, get_default_folder, set_client_credentials, get_rate_limit, set_rate_limit
import requests
import os

console = Console()

class RequestLogger:
    def __init__(self):
        self.logger = logging.getLogger('frame_io_cli')
        self.logger.setLevel(logging.DEBUG)
        
        # Create console handler
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        self.logger.addHandler(handler)
        
    def log_request(self, method, url, headers, body=None):
        if body:
            try:
                body = json.dumps(body, indent=2)
            except:
                pass
        
        self.logger.debug("\n" + "="*80 + "\nREQUEST:")
        self.logger.debug(f"{method} {url}")
        self.logger.debug("\nHeaders:")
        for key, value in headers.items():
            if key.lower() != 'authorization':  # Don't log auth token
                self.logger.debug(f"{key}: {value}")
        if body:
            self.logger.debug("\nBody:")
            self.logger.debug(body)
        self.logger.debug("="*80)
    
    def log_response(self, status_code, headers, body=None):
        if body:
            try:
                body = json.dumps(body, indent=2)
            except:
                pass
        
        self.logger.debug("\n" + "="*80 + "\nRESPONSE:")
        self.logger.debug(f"Status: {status_code}")
        self.logger.debug("\nHeaders:")
        for key, value in headers.items():
            self.logger.debug(f"{key}: {value}")
        if body:
            self.logger.debug("\nBody:")
            self.logger.debug(body)
        self.logger.debug("="*80)

request_logger = RequestLogger()

def enable_debug_logging():
    import logging
    logging.basicConfig(level=logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True

@click.group()
@click.option('--debug', '-d', is_flag=True, help='Enable debug mode to show API calls')
def cli(debug):
    """Frame.io CLI - A command-line interface for Frame.io"""
    if debug:
        enable_debug_logging()

@cli.command()
@click.option('--csv', is_flag=True, help='Output in CSV format')
@click.argument('account_id', required=False)
def accounts(account_id, csv):
    """List accounts or set default account by ID"""
    list_accounts(account_id, csv)

@cli.command()
@click.option('--account', help='Account ID to list workspaces for')
@click.option('--csv', is_flag=True, help='Output in CSV format')
@click.argument('name', required=False)
def workspaces(account, csv, name):
    """List workspaces or set default workspace by name"""
    list_workspaces(account, name, csv)

@cli.command()
@click.option('--account', help='Account ID to list workspaces for')
@click.option('--csv', is_flag=True, help='Output in CSV format')
@click.argument('name', required=False)
def ws(account, csv, name):
    """Alias for workspaces command"""
    list_workspaces(account, name, csv)

@cli.command()
@click.option('--account', help='Account ID to list projects for')
@click.option('--workspace', help='Workspace ID to list projects for')
@click.option('--all', is_flag=True, help='List projects from all workspaces')
@click.option('--csv', is_flag=True, help='Output in CSV format')
@click.argument('project_identifier', required=False)
def projects(account, workspace, all, csv, project_identifier):
    """List projects or set default project by ID or name"""
    list_projects(account, workspace, project_identifier, all, csv)

@cli.command()
@click.option('--account', help='Account ID to list projects for')
@click.option('--workspace', help='Workspace ID to list projects for')
@click.option('--all', is_flag=True, help='List projects from all workspaces')
@click.option('--csv', is_flag=True, help='Output in CSV format')
@click.argument('project_identifier', required=False)
def project(account, workspace, all, csv, project_identifier):
    """Alias for projects command"""
    list_projects(account, workspace, project_identifier, all, csv)

@cli.command()
@click.argument('folder_identifier', required=False)
@click.option('--account', help='Account ID to use')
def cd(folder_identifier, account):
    """Change to a different folder by name or ID
    
    FOLDER_IDENTIFIER can be:
    - A folder name: fio cd "My Folder"
    - A folder ID: fio cd 12345678-1234-1234-1234-123456789012
    - Go up one level: fio cd ..
    - An absolute path: fio cd "/Workspace/Project/Folder/Subfolder"
    
    Absolute paths follow the format: /{workspace}/{project}/{folder}/{subfolder}...
    This will automatically navigate through the hierarchy, setting the appropriate
    workspace, project, and folder as defaults.
    """
    change_directory(folder_identifier, account)

@cli.command()
def ls():
    """List contents of the current folder"""
    account_id = get_default_account()
    if not account_id:
        console.print("[red]No default account set. Please set a default account first.[/red]")
        return

    folder_id = get_default_folder()
    if not folder_id:
        console.print("[red]No default folder set. Please use 'fio cd' to navigate to a folder first.[/red]")
        return

    try:
        from .auth import get_access_token
        token = get_access_token()
        headers = {'Authorization': f'Bearer {token}'}
        url = f"https://api.frame.io/v4/accounts/{account_id}/folders/{folder_id}/children"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        folder_data = response.json()['data']
        show_folder_contents(folder_data)
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")

@cli.command()
@click.argument('name')
@click.option('--account', help='Account ID to use')
@click.option('--parent', help='Parent folder ID to create folder in')
def mkdir(name, account, parent):
    """Create a new folder in the current or specified parent folder"""
    create_folder(name, account, parent)

@cli.command()
@click.argument('folder_identifier')
@click.option('--account', help='Account ID to use')
def rmdir(folder_identifier, account):
    """Delete a folder by name or ID"""
    delete_folder(folder_identifier, account)

@cli.command()
@click.argument('folder_identifier')
@click.argument('new_name')
@click.option('--account', help='Account ID to use')
def renamedir(folder_identifier, new_name, account):
    """Rename a folder by name or ID"""
    rename_folder(folder_identifier, new_name, account)

@cli.command()
@click.argument('file_paths', nargs=-1, required=True)
@click.option('--md', is_flag=True, help='Extract and upload metadata from file')
@click.option('--debug', '-d', is_flag=True, help='Enable debug mode to show API calls')
def upload(file_paths, md, debug):
    """Upload files to the current folder.
    
    FILE_PATHS can be:
    - A single file: fio upload file.jpg
    - Multiple files: fio upload "file1.jpg" "file2.jpg"
    - A wildcard pattern: fio upload "*.jpg"
    - A folder: fio upload "./my_folder/"
    - All files and folders: fio upload *
    
    Note: Use quotes around file paths that contain spaces.
    When using '*' or folder paths, the command will:
    1. Check for folders in the current directory
    2. Compare them with folders in Frame.io
    3. Create missing folders
    4. Recursively upload files in each folder
    """
    if debug:
        enable_debug_logging()
    
    # Check if any path contains wildcards or is a directory
    has_wildcards_or_dirs = False
    for path in file_paths:
        if '*' in path or '?' in path or os.path.isdir(path):
            has_wildcards_or_dirs = True
            break
    
    if has_wildcards_or_dirs:
        # Use recursive upload with folder synchronization
        from .commands.projects import recursive_upload_with_folder_sync
        recursive_upload_with_folder_sync(file_paths, extract_metadata=md, debug=debug)
    else:
        # Use regular upload for individual files
        from .commands.projects import process_uploads
        process_uploads(file_paths, extract_metadata=md, debug=debug)

@cli.command()
@click.argument('file_identifier')
@click.option('--account-id', help='Account ID to use')
@click.option('--csv', is_flag=True, help='Output in CSV format')
def info(file_identifier, account_id, csv):
    """Get metadata for a file by name or ID"""
    from .commands.projects import get_file_metadata
    get_file_metadata(file_identifier, account_id, csv_output=csv)

@cli.command()
@click.argument('file_identifier')
@click.option('--account', help='Account ID to use')
@click.option('--debug', '-d', is_flag=True, help='Enable debug mode to show API calls')
@click.option('-Keywords', help='Keywords for the file')
@click.option('-Description', help='Description for the file')
@click.option('-Title', help='Title for the file')
@click.option('-Category', help='Category for the file')
@click.option('-Tags', help='Tags for the file')
def md(file_identifier, account, debug, **metadata_fields):
    """Update metadata for a file by name or ID"""
    if debug:
        enable_debug_logging()
    # Filter out None values
    metadata_fields = {k: v for k, v in metadata_fields.items() if v is not None}
    if not metadata_fields:
        console.print("[red]No metadata fields provided for update.[/red]")
        return
    update_file_metadata(file_identifier, account, debug=debug, **metadata_fields)

@cli.command()
@click.argument('file_identifiers', nargs=-1, required=True)
@click.option('--account', help='Account ID to use')
@click.option('--debug', '-d', is_flag=True, help='Enable debug mode to show API calls')
@click.option('--csv', is_flag=True, help='Output in CSV format')
def mdlist(file_identifiers, account, debug, csv):
    """List available metadata fields for files by name or ID.
    
    FILE_IDENTIFIERS can be:
    - A single file: fio mdlist file.jpg
    - Multiple files: fio mdlist "file1.jpg" "file2.jpg"
    - A wildcard pattern: fio mdlist "*.jpg"
    - All files: fio mdlist *
    
    Note: Use quotes around file paths that contain spaces.
    """
    if debug:
        enable_debug_logging()
    # If multiple files are provided, join them with a space
    file_identifier = ' '.join(file_identifiers)
    list_file_metadata_fields(file_identifier, account, csv)

@cli.command()
@click.option('--add', help='Add a new metadata mapping in format "field_id:display_name"')
@click.option('--rm', help='Remove a metadata mapping by display name')
@click.option('--list', 'list_mappings', is_flag=True, help='List all metadata mappings')
def mdmap(add, rm, list_mappings):
    """Manage metadata field mappings"""
    from .commands.projects import load_config, save_config
    config = load_config()
    metadata_mappings = config.get('metadata_mappings', {})

    if add:
        try:
            field_id, display_name = add.split(':', 1)
            if not is_valid_uuid(field_id):
                console.print("[red]Error:[/red] Invalid field ID format. Must be a valid UUID.")
                return
            metadata_mappings[field_id] = display_name
            config['metadata_mappings'] = metadata_mappings
            save_config(config)
            console.print(f"[green]Added mapping:[/green] {display_name} -> {field_id}")
        except ValueError:
            console.print("[red]Error:[/red] Invalid format. Use 'field_id:display_name'")
            return

    if rm:
        # Find the field ID by display name
        field_id = None
        for fid, name in metadata_mappings.items():
            if name.lower() == rm.lower():
                field_id = fid
                break
        
        if field_id:
            del metadata_mappings[field_id]
            config['metadata_mappings'] = metadata_mappings
            save_config(config)
            console.print(f"[green]Removed mapping:[/green] {rm} -> {field_id}")
        else:
            console.print(f"[red]Error:[/red] No mapping found for '{rm}'")
            return

    if list_mappings or not (add or rm):
        if not metadata_mappings:
            console.print("[yellow]No metadata mappings defined.[/yellow]")
            return

        table = Table(title="Metadata Field Mappings")
        table.add_column("Field ID", style="cyan")
        table.add_column("Display Name", style="green")
        for field_id, display_name in metadata_mappings.items():
            table.add_row(field_id, display_name)
        console.print(table)

@cli.command()
@click.option('--add', is_flag=True, help='Add a new custom action')
@click.option('--description', help='Description for the custom action')
@click.option('--event', help='Event name for the custom action')
@click.option('--name', help='Name for the custom action')
@click.option('--url', help='URL for the custom action')
@click.option('--account', help='Account ID to use')
@click.option('--workspace', help='Workspace ID to use')
@click.option('--list', 'list_actions', is_flag=True, help='List custom actions')
@click.option('--csv', is_flag=True, help='Output in CSV format')
@click.option('--delete', is_flag=True, help='Delete a custom action')
@click.option('--id', 'action_id', help='Action ID to delete')
def custom_action(add, description, event, name, url, account, workspace, list_actions, csv, delete, action_id):
    """Manage custom actions for workspaces
    
    Examples:
    - Add a custom action: fio custom-action --add --description "My description" --event "com.adobe.firefly.image.generate" --name "Generate Image" --url "https://example.com"
    - List custom actions: fio custom-action --list
    - Delete by ID: fio custom-action --delete --id abc12345
    - Delete by name: fio custom-action --delete --name "Generate Image"
    """
    if add:
        if not all([description, event, name, url]):
            console.print("[red]Error:[/red] When adding a custom action, all of --description, --event, --name, and --url are required.")
            return
        add_custom_action(description, event, name, url, account, workspace)
    elif list_actions:
        list_custom_actions(account, workspace, csv)
    elif delete:
        if not action_id and not name:
            console.print("[red]Error:[/red] When deleting a custom action, either --id or --name must be provided.")
            return
        delete_custom_action(action_id, name, account, workspace)
    else:
        console.print("[red]Error:[/red] Please specify either --add to create a custom action, --list to view existing actions, or --delete to remove an action.")

@cli.command()
@click.argument('client_id')
@click.argument('client_secret')
def set_credentials(client_id, client_secret):
    """Set Frame.io client credentials in the config file."""
    try:
        set_client_credentials(client_id, client_secret)
        console.print("[green]Client credentials saved successfully![/green]")
    except Exception as e:
        console.print(f"[red]Error saving credentials:[/red] {str(e)}")

@cli.command()
@click.argument('requests_per_minute', type=int)
def rate_limit(requests_per_minute):
    """Set the rate limit for API requests (requests per minute)"""
    if requests_per_minute < 1:
        console.print("[red]Rate limit must be at least 1 request per minute[/red]")
        return
    
    set_rate_limit(requests_per_minute)
    console.print(f"[green]Rate limit set to {requests_per_minute} requests per minute[/green]")

@cli.command()
def show_rate_limit():
    """Show the current rate limit setting"""
    current_limit = get_rate_limit()
    console.print(f"[blue]Current rate limit: {current_limit} requests per minute[/blue]")

if __name__ == '__main__':
    cli() 