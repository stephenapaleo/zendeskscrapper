"""Macros and groups data collector for Zendesk."""
from typing import Dict, Any, List, Optional
from collections import defaultdict

from src.zendesk_client import ZendeskClient, ZendeskAPIError
from src.exporters.markdown_formatter import MarkdownFormatter
from src.utils.config import config
from rich.console import Console
from rich.progress import Progress


class MacrosCollector:
    """Collector for Zendesk macros data."""
    
    def __init__(self):
        """Initialize macros collector."""
        self.client = ZendeskClient()
        self.formatter = MarkdownFormatter('macros')
        self.console = Console()
    
    def collect_all(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """Collect all macros data.
        
        Args:
            active_only: Only collect active macros
            
        Returns:
            List of macro data
        """
        self.console.print("⚡ Collecting macros data...", style="bold blue")
        
        macros = []
        total_macros = 0
        
        try:
            with Progress() as progress:
                task = progress.add_task("Fetching macros...", total=None)
                
                for macro in self.client.get_macros():
                    # Filter by active status if requested
                    if active_only and not macro.get('active', True):
                        continue
                    
                    macros.append(macro)
                    total_macros += 1
                    
                    progress.update(task, advance=1, description=f"Fetched {total_macros} macros...")
                
                progress.update(task, completed=True, description=f"Collected {total_macros} macros")
            
            self.console.print(f"✅ Successfully collected {total_macros} macros", style="bold green")
            return macros
            
        except ZendeskAPIError as e:
            self.console.print(f"❌ Error collecting macros: {e}", style="bold red")
            return []
    
    def export_to_markdown(self, macros: List[Dict[str, Any]]) -> bool:
        """Export macros to markdown files.
        
        Args:
            macros: List of macro data
            
        Returns:
            True if successful, False otherwise
        """
        self.console.print("📝 Exporting macros to markdown...", style="bold blue")
        
        total_exported = 0
        
        try:
            with Progress() as progress:
                task = progress.add_task("Exporting macros...", total=len(macros))
                
                for macro in macros:
                    # Generate markdown content
                    content = self.formatter.format_macro(macro)
                    
                    # Determine output path
                    output_path = self.formatter.get_output_path(macro)
                    
                    # Write file
                    if self.formatter.write_file(content, output_path):
                        total_exported += 1
                    
                    progress.update(task, advance=1)
                
                # Create main index
                self.formatter.create_index_file(macros)
            
            self.console.print(f"✅ Successfully exported {total_exported} macros", style="bold green")
            return True
            
        except Exception as e:
            self.console.print(f"❌ Error exporting macros: {e}", style="bold red")
            return False
    
    def get_statistics(self, macros: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get statistics about collected macros.
        
        Args:
            macros: List of macro data
            
        Returns:
            Statistics dictionary
        """
        stats = {
            'total_macros': len(macros),
            'active_macros': 0,
            'inactive_macros': 0,
            'action_types': defaultdict(int),
        }
        
        for macro in macros:
            if macro.get('active', True):
                stats['active_macros'] += 1
            else:
                stats['inactive_macros'] += 1
            
            # Count action types
            actions = macro.get('actions', [])
            for action in actions:
                action_field = action.get('field', 'unknown')
                stats['action_types'][action_field] += 1
        
        return stats


class GroupsCollector:
    """Collector for Zendesk groups data."""
    
    def __init__(self):
        """Initialize groups collector."""
        self.client = ZendeskClient()
        self.formatter = MarkdownFormatter('groups')
        self.console = Console()
        
        # Cache for related data
        self.users_cache = {}
    
    def collect_all(self, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """Collect all groups data.
        
        Args:
            include_deleted: Include deleted groups
            
        Returns:
            List of group data
        """
        self.console.print("👥 Collecting groups data...", style="bold blue")
        
        groups = []
        total_groups = 0
        
        try:
            with Progress() as progress:
                task = progress.add_task("Fetching groups...", total=None)
                
                for group in self.client.get_groups():
                    # Filter deleted groups if requested
                    if not include_deleted and group.get('deleted', False):
                        continue
                    
                    # Enrich group data
                    enriched_group = self._enrich_group_data(group)
                    
                    groups.append(enriched_group)
                    total_groups += 1
                    
                    progress.update(task, advance=1, description=f"Fetched {total_groups} groups...")
                
                progress.update(task, completed=True, description=f"Collected {total_groups} groups")
            
            self.console.print(f"✅ Successfully collected {total_groups} groups", style="bold green")
            return groups
            
        except ZendeskAPIError as e:
            self.console.print(f"❌ Error collecting groups: {e}", style="bold red")
            return []
    
    def _enrich_group_data(self, group: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich group data with additional information.
        
        Args:
            group: Base group data
            
        Returns:
            Enriched group data
        """
        # Add group members
        group['agents_info'] = self._get_group_agents(group['id'])
        
        return group
    
    def _get_group_agents(self, group_id: int) -> List[Dict[str, Any]]:
        """Get agents belonging to a group.
        
        Args:
            group_id: Group ID
            
        Returns:
            List of agent information
        """
        if group_id in self.users_cache:
            return self.users_cache[group_id]
        
        try:
            response = self.client.get(f'/groups/{group_id}/memberships.json')
            memberships = response.get('group_memberships', [])
            
            agents = []
            for membership in memberships:
                user_id = membership.get('user_id')
                if user_id:
                    user_info = self._get_user_info(user_id)
                    if user_info:
                        agents.append(user_info)
            
            self.users_cache[group_id] = agents
            return agents
        except ZendeskAPIError:
            self.users_cache[group_id] = []
            return []
    
    def _get_user_info(self, user_id: int) -> Dict[str, Any]:
        """Get user information.
        
        Args:
            user_id: User ID
            
        Returns:
            User information dictionary
        """
        try:
            response = self.client.get(f'/users/{user_id}.json')
            return response.get('user', {})
        except ZendeskAPIError:
            return {}
    
    def export_to_markdown(self, groups: List[Dict[str, Any]]) -> bool:
        """Export groups to markdown files.
        
        Args:
            groups: List of group data
            
        Returns:
            True if successful, False otherwise
        """
        self.console.print("📝 Exporting groups to markdown...", style="bold blue")
        
        total_exported = 0
        
        try:
            with Progress() as progress:
                task = progress.add_task("Exporting groups...", total=len(groups))
                
                for group in groups:
                    # Prepare context for template
                    context = self._prepare_group_context(group)
                    
                    # Generate markdown content
                    content = self.formatter.format_group(group, **context)
                    
                    # Determine output path
                    output_path = self.formatter.get_output_path(group)
                    
                    # Write file
                    if self.formatter.write_file(content, output_path):
                        total_exported += 1
                    
                    progress.update(task, advance=1)
                
                # Create main index
                self.formatter.create_index_file(groups)
            
            self.console.print(f"✅ Successfully exported {total_exported} groups", style="bold green")
            return True
            
        except Exception as e:
            self.console.print(f"❌ Error exporting groups: {e}", style="bold red")
            return False
    
    def _prepare_group_context(self, group: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare context for group template.
        
        Args:
            group: Group data
            
        Returns:
            Context dictionary for template rendering
        """
        context = {}
        
        # Agents information
        agents = group.get('agents_info', [])
        agents_with_filenames = []
        for agent in agents:
            agent_data = agent.copy()
            agent_data['filename'] = self.formatter.sanitize_filename(
                f"{agent.get('id', 'unknown')}-{agent.get('name', 'unknown')}"
            )
            agents_with_filenames.append(agent_data)
        
        context['agents'] = agents_with_filenames
        
        return context
    
    def get_statistics(self, groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get statistics about collected groups.
        
        Args:
            groups: List of group data
            
        Returns:
            Statistics dictionary
        """
        stats = {
            'total_groups': len(groups),
            'default_groups': 0,
            'deleted_groups': 0,
            'groups_with_agents': 0,
            'total_agents': 0,
        }
        
        for group in groups:
            if group.get('default', False):
                stats['default_groups'] += 1
            
            if group.get('deleted', False):
                stats['deleted_groups'] += 1
            
            agents = group.get('agents_info', [])
            if agents:
                stats['groups_with_agents'] += 1
                stats['total_agents'] += len(agents)
        
        return stats 