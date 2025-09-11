"""
Authentication module for Frame.io CLI
"""
import requests
from .config import TOKEN_URL, FRAME_CLIENT_ID, FRAME_CLIENT_SECRET

def get_access_token():
    """
    Get an access token from Frame.io using client credentials.
    
    Returns:
        str: The access token
    """
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'client_id': FRAME_CLIENT_ID,
        'client_secret': FRAME_CLIENT_SECRET,
        'grant_type': 'client_credentials',
        'scope': 'openid, AdobeID, frame.s2s.all'
    }
    
    response = requests.post(TOKEN_URL, headers=headers, data=data)
    response.raise_for_status()
    
    return response.json()['access_token'] 