#!/usr/bin/env python3
"""
Zendesk Data Collection CLI

This script collects data from Zendesk via REST API and exports it as organized markdown files.
"""
import sys
import os
import click
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.zendesk_client import ZendeskClient, ZendeskAPIError
from src.data_collectors.tickets import TicketsCollector
from src.data_collectors.users import UsersCollector
from src.data_collectors.organizations import OrganizationsCollector
from src.data_collectors.knowledge_base import KnowledgeBaseCollector
from src.data_collectors.macros import MacrosCollector, GroupsCollector
from src.utils.config import config
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


console = Console()


def print_banner():
    """Print application banner."""
    banner = """
    ╔══════════════════════════════════════════════╗
    ║             Zendesk Data Collector           ║
    ║         Export all your Zendesk data        ║
    ║              to Markdown files               ║
    ╚══════════════════════════════════════════════╝
    """
    console.print(banner, style="bold cyan")


def test_connection() -> bool:
    """Test connection to Zendesk API.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        client = ZendeskClient()
        success, message = client.test_connection()
        
        if success:
            console.print(f"✅ {message}", style="bold green")
            return True
        else:
            console.print(f"❌ {message}", style="bold red")
            return False
    except Exception as e:
        console.print(f"❌ Connection test failed: {e}", style="bold red")
        return False


def parse_date_range(date_range: Optional[str]) -> Optional[Tuple[str, str]]:
    """Parse date range string into tuple.
    
    Args:
        date_range: Date range in format "YYYY-MM-DD,YYYY-MM-DD"
        
    Returns:
        Tuple of (start_date, end_date) or None
    """
    if not date_range:
        return None
    
    try:
        start_date, end_date = date_range.split(',')
        # Validate date format
        datetime.strptime(start_date.strip(), '%Y-%m-%d')
        datetime.strptime(end_date.strip(), '%Y-%m-%d')
        return (start_date.strip(), end_date.strip())
    except (ValueError, AttributeError):
        console.print("❌ Invalid date range format. Use: YYYY-MM-DD,YYYY-MM-DD", style="bold red")
        return None


@click.group()
@click.option('--config-file', '-c', help='Path to configuration file')
def cli(config_file):
    """Zendesk Data Collector - Export all your Zendesk data to markdown files."""
    print_banner()
    
    # Test connection on startup
    if not test_connection():
        console.print("Please check your configuration and try again.", style="yellow")
        sys.exit(1)


@cli.command()
@click.option('--status', help='Filter by status (open, pending, solved, closed)')
@click.option('--date-range', help='Date range: YYYY-MM-DD,YYYY-MM-DD')
@click.option('--no-comments', is_flag=True, help='Skip ticket comments')
@click.option('--output-dir', help='Custom output directory')
def tickets(status, date_range, no_comments, output_dir):
    """Collect and export all tickets."""
    console.print("🎫 Starting tickets collection...", style="bold blue")
    
    # Parse date range
    parsed_date_range = parse_date_range(date_range)
    if date_range and not parsed_date_range:
        return
    
    try:
        collector = TicketsCollector()
        
        # Collect tickets
        tickets_data = collector.collect_all(
            status_filter=status,
            date_range=parsed_date_range,
            include_comments=not no_comments
        )
        
        if tickets_data:
            # Export to markdown
            success = collector.export_to_markdown(tickets_data)
            
            if success:
                # Show statistics
                stats = collector.get_statistics(tickets_data)
                display_statistics("Tickets", stats)
        else:
            console.print("No tickets found.", style="yellow")
            
    except Exception as e:
        console.print(f"❌ Error collecting tickets: {e}", style="bold red")


@cli.command()
@click.option('--role', help='Filter by role (agent, admin, end-user)')
@click.option('--output-dir', help='Custom output directory')
def users(role, output_dir):
    """Collect and export all users."""
    console.print("👥 Starting users collection...", style="bold blue")
    
    try:
        collector = UsersCollector()
        
        # Collect users
        users_data = collector.collect_all(role_filter=role)
        
        if users_data:
            # Export to markdown
            success = collector.export_to_markdown(users_data)
            
            if success:
                # Show statistics
                stats = collector.get_statistics(users_data)
                display_statistics("Users", stats)
        else:
            console.print("No users found.", style="yellow")
            
    except Exception as e:
        console.print(f"❌ Error collecting users: {e}", style="bold red")


@cli.command()
@click.option('--output-dir', help='Custom output directory')
def organizations(output_dir):
    """Collect and export all organizations."""
    console.print("🏢 Starting organizations collection...", style="bold blue")
    
    try:
        collector = OrganizationsCollector()
        
        # Collect organizations
        orgs_data = collector.collect_all()
        
        if orgs_data:
            # Export to markdown
            success = collector.export_to_markdown(orgs_data)
            
            if success:
                # Show statistics
                stats = collector.get_statistics(orgs_data)
                display_statistics("Organizations", stats)
        else:
            console.print("No organizations found.", style="yellow")
            
    except Exception as e:
        console.print(f"❌ Error collecting organizations: {e}", style="bold red")


@cli.command(name='knowledge-base')
@click.option('--output-dir', help='Custom output directory')
def knowledge_base(output_dir):
    """Collect and export knowledge base articles."""
    console.print("📚 Starting knowledge base collection...", style="bold blue")
    
    try:
        collector = KnowledgeBaseCollector()
        
        # Collect knowledge base data
        kb_data = collector.collect_all()
        
        if any(kb_data.values()):
            # Export to markdown
            success = collector.export_to_markdown(kb_data)
            
            if success:
                # Show statistics
                stats = collector.get_statistics(kb_data)
                display_statistics("Knowledge Base", stats)
        else:
            console.print("No knowledge base data found.", style="yellow")
            
    except Exception as e:
        console.print(f"❌ Error collecting knowledge base: {e}", style="bold red")


@cli.command()
@click.option('--active-only', is_flag=True, help='Only collect active macros')
@click.option('--output-dir', help='Custom output directory')
def macros(active_only, output_dir):
    """Collect and export all macros."""
    console.print("⚡ Starting macros collection...", style="bold blue")
    
    try:
        collector = MacrosCollector()
        
        # Collect macros
        macros_data = collector.collect_all(active_only=active_only)
        
        if macros_data:
            # Export to markdown
            success = collector.export_to_markdown(macros_data)
            
            if success:
                # Show statistics
                stats = collector.get_statistics(macros_data)
                display_statistics("Macros", stats)
        else:
            console.print("No macros found.", style="yellow")
            
    except Exception as e:
        console.print(f"❌ Error collecting macros: {e}", style="bold red")


@cli.command()
@click.option('--include-deleted', is_flag=True, help='Include deleted groups')
@click.option('--output-dir', help='Custom output directory')
def groups(include_deleted, output_dir):
    """Collect and export all groups."""
    console.print("👥 Starting groups collection...", style="bold blue")
    
    try:
        collector = GroupsCollector()
        
        # Collect groups
        groups_data = collector.collect_all(include_deleted=include_deleted)
        
        if groups_data:
            # Export to markdown
            success = collector.export_to_markdown(groups_data)
            
            if success:
                # Show statistics
                stats = collector.get_statistics(groups_data)
                display_statistics("Groups", stats)
        else:
            console.print("No groups found.", style="yellow")
            
    except Exception as e:
        console.print(f"❌ Error collecting groups: {e}", style="bold red")


@cli.command()
@click.option('--status', help='Filter tickets by status')
@click.option('--date-range', help='Filter tickets by date range: YYYY-MM-DD,YYYY-MM-DD')
@click.option('--no-comments', is_flag=True, help='Skip ticket comments')
@click.option('--user-role', help='Filter users by role')
@click.option('--active-macros-only', is_flag=True, help='Only collect active macros')
@click.option('--include-deleted-groups', is_flag=True, help='Include deleted groups')
@click.option('--output-dir', help='Custom output directory')
def all(status, date_range, no_comments, user_role, active_macros_only, 
        include_deleted_groups, output_dir):
    """Collect and export ALL Zendesk data."""
    console.print("🚀 Starting complete Zendesk data collection...", style="bold cyan")
    
    # Parse date range
    parsed_date_range = parse_date_range(date_range)
    if date_range and not parsed_date_range:
        return
    
    all_stats = {}
    
    try:
        # 1. Collect Tickets
        console.print("\n1️⃣ Collecting Tickets", style="bold yellow")
        tickets_collector = TicketsCollector()
        tickets_data = tickets_collector.collect_all(
            status_filter=status,
            date_range=parsed_date_range,
            include_comments=not no_comments
        )
        if tickets_data:
            tickets_collector.export_to_markdown(tickets_data)
            all_stats['Tickets'] = tickets_collector.get_statistics(tickets_data)
        
        # 2. Collect Users
        console.print("\n2️⃣ Collecting Users", style="bold yellow")
        users_collector = UsersCollector()
        users_data = users_collector.collect_all(role_filter=user_role)
        if users_data:
            users_collector.export_to_markdown(users_data)
            all_stats['Users'] = users_collector.get_statistics(users_data)
        
        # 3. Collect Organizations
        console.print("\n3️⃣ Collecting Organizations", style="bold yellow")
        orgs_collector = OrganizationsCollector()
        orgs_data = orgs_collector.collect_all()
        if orgs_data:
            orgs_collector.export_to_markdown(orgs_data)
            all_stats['Organizations'] = orgs_collector.get_statistics(orgs_data)
        
        # 4. Collect Knowledge Base
        console.print("\n4️⃣ Collecting Knowledge Base", style="bold yellow")
        kb_collector = KnowledgeBaseCollector()
        kb_data = kb_collector.collect_all()
        if any(kb_data.values()):
            kb_collector.export_to_markdown(kb_data)
            all_stats['Knowledge Base'] = kb_collector.get_statistics(kb_data)
        
        # 5. Collect Macros
        console.print("\n5️⃣ Collecting Macros", style="bold yellow")
        macros_collector = MacrosCollector()
        macros_data = macros_collector.collect_all(active_only=active_macros_only)
        if macros_data:
            macros_collector.export_to_markdown(macros_data)
            all_stats['Macros'] = macros_collector.get_statistics(macros_data)
        
        # 6. Collect Groups
        console.print("\n6️⃣ Collecting Groups", style="bold yellow")
        groups_collector = GroupsCollector()
        groups_data = groups_collector.collect_all(include_deleted=include_deleted_groups)
        if groups_data:
            groups_collector.export_to_markdown(groups_data)
            all_stats['Groups'] = groups_collector.get_statistics(groups_data)
        
        # Display summary
        console.print("\n" + "="*60, style="bold cyan")
        console.print("📊 COLLECTION SUMMARY", style="bold cyan")
        console.print("="*60, style="bold cyan")
        
        for category, stats in all_stats.items():
            display_statistics(category, stats)
        
        console.print("\n🎉 Complete data collection finished!", style="bold green")
        console.print(f"📁 All files saved to: {config.get_output_config()['base_directory']}", style="green")
        
    except Exception as e:
        console.print(f"❌ Error during complete collection: {e}", style="bold red")


@cli.command()
def test():
    """Test connection to Zendesk API."""
    console.print("🔍 Testing Zendesk API connection...", style="bold blue")
    
    if test_connection():
        console.print("✅ Connection test successful!", style="bold green")
    else:
        console.print("❌ Connection test failed!", style="bold red")
        sys.exit(1)


def display_statistics(category: str, stats: dict):
    """Display statistics in a formatted table.
    
    Args:
        category: Data category name
        stats: Statistics dictionary
    """
    table = Table(title=f"{category} Statistics", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")
    
    for key, value in stats.items():
        if isinstance(value, dict):
            # Handle nested dictionaries
            for sub_key, sub_value in value.items():
                table.add_row(f"{key.replace('_', ' ').title()} - {sub_key}", str(sub_value))
        else:
            table.add_row(key.replace('_', ' ').title(), str(value))
    
    console.print(table)
    console.print()


@cli.command()
def version():
    """Show version information."""
    console.print("Zendesk Data Collector v1.0.0", style="bold cyan")
    console.print("Built with Python, Click, Rich, and ❤️", style="dim")


if __name__ == '__main__':
    cli() 