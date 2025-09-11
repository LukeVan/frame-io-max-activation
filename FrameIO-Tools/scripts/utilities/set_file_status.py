#!/usr/bin/env python3
"""
Helper script to set the Approval metadata field on a Frame.io file
This helps test the approval monitoring workflow
"""

import requests
import argparse
from fio.config import get_default_account
from fio.auth import get_access_token

def set_file_status(file_id: str, status_value: str):
    """Set the status metadata field on a Frame.io file"""
    
    account_id = get_default_account()
    if not account_id:
        print("❌ No Frame.io account configured")
        return False
    
    token = get_access_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # First, let's get the file's current metadata to see available fields
    print(f"🔍 Getting current metadata for file {file_id}...")
    
    url = f"https://api.frame.io/v4/accounts/{account_id}/files/{file_id}/metadata"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        metadata_response = response.json()
        
        print("📋 Current metadata fields:")
        if 'data' in metadata_response and 'metadata' in metadata_response['data']:
            for field in metadata_response['data']['metadata']:
                field_name = field.get('field_definition_name', 'Unknown')
                field_type = field.get('field_type', 'Unknown')
                current_value = field.get('value', 'None')
                print(f"   {field_name} ({field_type}): {current_value}")
        else:
            print("   No metadata fields found")
            print("   You may need to create a 'Status' metadata field in Frame.io first")
        
        return True
        
    except Exception as e:
        print(f"❌ Error getting file metadata: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Set status metadata on a Frame.io file')
    parser.add_argument('file_id', help='Frame.io file ID')
    parser.add_argument('status', help='Status value to set (e.g., "Approved")')
    
    args = parser.parse_args()
    
    set_file_status(args.file_id, args.status)

if __name__ == "__main__":
    main()
