"""Base exporter class with common functionality."""
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import unicodedata

from src.utils.config import config


class BaseExporter:
    """Base class for exporting Zendesk data to files."""
    
    def __init__(self, category: str):
        """Initialize base exporter.
        
        Args:
            category: Data category (e.g., 'tickets', 'users')
        """
        self.category = category
        self.output_config = config.get_output_config()
        self.category_config = config.get_category_config(category)
        self.base_directory = Path(self.output_config['base_directory'])
        self.category_directory = self.base_directory / self.category_config.get('directory', category)
        
        # Ensure output directories exist
        self._create_directories()
    
    def _create_directories(self):
        """Create necessary output directories."""
        self.category_directory.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories if configured
        subcategories = self.category_config.get('subcategories', [])
        for subcat in subcategories:
            (self.category_directory / subcat).mkdir(parents=True, exist_ok=True)
    
    def sanitize_filename(self, filename: str, max_length: int = 100) -> str:
        """Sanitize filename for filesystem compatibility.
        
        Args:
            filename: Original filename
            max_length: Maximum filename length
            
        Returns:
            Sanitized filename
        """
        # Normalize unicode characters
        filename = unicodedata.normalize('NFKD', filename)
        
        # Replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '-', filename)
        
        # Replace multiple spaces/hyphens with single ones
        filename = re.sub(r'[-\s]+', '-', filename)
        
        # Remove leading/trailing hyphens and spaces
        filename = filename.strip('- ')
        
        # Truncate if too long, but preserve extension
        if len(filename) > max_length:
            name_part = filename[:max_length-3]
            filename = name_part + '...'
        
        return filename or 'untitled'
    
    def generate_filename(self, item: Dict[str, Any], template: str = None) -> str:
        """Generate filename for an item.
        
        Args:
            item: Data item
            template: Filename template (optional)
            
        Returns:
            Generated filename
        """
        if template:
            # Use template if provided
            try:
                filename = template.format(**item)
            except (KeyError, ValueError):
                # Fallback to default if template fails
                filename = f"{item.get('id', 'unknown')}-{item.get('title', item.get('name', 'untitled'))}"
        else:
            # Default filename generation
            item_id = item.get('id', 'unknown')
            title = item.get('title') or item.get('subject') or item.get('name') or 'untitled'
            filename = f"{item_id}-{title}"
        
        # Sanitize and add .md extension
        filename = self.sanitize_filename(filename)
        if not filename.endswith('.md'):
            filename += '.md'
        
        return filename
    
    def get_output_path(self, item: Dict[str, Any], subcategory: str = None, filename: str = None) -> Path:
        """Get output path for an item.
        
        Args:
            item: Data item
            subcategory: Subcategory for organization
            filename: Custom filename (optional)
            
        Returns:
            Full path for output file
        """
        if not filename:
            filename = self.generate_filename(item)
        
        if subcategory:
            return self.category_directory / subcategory / filename
        else:
            return self.category_directory / filename
    
    def write_file(self, content: str, filepath: Path) -> bool:
        """Write content to file.
        
        Args:
            content: File content
            filepath: Path to write to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Error writing file {filepath}: {e}")
            return False
    
    def create_index_file(self, items: List[Dict[str, Any]], subcategory: str = None) -> bool:
        """Create index file for a category or subcategory.
        
        Args:
            items: List of items to include in index
            subcategory: Subcategory name (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if subcategory:
            index_path = self.category_directory / subcategory / 'index.md'
            title = f"{self.category.title()} - {subcategory.title()}"
        else:
            index_path = self.category_directory / 'index.md'
            title = f"{self.category.title()}"
        
        # Generate index content
        content = self._generate_index_content(items, title, subcategory)
        
        return self.write_file(content, index_path)
    
    def _generate_index_content(self, items: List[Dict[str, Any]], title: str, subcategory: str = None) -> str:
        """Generate content for index file.
        
        Args:
            items: List of items
            title: Index title
            subcategory: Subcategory name
            
        Returns:
            Markdown content for index
        """
        content = f"# {title}\n\n"
        content += f"Generated on: {datetime.now().strftime(self.output_config['date_format'])}\n"
        content += f"Total items: {len(items)}\n\n"
        
        if not items:
            content += "No items found.\n"
            return content
        
        # Group items by some criteria if needed
        content += "## Items\n\n"
        
        for item in sorted(items, key=lambda x: x.get('created_at', x.get('id', ''))):
            item_id = item.get('id', 'unknown')
            title = item.get('title') or item.get('subject') or item.get('name') or 'Untitled'
            filename = self.generate_filename(item)
            
            # Create relative link
            if subcategory:
                link = f"./{filename}"
            else:
                link = f"./{filename}"
            
            # Add item to index
            content += f"- [{title}]({link})"
            
            # Add metadata
            if item.get('status'):
                content += f" - Status: {item['status']}"
            if item.get('created_at'):
                content += f" - Created: {item['created_at'][:10]}"  # Date only
            
            content += "\n"
        
        return content
    
    def get_relative_link(self, from_path: Path, to_path: Path) -> str:
        """Get relative link between two paths.
        
        Args:
            from_path: Source file path
            to_path: Target file path
            
        Returns:
            Relative link string
        """
        try:
            rel_path = os.path.relpath(to_path, from_path.parent)
            # Convert Windows paths to Unix-style for URLs
            return rel_path.replace('\\', '/')
        except ValueError:
            # If paths are on different drives (Windows), use absolute path
            return str(to_path)
    
    def format_date(self, date_string: Optional[str]) -> str:
        """Format date string for display.
        
        Args:
            date_string: ISO date string
            
        Returns:
            Formatted date string
        """
        if not date_string:
            return "N/A"
        
        try:
            # Parse ISO date
            date_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            return date_obj.strftime(self.output_config['date_format'])
        except (ValueError, AttributeError):
            return date_string
    
    def format_list_as_markdown(self, items: List[str], bullet_type: str = "-") -> str:
        """Format list of items as markdown.
        
        Args:
            items: List of items
            bullet_type: Bullet type ("-" or "*")
            
        Returns:
            Markdown formatted list
        """
        if not items:
            return "None"
        
        return "\n".join(f"{bullet_type} {item}" for item in items)
    
    def format_table(self, headers: List[str], rows: List[List[str]]) -> str:
        """Format data as markdown table.
        
        Args:
            headers: Table headers
            rows: Table rows
            
        Returns:
            Markdown formatted table
        """
        if not headers or not rows:
            return "No data available."
        
        # Create header
        table = "| " + " | ".join(headers) + " |\n"
        table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
        
        # Add rows
        for row in rows:
            # Ensure row has same number of columns as headers
            padded_row = row + [""] * (len(headers) - len(row))
            table += "| " + " | ".join(str(cell) for cell in padded_row[:len(headers)]) + " |\n"
        
        return table 