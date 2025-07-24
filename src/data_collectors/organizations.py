"""Organizations data collector for Zendesk."""
from typing import Dict, Any, List, Optional
from collections import defaultdict

from src.zendesk_client import ZendeskClient, ZendeskAPIError
from src.exporters.markdown_formatter import MarkdownFormatter
from src.utils.config import config
from rich.console import Console
from rich.progress import Progress


class OrganizationsCollector:
    """Collector for Zendesk organizations data."""
    
    def __init__(self):
        """Initialize organizations collector."""
        self.client = ZendeskClient()
        self.formatter = MarkdownFormatter('organizations')
        self.console = Console()
        
        # Cache for related data
        self.users_cache = {}
    
    def collect_all(self) -> List[Dict[str, Any]]:
        """Collect all organizations data.
        
        Returns:
            List of organization data
        """
        self.console.print("🏢 Collecting organizations data...", style="bold blue")
        
        organizations = []
        total_organizations = 0
        
        try:
            with Progress() as progress:
                task = progress.add_task("Fetching organizations...", total=None)
                
                for organization in self.client.get_organizations():
                    # Get additional organization details
                    enriched_org = self._enrich_organization_data(organization)
                    
                    organizations.append(enriched_org)
                    total_organizations += 1
                    
                    progress.update(task, advance=1, description=f"Fetched {total_organizations} organizations...")
                
                progress.update(task, completed=True, description=f"Collected {total_organizations} organizations")
            
            self.console.print(f"✅ Successfully collected {total_organizations} organizations", style="bold green")
            return organizations
            
        except ZendeskAPIError as e:
            self.console.print(f"❌ Error collecting organizations: {e}", style="bold red")
            return []
    
    def _enrich_organization_data(self, organization: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich organization data with additional information.
        
        Args:
            organization: Base organization data
            
        Returns:
            Enriched organization data
        """
        # Add organization users
        organization['users_info'] = self._get_organization_users(organization['id'])
        
        return organization
    
    def _get_organization_users(self, org_id: int) -> List[Dict[str, Any]]:
        """Get users belonging to an organization.
        
        Args:
            org_id: Organization ID
            
        Returns:
            List of user information
        """
        if org_id in self.users_cache:
            return self.users_cache[org_id]
        
        try:
            users = []
            for user in self.client.get_paginated(f'/organizations/{org_id}/users.json'):
                users.append(user)
            
            self.users_cache[org_id] = users
            return users
        except ZendeskAPIError:
            self.users_cache[org_id] = []
            return []
    
    def export_to_markdown(self, organizations: List[Dict[str, Any]]) -> bool:
        """Export organizations to markdown files.
        
        Args:
            organizations: List of organization data
            
        Returns:
            True if successful, False otherwise
        """
        self.console.print("📝 Exporting organizations to markdown...", style="bold blue")
        
        total_exported = 0
        
        try:
            with Progress() as progress:
                task = progress.add_task("Exporting organizations...", total=len(organizations))
                
                for organization in organizations:
                    # Prepare context for template
                    context = self._prepare_organization_context(organization)
                    
                    # Generate markdown content
                    content = self.formatter.format_organization(organization, **context)
                    
                    # Determine output path
                    output_path = self.formatter.get_output_path(organization)
                    
                    # Write file
                    if self.formatter.write_file(content, output_path):
                        total_exported += 1
                    
                    progress.update(task, advance=1)
                
                # Create main index
                self.formatter.create_index_file(organizations)
            
            self.console.print(f"✅ Successfully exported {total_exported} organizations", style="bold green")
            return True
            
        except Exception as e:
            self.console.print(f"❌ Error exporting organizations: {e}", style="bold red")
            return False
    
    def _prepare_organization_context(self, organization: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare context for organization template.
        
        Args:
            organization: Organization data
            
        Returns:
            Context dictionary for template rendering
        """
        context = {}
        
        # Users information
        users = organization.get('users_info', [])
        users_with_filenames = []
        for user in users:
            user_data = user.copy()
            user_data['filename'] = self.formatter.sanitize_filename(
                f"{user.get('id', 'unknown')}-{user.get('name', 'unknown')}"
            )
            users_with_filenames.append(user_data)
        
        context['users'] = users_with_filenames
        
        return context
    
    def get_statistics(self, organizations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get statistics about collected organizations.
        
        Args:
            organizations: List of organization data
            
        Returns:
            Statistics dictionary
        """
        stats = {
            'total_organizations': len(organizations),
            'with_users': 0,
            'total_users': 0,
            'with_domains': 0,
            'with_notes': 0,
        }
        
        for org in organizations:
            users = org.get('users_info', [])
            if users:
                stats['with_users'] += 1
                stats['total_users'] += len(users)
            
            if org.get('domain_names'):
                stats['with_domains'] += 1
            
            if org.get('notes'):
                stats['with_notes'] += 1
        
        return stats 