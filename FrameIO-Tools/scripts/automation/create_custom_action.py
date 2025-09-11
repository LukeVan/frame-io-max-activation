#!/usr/bin/env python3
"""
Create Custom Action in Frame.io v4 Experimental API

This script creates a Custom Action that integrates with Workfront Fusion
for Firefly Services processing (Crop, Background remove, LR preset).
"""

import requests
import json
import os
from dotenv import load_dotenv
from fio.auth import get_access_token
from fio.config import API_BASE_URL

# Load environment variables
load_dotenv()

def create_custom_action(workspace_id: str):
    """
    Create a Custom Action in the specified workspace
    
    Args:
        workspace_id: The Frame.io workspace ID where the action will be created
    """
    
    # Get authentication token
    token = get_access_token()
    if not token:
        print("❌ Failed to get authentication token")
        return False
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Custom Action configuration
    custom_action_data = {
        "data": {
            "name": "Normalize in Firefly Services",
            "description": "Frame 2 Fusion 4 FFS (Crop, Background remove, LR preset)",
            "url": "https://hook.app.workfrontfusion.com/lotw9txq8gf227kmsz8lxa9lymlo9e5p",
            "event": "meow.ffs.max.lukevan.com",
            "access": "all"  # Admins, team members, and collaborators
        }
    }
    
    # Experimental API endpoint for creating custom actions
    # Note: This uses the experimental API, not the stable v4 API
    experimental_base_url = API_BASE_URL.replace('/v4', '/experimental')
    url = f"{experimental_base_url}/workspaces/{workspace_id}/actions"
    
    print(f"🚀 Creating Custom Action in workspace {workspace_id}...")
    print(f"📡 API URL: {url}")
    print(f"📋 Action Name: {custom_action_data['data']['name']}")
    print(f"🔗 Webhook URL: {custom_action_data['data']['url']}")
    print(f"📝 Event: {custom_action_data['data']['event']}")
    
    try:
        response = requests.post(url, headers=headers, json=custom_action_data)
        
        if response.status_code == 201:
            result = response.json()
            action_data = result.get('data', {})
            
            print("✅ Custom Action created successfully!")
            print(f"🆔 Action ID: {action_data.get('id')}")
            print(f"🔑 Signing Secret: {action_data.get('secret', 'Not provided')}")
            print(f"📅 Created: {action_data.get('created_at')}")
            
            # Save the signing secret for verification
            if action_data.get('secret'):
                print("\n⚠️  IMPORTANT: Save this signing secret securely!")
                print("You'll need it to verify webhook requests from Frame.io")
                
                # Optionally save to .env file
                try:
                    with open('.env', 'a') as f:
                        f.write(f"\n# Custom Action Signing Secret\n")
                        f.write(f"FRAMEIO_CUSTOM_ACTION_SECRET={action_data.get('secret')}\n")
                    print("💾 Signing secret saved to .env file")
                except Exception as e:
                    print(f"⚠️  Could not save to .env file: {e}")
            
            return True
            
        else:
            print(f"❌ Failed to create Custom Action")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def list_workspaces():
    """List available workspaces to help user choose the right one"""
    
    token = get_access_token()
    if not token:
        print("❌ Failed to get authentication token")
        return []
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Get account ID first
    accounts_url = f"{API_BASE_URL}/accounts"
    try:
        accounts_response = requests.get(accounts_url, headers=headers)
        accounts_response.raise_for_status()
        accounts = accounts_response.json()['data']
        
        if not accounts:
            print("❌ No accounts found")
            return []
        
        account_id = accounts[0]['id']
        print(f"📊 Using account: {accounts[0]['display_name']} ({account_id})")
        
        # Get workspaces for this account
        workspaces_url = f"{API_BASE_URL}/accounts/{account_id}/workspaces"
        workspaces_response = requests.get(workspaces_url, headers=headers)
        workspaces_response.raise_for_status()
        workspaces = workspaces_response.json()['data']
        
        print("\n📁 Available Workspaces:")
        for i, workspace in enumerate(workspaces):
            print(f"  {i+1}. {workspace['name']} ({workspace['id']})")
        
        return workspaces
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to list workspaces: {e}")
        return []

def main():
    """Main function to create the custom action"""
    
    print("🎬 Frame.io Custom Action Creator")
    print("=" * 50)
    
    # List available workspaces
    workspaces = list_workspaces()
    if not workspaces:
        return
    
    # Let user choose workspace
    if len(workspaces) == 1:
        selected_workspace = workspaces[0]
        print(f"\n✅ Using the only available workspace: {selected_workspace['name']}")
    else:
        print(f"\nPlease select a workspace (1-{len(workspaces)}):")
        try:
            choice = int(input("Enter workspace number: ")) - 1
            if 0 <= choice < len(workspaces):
                selected_workspace = workspaces[choice]
            else:
                print("❌ Invalid workspace selection")
                return
        except ValueError:
            print("❌ Invalid input. Please enter a number.")
            return
    
    workspace_id = selected_workspace['id']
    workspace_name = selected_workspace['name']
    
    print(f"\n🎯 Creating Custom Action in workspace: {workspace_name}")
    
    # Confirm action
    confirm = input("\nProceed with Custom Action creation? (y/N): ").lower().strip()
    if confirm != 'y':
        print("❌ Operation cancelled")
        return
    
    # Create the custom action
    success = create_custom_action(workspace_id)
    
    if success:
        print("\n🎉 Custom Action setup complete!")
        print("\n📋 Next Steps:")
        print("1. Test the action by clicking on a file in Frame.io")
        print("2. Check your Workfront Fusion webhook for incoming payloads")
        print("3. Configure Fusion to process the webhook data")
        print("4. Set up response callbacks if needed")
    else:
        print("\n❌ Custom Action creation failed. Please check the error messages above.")

if __name__ == "__main__":
    main()
