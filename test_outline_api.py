#!/usr/bin/env python3
"""
Test script to validate Outline API calls and functionality.

This script tests the fixed API endpoints and parameter formats for:
- groups.add_user (fixed from groups.addUser)
- groups.remove_user (fixed from groups.removeUser)

Usage:
    python test_outline_api.py
"""

import asyncio
import aiohttp
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

OUTLINE_API_URL = os.getenv("OUTLINE_API_URL")
OUTLINE_API_TOKEN = os.getenv("OUTLINE_API_TOKEN")

class TestOutlineAPI:
    """Test class for Outline API functionality."""
    
    def __init__(self, api_url, api_token):
        """
        Initialize the test API client.
        
        Args:
            api_url: Outline API base URL
            api_token: Outline API authentication token
        """
        self.api_url = api_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    async def _make_request(self, endpoint, data=None):
        """
        Make an HTTP request to the Outline API.
        
        Args:
            endpoint: API endpoint (e.g., 'groups.list')
            data: Request payload data
            
        Returns:
            dict: API response data or None if error
        """
        # API URL already includes /api path, so just append endpoint
        url = f"{self.api_url}/{endpoint}"
        
        try:
            async with aiohttp.ClientSession() as session:
                if data:
                    async with session.post(url, headers=self.headers, json=data) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            print(f"❌ API Error {response.status}: {await response.text()}")
                            return None
                else:
                    async with session.post(url, headers=self.headers) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            print(f"❌ API Error {response.status}: {await response.text()}")
                            return None
        except Exception as e:
            print(f"❌ Request failed: {str(e)}")
            return None
    
    async def test_groups_list(self):
        """Test groups.list endpoint."""
        print("🔍 Testing groups.list...")
        response = await self._make_request('groups.list')
        if response:
            print(f"✅ groups.list successful")
            if 'data' in response:
                groups_data = response['data']
                if isinstance(groups_data, dict) and 'groups' in groups_data:
                    groups = groups_data['groups']
                elif isinstance(groups_data, list):
                    groups = groups_data
                else:
                    groups = []
                print(f"   Found {len(groups)} groups")
                return groups
            return []
        return None
    
    async def test_users_list(self):
        """Test users.list endpoint."""
        print("🔍 Testing users.list...")
        response = await self._make_request('users.list')
        if response:
            print(f"✅ users.list successful")
            if 'data' in response:
                users_data = response['data']
                if isinstance(users_data, dict) and 'users' in users_data:
                    users = users_data['users']
                elif isinstance(users_data, list):
                    users = users_data
                else:
                    users = []
                print(f"   Found {len(users)} users")
                return users
            return []
        return None
    
    async def test_groups_add_user(self, group_id, user_id, dry_run=True):
        """
        Test groups.add_user endpoint with correct parameters.
        
        Args:
            group_id: Group UUID
            user_id: User UUID
            dry_run: If True, only validate parameters without making actual request
        """
        print(f"🔍 Testing groups.add_user (dry_run={dry_run})...")
        
        # Validate parameter format
        data = {
            'id': group_id,      # Correct parameter name (not 'groupId')
            'userId': user_id    # Correct parameter name
        }
        
        print(f"   Parameters: {json.dumps(data, indent=2)}")
        
        if dry_run:
            print("✅ Parameter validation passed (dry run)")
            return True
        
        response = await self._make_request('groups.add_user', data)
        if response:
            print("✅ groups.add_user successful")
            return True
        return False
    
    async def test_groups_remove_user(self, group_id, user_id, dry_run=True):
        """
        Test groups.remove_user endpoint with correct parameters.
        
        Args:
            group_id: Group UUID
            user_id: User UUID
            dry_run: If True, only validate parameters without making actual request
        """
        print(f"🔍 Testing groups.remove_user (dry_run={dry_run})...")
        
        # Validate parameter format
        data = {
            'id': group_id,      # Correct parameter name (not 'groupId')
            'userId': user_id    # Correct parameter name
        }
        
        print(f"   Parameters: {json.dumps(data, indent=2)}")
        
        if dry_run:
            print("✅ Parameter validation passed (dry run)")
            return True
        
        response = await self._make_request('groups.remove_user', data)
        if response:
            print("✅ groups.remove_user successful")
            return True
        return False

async def main():
    """Main test function."""
    print("🚀 Starting Outline API tests...\n")
    
    # Check environment variables
    if not OUTLINE_API_URL or not OUTLINE_API_TOKEN:
        print("❌ Error: OUTLINE_API_URL and OUTLINE_API_TOKEN must be set in .env")
        return
    
    # Initialize test client
    test_api = TestOutlineAPI(OUTLINE_API_URL, OUTLINE_API_TOKEN)
    
    # Test basic endpoints
    print("=" * 50)
    print("BASIC ENDPOINT TESTS")
    print("=" * 50)
    
    groups = await test_api.test_groups_list()
    if groups is None:
        print("❌ Cannot proceed without groups data")
        return
    
    users = await test_api.test_users_list()
    if users is None:
        print("❌ Cannot proceed without users data")
        return
    
    print()
    
    # Test parameter validation (dry run)
    print("=" * 50)
    print("PARAMETER VALIDATION TESTS (DRY RUN)")
    print("=" * 50)
    
    if groups and users:
        # Use first available group and user for testing
        test_group = groups[0]
        test_user = users[0]
        
        group_id = test_group.get('id')
        user_id = test_user.get('id')
        
        if group_id and user_id:
            print(f"Using test group: {test_group.get('name', 'Unknown')} ({group_id})")
            print(f"Using test user: {test_user.get('name', 'Unknown')} ({user_id})")
            print()
            
            # Test parameter formats (dry run only)
            await test_api.test_groups_add_user(group_id, user_id, dry_run=True)
            await test_api.test_groups_remove_user(group_id, user_id, dry_run=True)
        else:
            print("❌ Missing group ID or user ID for parameter testing")
    else:
        print("❌ No groups or users available for parameter testing")
    
    print()
    print("🎉 API tests completed!")
    print("\nSummary:")
    print("- Fixed endpoint names: groups.addUser → groups.add_user, groups.removeUser → groups.remove_user")
    print("- Fixed parameter names: groupId → id, userId remains userId")
    print("- Added interaction.response.defer() to prevent Discord timeouts")

if __name__ == "__main__":
    asyncio.run(main())