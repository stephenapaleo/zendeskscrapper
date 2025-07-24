"""Tickets data collector for Zendesk."""
from typing import Dict, Any, List, Optional, Iterator
from collections import defaultdict
import time

from src.zendesk_client import ZendeskClient, ZendeskAPIError
from src.exporters.markdown_formatter import MarkdownFormatter
from src.utils.config import config
from rich.console import Console
from rich.progress import Progress, TaskID


class TicketsCollector:
    """Collector for Zendesk tickets data."""
    
    def __init__(self):
        """Initialize tickets collector."""
        self.client = ZendeskClient()
        self.formatter = MarkdownFormatter('tickets')
        self.console = Console()
        
        # Cache for related data
        self.users_cache = {}
        self.organizations_cache = {}
        self.groups_cache = {}
        self.custom_fields_cache = {}
    
    def collect_all(self, status_filter: Optional[str] = None, 
                   date_range: Optional[tuple] = None, 
                   include_comments: bool = True) -> Dict[str, List[Dict[str, Any]]]:
        """Collect all tickets data.
        
        Args:
            status_filter: Filter by status (open, pending, solved, closed)
            date_range: Tuple of (start_date, end_date) in ISO format
            include_comments: Whether to include ticket comments
            
        Returns:
            Dictionary organized by status containing ticket lists
        """
        self.console.print("🎫 Collecting tickets data...", style="bold blue")
        
        # Build query parameters
        params = {}
        if status_filter:
            params['status'] = status_filter
        if date_range:
            params['created>='] = date_range[0]
            params['created<='] = date_range[1]
        
        # Collect tickets
        tickets_by_status = defaultdict(list)
        total_tickets = 0
        
        try:
            with Progress() as progress:
                task = progress.add_task("Fetching tickets...", total=None)
                
                for ticket in self.client.get_tickets(**params):
                    # Get additional ticket details if needed
                    enriched_ticket = self._enrich_ticket_data(ticket, include_comments)
                    
                    status = ticket.get('status', 'unknown')
                    tickets_by_status[status].append(enriched_ticket)
                    total_tickets += 1
                    
                    progress.update(task, advance=1, description=f"Fetched {total_tickets} tickets...")
                    
                    # Add small delay to avoid overwhelming the API
                    if total_tickets % 100 == 0:
                        time.sleep(0.1)
                
                progress.update(task, completed=True, description=f"Collected {total_tickets} tickets")
            
            self.console.print(f"✅ Successfully collected {total_tickets} tickets", style="bold green")
            return dict(tickets_by_status)
            
        except ZendeskAPIError as e:
            self.console.print(f"❌ Error collecting tickets: {e}", style="bold red")
            return {}
    
    def _enrich_ticket_data(self, ticket: Dict[str, Any], include_comments: bool = True) -> Dict[str, Any]:
        """Enrich ticket data with additional information.
        
        Args:
            ticket: Base ticket data
            include_comments: Whether to include comments
            
        Returns:
            Enriched ticket data
        """
        # Add comments if requested
        if include_comments:
            try:
                comments = self.client.get_ticket_comments(ticket['id'])
                # Enrich comments with author information
                enriched_comments = []
                for comment in comments:
                    comment_data = comment.copy()
                    author = self._get_user_info(comment.get('author_id'))
                    comment_data['author_name'] = author.get('name', 'Unknown')
                    enriched_comments.append(comment_data)
                ticket['comments'] = enriched_comments
            except ZendeskAPIError:
                ticket['comments'] = []
        
        # Add related data
        ticket['requester_info'] = self._get_user_info(ticket.get('requester_id'))
        ticket['assignee_info'] = self._get_user_info(ticket.get('assignee_id'))
        ticket['organization_info'] = self._get_organization_info(ticket.get('organization_id'))
        ticket['group_info'] = self._get_group_info(ticket.get('group_id'))
        
        # Process custom fields
        if ticket.get('custom_fields'):
            ticket['custom_fields_processed'] = self._process_custom_fields(ticket['custom_fields'])
        
        return ticket
    
    def _get_user_info(self, user_id: Optional[int]) -> Dict[str, Any]:
        """Get user information with caching.
        
        Args:
            user_id: User ID
            
        Returns:
            User information dictionary
        """
        if not user_id:
            return {}
        
        if user_id not in self.users_cache:
            try:
                response = self.client.get(f'/users/{user_id}.json')
                self.users_cache[user_id] = response.get('user', {})
            except ZendeskAPIError:
                self.users_cache[user_id] = {}
        
        return self.users_cache[user_id]
    
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
    
    def _get_group_info(self, group_id: Optional[int]) -> Dict[str, Any]:
        """Get group information with caching.
        
        Args:
            group_id: Group ID
            
        Returns:
            Group information dictionary
        """
        if not group_id:
            return {}
        
        if group_id not in self.groups_cache:
            try:
                response = self.client.get(f'/groups/{group_id}.json')
                self.groups_cache[group_id] = response.get('group', {})
            except ZendeskAPIError:
                self.groups_cache[group_id] = {}
        
        return self.groups_cache[group_id]
    
    def _process_custom_fields(self, custom_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process custom fields into a more readable format.
        
        Args:
            custom_fields: List of custom field data
            
        Returns:
            Processed custom fields dictionary
        """
        processed = {}
        
        for field in custom_fields:
            field_id = field.get('id')
            field_value = field.get('value')
            
            if field_value is None:
                continue
            
            # Get field definition if not cached
            if field_id not in self.custom_fields_cache:
                try:
                    response = self.client.get(f'/ticket_fields/{field_id}.json')
                    self.custom_fields_cache[field_id] = response.get('ticket_field', {})
                except ZendeskAPIError:
                    self.custom_fields_cache[field_id] = {}
            
            field_def = self.custom_fields_cache[field_id]
            field_title = field_def.get('title', f'Custom Field {field_id}')
            
            processed[field_title] = field_value
        
        return processed
    
    def export_to_markdown(self, tickets_by_status: Dict[str, List[Dict[str, Any]]]) -> bool:
        """Export tickets to markdown files.
        
        Args:
            tickets_by_status: Tickets organized by status
            
        Returns:
            True if successful, False otherwise
        """
        self.console.print("📝 Exporting tickets to markdown...", style="bold blue")
        
        total_exported = 0
        
        try:
            with Progress() as progress:
                # Calculate total tickets for progress
                total_tickets = sum(len(tickets) for tickets in tickets_by_status.values())
                task = progress.add_task("Exporting tickets...", total=total_tickets)
                
                for status, tickets in tickets_by_status.items():
                    self.console.print(f"Exporting {len(tickets)} {status} tickets...")
                    
                    for ticket in tickets:
                        # Prepare context for template
                        context = self._prepare_ticket_context(ticket)
                        
                        # Generate markdown content
                        content = self.formatter.format_ticket(ticket, **context)
                        
                        # Determine output path
                        subcategory = status if status in ['open', 'solved', 'closed', 'pending'] else None
                        output_path = self.formatter.get_output_path(ticket, subcategory)
                        
                        # Write file
                        if self.formatter.write_file(content, output_path):
                            total_exported += 1
                        
                        progress.update(task, advance=1)
                    
                    # Create index for this status
                    self.formatter.create_index_file(tickets, status)
                
                # Create main index
                all_tickets = []
                for tickets in tickets_by_status.values():
                    all_tickets.extend(tickets)
                self.formatter.create_index_file(all_tickets)
            
            self.console.print(f"✅ Successfully exported {total_exported} tickets", style="bold green")
            return True
            
        except Exception as e:
            self.console.print(f"❌ Error exporting tickets: {e}", style="bold red")
            return False
    
    def _prepare_ticket_context(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare context for ticket template.
        
        Args:
            ticket: Ticket data
            
        Returns:
            Context dictionary for template rendering
        """
        context = {}
        
        # Requester information
        requester = ticket.get('requester_info', {})
        context['requester_name'] = requester.get('name', 'Unknown')
        context['requester_file'] = self.formatter.sanitize_filename(
            f"{requester.get('id', 'unknown')}-{requester.get('name', 'unknown')}"
        )
        
        # Assignee information  
        assignee = ticket.get('assignee_info', {})
        if assignee:
            context['assignee_name'] = assignee.get('name')
            context['assignee_file'] = self.formatter.sanitize_filename(
                f"{assignee.get('id', 'unknown')}-{assignee.get('name', 'unknown')}"
            )
        else:
            context['assignee_name'] = None
            context['assignee_file'] = None
        
        # Organization information
        organization = ticket.get('organization_info', {})
        if organization:
            context['organization_name'] = organization.get('name')
            context['organization_file'] = self.formatter.sanitize_filename(  
                f"{organization.get('id', 'unknown')}-{organization.get('name', 'unknown')}"
            )
        else:
            context['organization_name'] = None
            context['organization_file'] = None
        
        # Group information
        group = ticket.get('group_info', {})
        context['group_name'] = group.get('name', 'Unknown') if group else None
        
        # Comments with author names
        comments = ticket.get('comments', [])
        context['comments'] = comments
        
        # Custom fields table
        custom_fields = ticket.get('custom_fields_processed', {})
        if custom_fields:
            headers = ['Field', 'Value']
            rows = [[k, str(v)] for k, v in custom_fields.items()]
            context['custom_fields_table'] = self.formatter.format_table(headers, rows)
        else:
            context['custom_fields_table'] = None
        
        return context
    
    def get_statistics(self, tickets_by_status: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Get statistics about collected tickets.
        
        Args:
            tickets_by_status: Tickets organized by status
            
        Returns:
            Statistics dictionary
        """
        stats = {
            'total_tickets': sum(len(tickets) for tickets in tickets_by_status.values()),
            'by_status': {status: len(tickets) for status, tickets in tickets_by_status.items()},
            'by_priority': defaultdict(int),
            'by_type': defaultdict(int),
            'with_assignee': 0,
            'with_organization': 0,
        }
        
        for tickets in tickets_by_status.values():
            for ticket in tickets:
                # Priority stats
                priority = ticket.get('priority', 'unknown')
                stats['by_priority'][priority] += 1
                
                # Type stats
                ticket_type = ticket.get('type', 'unknown')
                stats['by_type'][ticket_type] += 1
                
                # Assignment stats
                if ticket.get('assignee_id'):
                    stats['with_assignee'] += 1
                
                if ticket.get('organization_id'):
                    stats['with_organization'] += 1
        
        return stats 