"""Users data collector for Zendesk."""
from typing import Dict, Any, List, Optional
from collections import defaultdict

from src.zendesk_client import ZendeskClient, ZendeskAPIError
from src.exporters.markdown_formatter import MarkdownFormatter
from src.utils.config import config
from rich.console import Console
from rich.progress import Progress


class UsersCollector:
    """Collector for Zendesk users data."""
    
    def __init__(self):
        """Initialize users collector."""
        self.client = ZendeskClient()
        self.formatter = MarkdownFormatter('users')
        self.console = Console()
        
        # Cache for related data
        self.organizations_cache = {}
        self.groups_cache = {}
        self.user_stats_cache = {}
    
    def collect_all(self, role_filter: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Collect all users data.
        
        Args:
            role_filter: Filter by role (agent, admin, end-user)
            
        Returns:
            Dictionary organized by role containing user lists
        """
        self.console.print("👥 Collecting users data...", style="bold blue")
        
        # Build query parameters
        params = {}
        if role_filter:
            params['role'] = role_filter
        
        # Collect users
        users_by_role = defaultdict(list)
        total_users = 0
        
        try:
            with Progress() as progress:
                task = progress.add_task("Fetching users...", total=None)
                
                for user in self.client.get_users(**params):
                    # Get additional user details
                    enriched_user = self._enrich_user_data(user)
                    
                    role = user.get('role', 'end-user')
                    # Map roles to subcategories
                    if role in ['admin', 'agent']:
                        subcategory = 'agents'
                    else:
                        subcategory = 'end-users'
                    
                    users_by_role[subcategory].append(enriched_user)
                    total_users += 1
                    
                    progress.update(task, advance=1, description=f"Fetched {total_users} users...")
                
                progress.update(task, completed=True, description=f"Collected {total_users} users")
            
            self.console.print(f"✅ Successfully collected {total_users} users", style="bold green")
            return dict(users_by_role)
            
        except ZendeskAPIError as e:
            self.console.print(f"❌ Error collecting users: {e}", style="bold red")
            return {}
    
    def _enrich_user_data(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich user data with additional information.
        
        Args:
            user: Base user data
            
        Returns:
            Enriched user data
        """
        # Add organization info
        user['organization_info'] = self._get_organization_info(user.get('organization_id'))
        
        # Add group memberships
        user['groups_info'] = self._get_user_groups(user['id'])
        
        # Add user statistics
        user['statistics'] = self._get_user_statistics(user['id'])
        
        return user
    
    def _get_organization_info(self, org_id: Optional[int]) -> Dict[str, Any]:
        """Get organization information with caching.
        
        Args:
            org_id: Organization ID
            
        Returns:
            Organization information dictionary
        """
        if not org_id:
            return {}
        
        if org_id not in self.organizations_cache:
            try:
                response = self.client.get(f'/organizations/{org_id}.json')
                self.organizations_cache[org_id] = response.get('organization', {})
            except ZendeskAPIError:
                self.organizations_cache[org_id] = {}
        
        return self.organizations_cache[org_id]
    
    def _get_user_groups(self, user_id: int) -> List[Dict[str, Any]]:
        """Get groups that a user belongs to.
        
        Args:
            user_id: User ID
            
        Returns:
            List of group information
        """
        try:
            response = self.client.get(f'/users/{user_id}/group_memberships.json')
            memberships = response.get('group_memberships', [])
            
            groups = []
            for membership in memberships:
                group_id = membership.get('group_id')
                if group_id:
                    group_info = self._get_group_info(group_id)
                    if group_info:
                        groups.append(group_info)
            
            return groups
        except ZendeskAPIError:
            return []
    
    def _get_group_info(self, group_id: int) -> Dict[str, Any]:
        """Get group information with caching.
        
        Args:
            group_id: Group ID
            
        Returns:
            Group information dictionary
        """
        if group_id not in self.groups_cache:
            try:
                response = self.client.get(f'/groups/{group_id}.json')
                self.groups_cache[group_id] = response.get('group', {})
            except ZendeskAPIError:
                self.groups_cache[group_id] = {}
        
        return self.groups_cache[group_id]
    
    def _get_user_statistics(self, user_id: int) -> Dict[str, Any]:
        """Get user statistics.
        
        Args:
            user_id: User ID
            
        Returns:
            User statistics dictionary
        """
        if user_id in self.user_stats_cache:
            return self.user_stats_cache[user_id]
        
        stats = {
            'tickets_requested': 0,
            'tickets_assigned': 0,
            'tickets_solved': 0
        }
        
        try:
            # Count requested tickets
            response = self.client.get('/search.json', {
                'query': f'type:ticket requester:{user_id}',
                'type': 'ticket'
            })
            stats['tickets_requested'] = response.get('count', 0)
        except ZendeskAPIError:
            pass
        
        try:
            # Count assigned tickets
            response = self.client.get('/search.json', {
                'query': f'type:ticket assignee:{user_id}',
                'type': 'ticket'
            })
            stats['tickets_assigned'] = response.get('count', 0)
        except ZendeskAPIError:
            pass
        
        try:
            # Count solved tickets
            response = self.client.get('/search.json', {
                'query': f'type:ticket assignee:{user_id} status:solved',
                'type': 'ticket'
            })
            stats['tickets_solved'] = response.get('count', 0)
        except ZendeskAPIError:
            pass
        
        self.user_stats_cache[user_id] = stats
        return stats
    
    def export_to_markdown(self, users_by_role: Dict[str, List[Dict[str, Any]]]) -> bool:
        """Export users to markdown files.
        
        Args:
            users_by_role: Users organized by role
            
        Returns:
            True if successful, False otherwise
        """
        self.console.print("📝 Exporting users to markdown...", style="bold blue")
        
        total_exported = 0
        
        try:
            with Progress() as progress:
                # Calculate total users for progress
                total_users = sum(len(users) for users in users_by_role.values())
                task = progress.add_task("Exporting users...", total=total_users)
                
                for role, users in users_by_role.items():
                    self.console.print(f"Exporting {len(users)} {role}...")
                    
                    for user in users:
                        # Prepare context for template
                        context = self._prepare_user_context(user)
                        
                        # Generate markdown content
                        content = self.formatter.format_user(user, **context)
                        
                        # Determine output path
                        output_path = self.formatter.get_output_path(user, role)
                        
                        # Write file
                        if self.formatter.write_file(content, output_path):
                            total_exported += 1
                        
                        progress.update(task, advance=1)
                    
                    # Create index for this role
                    self.formatter.create_index_file(users, role)
                
                # Create main index
                all_users = []
                for users in users_by_role.values():
                    all_users.extend(users)
                self.formatter.create_index_file(all_users)
            
            self.console.print(f"✅ Successfully exported {total_exported} users", style="bold green")
            return True
            
        except Exception as e:
            self.console.print(f"❌ Error exporting users: {e}", style="bold red")
            return False
    
    def _prepare_user_context(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare context for user template.
        
        Args:
            user: User data
            
        Returns:
            Context dictionary for template rendering
        """
        context = {}
        
        # Organization information
        organization = user.get('organization_info', {})
        if organization:
            context['organization_name'] = organization.get('name')
            context['organization_file'] = self.formatter.sanitize_filename(
                f"{organization.get('id', 'unknown')}-{organization.get('name', 'unknown')}"
            )
        else:
            context['organization_name'] = None
            context['organization_file'] = None
        
        # Groups information
        groups = user.get('groups_info', [])
        context['groups'] = [group.get('name', 'Unknown') for group in groups]
        
        # Statistics
        context['stats'] = user.get('statistics', {})
        
        return context
    
    def get_statistics(self, users_by_role: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Get statistics about collected users.
        
        Args:
            users_by_role: Users organized by role
            
        Returns:
            Statistics dictionary
        """
        stats = {
            'total_users': sum(len(users) for users in users_by_role.values()),
            'by_role': {role: len(users) for role, users in users_by_role.items()},
            'active_users': 0,
            'verified_users': 0,
            'with_organization': 0,
            'with_groups': 0,
        }
        
        for users in users_by_role.values():
            for user in users:
                if user.get('active'):
                    stats['active_users'] += 1
                
                if user.get('verified'):
                    stats['verified_users'] += 1
                
                if user.get('organization_id'):
                    stats['with_organization'] += 1
                
                if user.get('groups_info'):
                    stats['with_groups'] += 1
        
        return stats 