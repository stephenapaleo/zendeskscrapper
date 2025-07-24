"""Zendesk API client with authentication and error handling."""
import base64
import requests
from typing import Dict, Any, List, Optional, Iterator, Tuple
from urllib.parse import urljoin, urlparse, parse_qs
import time
import json
from pathlib import Path

from src.utils.config import config
from src.utils.rate_limiter import rate_limited_request


class ZendeskAPIError(Exception):
    """Custom exception for Zendesk API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[requests.Response] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class ZendeskClient:
    """Zendesk API client with authentication, pagination, and error handling."""
    
    def __init__(self):
        """Initialize Zendesk client with configuration."""
        zendesk_config = config.get_zendesk_config()
        rate_config = config.get_rate_limit_config()
        
        self.base_url = zendesk_config['base_url']
        # Correct Zendesk API token authentication format: email/token:api_token
        apiKey = base64.b64encode(f"{zendesk_config['email']}/token:{zendesk_config['api_token']}".encode('utf-8')).decode('utf-8')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization':f'Basic {apiKey}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'ZendeskScraper/1.0'
        })
        
        # Apply rate limiting to the request method
        self._make_request = rate_limited_request(
            requests_per_minute=rate_config['requests_per_minute'],
            retry_attempts=rate_config['retry_attempts']
        )(self._make_request)
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request to Zendesk API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., '/tickets.json')
            **kwargs: Additional arguments for requests
            
        Returns:
            Response object
            
        Raises:
            ZendeskAPIError: If API request fails
        """
        url = self.base_url + endpoint
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            # Handle different HTTP status codes
            if response.status_code == 200:
                return response
            elif response.status_code == 201:
                return response
            elif response.status_code == 204:
                return response
            elif response.status_code == 401:
                raise ZendeskAPIError("Authentication failed. Check your API credentials.", 401, response)
            elif response.status_code == 403:
                raise ZendeskAPIError("Access forbidden. Check your permissions.", 403, response)
            elif response.status_code == 404:
                raise ZendeskAPIError(f"Resource not found: {endpoint}", 404, response)
            elif response.status_code == 429:
                # Rate limit - should be handled by retry logic
                retry_after = int(response.headers.get('Retry-After', 60))
                raise ZendeskAPIError(f"Rate limit exceeded. Retry after {retry_after} seconds.", 429, response)
            elif response.status_code >= 500:
                raise ZendeskAPIError(f"Server error: {response.status_code}", response.status_code, response)
            else:
                raise ZendeskAPIError(f"Unexpected status code: {response.status_code}", response.status_code, response)
                
        except requests.exceptions.RequestException as e:
            raise ZendeskAPIError(f"Request failed: {str(e)}")
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request to Zendesk API.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            JSON response data
        """
        response = self._make_request('GET', endpoint, params=params)
        
        try:
            return response.json()
        except json.JSONDecodeError:
            raise ZendeskAPIError("Invalid JSON response from API")
    
    def get_paginated(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Iterator[Dict[str, Any]]:
        """Get all pages of results from a paginated endpoint.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Yields:
            Individual items from all pages
        """
        url = endpoint
        request_params = params or {}
        
        while url:
            # Extract endpoint from full URL if needed
            if url.startswith('http'):
                parsed_url = urlparse(url)
                endpoint_path = parsed_url.path
                # Remove API base path
                if endpoint_path.startswith('/api/v2'):
                    endpoint_path = endpoint_path[7:]
                
                # Parse query parameters from URL
                url_params = parse_qs(parsed_url.query)
                # Convert list values to single values
                url_params = {k: v[0] if isinstance(v, list) and len(v) == 1 else v 
                             for k, v in url_params.items()}
                
                response_data = self.get(endpoint_path, url_params)
            else:
                response_data = self.get(url, request_params)
            
            # Determine the key that contains the list of items
            data_key = None
            for key in response_data.keys():
                if isinstance(response_data[key], list) and key != 'next_page':
                    data_key = key
                    break
            
            if data_key:
                for item in response_data[data_key]:
                    yield item
            
            # Get next page URL
            url = response_data.get('next_page')
            request_params = {}  # Clear params for subsequent requests as they're in the URL
    
    def get_all(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get all items from a paginated endpoint.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            List of all items
        """
        return list(self.get_paginated(endpoint, params))
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test the API connection and authentication.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            response = self.get('/users.json')
            user = response.get('user', {})
            return True, f"Successfully connected as {user.get('name', 'Unknown')} ({user.get('email', 'No email')})"
        except ZendeskAPIError as e:
            return False, f"Connection failed: {e}"
    
    # Convenience methods for common endpoints
    
    def get_tickets(self, **params) -> Iterator[Dict[str, Any]]:
        """Get all tickets.
        
        Args:
            **params: Query parameters (e.g., status, created_after)
            
        Yields:
            Ticket objects
        """
        return self.get_paginated('/tickets.json', params)
    
    def get_ticket_comments(self, ticket_id: int) -> List[Dict[str, Any]]:
        """Get comments for a specific ticket.
        
        Args:
            ticket_id: Ticket ID
            
        Returns:
            List of comment objects
        """
        response = self.get(f'/tickets/{ticket_id}/comments.json')
        return response.get('comments', [])
    
    def get_users(self, **params) -> Iterator[Dict[str, Any]]:
        """Get all users.
        
        Args:
            **params: Query parameters
            
        Yields:
            User objects
        """
        return self.get_paginated('/users.json', params)
    
    def get_organizations(self, **params) -> Iterator[Dict[str, Any]]:
        """Get all organizations.
        
        Args:
            **params: Query parameters
            
        Yields:
            Organization objects
        """
        return self.get_paginated('/organizations.json', params)
    
    def get_groups(self, **params) -> Iterator[Dict[str, Any]]:
        """Get all groups.
        
        Args:
            **params: Query parameters
            
        Yields:
            Group objects
        """
        return self.get_paginated('/groups.json', params)
    
    def get_macros(self, **params) -> Iterator[Dict[str, Any]]:
        """Get all macros.
        
        Args:
            **params: Query parameters
            
        Yields:
            Macro objects
        """
        return self.get_paginated('/macros.json', params)
    
    def get_help_center_articles(self, **params) -> Iterator[Dict[str, Any]]:
        """Get all Help Center articles.
        
        Args:
            **params: Query parameters
            
        Yields:
            Article objects
        """
        return self.get_paginated('/help_center/articles.json', params)
    
    def get_help_center_sections(self, **params) -> Iterator[Dict[str, Any]]:
        """Get all Help Center sections.
        
        Args:
            **params: Query parameters
            
        Yields:
            Section objects
        """
        return self.get_paginated('/help_center/sections.json', params)
    
    def get_help_center_categories(self, **params) -> Iterator[Dict[str, Any]]:
        """Get all Help Center categories.
        
        Args:
            **params: Query parameters
            
        Yields:
            Category objects
        """
        return self.get_paginated('/help_center/categories.json', params) 