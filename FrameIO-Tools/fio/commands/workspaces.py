"""
Workspaces command module for Frame.io CLI
"""
import json
import os
from pathlib import Path
import requests
from rich.console import Console
from rich.table import Table
from ..config import API_BASE_URL, get_default_account, set_default_workspace
import click
import csv
from io import StringIO

console = Console()

# Cache file path
CACHE_FILE = Path.home() / '.fio' / 'workspace_cache.json'

def ensure_cache_dir():
    """Ensure the cache directory exists."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CACHE_FILE.exists():
        with open(CACHE_FILE, 'w') as f:
            json.dump({"workspaces": {}}, f)

def get_workspace_by_name(name, account_id=None):
    """Get workspace ID by name."""
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No account specified and no default account set.[/red]")
            return None

    ensure_cache_dir()
    with open(CACHE_FILE, 'r') as f:
        cache = json.load(f)
    
    # Look for exact match first
    for ws_id, ws_info in cache.get('workspaces', {}).items():
        if ws_info['name'].lower() == name.lower() and ws_info['account_id'] == account_id:
            return ws_id
    
    # If no exact match, look for partial matches
    matches = []
    for ws_id, ws_info in cache.get('workspaces', {}).items():
        if name.lower() in ws_info['name'].lower() and ws_info['account_id'] == account_id:
            matches.append((ws_id, ws_info['name']))
    
    if len(matches) == 1:
        return matches[0][0]
    elif len(matches) > 1:
        console.print("[yellow]Multiple matches found:[/yellow]")
        for ws_id, ws_name in matches:
            console.print(f"  {ws_name} ({ws_id})")
        return None
    return None

def delete_workspace(workspace_id, account_id=None):
    """
    Delete a workspace.
    """
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No account specified and no default account set.[/red]")
            return False

    # Get workspace name from cache for confirmation
    ensure_cache_dir()
    with open(CACHE_FILE, 'r') as f:
        cache = json.load(f)
    
    workspace_info = cache.get('workspaces', {}).get(workspace_id)
    if not workspace_info:
        console.print(f"[red]Workspace {workspace_id} not found in cache.[/red]")
        return False

    # Confirm deletion
    console.print(f"[yellow]Are you sure you want to delete workspace '{workspace_info['name']}' ({workspace_id})?[/yellow]")
    console.print("[yellow]This action cannot be undone.[/yellow]")
    if not click.confirm("Do you want to continue?"):
        console.print("[yellow]Deletion cancelled.[/yellow]")
        return False

    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {'Authorization': f'Bearer {token}'}
        url = f"{API_BASE_URL}/accounts/{account_id}/workspaces/{workspace_id}"
        
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
        
        # Remove from cache
        if workspace_id in cache['workspaces']:
            del cache['workspaces'][workspace_id]
            with open(CACHE_FILE, 'w') as f:
                json.dump(cache, f, indent=4)
        
        console.print(f"[green]Successfully deleted workspace '{workspace_info['name']}'[/green]")
        return True
        
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error deleting workspace:[/red] {str(e)}")
        return False

def list_workspaces(account_id=None, name=None, csv_output=False):
    """
    List all workspaces for the given or default account.
    If name is provided, set it as the default workspace.
    """
    if not account_id:
        account_id = get_default_account()
        if not account_id:
            console.print("[red]No account specified and no default account set.[/red]")
            return

    url = f"{API_BASE_URL}/accounts/{account_id}/workspaces"
    try:
        from ..auth import get_access_token
        token = get_access_token()
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        # Update cache with latest workspace information
        ensure_cache_dir()
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
        
        # Clear existing workspaces for this account
        cache['workspaces'] = {k: v for k, v in cache.get('workspaces', {}).items() 
                             if v.get('account_id') != account_id}
        
        # Add new workspace data
        for ws in data.get('data', []):
            cache['workspaces'][ws['id']] = {
                'name': ws['name'],
                'account_id': account_id,
                'created_at': ws['created_at'],
                'updated_at': ws['updated_at']
            }
        
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=4)

        # If name is provided, try to set it as default
        if name:
            # Look for exact match first
            for ws in data.get('data', []):
                if ws['name'].lower() == name.lower():
                    set_default_workspace(ws['id'])
                    console.print(f"[green]Default workspace set to:[/green] {ws['name']} ({ws['id']})")
                    return
            
            # If no exact match, look for partial matches
            matches = []
            for ws in data.get('data', []):
                if name.lower() in ws['name'].lower():
                    matches.append((ws['id'], ws['name']))
            
            if len(matches) == 1:
                ws_id, ws_name = matches[0]
                set_default_workspace(ws_id)
                console.print(f"[green]Default workspace set to:[/green] {ws_name} ({ws_id})")
            elif len(matches) > 1:
                console.print("[yellow]Multiple matches found:[/yellow]")
                for ws_id, ws_name in matches:
                    console.print(f"  {ws_name} ({ws_id})")
            else:
                console.print(f"[red]No workspace found with name:[/red] {name}")
            return

        if csv_output:
            # Create CSV output
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['Name', 'ID', 'Created', 'Updated'])
            
            # Write data rows
            for ws in data.get('data', []):
                writer.writerow([
                    ws['name'],
                    ws['id'],
                    ws['created_at'].split('T')[0],
                    ws['updated_at'].split('T')[0]
                ])
            
            # Print CSV to stdout
            print(output.getvalue())
            return

        # Display workspaces in a table
        table = Table(title="Frame.io Workspaces", show_header=True, header_style="bold magenta")
        table.add_column("Name", style="green")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Created", style="yellow")
        table.add_column("Updated", style="magenta")
        
        for ws in data.get('data', []):
            table.add_row(
                ws['name'],
                ws['id'],
                ws['created_at'].split('T')[0],
                ws['updated_at'].split('T')[0]
            )
        
        console.print(table)
        
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise 