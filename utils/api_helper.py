#!/usr/bin/env python3
"""
API helper utilities for HTTP requests and API interactions
"""

import requests
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

class APIHelper:
    """Helper class for making HTTP API requests with consistent error handling."""
    
    def __init__(self, base_url: str = "", default_timeout: int = 15):
        self.base_url = base_url
        self.default_timeout = default_timeout
        self.session = requests.Session()
    
    def get(
        self, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Make a GET request with consistent error handling.
        
        Returns:
            Dict with 'success', 'data', 'error', 'status_code' keys
        """
        try:
            url = urljoin(self.base_url, endpoint) if self.base_url else endpoint
            timeout = timeout or self.default_timeout
            
            response = self.session.get(
                url, 
                params=params, 
                headers=headers, 
                timeout=timeout
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError:
                    data = response.text
                
                return {
                    'success': True,
                    'data': data,
                    'status_code': response.status_code
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text}",
                    'status_code': response.status_code
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': f"Request timed out after {timeout} seconds",
                'status_code': -1
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': "Connection error - unable to reach server",
                'status_code': -2
            }
        except Exception as e:
            logger.error(f"API request error: {e}")
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'status_code': -3
            }
    
    def post(
        self, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """Make a POST request with consistent error handling."""
        try:
            url = urljoin(self.base_url, endpoint) if self.base_url else endpoint
            timeout = timeout or self.default_timeout
            
            response = self.session.post(
                url,
                data=data,
                json=json_data,
                headers=headers,
                timeout=timeout
            )
            
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                except ValueError:
                    data = response.text
                
                return {
                    'success': True,
                    'data': data,
                    'status_code': response.status_code
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text}",
                    'status_code': response.status_code
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': f"Request timed out after {timeout} seconds",
                'status_code': -1
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': "Connection error - unable to reach server",
                'status_code': -2
            }
        except Exception as e:
            logger.error(f"API request error: {e}")
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'status_code': -3
            }

class GitHubAPIHelper(APIHelper):
    """Specialized helper for GitHub API requests."""
    
    def __init__(self, token: Optional[str] = None):
        super().__init__("https://api.github.com")
        self.token = token
        if token:
            self.session.headers.update({
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github.v3+json'
            })
    
    def search_repositories(
        self, 
        query: str, 
        language: Optional[str] = None,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """Search GitHub repositories."""
        search_query = query
        if language:
            search_query += f" language:{language}"
        
        params = {
            'q': search_query,
            'sort': 'stars',
            'order': 'desc',
            'per_page': min(max_results, 100)
        }
        
        return self.get('/search/repositories', params=params)
    
    def get_repository_issues(
        self, 
        owner: str, 
        repo: str, 
        state: str = 'open',
        max_results: int = 10
    ) -> Dict[str, Any]:
        """Get repository issues and pull requests."""
        params = {
            'state': state,
            'per_page': min(max_results, 100)
        }
        
        return self.get(f'/repos/{owner}/{repo}/issues', params=params)
    
    def get_repository_releases(
        self, 
        owner: str, 
        repo: str,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """Get repository releases."""
        params = {
            'per_page': min(max_results, 100)
        }
        
        return self.get(f'/repos/{owner}/{repo}/releases', params=params)