"""
Accounts command module for Frame.io CLI
"""
import json
import os
from pathlib import Path
import requests
from rich.console import Console
from rich.table import Table
import csv
from io import StringIO
from ..config import API_BASE_URL, get_default_account, set_default_account
from ..auth import get_access_token

console = Console()

# Cache file path
CACHE_FILE = Path.home() / '.fio' / 'account_cache.json'

def ensure_cache_dir():
    """Ensure the cache directory exists."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CACHE_FILE.exists():
        with open(CACHE_FILE, 'w') as f:
            json.dump({"accounts": {}}, f)

def list_accounts(account_id=None, csv_output=False):
    """List all accounts or set default account by ID."""
    try:
        token = get_access_token()
        headers = {'Authorization': f'Bearer {token}'}
        url = f"{API_BASE_URL}/accounts"
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        accounts = response.json()['data']

        # Update cache with latest account information
        ensure_cache_dir()
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
        
        for account in accounts:
            cache['accounts'][account['id']] = {
                'name': account['display_name'],
                'created_at': account.get('created_at'),
                'updated_at': account.get('updated_at'),
                'status': account.get('status')
            }
        
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=4)

        # If account_id is provided, set it as default
        if account_id:
            if account_id in [acc['id'] for acc in accounts]:
                set_default_account(account_id)
                console.print(f"[green]Default account set to:[/green] {account_id}")
            else:
                console.print(f"[red]Account not found:[/red] {account_id}")
            return

        if csv_output:
            # Create CSV output
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['Name', 'ID', 'Created', 'Updated', 'Status'])
            
            # Write data rows
            for account in accounts:
                writer.writerow([
                    account['display_name'],
                    account['id'],
                    account.get('created_at', 'N/A').split('T')[0],
                    account.get('updated_at', 'N/A').split('T')[0],
                    account.get('status', 'N/A')
                ])
            
            # Print CSV to stdout
            print(output.getvalue())
            return

        # Display accounts in a table
        table = Table(title="Frame.io Accounts", show_header=True, header_style="bold magenta")
        table.add_column("Name", style="green")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Created", style="yellow")
        table.add_column("Updated", style="magenta")
        table.add_column("Status", style="blue")
        
        for account in accounts:
            table.add_row(
                account['display_name'],
                account['id'],
                account.get('created_at', 'N/A').split('T')[0],
                account.get('updated_at', 'N/A').split('T')[0],
                account.get('status', 'N/A')
            )
        
        console.print(table)
        
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise

def set_default_account(account_id):
    """Set the default account."""
    from ..config import set_default_account as config_set_default_account
    config_set_default_account(account_id) 