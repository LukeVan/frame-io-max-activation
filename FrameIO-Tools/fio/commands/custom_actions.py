"""
Custom Actions command module for Frame.io CLI
"""
import json
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path
from ..config import API_BASE_URL, get_default_account, get_default_workspace
from ..auth import get_access_token

console = Console()

# Cache file path for workspaces
WORKSPACE_CACHE_FILE = Path.home() / '.fio' / 'workspace_cache.json'

def get_workspace_name(workspace_id, account_id=None):
    """Get workspace name by ID from cache."""
    try:
        if not WORKSPACE_CACHE_FILE.exists():
            return workspace_id  # Return ID if cache doesn't exist
        
        with open(WORKSPACE_CACHE_FILE, 'r') as f:
            cache = json.load(f)
        
        workspace_info = cache.get('workspaces', {}).get(workspace_id)
        if workspace_info:
            return workspace_info.get('name', workspace_id)
        
        return workspace_id  # Return ID if not found in cache
    except Exception:
        return workspace_id  # Return ID if any error occurs

def add_custom_action(description, event, name, url, account_id=None, workspace_id=None):
    """Add a custom action to a workspace."""
    try:
        # Get account and workspace IDs
        if not account_id:
            account_id = get_default_account()
            if not account_id:
                console.print("[red]No account ID provided and no default account set. Please set a default account first.[/red]")
                return
        
        if not workspace_id:
            workspace_id = get_default_workspace()
            if not workspace_id:
                console.print("[red]No workspace ID provided and no default workspace set. Please set a default workspace first.[/red]")
                return

        # Get access token
        token = get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }

        # Prepare the request body - try different formats for different endpoints
        action_body = {
            "data": {
                "description": description,
                "event": event,
                "name": name,
                "url": url
            }
        }
        
        webhook_body = {
            "data": {
                "event": event,
                "name": name,
                "url": url
            }
        }

        # Make the API call - try different possible endpoints with appropriate body formats
        endpoints_to_try = [
            (f"{API_BASE_URL}/accounts/{account_id}/workspaces/{workspace_id}/actions", action_body),
            (f"{API_BASE_URL}/accounts/{account_id}/actions", action_body),
            (f"{API_BASE_URL}/accounts/{account_id}/webhooks", webhook_body),
            (f"{API_BASE_URL}/accounts/{account_id}/workspaces/{workspace_id}/webhooks", webhook_body)
        ]
        
        # Try each URL until one works
        response = None
        working_url = None
        working_body = None
        
        for url, body in endpoints_to_try:
            try:
                console.print(f"[blue]Trying endpoint:[/blue] {url}")
                response = requests.post(url, headers=headers, json=body)
                if response.status_code not in [404, 422]:  # Skip 404 and 422 errors
                    working_url = url
                    working_body = body
                    break
            except requests.exceptions.RequestException:
                continue
        
        if not working_url:
            console.print("[red]Error:[/red] Could not find a valid endpoint for custom actions.")
            console.print("[yellow]Tried the following endpoints:[/yellow]")
            for url, _ in endpoints_to_try:
                console.print(f"  - {url}")
            return
        
        console.print(f"[blue]Request body:[/blue]")
        console.print(Panel(json.dumps(working_body, indent=2), title="Request Body"))
        response.raise_for_status()
        
        # Parse and display the response
        result = response.json()
        
        console.print(f"[green]✓ Custom action created successfully![/green]")
        console.print(f"[blue]Response:[/blue]")
        console.print(Panel(json.dumps(result, indent=2), title="Response"))
        
        # Display the created action in a table
        if 'data' in result:
            action = result['data']
            table = Table(title="Created Custom Action", show_header=True, header_style="bold magenta")
            table.add_column("Field", style="green")
            table.add_column("Value", style="cyan")
            
            table.add_row("Name", action.get('name', 'N/A'))
            table.add_row("Description", action.get('description', 'N/A'))
            table.add_row("Event", action.get('event', 'N/A'))
            table.add_row("URL", action.get('url', 'N/A'))
            table.add_row("ID", action.get('id', 'N/A'))
            table.add_row("Created", action.get('created_at', 'N/A').split('T')[0] if action.get('created_at') else 'N/A')
            
            console.print(table)
        
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                console.print(f"[red]Error details:[/red] {json.dumps(error_detail, indent=2)}")
            except:
                console.print(f"[red]Response status:[/red] {e.response.status_code}")
                console.print(f"[red]Response text:[/red] {e.response.text}")
        raise

def delete_custom_action(action_id=None, action_name=None, account_id=None, workspace_id=None):
    """Delete a custom action by ID or name."""
    try:
        # Get account and workspace IDs
        if not account_id:
            account_id = get_default_account()
            if not account_id:
                console.print("[red]No account ID provided and no default account set. Please set a default account first.[/red]")
                return
        
        if not workspace_id:
            workspace_id = get_default_workspace()
            if not workspace_id:
                console.print("[red]No workspace ID provided and no default workspace set. Please set a default workspace first.[/red]")
                return

        # If name is provided, we need to look up the ID first
        if action_name and not action_id:
            console.print(f"[blue]Looking up action ID for name:[/blue] {action_name}")
            actions = list_custom_actions(account_id, workspace_id, return_data=True)
            
            if not actions:
                console.print("[red]No custom actions found.[/red]")
                return
            
            # Find the action with matching name
            matching_action = None
            for action in actions:
                if action.get('name', '').lower() == action_name.lower():
                    matching_action = action
                    break
            
            if not matching_action:
                console.print(f"[red]No custom action found with name:[/red] {action_name}")
                console.print("[yellow]Available actions:[/yellow]")
                for action in actions:
                    console.print(f"  - {action.get('name', 'N/A')} (ID: {action.get('id', 'N/A')})")
                return
            
            action_id = matching_action['id']
            console.print(f"[green]Found action ID:[/green] {action_id}")

        if not action_id:
            console.print("[red]Error:[/red] Either --id or --name must be provided.")
            return

        # Get access token
        token = get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
        }

        # Make the DELETE API call
        url = f"{API_BASE_URL}/accounts/{account_id}/actions/{action_id}"
        
        console.print(f"[blue]Making DELETE request to:[/blue] {url}")
        
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
        
        console.print(f"[green]✓ Custom action deleted successfully![/green]")
        console.print(f"[blue]Action ID:[/blue] {action_id}")
        if action_name:
            console.print(f"[blue]Action Name:[/blue] {action_name}")
        
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                console.print(f"[red]Error details:[/red] {json.dumps(error_detail, indent=2)}")
            except:
                console.print(f"[red]Response status:[/red] {e.response.status_code}")
                console.print(f"[red]Response text:[/red] {e.response.text}")
        raise

def list_custom_actions(account_id=None, workspace_id=None, csv_output=False, return_data=False):
    """List custom actions for a workspace."""
    try:
        # Get account and workspace IDs
        if not account_id:
            account_id = get_default_account()
            if not account_id:
                console.print("[red]No account ID provided and no default account set. Please set a default account first.[/red]")
                return [] if return_data else None
        
        if not workspace_id:
            workspace_id = get_default_workspace()
            if not workspace_id:
                console.print("[red]No workspace ID provided and no default workspace set. Please set a default workspace first.[/red]")
                return [] if return_data else None

        # Get access token
        token = get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
        }

        # Make the API call - try different possible endpoints
        possible_urls = [
            f"{API_BASE_URL}/accounts/{account_id}/workspaces/{workspace_id}/actions",
            f"{API_BASE_URL}/accounts/{account_id}/actions",
            f"{API_BASE_URL}/accounts/{account_id}/webhooks",
            f"{API_BASE_URL}/accounts/{account_id}/workspaces/{workspace_id}/webhooks"
        ]
        
        # Try each URL until one works
        response = None
        working_url = None
        
        for url in possible_urls:
            try:
                if not return_data:  # Only show trying message if not called internally
                    console.print(f"[blue]Trying endpoint:[/blue] {url}")
                response = requests.get(url, headers=headers)
                if response.status_code != 404:
                    working_url = url
                    break
            except requests.exceptions.RequestException:
                continue
        
        if not working_url:
            if not return_data:  # Only show error if not called internally
                console.print("[red]Error:[/red] Could not find a valid endpoint for custom actions.")
                console.print("[yellow]Tried the following endpoints:[/yellow]")
                for url in possible_urls:
                    console.print(f"  - {url}")
            return [] if return_data else None
        
        response.raise_for_status()
        actions = response.json().get('data', [])

        if return_data:
            return actions

        if csv_output:
            # Create CSV output
            from io import StringIO
            import csv
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['Name', 'Description', 'Event', 'URL', 'Active', 'Workspace', 'ID', 'Created'])
            
            # Write data rows
            for action in actions:
                # Get workspace name
                workspace_id = action.get('workspace_id', 'N/A')
                workspace_name = get_workspace_name(workspace_id, account_id)
                
                writer.writerow([
                    action.get('name', 'N/A'),
                    action.get('description', 'N/A'),
                    action.get('event', 'N/A'),
                    action.get('url', 'N/A'),
                    'Yes' if action.get('active', False) else 'No',
                    workspace_name,
                    action.get('id', 'N/A'),
                    action.get('created_at', 'N/A').split('T')[0] if action.get('created_at') else 'N/A'
                ])
            
            # Print CSV to stdout
            print(output.getvalue())
            return

        if not actions:
            console.print("[yellow]No custom actions found for this workspace.[/yellow]")
            return

        # Display actions in a table
        table = Table(title=f"Custom Actions for Workspace {workspace_id}", show_header=True, header_style="bold magenta")
        table.add_column("Name", style="green")
        table.add_column("Description", style="cyan")
        table.add_column("Event", style="yellow")
        table.add_column("URL", style="blue")
        table.add_column("Active", style="green")
        table.add_column("Workspace", style="blue")
        table.add_column("ID", style="magenta", no_wrap=True)
        table.add_column("Created", style="red")
        
        for action in actions:
            # Format active status
            active_status = "✓" if action.get('active', False) else "✗"
            active_style = "green" if action.get('active', False) else "red"
            
            # Get workspace name
            workspace_id = action.get('workspace_id', 'N/A')
            workspace_name = get_workspace_name(workspace_id, account_id)
            
            table.add_row(
                action.get('name', 'N/A'),
                action.get('description', 'N/A'),
                action.get('event', 'N/A'),
                action.get('url', 'N/A'),
                f"[{active_style}]{active_status}[/{active_style}]",
                workspace_name,
                action.get('id', 'N/A'),
                action.get('created_at', 'N/A').split('T')[0] if action.get('created_at') else 'N/A'
            )
        
        console.print(table)
        
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        if return_data:
            return []
        raise 