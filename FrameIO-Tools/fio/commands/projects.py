"""
Projects command module for Frame.io CLI
"""
import json
import os
import webbrowser
import time
from pathlib import Path
import requests
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..config import (
    API_BASE_URL, get_default_account, get_default_workspace,
    set_default_project, get_default_project, set_default_folder,
    get_default_folder, load_config, save_config, get_rate_limit
)
from ..utils import is_valid_uuid
import subprocess
import glob
import threading
import csv
import sys
from io import StringIO

console = Console()

# Cache file path
CACHE_FILE = Path.home() / '.fio' / 'project_cache.json'
HISTORY_FILE = Path.home() / '.fio' / 'folder_history.json'

class RateLimiter:
    def __init__(self, requests_per_minute):
        self.rate = requests_per_minute
        self.tokens = requests_per_minute
        self.last_update = time.time()
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            now = time.time()
            time_passed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + time_passed * (self.rate / 60.0))
            self.last_update = now

            if self.tokens < 1:
                sleep_time = (1 - self.tokens) * (60.0 / self.rate)
                time.sleep(sleep_time)
                self.tokens = 0
            else:
                self.tokens -= 1

def ensure_cache_dir():
    """Ensure the cache directory exists."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CACHE_FILE.exists():
        with open(CACHE_FILE, 'w') as f:
            json.dump({"projects": {}}, f)
    if not HISTORY_FILE.exists():
        with open(HISTORY_FILE, 'w') as f:
            json.dump({"history": []}, f)

def get_folder_history():
    """Get the folder navigation history."""
    ensure_cache_dir()
    with open(HISTORY_FILE, 'r') as f:
        return json.load(f)['history']

def save_folder_history(history):
    """Save the folder navigation history."""
    ensure_cache_dir()
    with open(HISTORY_FILE, 'w') as f:
        json.dump({"history": history}, f, indent=2)

def get_project_by_name(name, account_id=None, workspace_id=None):
    """Get project ID by name."""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No account specified and no default account set.[/red]")
            return None

    if not workspace_id:
        workspace_id = get_default_workspace()
        if not workspace_id:
            console.print("[red]No workspace specified and no default workspace set.[/red]")
            return None

    ensure_cache_dir()
    with open(CACHE_FILE, 'r') as f:
        cache = json.load(f)
    
    # Look for exact match first
    for proj_id, proj_info in cache.get('projects', {}).items():
        if (proj_info['name'].lower() == name.lower() and 
            proj_info['account_id'] == account_id and 
            proj_info['workspace_id'] == workspace_id):
            return proj_id
    
    # If no exact match, look for partial matches
    matches = []
    for proj_id, proj_info in cache.get('projects', {}).items():
        if (name.lower() in proj_info['name'].lower() and 
            proj_info['account_id'] == account_id and 
            proj_info['workspace_id'] == workspace_id):
            matches.append((proj_id, proj_info['name']))
    
    if len(matches) == 1:
        return matches[0][0]
    elif len(matches) > 1:
        console.print("[yellow]Multiple matches found:[/yellow]")
        for proj_id, proj_name in matches:
            console.print(f"  {proj_name} ({proj_id})")
        return None
    return None

def get_project_details(project_id, account_id=None, workspace_id=None):
    """Get details for a specific project."""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No account specified and no default account set.[/red]")
            return None

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {'Authorization': f'Bearer {token}'}
        url = f"{API_BASE_URL}/accounts/{account_id}/projects/{project_id}"
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        return None

def open_project_url(project_data):
    """Open project view URL in default browser."""
    if not project_data or 'view_url' not in project_data:
        console.print("[red]No view URL available for this project.[/red]")
        return False

    try:
        webbrowser.open(project_data['view_url'])
        console.print(f"[green]Opening project in browser:[/green] {project_data['view_url']}")
        return True
    except Exception as e:
        console.print(f"[red]Error opening browser:[/red] {str(e)}")
        return False

def list_folder_contents(folder_id, account_id=None):
    """List contents of a folder."""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No account specified and no default account set.[/red]")
            return None

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {'Authorization': f'Bearer {token}'}
        url = f"{API_BASE_URL}/accounts/{account_id}/folders/{folder_id}/children"
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()['data']
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        return None

def show_folder_contents(folder_data):
    """Display folder contents in a formatted table."""
    if not folder_data:
        return

    table = Table(title="Folder Contents", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="green", width=50)  # Increased width to accommodate ID
    table.add_column("Created", style="magenta", width=12)
    table.add_column("Updated", style="blue", width=12)
    
    for item in folder_data:
        # Add folder emoji for folders, file emoji for files
        prefix = "📁 " if item['type'] == 'folder' else "📄 "
        
        # Format dates to YYYY-MM-dd
        created = item.get('created_at', 'N/A')
        updated = item.get('updated_at', 'N/A')
        if created != 'N/A':
            created = created.split('T')[0]
        if updated != 'N/A':
            updated = updated.split('T')[0]
            
        # Combine name and ID with newline
        name_with_id = f"{prefix}{item['name']}\n({item['id']})"
            
        table.add_row(
            name_with_id,
            created,
            updated
        )
    
    console.print(table)

def show_project_details(project_data, open_browser=False):
    """Display project details in a formatted panel."""
    if not project_data:
        return

    # Create a formatted string with project details
    details = [
        f"[bold cyan]Name:[/bold cyan] {project_data['name']}",
        f"[bold cyan]ID:[/bold cyan] {project_data['id']}",
        f"[bold cyan]Description:[/bold cyan] {project_data.get('description', 'N/A')}",
        f"[bold cyan]Created:[/bold cyan] {project_data['created_at']}",
        f"[bold cyan]Updated:[/bold cyan] {project_data['updated_at']}",
        f"[bold cyan]Storage:[/bold cyan] {project_data.get('storage', 'N/A')} bytes",
        f"[bold cyan]View URL:[/bold cyan] {project_data.get('view_url', 'N/A')}",
        f"[bold cyan]Workspace ID:[/bold cyan] {project_data['workspace_id']}",
        f"[bold cyan]Root Folder ID:[/bold cyan] {project_data.get('root_folder_id', 'N/A')}"
    ]

    # Add owner information if available
    if 'owner' in project_data:
        details.extend([
            "\n[bold cyan]Owner:[/bold cyan]",
            f"  Name: {project_data['owner'].get('name', 'N/A')}",
            f"  Email: {project_data['owner'].get('email', 'N/A')}",
            f"  ID: {project_data['owner'].get('id', 'N/A')}"
        ])

    # Create and display the panel
    panel = Panel(
        "\n".join(details),
        title="Project Details",
        border_style="green"
    )
    console.print(panel)

    # Set default folder if root_folder_id is available
    if 'root_folder_id' in project_data:
        set_default_folder(project_data['root_folder_id'])
        # List folder contents
        folder_contents = list_folder_contents(project_data['root_folder_id'])
        if folder_contents:
            show_folder_contents(folder_contents)

    # Open in browser if requested
    if open_browser:
        open_project_url(project_data)

def show_default_project():
    """Show details of the default project."""
    project_id = get_default_project()
    if not project_id:
        console.print("[yellow]No default project set.[/yellow]")
        return

    project_data = get_project_details(project_id)
    if project_data:
        show_project_details(project_data)
    else:
        console.print("[yellow]Could not fetch default project details.[/yellow]")

def delete_project(project_id, account_id=None):
    """Delete a project after confirmation."""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No account specified and no default account set.[/red]")
            return False

    # Get project details for confirmation
    project_data = get_project_details(project_id, account_id)
    if not project_data:
        console.print(f"[red]Could not find project with ID:[/red] {project_id}")
        return False

    # Confirm deletion
    if not click.confirm(f"Are you sure you want to delete project '{project_data['name']}' ({project_id})?"):
        console.print("[yellow]Deletion cancelled.[/yellow]")
        return False

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {'Authorization': f'Bearer {token}'}
        url = f"{API_BASE_URL}/accounts/{account_id}/projects/{project_id}"
        
        response = requests.delete(url, headers=headers)
        response.raise_for_status()

        # Remove from cache if it exists
        ensure_cache_dir()
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
        
        if project_id in cache.get('projects', {}):
            del cache['projects'][project_id]
            with open(CACHE_FILE, 'w') as f:
                json.dump(cache, f, indent=4)

        console.print(f"[green]Successfully deleted project:[/green] {project_data['name']} ({project_id})")
        return True

    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error deleting project:[/red] {str(e)}")
        return False

def rename_project(project_id, new_name, account_id=None):
    """Rename a project."""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No account specified and no default account set.[/red]")
            return False

    # Get current project details for confirmation
    project_data = get_project_details(project_id, account_id)
    if not project_data:
        console.print(f"[red]Could not find project with ID:[/red] {project_id}")
        return False

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        url = f"{API_BASE_URL}/accounts/{account_id}/projects/{project_id}"
        
        # Prepare the request body
        data = {
            "data": {
                "name": new_name
            }
        }
        
        response = requests.patch(url, headers=headers, json=data)
        response.raise_for_status()

        # Update cache with new name
        ensure_cache_dir()
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
        
        if project_id in cache.get('projects', {}):
            cache['projects'][project_id]['name'] = new_name
            with open(CACHE_FILE, 'w') as f:
                json.dump(cache, f, indent=4)

        console.print(f"[green]Successfully renamed project from '{project_data['name']}' to '{new_name}'[/green]")
        return True

    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error renaming project:[/red] {str(e)}")
        return False

def create_project(name, account_id=None, workspace_id=None, set_default=False, open_browser=False):
    """Create a new project."""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No account specified and no default account set.[/red]")
            return False

    if not workspace_id:
        workspace_id = get_default_workspace()
        if not workspace_id:
            console.print("[red]No workspace specified and no default workspace set.[/red]")
            return False

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        url = f"{API_BASE_URL}/accounts/{account_id}/workspaces/{workspace_id}/projects"
        
        # Prepare the request body
        data = {
            "data": {
                "name": name
            }
        }
        
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        project_data = response.json()['data']

        # Update cache with new project
        ensure_cache_dir()
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
        
        cache['projects'][project_data['id']] = {
            'name': project_data['name'],
            'account_id': account_id,
            'workspace_id': workspace_id,
            'created_at': project_data.get('created_at'),
            'updated_at': project_data.get('updated_at'),
            'status': project_data.get('status'),
            'description': project_data.get('description')
        }
        
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=4)

        # Show project details
        show_project_details(project_data, open_browser)

        # Handle default project setting
        if set_default:
            set_default_project(project_data['id'])
            console.print(f"[green]Set as default project[/green]")
        else:
            if click.confirm("Would you like to set this as your default project?"):
                set_default_project(project_data['id'])
                console.print(f"[green]Set as default project[/green]")

        return True

    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error creating project:[/red] {str(e)}")
        return False

def list_projects(account_id=None, workspace_id=None, name=None, all_workspaces=False, csv_output=False):
    """List all projects for the specified or default account/workspace."""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No account specified and no default account set.[/red]")
            return False

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {'Authorization': f'Bearer {token}'}

        # If listing all workspaces, get workspaces first
        if all_workspaces:
            # Get all workspaces
            url = f"{API_BASE_URL}/accounts/{account_id}/workspaces"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            workspaces = response.json()['data']

            # Collect all projects from all workspaces
            all_projects = []
            for workspace in workspaces:
                url = f"{API_BASE_URL}/accounts/{account_id}/workspaces/{workspace['id']}/projects"
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                projects = response.json()['data']
                
                # Add workspace name to each project
                for project in projects:
                    project['workspace_name'] = workspace['name']
                all_projects.extend(projects)

            # Sort projects by name
            all_projects.sort(key=lambda x: x['name'].lower())

            if csv_output:
                # Create CSV output
                output = StringIO()
                writer = csv.writer(output)
                
                # Write header
                writer.writerow(['Name', 'Workspace', 'Created', 'Updated', 'URL'])
                
                # Write data rows
                for project in all_projects:
                    writer.writerow([
                        project['name'],
                        project['workspace_name'],
                        project['created_at'].split('T')[0],
                        project['updated_at'].split('T')[0],
                        project.get('view_url', 'N/A')
                    ])
                
                # Print CSV to stdout
                print(output.getvalue())
                return True

            # Create table with all columns
            table = Table(title="All Projects", show_header=True, header_style="bold magenta")
            table.add_column("Name", style="green", width=40)
            table.add_column("Workspace", style="cyan", width=20)
            table.add_column("Created", style="magenta", width=12)
            table.add_column("Updated", style="blue", width=12)
            table.add_column("URL", style="blue", no_wrap=True)

            # Add projects to table
            for project in all_projects:
                table.add_row(
                    project['name'],
                    project['workspace_name'],
                    project['created_at'].split('T')[0],
                    project['updated_at'].split('T')[0],
                    project.get('view_url', 'N/A')
                )

            console.print(table)
            return True

        # If not listing all workspaces, use the original logic
        if not workspace_id:
            workspace_id = get_default_workspace()
            if not workspace_id:
                console.print("[red]No workspace specified and no default workspace set.[/red]")
                return False

        url = f"{API_BASE_URL}/accounts/{account_id}/workspaces/{workspace_id}/projects"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        projects = response.json()['data']

        # Update cache with latest project information
        ensure_cache_dir()
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
        
        for project in projects:
            cache['projects'][project['id']] = {
                'name': project['name'],
                'account_id': account_id,
                'workspace_id': workspace_id,
                'created_at': project.get('created_at'),
                'updated_at': project.get('updated_at'),
                'status': project.get('status'),
                'description': project.get('description')
            }
        
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=4)

        # If a name is provided, search for matching projects
        if name:
            found_projects = []
            for project in projects:
                if name.lower() in project['name'].lower():
                    found_projects.append(project)

            if not found_projects:
                console.print(f"[red]No projects found with name containing '{name}'[/red]")
                return False
            elif len(found_projects) > 1:
                console.print("[yellow]Multiple projects found:[/yellow]")
                for project in found_projects:
                    console.print(f"  - {project['name']} ({project['id']})")
                return False
            else:
                # If exactly one match is found, set it as default and show details
                project = found_projects[0]
                set_default_project(project['id'])
                show_project_details(project)
                return True

        if csv_output:
            # Create CSV output
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['Name', 'Created', 'Updated', 'URL'])
            
            # Write data rows
            for project in projects:
                writer.writerow([
                    project['name'],
                    project['created_at'].split('T')[0],
                    project['updated_at'].split('T')[0],
                    project.get('view_url', 'N/A')
                ])
            
            # Print CSV to stdout
            print(output.getvalue())
            return True

        # If no name provided, show all projects
        table = Table(title="Projects", show_header=True, header_style="bold magenta")
        table.add_column("Name", style="green", width=50)
        table.add_column("Created", style="magenta", width=12)
        table.add_column("Updated", style="blue", width=12)
        
        for project in projects:
            # Combine name and ID with newline, adding project emoji
            name_with_id = f"📋 {project['name']}\n({project['id']})"
            table.add_row(
                name_with_id,
                project['created_at'].split('T')[0],
                project['updated_at'].split('T')[0]
            )
        
        console.print(table)
        return True

    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        return False

def change_directory(folder_identifier, account_id=None):
    """Change to a different folder by name or ID."""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No account specified and no default account set.[/red]")
            return False

    # Handle absolute paths (starting with '/')
    if folder_identifier and folder_identifier.startswith('/'):
        return navigate_to_path(folder_identifier, account_id)

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {'Authorization': f'Bearer {token}'}

        # Handle going up one level with '..'
        if folder_identifier == '..':
            history = get_folder_history()
            if not history:
                console.print("[yellow]No folder history available.[/yellow]")
                return False

            # Get the previous folder from history
            previous_folder = history.pop()
            save_folder_history(history)
            
            # Set as default folder
            set_default_folder(previous_folder)
            
            # Get folder name directly from folder endpoint
            url = f"{API_BASE_URL}/accounts/{account_id}/folders/{previous_folder}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            folder_data = response.json()['data']
            folder_name = folder_data['name']
            
            # Get and display new folder contents
            url = f"{API_BASE_URL}/accounts/{account_id}/folders/{previous_folder}/children"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            folder_data = response.json()['data']

            console.print(f"\n[green]Changed to previous folder: {folder_name}[/green]")
            show_folder_contents(folder_data)
            return True

        # If folder_identifier is not a UUID, try to find it by name
        if not len(folder_identifier) == 36:
            # Get current folder contents to search for the name
            current_folder_id = get_default_folder()
            if not current_folder_id:
                console.print("[red]No default folder set.[/red]")
                return False

            url = f"{API_BASE_URL}/accounts/{account_id}/folders/{current_folder_id}/children"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            folder_data = response.json()['data']

            # Search for folder by name
            found_folders = []
            for item in folder_data:
                if item['type'] == 'folder' and folder_identifier.lower() in item['name'].lower():
                    found_folders.append(item)

            if not found_folders:
                console.print(f"[red]No folder found with name containing '{folder_identifier}'[/red]")
                return False
            elif len(found_folders) > 1:
                console.print("[yellow]Multiple folders found:[/yellow]")
                for folder in found_folders:
                    console.print(f"  - {folder['name']} ({folder['id']})")
                return False
            else:
                folder_id = found_folders[0]['id']
        else:
            folder_id = folder_identifier

        # Save current folder to history before changing
        current_folder = get_default_folder()
        if current_folder:
            history = get_folder_history()
            history.append(current_folder)
            save_folder_history(history)

        # Set as default folder
        set_default_folder(folder_id)
        
        # Get folder name directly from folder endpoint
        url = f"{API_BASE_URL}/accounts/{account_id}/folders/{folder_id}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        folder_data = response.json()['data']
        folder_name = folder_data['name']
        
        # Get and display new folder contents
        url = f"{API_BASE_URL}/accounts/{account_id}/folders/{folder_id}/children"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        folder_data = response.json()['data']

        console.print(f"\n[green]Changed to folder: {folder_name}[/green]")
        show_folder_contents(folder_data)
        return True

    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        return False

def create_folder(name, account_id=None, parent_folder_id=None):
    """Create a new folder in the current or specified parent folder."""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No account specified and no default account set.[/red]")
            return False

    if not parent_folder_id:
        parent_folder_id = get_default_folder()
        if not parent_folder_id:
            console.print("[red]No parent folder specified and no default folder set.[/red]")
            return False

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        url = f"{API_BASE_URL}/accounts/{account_id}/folders/{parent_folder_id}/folders"
        payload = {
            "data": {
                "name": name
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        folder_data = response.json()['data']
        
        # Show success message with folder details
        console.print(f"\n[green]Created new folder:[/green] {folder_data['name']}")
        console.print(f"Folder ID: {folder_data['id']}")
        console.print(f"Created at: {folder_data['created_at']}")
        
        # Optionally set as default folder
        if click.confirm("Set as current folder?"):
            set_default_folder(folder_data['id'])
            console.print("[green]Set as current folder[/green]")
            
            # List contents of the new folder
            folder_contents = list_folder_contents(folder_data['id'], account_id)
            if folder_contents:
                show_folder_contents(folder_contents)
        
        return True

    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error creating folder:[/red] {str(e)}")
        return False

def delete_folder(folder_identifier, account_id=None):
    """Delete a folder by name or ID."""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No account specified and no default account set.[/red]")
            return False

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {'Authorization': f'Bearer {token}'}

        # If folder_identifier is not a UUID, try to find it by name
        if not len(folder_identifier) == 36:
            # Get current folder contents to search for the name
            current_folder_id = get_default_folder()
            if not current_folder_id:
                console.print("[red]No default folder set.[/red]")
                return False

            url = f"{API_BASE_URL}/accounts/{account_id}/folders/{current_folder_id}/children"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            folder_data = response.json()['data']

            # Search for folder by name
            found_folders = []
            for item in folder_data:
                if item['type'] == 'folder' and folder_identifier.lower() in item['name'].lower():
                    found_folders.append(item)

            if not found_folders:
                console.print(f"[red]No folder found with name containing '{folder_identifier}'[/red]")
                return False
            elif len(found_folders) > 1:
                console.print("[yellow]Multiple folders found:[/yellow]")
                for folder in found_folders:
                    console.print(f"  - {folder['name']} ({folder['id']})")
                return False
            else:
                folder_id = found_folders[0]['id']
                folder_name = found_folders[0]['name']
        else:
            folder_id = folder_identifier
            # Get folder name for confirmation
            url = f"{API_BASE_URL}/accounts/{account_id}/folders/{folder_id}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            folder_data = response.json()['data']
            folder_name = folder_data['name']

        # Confirm deletion
        if not click.confirm(f"Are you sure you want to delete folder '{folder_name}'?"):
            console.print("[yellow]Deletion cancelled.[/yellow]")
            return False

        # Delete the folder
        url = f"{API_BASE_URL}/accounts/{account_id}/folders/{folder_id}"
        response = requests.delete(url, headers=headers)
        response.raise_for_status()

        console.print(f"[green]Successfully deleted folder:[/green] {folder_name}")

        # If the deleted folder was the current folder, go up one level
        if folder_id == get_default_folder():
            history = get_folder_history()
            if history:
                previous_folder = history.pop()
                save_folder_history(history)
                set_default_folder(previous_folder)
                console.print("[yellow]Changed to parent folder.[/yellow]")
            else:
                set_default_folder(None)
                console.print("[yellow]No parent folder available.[/yellow]")

        return True

    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        return False

def rename_folder(folder_identifier, new_name, account_id=None):
    """Rename a folder by name or ID."""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No account specified and no default account set.[/red]")
            return False

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        # If folder_identifier is not a UUID, try to find it by name
        if not len(folder_identifier) == 36:
            # Get current folder contents to search for the name
            current_folder_id = get_default_folder()
            if not current_folder_id:
                console.print("[red]No default folder set.[/red]")
                return False

            url = f"{API_BASE_URL}/accounts/{account_id}/folders/{current_folder_id}/children"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            folder_data = response.json()['data']

            # Search for folder by name
            found_folders = []
            for item in folder_data:
                if item['type'] == 'folder' and folder_identifier.lower() in item['name'].lower():
                    found_folders.append(item)

            if not found_folders:
                console.print(f"[red]No folder found with name containing '{folder_identifier}'[/red]")
                return False
            elif len(found_folders) > 1:
                console.print("[yellow]Multiple folders found:[/yellow]")
                for folder in found_folders:
                    console.print(f"  - {folder['name']} ({folder['id']})")
                return False
            else:
                folder_id = found_folders[0]['id']
                old_name = found_folders[0]['name']
        else:
            folder_id = folder_identifier
            # Get current folder name
            url = f"{API_BASE_URL}/accounts/{account_id}/folders/{folder_id}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            folder_data = response.json()['data']
            old_name = folder_data['name']

        # Rename the folder
        url = f"{API_BASE_URL}/accounts/{account_id}/folders/{folder_id}"
        payload = {
            "data": {
                "name": new_name
            }
        }
        response = requests.patch(url, headers=headers, json=payload)
        response.raise_for_status()

        console.print(f"[green]Successfully renamed folder:[/green] {old_name} → {new_name}")
        return True

    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        return False

def extract_and_map_metadata(file_path):
    """Extract metadata from file using exiftool and map to Frame.io fields"""
    try:
        # Run exiftool to get metadata in JSON format
        result = subprocess.run(['exiftool', '-j', file_path], capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"[red]Error running exiftool: {result.stderr}[/red]")
            return None

        # Parse the JSON output
        metadata = json.loads(result.stdout)[0]
        console.print("\nFound metadata in file:")
        for key, value in metadata.items():
            console.print(f"  {key}: {value}")

        # Load existing metadata mappings
        config = load_config()
        metadata_mappings = config.get('metadata_mappings', {})
        console.print("\nCurrent metadata mappings:")
        for name, field_id in metadata_mappings.items():
            console.print(f"  {name} -> {field_id}")

        # Map metadata fields using configuration mappings
        mapped_fields = {}
        for field_name, field_id in metadata_mappings.items():
            # Try different possible exiftool field names
            possible_fields = [
                field_name,
                field_name.lower(),
                field_name.upper(),
                field_name.replace(' ', ''),
                field_name.replace(' ', '_'),
                field_name.replace(' ', '-')
            ]
            
            for exif_field in possible_fields:
                if exif_field in metadata:
                    value = metadata[exif_field]
                    # Handle arrays (like Keywords)
                    if isinstance(value, list):
                        value = ', '.join(value)
                    mapped_fields[field_id] = value
                    console.print(f"\nFound match: {field_name} -> {exif_field} (ID: {field_id})")
                    console.print(f"  Value: {value}")
                    break

        if not mapped_fields:
            console.print("\n[yellow]No matching metadata fields found in the file.[/yellow]")
            return None

        console.print("\nAttempting to update metadata with:")
        for field_id, value in mapped_fields.items():
            console.print(f"  Field ID {field_id}: {value}")

        return mapped_fields

    except Exception as e:
        console.print(f"[red]Error extracting metadata: {str(e)}[/red]")
        return None

def get_files_to_upload(path_pattern):
    """Get list of files to upload based on path pattern."""
    # Convert to absolute path if relative
    path_pattern = os.path.abspath(path_pattern)
    
    # If it's a directory, get all files in it
    if os.path.isdir(path_pattern):
        files = []
        for root, _, filenames in os.walk(path_pattern):
            for filename in filenames:
                files.append(os.path.join(root, filename))
        return files
    
    # If it's a wildcard pattern, get matching files
    if '*' in path_pattern or '?' in path_pattern:
        return glob.glob(path_pattern)
    
    # If it's a single file, return it
    if os.path.isfile(path_pattern):
        return [path_pattern]
    
    return []

def upload_files(path_pattern, extract_metadata=False, debug=False):
    """Upload multiple files based on path pattern."""
    files = get_files_to_upload(path_pattern)
    
    if not files:
        console.print(f"[red]No files found matching pattern: {path_pattern}[/red]")
        return files
    
    return files

def process_uploads(file_paths, extract_metadata=False, debug=False):
    """Process multiple file uploads in parallel with rate limiting"""
    # Get all files to upload
    all_files = []
    for path in file_paths:
        if os.path.isdir(path):
            # If it's a directory, add all files in it
            all_files.extend([os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))])
        elif '*' in path or '?' in path:
            # If it's a wildcard pattern, expand it
            all_files.extend(glob.glob(path))
        else:
            # It's a single file
            all_files.append(path)

    if not all_files:
        console.print("[yellow]No files found to upload.[/yellow]")
        return

    # Show files that will be uploaded
    console.print("\n[blue]Files to upload:[/blue]")
    for file in all_files:
        console.print(f"  {file}")
    
    if not click.confirm(f"\nUpload {len(all_files)} files?"):
        console.print("[yellow]Upload cancelled.[/yellow]")
        return

    # Initialize rate limiter
    rate_limiter = RateLimiter(get_rate_limit())
    console.print(f"[blue]Rate limit: {get_rate_limit()} requests per minute[/blue]")

    # Process uploads in parallel
    successful = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all upload tasks
        future_to_file = {
            executor.submit(upload_file_with_rate_limit, file, rate_limiter, extract_metadata=extract_metadata, debug=debug): file 
            for file in all_files
        }

        # Process results as they complete
        for future in as_completed(future_to_file):
            file = future_to_file[future]
            try:
                future.result()
                successful += 1
                console.print(f"[green]Successfully uploaded: {file}[/green]")
            except Exception as e:
                failed += 1
                console.print(f"[red]Failed to upload {file}: {str(e)}[/red]")

    # Show final summary
    console.print(f"\n[green]Upload complete: {successful} successful, {failed} failed[/green]")

def upload_file_with_rate_limit(local_path, rate_limiter, upload_name=None, account_id=None, extract_metadata=False, debug=False, target_folder_id=None):
    """Upload a file with rate limiting"""
    # Acquire rate limit token before making API calls
    rate_limiter.acquire()
    return upload_file(local_path, upload_name, account_id, extract_metadata, debug, target_folder_id)

def upload_file(local_path, upload_name=None, account_id=None, extract_metadata=False, debug=False, target_folder_id=None):
    """Upload a file to the current folder or specified target folder"""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No default account set. Please set a default account first.[/red]")
            return

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        # Get project ID from default project
        project_id = get_default_project()
        if not project_id:
            console.print("[red]No default project set. Please set a default project first.[/red]")
            return

        # Use target folder ID if provided, otherwise use default folder
        if target_folder_id:
            folder_id = target_folder_id
        else:
            folder_id = get_default_folder()
            if not folder_id:
                console.print("[red]No default folder set. Please use 'fio cd' to navigate to a folder first.[/red]")
                return

        # Get file name from path if not provided
        if not upload_name:
            upload_name = os.path.basename(local_path)

        # Check for existing file with same name
        existing_file_id = None
        url = f"{API_BASE_URL}/accounts/{account_id}/folders/{folder_id}/children"
        if debug:
            from ..cli import request_logger
            request_logger.log_request('GET', url, headers)
        response = requests.get(url, headers=headers)
        if debug:
            request_logger.log_response(response.status_code, response.headers, response.json())
        response.raise_for_status()
        
        for item in response.json()['data']:
            if item['type'] == 'file' and item['name'].lower() == upload_name.lower():
                existing_file_id = item['id']
                console.print(f"[yellow]Found existing file with same name: {upload_name} (ID: {existing_file_id})[/yellow]")
                break

        # Get file size
        file_size = os.path.getsize(local_path)

        # Get upload URL
        url = f"{API_BASE_URL}/accounts/{account_id}/folders/{folder_id}/files/local_upload"
        data = {
            'data': {
                'name': upload_name,
                'file_size': file_size
            }
        }
        if debug:
            request_logger.log_request('POST', url, headers, data)
        response = requests.post(url, headers=headers, json=data)
        if debug:
            request_logger.log_response(response.status_code, response.headers, response.json())
        response.raise_for_status()
        upload_data = response.json()['data']

        # Get the upload URL from the response
        upload_url = upload_data['upload_urls'][0]['url']

        # Get content type
        import mimetypes
        content_type, _ = mimetypes.guess_type(local_path)
        if not content_type:
            content_type = 'application/octet-stream'

        # Set up upload headers
        upload_headers = {
            'Content-Type': content_type,
            'x-amz-acl': 'private'
        }

        # Upload file to presigned URL
        with open(local_path, 'rb') as f:
            if debug:
                request_logger.log_request('PUT', upload_url, upload_headers)
            upload_response = requests.put(upload_url, data=f, headers=upload_headers)
            if debug:
                request_logger.log_response(upload_response.status_code, upload_response.headers)
            upload_response.raise_for_status()

        # If there was an existing file, create a version stack
        if existing_file_id:
            url = f"{API_BASE_URL}/accounts/{account_id}/folders/{folder_id}/version_stacks"
            data = {
                'data': {
                    'file_ids': [existing_file_id, upload_data['id']]
                }
            }
            if debug:
                request_logger.log_request('POST', url, headers, data)
            response = requests.post(url, headers=headers, json=data)
            if debug:
                request_logger.log_response(response.status_code, response.headers, response.json())
            response.raise_for_status()
            console.print(f"[green]Created version stack with files:[/green]")
            console.print(f"  - Previous version: {existing_file_id}")
            console.print(f"  - New version: {upload_data['id']}")

        # Extract and update metadata if requested
        if extract_metadata:
            metadata = extract_and_map_metadata(local_path)
            if metadata:
                # Get current metadata to find field IDs
                url = f"https://api.frame.io/v4/accounts/{account_id}/files/{upload_data['id']}/metadata"
                if debug:
                    request_logger.log_request('GET', url, headers)
                response = requests.get(url, headers=headers)
                if debug:
                    request_logger.log_response(response.status_code, response.headers, response.json())
                response.raise_for_status()
                current_metadata = response.json()['data']

                # Find field IDs for the extracted metadata
                field_updates = []
                for field_id, field_value in metadata.items():
                    field_updates.append({
                        'field_definition_id': field_id,
                        'value': field_value
                    })

                if field_updates:
                    # Update metadata using project-level endpoint
                    url = f"https://api.frame.io/v4/accounts/{account_id}/projects/{project_id}/metadata/values"
                    data = {
                        'data': {
                            'asset_ids': [upload_data['id']],
                            'values': field_updates
                        }
                    }
                    if debug:
                        request_logger.log_request('PATCH', url, headers, data)
                    response = requests.patch(url, headers=headers, json=data)
                    if debug:
                        request_logger.log_response(response.status_code, response.headers, response.json())
                    response.raise_for_status()

    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            console.print(f"[red]Response:[/red] {e.response.text}")
        raise

def delete_file(file_identifier, account_id=None):
    """Delete a file by name or ID."""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No account specified and no default account set.[/red]")
            return False

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {'Authorization': f'Bearer {token}'}

        # If file_identifier is not a UUID, try to find it by name
        if not len(file_identifier) == 36:
            # Get current folder contents to search for the name
            current_folder_id = get_default_folder()
            if not current_folder_id:
                console.print("[red]No default folder set.[/red]")
                return False

            url = f"{API_BASE_URL}/accounts/{account_id}/folders/{current_folder_id}/children"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            folder_data = response.json()['data']

            # Search for file by name
            found_files = []
            for item in folder_data:
                if item['type'] == 'file' and file_identifier.lower() in item['name'].lower():
                    found_files.append(item)

            if not found_files:
                console.print(f"[red]No file found with name containing '{file_identifier}'[/red]")
                return False
            elif len(found_files) > 1:
                console.print("[yellow]Multiple files found:[/yellow]")
                for file in found_files:
                    console.print(f"  - {file['name']} ({file['id']})")
                return False
            else:
                file_id = found_files[0]['id']
                file_name = found_files[0]['name']
        else:
            file_id = file_identifier
            # Get file name for confirmation
            url = f"{API_BASE_URL}/accounts/{account_id}/files/{file_id}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            file_data = response.json()['data']
            file_name = file_data['name']

        # Confirm deletion
        if not click.confirm(f"Are you sure you want to delete file '{file_name}'?"):
            console.print("[yellow]Deletion cancelled.[/yellow]")
            return False

        # Delete the file
        url = f"{API_BASE_URL}/accounts/{account_id}/files/{file_id}"
        response = requests.delete(url, headers=headers)
        response.raise_for_status()

        console.print(f"[green]Successfully deleted file:[/green] {file_name}")
        return True

    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        return False

def get_file_metadata(file_identifier, account_id=None, csv_output=False):
    """Get metadata for a file by name or ID"""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No default account set. Please set a default account first.[/red]")
            return

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
        }

        # Get current folder contents to find the file
        folder_id = get_default_folder()
        if not folder_id:
            console.print("[red]No default folder set. Please use 'fio cd' to navigate to a folder first.[/red]")
            return

        url = f"https://api.frame.io/v4/accounts/{account_id}/folders/{folder_id}/children"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        folder_data = response.json()['data']

        # Find file by name or ID
        file_id = None
        file_name = None
        if not is_valid_uuid(file_identifier):
            matching_files = []
            for item in folder_data:
                if item['type'] == 'file' and file_identifier.lower() in item['name'].lower():
                    matching_files.append(item)

            if not matching_files:
                console.print(f"[red]No file found with name: {file_identifier}[/red]")
                return
            elif len(matching_files) > 1:
                console.print(f"[yellow]Multiple files found with name containing '{file_identifier}':[/yellow]")
                for i, file in enumerate(matching_files, 1):
                    console.print(f"{i}. {file['name']} (ID: {file['id']})")
                choice = click.prompt("Enter the number of the file to get metadata for", type=int)
                if 1 <= choice <= len(matching_files):
                    file_id = matching_files[choice - 1]['id']
                    file_name = matching_files[choice - 1]['name']
                else:
                    console.print("[red]Invalid selection.[/red]")
                    return
            else:
                file_id = matching_files[0]['id']
                file_name = matching_files[0]['name']
        else:
            file_id = file_identifier
            # Get file name for the ID
            for item in folder_data:
                if item['type'] == 'file' and item['id'] == file_id:
                    file_name = item['name']
                    break

        # Get metadata
        url = f"https://api.frame.io/v4/accounts/{account_id}/files/{file_id}/metadata"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        metadata = response.json()['data']

        # Load metadata mappings to show friendly names
        config = load_config()
        metadata_mappings = config.get('metadata_mappings', {})
        reverse_mappings = {v: k for k, v in metadata_mappings.items()}

        def format_value(value, field_type):
            if value is None:
                return ''
            if isinstance(value, list):
                if field_type in ['user_single', 'user_multi']:
                    return ', '.join(item.get('display_name', item.get('id', '')) for item in value)
                elif field_type == 'select':
                    return ', '.join(item.get('display_name', '') for item in value)
                return ', '.join(str(v) for v in value)
            if isinstance(value, bool):
                return str(value).lower()
            if isinstance(value, (int, float)):
                if field_type == 'number':
                    return f"{value:,}"
                return str(value)
            return str(value)

        if csv_output:
            # Create CSV output
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['File Name', 'File ID', 'Field Name', 'Field ID', 'Value', 'Type'])
            
            # Write all fields from the actual API response structure
            if 'metadata' in metadata:
                for field in metadata['metadata']:
                    field_name = field['field_definition_name']
                    value = format_value(field.get('value'), field.get('field_type'))
                    field_type = 'Custom' if field.get('mutable', True) else 'Standard'
                    writer.writerow([
                        file_name,
                        file_id,
                        field_name,
                        field['field_definition_id'],
                        value,
                        field_type
                    ])
            
            # Legacy support for old response structure
            if 'file_attributes' in metadata:
                for field in metadata['file_attributes']:
                    field_name = field['field_definition_name']
                    value = format_value(field.get('value'), field.get('field_type'))
                    writer.writerow([
                        file_name,
                        file_id,
                        field_name,
                        field['field_definition_id'],
                        value,
                        'Standard'
                    ])
            
            if 'custom_fields' in metadata:
                for field in metadata['custom_fields']:
                    field_name = field['field_definition_name']
                    value = format_value(field.get('value'), field.get('field_type'))
                    writer.writerow([
                        file_name,
                        file_id,
                        field_name,
                        field['field_definition_id'],
                        value,
                        'Custom'
                    ])
            
            # Print CSV output
            print(output.getvalue())
            return

        # Create table for metadata
        table = Table(title=f"Metadata for {file_name} (ID: {file_id})")
        table.add_column("Field Name", style="cyan")
        table.add_column("Field ID", style="green")
        table.add_column("Value", style="yellow")
        table.add_column("Type", style="magenta")

        # Handle the actual API response structure - all fields are in metadata array
        if 'metadata' in metadata:
            for field in metadata['metadata']:
                field_name = field['field_definition_name']
                value = format_value(field.get('value'), field.get('field_type'))
                field_type = 'Custom' if field.get('mutable', True) else 'Standard'
                table.add_row(
                    field_name,
                    field['field_definition_id'],
                    value,
                    field_type
                )
        
        # Legacy support for old response structure (if it exists)
        if 'file_attributes' in metadata:
            for field in metadata['file_attributes']:
                field_name = field['field_definition_name']
                value = format_value(field.get('value'), field.get('field_type'))
                table.add_row(
                    field_name,
                    field['field_definition_id'],
                    value,
                    'Standard'
                )

        if 'custom_fields' in metadata:
            for field in metadata['custom_fields']:
                field_name = field['field_definition_name']
                value = format_value(field.get('value'), field.get('field_type'))
                table.add_row(
                    field_name,
                    field['field_definition_id'],
                    value,
                    'Custom'
                )

        if not table.rows:
            console.print("[yellow]No metadata fields found for this file.[/yellow]")
        else:
            console.print(table)

    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            console.print(f"[red]Response:[/red] {e.response.text}")

def update_file_metadata(file_identifier, account_id=None, debug=False, **metadata_fields):
    """Update metadata for a file by name or ID"""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No default account set. Please set a default account first.[/red]")
            return

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
        }

        # Get project ID from default project
        project_id = get_default_project()
        if not project_id:
            console.print("[red]No default project set. Please set a default project first.[/red]")
            return

        # Get current folder contents to find the file
        folder_id = get_default_folder()
        if not folder_id:
            console.print("[red]No default folder set. Please use 'fio cd' to navigate to a folder first.[/red]")
            return

        url = f"https://api.frame.io/v4/accounts/{account_id}/folders/{folder_id}/children"
        if debug:
            from ..cli import request_logger
            request_logger.log_request('GET', url, headers)
        response = requests.get(url, headers=headers)
        if debug:
            request_logger.log_response(response.status_code, response.headers, response.json())
        response.raise_for_status()
        folder_data = response.json()['data']

        # Find file by name or ID
        file_id = None
        if not is_valid_uuid(file_identifier):
            matching_files = []
            for item in folder_data:
                if item['type'] == 'file' and file_identifier.lower() in item['name'].lower():
                    matching_files.append(item)

            if not matching_files:
                console.print(f"[red]No file found with name: {file_identifier}[/red]")
                return
            elif len(matching_files) > 1:
                console.print(f"[yellow]Multiple files found with name containing '{file_identifier}':[/yellow]")
                for i, file in enumerate(matching_files, 1):
                    console.print(f"{i}. {file['name']} (ID: {file['id']})")
                choice = click.prompt("Enter the number of the file to update", type=int)
                if 1 <= choice <= len(matching_files):
                    file_id = matching_files[choice - 1]['id']
                else:
                    console.print("[red]Invalid selection.[/red]")
                    return
            else:
                file_id = matching_files[0]['id']
        else:
            file_id = file_identifier

        # Get current metadata to find field IDs
        url = f"https://api.frame.io/v4/accounts/{account_id}/files/{file_id}/metadata"
        if debug:
            request_logger.log_request('GET', url, headers)
        response = requests.get(url, headers=headers)
        if debug:
            request_logger.log_response(response.status_code, response.headers, response.json())
        response.raise_for_status()
        metadata = response.json()['data']

        # Find field IDs for the requested updates
        field_updates = []
        for field_name, field_value in metadata_fields.items():
            # Search in custom fields
            for field in metadata.get('custom_fields', []):
                if field['field_definition_id'] == field_name:
                    field_updates.append({
                        'field_definition_id': field['field_definition_id'],
                        'value': field_value
                    })
                    break

        if not field_updates:
            console.print("[red]No matching metadata fields found for the provided updates.[/red]")
            return

        # Update metadata
        url = f"https://api.frame.io/v4/accounts/{account_id}/projects/{project_id}/metadata/values"
        data = {
            'data': {
                'asset_ids': [file_id],
                'values': field_updates
            }
        }
        if debug:
            request_logger.log_request('PATCH', url, headers, data)
        response = requests.patch(url, headers=headers, json=data)
        if debug:
            request_logger.log_response(response.status_code, response.headers, response.json())
        response.raise_for_status()

        console.print(f"[green]Successfully updated metadata for file (ID: {file_id})[/green]")
        for update in field_updates:
            console.print(f"Updated field {update['field_definition_id']} with value: {update['value']}")

    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            console.print(f"[red]Response:[/red] {e.response.text}")

def list_file_metadata_fields(file_identifier, account_id=None, csv_output=False):
    """List available metadata fields for a file by name or ID"""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No default account set. Please set a default account first.[/red]")
            return

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
        }

        # Get current folder contents to find the file
        folder_id = get_default_folder()
        if not folder_id:
            console.print("[red]No default folder set. Please use 'fio cd' to navigate to a folder first.[/red]")
            return

        url = f"https://api.frame.io/v4/accounts/{account_id}/folders/{folder_id}/children"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        folder_data = response.json()['data']

        # Find matching files
        matching_files = []
        if file_identifier == '*':
            # Get all files
            matching_files = [item for item in folder_data if item['type'] == 'file']
        else:
            # Split file_identifier into individual patterns
            patterns = file_identifier.split()
            for pattern in patterns:
                if not is_valid_uuid(pattern):
                    for item in folder_data:
                        if item['type'] == 'file' and pattern.lower() in item['name'].lower():
                            if item not in matching_files:  # Avoid duplicates
                                matching_files.append(item)
                else:
                    for item in folder_data:
                        if item['type'] == 'file' and item['id'] == pattern:
                            if item not in matching_files:  # Avoid duplicates
                                matching_files.append(item)

        if not matching_files:
            console.print(f"[red]No files found matching: {file_identifier}[/red]")
            return

        # Get all unique field names across all files
        all_field_names = set()
        all_files_metadata = []

        for file_item in matching_files:
            file_id = file_item['id']
            file_name = file_item['name']

            # Get metadata fields
            url = f"https://api.frame.io/v4/accounts/{account_id}/files/{file_id}/metadata"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            metadata = response.json()['data']

            def format_value(value, field_type):
                if value is None:
                    return ''
                if isinstance(value, list):
                    if field_type in ['user_single', 'user_multi']:
                        return ', '.join(item.get('display_name', item.get('id', '')) for item in value)
                    elif field_type == 'select':
                        return ', '.join(item.get('display_name', '') for item in value)
                    return ', '.join(str(v) for v in value)
                if isinstance(value, bool):
                    return str(value).lower()
                if isinstance(value, (int, float)):
                    if field_type == 'number':
                        return f"{value:,}"
                    return str(value)
                return str(value)

            # Collect all fields for this file
            file_fields = {}

            # Add standard fields (file attributes)
            if 'file_attributes' in metadata:
                for field in metadata['file_attributes']:
                    field_name = field['field_definition_name']
                    value = format_value(field.get('value'), field.get('field_type'))
                    file_fields[field_name] = {
                        'id': field['field_definition_id'],
                        'value': value,
                        'type': 'Standard'
                    }
                    all_field_names.add(field_name)

            # Add custom fields
            if 'custom_fields' in metadata:
                for field in metadata['custom_fields']:
                    field_name = field['field_definition_name']
                    value = format_value(field.get('value'), field.get('field_type'))
                    file_fields[field_name] = {
                        'id': field['field_definition_id'],
                        'value': value,
                        'type': 'Custom'
                    }
                    all_field_names.add(field_name)

            all_files_metadata.append({
                'name': file_name,
                'id': file_id,
                'fields': file_fields
            })

        # Sort field names
        sorted_field_names = sorted(all_field_names)

        if csv_output:
            # Create CSV output
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header with standard columns first
            header = ['Name', 'Value', 'Field ID', 'Type']
            # Add field names as additional columns
            header.extend(sorted_field_names)
            writer.writerow(header)
            
            # Write data rows for each file
            for file_data in all_files_metadata:
                row = [file_data['name'], '', file_data['id'], 'File']  # Basic file info
                # Add values for each field
                for field_name in sorted_field_names:
                    field_data = file_data['fields'].get(field_name, {})
                    row.append(field_data.get('value', ''))
                writer.writerow(row)
            
            # Print CSV to stdout
            print(output.getvalue())
            return

        # Display metadata for each file
        for file_data in all_files_metadata:
            # Create table for all fields
            table = Table(title=f"Metadata Fields for {file_data['name']} (ID: {file_data['id']})")
            table.add_column("Field Name", style="cyan")
            table.add_column("Field ID", style="green")
            table.add_column("Value", style="yellow")
            table.add_column("Type", style="magenta")

            # Add fields to table
            for field_name in sorted_field_names:
                field_data = file_data['fields'].get(field_name, {})
                table.add_row(
                    field_name,
                    field_data.get('id', ''),
                    field_data.get('value', ''),
                    field_data.get('type', '')
                )

            if not table.rows:
                console.print("[yellow]No metadata fields found for this file.[/yellow]")
            else:
                console.print(table)
            console.print()  # Add blank line between files

    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            console.print(f"[red]Response:[/red] {e.response.text}")

def set_metadata_field_mapping(field_name=None, field_id=None):
    """Set a mapping between a metadata field name and its ID in the config, or list existing mappings"""
    try:
        # Load existing config
        config = load_config()
        
        # Initialize metadata_mappings if it doesn't exist
        if 'metadata_mappings' not in config:
            config['metadata_mappings'] = {}
        
        # If no parameters provided, show existing mappings
        if field_name is None or field_id is None:
            if not config['metadata_mappings']:
                console.print("[yellow]No metadata field mappings found in config.[/yellow]")
                return
            
            # Create table for mappings
            table = Table(title="Metadata Field Mappings")
            table.add_column("Field Name", style="cyan")
            table.add_column("Field ID", style="green")
            
            # Add mappings to table
            for name, id in config['metadata_mappings'].items():
                table.add_row(name, id)
            
            console.print(table)
            return
        
        # Add or update the mapping
        config['metadata_mappings'][field_name] = field_id
        
        # Save the updated config
        save_config(config)
        
        console.print(f"[green]Successfully mapped metadata field '{field_name}' to ID: {field_id}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error managing metadata field mapping:[/red] {str(e)}")

def recursive_upload_with_folder_sync(file_paths, extract_metadata=False, debug=False):
    """Recursively upload files with folder synchronization.
    
    This function:
    1. Checks for folders in the current directory
    2. Compares them with folders in Frame.io
    3. Creates missing folders
    4. Recursively uploads files in each folder
    """
    if not file_paths:
        console.print("[yellow]No files specified for upload.[/yellow]")
        return

    account_id = get_default_account()
    if not account_id:
        console.print("[red]No default account set. Please set a default account first.[/red]")
        return

    folder_id = get_default_folder()
    if not folder_id:
        console.print("[red]No default folder set. Please use 'fio cd' to navigate to a folder first.[/red]")
        return

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {
            'Authorization': f'Bearer {token}'
        }

        # Get current Frame.io folder contents
        url = f"{API_BASE_URL}/accounts/{account_id}/folders/{folder_id}/children"
        if debug:
            from ..cli import request_logger
            request_logger.log_request('GET', url, headers)
        response = requests.get(url, headers=headers)
        if debug:
            request_logger.log_response(response.status_code, response.headers, response.json())
        response.raise_for_status()
        frame_folders = response.json()['data']

        # Create a mapping of folder names to IDs in Frame.io
        frame_folder_map = {}
        for item in frame_folders:
            if item['type'] == 'folder':
                frame_folder_map[item['name'].lower()] = item['id']

        # Process each path
        all_files_to_upload = []
        folder_mapping = {}  # Maps local folder paths to Frame.io folder IDs

        for path_pattern in file_paths:
            if '*' in path_pattern or '?' in path_pattern:
                # Handle wildcard patterns
                import glob
                matched_paths = glob.glob(path_pattern)
                for matched_path in matched_paths:
                    if os.path.isdir(matched_path):
                        # Process directory
                        folder_files, folder_map = process_directory_recursively(
                            matched_path, frame_folder_map, account_id, headers, debug, folder_id
                        )
                        all_files_to_upload.extend(folder_files)
                        folder_mapping.update(folder_map)
                    elif os.path.isfile(matched_path):
                        # Single file
                        all_files_to_upload.append((matched_path, folder_id))
            else:
                # Single path
                if os.path.isdir(path_pattern):
                    # Process directory
                    folder_files, folder_map = process_directory_recursively(
                        path_pattern, frame_folder_map, account_id, headers, debug, folder_id
                    )
                    all_files_to_upload.extend(folder_files)
                    folder_mapping.update(folder_map)
                elif os.path.isfile(path_pattern):
                    # Single file
                    all_files_to_upload.append((path_pattern, folder_id))
                else:
                    console.print(f"[yellow]Path not found: {path_pattern}[/yellow]")

        if not all_files_to_upload:
            console.print("[yellow]No files found to upload.[/yellow]")
            return

        # Show files that will be uploaded
        console.print("\n[blue]Files to upload:[/blue]")
        for file_path, target_folder_id in all_files_to_upload:
            console.print(f"  {file_path} -> Frame.io folder ID: {target_folder_id}")
        
        if not click.confirm(f"\nUpload {len(all_files_to_upload)} files?"):
            console.print("[yellow]Upload cancelled.[/yellow]")
            return

        # Initialize rate limiter
        rate_limiter = RateLimiter(get_rate_limit())
        console.print(f"[blue]Rate limit: {get_rate_limit()} requests per minute[/blue]")

        # Process uploads in parallel
        successful = 0
        failed = 0
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all upload tasks
            future_to_file = {
                executor.submit(
                    upload_file_with_rate_limit, 
                    file_path, 
                    rate_limiter, 
                    upload_name=os.path.basename(file_path),
                    account_id=account_id,
                    extract_metadata=extract_metadata, 
                    debug=debug,
                    target_folder_id=target_folder_id
                ): file_path 
                for file_path, target_folder_id in all_files_to_upload
            }

            # Process results as they complete
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    future.result()
                    successful += 1
                    console.print(f"[green]Successfully uploaded: {file_path}[/green]")
                except Exception as e:
                    failed += 1
                    console.print(f"[red]Failed to upload {file_path}: {str(e)}[/red]")

        # Show final summary
        console.print(f"\n[green]Upload complete: {successful} successful, {failed} failed[/green]")

    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise

def process_directory_recursively(local_dir_path, frame_folder_map, account_id, headers, debug, parent_folder_id=None):
    """Process a directory recursively, creating folders and collecting files to upload."""
    files_to_upload = []
    folder_mapping = {}
    
    # Get the base folder name
    base_folder_name = os.path.basename(local_dir_path)
    
    # Check if folder exists in Frame.io
    if base_folder_name.lower() in frame_folder_map:
        # Folder exists, use its ID
        frame_folder_id = frame_folder_map[base_folder_name.lower()]
        console.print(f"[blue]Found existing folder: {base_folder_name} (ID: {frame_folder_id})[/blue]")
    else:
        # Create new folder using the provided parent folder ID
        frame_folder_id = create_folder_in_frame(base_folder_name, account_id, headers, debug, parent_folder_id)
        if frame_folder_id:
            console.print(f"[green]Created new folder: {base_folder_name} (ID: {frame_folder_id})[/green]")
            frame_folder_map[base_folder_name.lower()] = frame_folder_id
        else:
            console.print(f"[red]Failed to create folder: {base_folder_name}[/red]")
            return files_to_upload, folder_mapping
    
    folder_mapping[local_dir_path] = frame_folder_id
    
    # Get the current Frame.io folder contents for this folder
    try:
        url = f"{API_BASE_URL}/accounts/{account_id}/folders/{frame_folder_id}/children"
        if debug:
            from ..cli import request_logger
            request_logger.log_request('GET', url, headers)
        response = requests.get(url, headers=headers)
        if debug:
            request_logger.log_response(response.status_code, response.headers, response.json())
        response.raise_for_status()
        current_frame_folders = response.json()['data']
        
        # Update the frame folder map for this level
        current_frame_folder_map = {}
        for item in current_frame_folders:
            if item['type'] == 'folder':
                current_frame_folder_map[item['name'].lower()] = item['id']
        
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error getting folder contents for {base_folder_name}:[/red] {str(e)}")
        current_frame_folder_map = {}
    
    # Process contents of the directory
    try:
        for item in os.listdir(local_dir_path):
            item_path = os.path.join(local_dir_path, item)
            
            if os.path.isdir(item_path):
                # Recursively process subdirectory, passing the current folder as parent
                sub_files, sub_mapping = process_directory_recursively(
                    item_path, current_frame_folder_map, account_id, headers, debug, frame_folder_id
                )
                files_to_upload.extend(sub_files)
                folder_mapping.update(sub_mapping)
            elif os.path.isfile(item_path):
                # Add file to upload list
                files_to_upload.append((item_path, frame_folder_id))
                
    except PermissionError:
        console.print(f"[yellow]Permission denied accessing directory: {local_dir_path}[/yellow]")
    except Exception as e:
        console.print(f"[red]Error processing directory {local_dir_path}: {str(e)}[/red]")
    
    return files_to_upload, folder_mapping

def create_folder_in_frame(folder_name, account_id, headers, debug, parent_folder_id=None):
    """Create a folder in Frame.io and return its ID."""
    try:
        if not parent_folder_id:
            parent_folder_id = get_default_folder()
            if not parent_folder_id:
                console.print("[red]No default folder set.[/red]")
                return None
        
        # Use the same headers as the working create_folder function
        from ..auth import get_access_token
        token = get_access_token()
        folder_headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        url = f"{API_BASE_URL}/accounts/{account_id}/folders/{parent_folder_id}/folders"
        payload = {
            "data": {
                "name": folder_name
            }
        }
        
        if debug:
            from ..cli import request_logger
            request_logger.log_request('POST', url, folder_headers, payload)
        
        response = requests.post(url, headers=folder_headers, json=payload)
        
        if debug:
            request_logger.log_response(response.status_code, response.headers, response.json())
        
        response.raise_for_status()
        folder_data = response.json()['data']
        return folder_data['id']
        
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error creating folder {folder_name}:[/red] {str(e)}")
        return None

def parse_frame_path(path_string):
    """Parse a Frame.io path string into components.
    
    Expected format: /{workspace}/{project}/{folder}/{subfolder}...
    
    Returns:
        dict: {
            'workspace': str,
            'project': str, 
            'folders': list[str]
        }
    """
    if not path_string.startswith('/'):
        return None
    
    # Remove leading slash and split by '/'
    components = path_string[1:].split('/')
    
    if len(components) < 2:
        console.print("[red]Invalid path format. Expected: /{workspace}/{project}[/red]")
        return None
    
    result = {
        'workspace': components[0],
        'project': components[1],
        'folders': components[2:] if len(components) > 2 else []
    }
    
    return result

def navigate_to_path(path_string, account_id=None):
    """Navigate to a specific path in Frame.io.
    
    Args:
        path_string: Path in format /{workspace}/{project}/{folder}/{subfolder}...
        account_id: Account ID to use (optional)
    
    Returns:
        bool: True if navigation successful, False otherwise
    """
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No default account set. Please set a default account first.[/red]")
            return False
    
    # Parse the path
    path_components = parse_frame_path(path_string)
    if not path_components:
        return False
    
    console.print(f"[blue]Navigating to path: {path_string}[/blue]")
    
    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {'Authorization': f'Bearer {token}'}
        
        # Step 1: Set workspace
        workspace_name = path_components['workspace']
        console.print(f"[blue]Setting workspace: {workspace_name}[/blue]")
        
        # Get workspace by name
        from ..commands.workspaces import get_workspace_by_name
        workspace_id = get_workspace_by_name(workspace_name, account_id)
        
        if not workspace_id:
            console.print(f"[red]Workspace not found: {workspace_name}[/red]")
            return False
        
        # Set as default workspace
        from ..config import set_default_workspace
        set_default_workspace(workspace_id)
        console.print(f"[green]Set workspace: {workspace_name}[/green]")
        
        # Step 2: Set project
        project_name = path_components['project']
        console.print(f"[blue]Setting project: {project_name}[/blue]")
        
        # Get project by name
        project_id = get_project_by_name(project_name, account_id, workspace_id)
        
        if not project_id:
            console.print(f"[red]Project not found: {project_name}[/red]")
            return False
        
        # Set as default project
        set_default_project(project_id)
        console.print(f"[green]Set project: {project_name}[/green]")
        
        # Get project details to get root folder
        project_data = get_project_details(project_id, account_id)
        if not project_data:
            console.print(f"[red]Could not get project details for: {project_name}[/red]")
            return False
        
        root_folder_id = project_data.get('root_folder_id')
        if not root_folder_id:
            console.print(f"[red]No root folder found for project: {project_name}[/red]")
            return False
        
        # Set root folder as current folder
        set_default_folder(root_folder_id)
        current_folder_id = root_folder_id
        
        # Step 3: Navigate through folders
        for folder_name in path_components['folders']:
            console.print(f"[blue]Navigating to folder: {folder_name}[/blue]")
            
            # Get current folder contents
            url = f"{API_BASE_URL}/accounts/{account_id}/folders/{current_folder_id}/children"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            folder_data = response.json()['data']
            
            # Find the folder by name
            target_folder_id = None
            for item in folder_data:
                if item['type'] == 'folder' and item['name'].lower() == folder_name.lower():
                    target_folder_id = item['id']
                    break
            
            if not target_folder_id:
                console.print(f"[red]Folder not found: {folder_name}[/red]")
                return False
            
            # Navigate to the folder
            current_folder_id = target_folder_id
            set_default_folder(current_folder_id)
            console.print(f"[green]Navigated to folder: {folder_name}[/green]")
        
        # Show final folder contents
        console.print(f"\n[green]Successfully navigated to: {path_string}[/green]")
        
        # Get and display folder contents
        folder_contents = list_folder_contents(current_folder_id, account_id)
        if folder_contents:
            show_folder_contents(folder_contents)
        
        return True
        
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error navigating to path:[/red] {str(e)}")
        return False