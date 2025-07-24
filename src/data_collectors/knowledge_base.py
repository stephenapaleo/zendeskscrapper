"""Knowledge base data collector for Zendesk."""
from typing import Dict, Any, List, Optional
from collections import defaultdict

from src.zendesk_client import ZendeskClient, ZendeskAPIError
from src.exporters.markdown_formatter import MarkdownFormatter
from src.utils.config import config
from rich.console import Console
from rich.progress import Progress


class KnowledgeBaseCollector:
    """Collector for Zendesk knowledge base data."""
    
    def __init__(self):
        """Initialize knowledge base collector."""
        self.client = ZendeskClient()
        self.formatter = MarkdownFormatter('knowledge-base')
        self.console = Console()
        
        # Cache for related data
        self.users_cache = {}
        self.sections_cache = {}
        self.categories_cache = {}
    
    def collect_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """Collect all knowledge base data.
        
        Returns:
            Dictionary with articles, sections, and categories
        """
        self.console.print("📚 Collecting knowledge base data...", style="bold blue")
        
        result = {
            'articles': [],
            'sections': [],
            'categories': []
        }
        
        try:
            # Collect categories first
            result['categories'] = self._collect_categories()
            
            # Collect sections
            result['sections'] = self._collect_sections()
            
            # Collect articles
            result['articles'] = self._collect_articles()
            
            return result
            
        except ZendeskAPIError as e:
            self.console.print(f"❌ Error collecting knowledge base data: {e}", style="bold red")
            return result
    
    def _collect_categories(self) -> List[Dict[str, Any]]:
        """Collect help center categories.
        
        Returns:
            List of category data
        """
        categories = []
        total_categories = 0
        
        try:
            with Progress() as progress:
                task = progress.add_task("Fetching categories...", total=None)
                
                for category in self.client.get_help_center_categories():
                    categories.append(category)
                    self.categories_cache[category['id']] = category
                    total_categories += 1
                    
                    progress.update(task, advance=1, description=f"Fetched {total_categories} categories...")
                
                progress.update(task, completed=True, description=f"Collected {total_categories} categories")
            
            self.console.print(f"✅ Successfully collected {total_categories} categories", style="bold green")
            
        except ZendeskAPIError as e:
            self.console.print(f"❌ Error collecting categories: {e}", style="bold red")
        
        return categories
    
    def _collect_sections(self) -> List[Dict[str, Any]]:
        """Collect help center sections.
        
        Returns:
            List of section data
        """
        sections = []
        total_sections = 0
        
        try:
            with Progress() as progress:
                task = progress.add_task("Fetching sections...", total=None)
                
                for section in self.client.get_help_center_sections():
                    # Enrich with category information
                    section['category_info'] = self.categories_cache.get(section.get('category_id'), {})
                    
                    sections.append(section)
                    self.sections_cache[section['id']] = section
                    total_sections += 1
                    
                    progress.update(task, advance=1, description=f"Fetched {total_sections} sections...")
                
                progress.update(task, completed=True, description=f"Collected {total_sections} sections")
            
            self.console.print(f"✅ Successfully collected {total_sections} sections", style="bold green")
            
        except ZendeskAPIError as e:
            self.console.print(f"❌ Error collecting sections: {e}", style="bold red")
        
        return sections
    
    def _collect_articles(self) -> List[Dict[str, Any]]:
        """Collect help center articles.
        
        Returns:
            List of article data
        """
        articles = []
        total_articles = 0
        
        try:
            with Progress() as progress:
                task = progress.add_task("Fetching articles...", total=None)
                
                for article in self.client.get_help_center_articles():
                    # Enrich article data
                    enriched_article = self._enrich_article_data(article)
                    
                    articles.append(enriched_article)
                    total_articles += 1
                    
                    progress.update(task, advance=1, description=f"Fetched {total_articles} articles...")
                
                progress.update(task, completed=True, description=f"Collected {total_articles} articles")
            
            self.console.print(f"✅ Successfully collected {total_articles} articles", style="bold green")
            
        except ZendeskAPIError as e:
            self.console.print(f"❌ Error collecting articles: {e}", style="bold red")
        
        return articles
    
    def _enrich_article_data(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich article data with additional information.
        
        Args:
            article: Base article data
            
        Returns:
            Enriched article data
        """
        # Add author information
        article['author_info'] = self._get_user_info(article.get('author_id'))
        
        # Add section information
        article['section_info'] = self.sections_cache.get(article.get('section_id'), {})
        
        # Add category information (through section)
        section = article.get('section_info', {})
        if section:
            article['category_info'] = section.get('category_info', {})
        
        return article
    
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
    
    def export_to_markdown(self, kb_data: Dict[str, List[Dict[str, Any]]]) -> bool:
        """Export knowledge base data to markdown files.
        
        Args:
            kb_data: Knowledge base data (articles, sections, categories)
            
        Returns:
            True if successful, False otherwise
        """
        self.console.print("📝 Exporting knowledge base to markdown...", style="bold blue")
        
        total_exported = 0
        
        try:
            # Export articles organized by section/category
            articles = kb_data.get('articles', [])
            if articles:
                articles_by_section = defaultdict(list)
                
                for article in articles:
                    section_name = article.get('section_info', {}).get('name', 'uncategorized')
                    section_name = self.formatter.sanitize_filename(section_name.lower())
                    articles_by_section[section_name].append(article)
                
                with Progress() as progress:
                    total_articles = len(articles)
                    task = progress.add_task("Exporting articles...", total=total_articles)
                    
                    for section_name, section_articles in articles_by_section.items():
                        for article in section_articles:
                            # Prepare context for template
                            context = self._prepare_article_context(article)
                            
                            # Generate markdown content
                            content = self.formatter.format_article(article, **context)
                            
                            # Determine output path (organize by section)
                            output_path = self.formatter.get_output_path(article, section_name)
                            
                            # Write file
                            if self.formatter.write_file(content, output_path):
                                total_exported += 1
                            
                            progress.update(task, advance=1)
                        
                        # Create index for this section
                        self.formatter.create_index_file(section_articles, section_name)
                
                # Create main index
                self.formatter.create_index_file(articles)
            
            self.console.print(f"✅ Successfully exported {total_exported} knowledge base items", style="bold green")
            return True
            
        except Exception as e:
            self.console.print(f"❌ Error exporting knowledge base: {e}", style="bold red")
            return False
    
    def _prepare_article_context(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare context for article template.
        
        Args:
            article: Article data
            
        Returns:
            Context dictionary for template rendering
        """
        context = {}
        
        # Author information
        author = article.get('author_info', {})
        context['author_name'] = author.get('name', 'Unknown')
        
        # Section information
        section = article.get('section_info', {})
        context['section_name'] = section.get('name', 'Unknown')
        context['section_file'] = self.formatter.sanitize_filename(
            f"{section.get('id', 'unknown')}-{section.get('name', 'unknown')}"
        )
        
        # Category information
        category = article.get('category_info', {})
        context['category_name'] = category.get('name', 'Unknown')
        context['category_file'] = self.formatter.sanitize_filename(
            f"{category.get('id', 'unknown')}-{category.get('name', 'unknown')}"
        )
        
        return context
    
    def get_statistics(self, kb_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Get statistics about collected knowledge base data.
        
        Args:
            kb_data: Knowledge base data
            
        Returns:
            Statistics dictionary
        """
        articles = kb_data.get('articles', [])
        sections = kb_data.get('sections', [])
        categories = kb_data.get('categories', [])
        
        stats = {
            'total_articles': len(articles),
            'total_sections': len(sections),
            'total_categories': len(categories),
            'articles_by_locale': defaultdict(int),
            'articles_with_votes': 0,
            'average_votes': 0,
        }
        
        total_votes = 0
        articles_with_votes = 0
        
        for article in articles:
            # Locale stats
            locale = article.get('locale', 'unknown')
            stats['articles_by_locale'][locale] += 1
            
            # Vote stats
            vote_sum = article.get('vote_sum', 0)
            if vote_sum:
                articles_with_votes += 1
                total_votes += vote_sum
        
        stats['articles_with_votes'] = articles_with_votes
        if articles_with_votes > 0:
            stats['average_votes'] = total_votes / articles_with_votes
        
        return stats 