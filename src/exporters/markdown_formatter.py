"""Markdown formatter for Zendesk data types."""
from typing import Dict, Any, List, Optional
from jinja2 import Template, Environment, DictLoader
import html
import re
from datetime import datetime

from src.exporters.base_exporter import BaseExporter


class MarkdownFormatter(BaseExporter):
    """Formatter for converting Zendesk data to markdown."""
    
    def __init__(self, category: str):
        """Initialize markdown formatter.
        
        Args:
            category: Data category
        """
        super().__init__(category)
        self.jinja_env = Environment(loader=DictLoader(self._get_templates()))
        self.jinja_env.filters['format_date'] = self.format_date
        self.jinja_env.filters['format_html'] = self._format_html_to_markdown
        self.jinja_env.filters['format_list'] = self.format_list_as_markdown
    
    def _get_templates(self) -> Dict[str, str]:
        """Get Jinja2 templates for different data types.
        
        Returns:
            Dictionary of template names and content
        """
        return {
            'ticket': '''# Ticket #{{ ticket.id }}: {{ ticket.subject }}

**Status:** {{ ticket.status | title }}  
**Priority:** {{ ticket.priority | title }}  
**Type:** {{ ticket.type | title }}  
**Created:** {{ ticket.created_at | format_date }}  
**Updated:** {{ ticket.updated_at | format_date }}  
{% if ticket.due_at %}**Due:** {{ ticket.due_at | format_date }}  {% endif %}
**Requester:** [{{ requester_name }}](../users/{{ requester_file }})  
**Assignee:** {% if assignee_name %}[{{ assignee_name }}](../users/{{ assignee_file }}){% else %}Unassigned{% endif %}  
{% if organization_name %}**Organization:** [{{ organization_name }}](../organizations/{{ organization_file }})  {% endif %}
{% if ticket.group_id %}**Group:** {{ group_name }}  {% endif %}

## Description
{{ ticket.description | format_html }}

{% if comments %}## Comments
{% for comment in comments %}
### Comment by {{ comment.author_name }} - {{ comment.created_at | format_date }}
{{ comment.html_body | format_html }}
{% if comment.attachments %}
**Attachments:**
{% for attachment in comment.attachments %}
- [{{ attachment.file_name }}]({{ attachment.content_url }})
{% endfor %}
{% endif %}

---
{% endfor %}
{% endif %}

{% if custom_fields %}## Custom Fields
{{ custom_fields_table }}
{% endif %}

{% if ticket.tags %}## Tags
{{ ticket.tags | format_list }}
{% endif %}

{% if ticket.satisfaction_rating %}## Satisfaction Rating
**Score:** {{ ticket.satisfaction_rating.score }}  
{% if ticket.satisfaction_rating.comment %}**Comment:** {{ ticket.satisfaction_rating.comment }}{% endif %}
{% endif %}''',

            'user': '''# {{ user.name }}

**Email:** {{ user.email }}  
**Role:** {{ user.role | title }}  
**Active:** {{ "Yes" if user.active else "No" }}  
**Verified:** {{ "Yes" if user.verified else "No" }}  
**Created:** {{ user.created_at | format_date }}  
**Updated:** {{ user.updated_at | format_date }}  
{% if user.last_login_at %}**Last Login:** {{ user.last_login_at | format_date }}  {% endif %}
{% if organization_name %}**Organization:** [{{ organization_name }}](../organizations/{{ organization_file }})  {% endif %}
**Locale:** {{ user.locale }}  
**Time Zone:** {{ user.time_zone }}  

{% if user.details %}## Details
{{ user.details | format_html }}
{% endif %}

{% if user.notes %}## Notes
{{ user.notes | format_html }}
{% endif %}

{% if user.phone %}## Contact Information
**Phone:** {{ user.phone }}  
{% endif %}

{% if groups %}## Groups
{{ groups | format_list }}
{% endif %}

{% if user.user_fields %}## Custom Fields
{% for field_name, field_value in user.user_fields.items() %}
**{{ field_name }}:** {{ field_value }}  
{% endfor %}
{% endif %}

{% if user.tags %}## Tags
{{ user.tags | format_list }}
{% endif %}

## Statistics
- **Tickets Requested:** {{ stats.tickets_requested | default(0) }}
- **Tickets Solved:** {{ stats.tickets_solved | default(0) }}
- **Tickets Assigned:** {{ stats.tickets_assigned | default(0) }}''',

            'organization': '''# {{ organization.name }}

{% if organization.domain_names %}**Domains:** {{ organization.domain_names | join(", ") }}  {% endif %}
**Created:** {{ organization.created_at | format_date }}  
**Updated:** {{ organization.updated_at | format_date }}  

{% if organization.details %}## Details
{{ organization.details | format_html }}
{% endif %}

{% if organization.notes %}## Notes
{{ organization.notes | format_html }}
{% endif %}

{% if organization.organization_fields %}## Custom Fields
{% for field_name, field_value in organization.organization_fields.items() %}
**{{ field_name }}:** {{ field_value }}  
{% endfor %}
{% endif %}

{% if organization.tags %}## Tags
{{ organization.tags | format_list }}
{% endif %}

{% if users %}## Users ({{ users | length }})
{% for user in users[:10] %}- [{{ user.name }}](../users/{{ user.filename }}) - {{ user.role | title }}
{% endfor %}
{% if users | length > 10 %}
... and {{ (users | length) - 10 }} more users
{% endif %}
{% endif %}''',

            'article': '''# {{ article.title }}

**Author:** {{ author_name }}  
**Created:** {{ article.created_at | format_date }}  
**Updated:** {{ article.updated_at | format_date }}  
**Section:** [{{ section_name }}](../sections/{{ section_file }})  
**Category:** [{{ category_name }}](../categories/{{ category_file }})  
**Locale:** {{ article.locale }}  
**Position:** {{ article.position }}  
{% if article.vote_sum %}**Votes:** {{ article.vote_sum }} ({{ article.vote_count }} total)  {% endif %}

{% if article.label_names %}## Labels
{{ article.label_names | format_list }}
{% endif %}

## Content
{{ article.body | format_html }}

{% if article.attachments %}## Attachments
{% for attachment in article.attachments %}
- [{{ attachment.file_name }}]({{ attachment.content_url }})
{% endfor %}
{% endif %}''',

            'macro': '''# {{ macro.title }}

**Active:** {{ "Yes" if macro.active else "No" }}  
**Created:** {{ macro.created_at | format_date }}  
**Updated:** {{ macro.updated_at | format_date }}  
**Position:** {{ macro.position }}  

{% if macro.description %}## Description
{{ macro.description }}
{% endif %}

## Actions
{% for action in macro.actions %}
### {{ action.field | title }}
**Value:** {{ action.value }}  
{% endfor %}

{% if macro.restriction %}## Restrictions
{{ macro.restriction }}
{% endif %}''',

            'group': '''# {{ group.name }}

**Created:** {{ group.created_at | format_date }}  
**Updated:** {{ group.updated_at | format_date }}  
**Default:** {{ "Yes" if group.default else "No" }}  
**Deleted:** {{ "Yes" if group.deleted else "No" }}  

{% if group.description %}## Description
{{ group.description }}
{% endif %}

{% if agents %}## Agents ({{ agents | length }})
{% for agent in agents %}- [{{ agent.name }}](../users/{{ agent.filename }})
{% endfor %}
{% endif %}'''
        }
    
    def _format_html_to_markdown(self, html_content: str) -> str:
        """Convert HTML content to markdown.
        
        Args:
            html_content: HTML content string
            
        Returns:
            Markdown formatted content
        """
        if not html_content:
            return ""
        
        # Unescape HTML entities
        content = html.unescape(html_content)
        
        # Convert common HTML tags to markdown
        conversions = [
            # Headers
            (r'<h1[^>]*>(.*?)</h1>', r'# \1'),
            (r'<h2[^>]*>(.*?)</h2>', r'## \1'),
            (r'<h3[^>]*>(.*?)</h3>', r'### \1'),
            (r'<h4[^>]*>(.*?)</h4>', r'#### \1'),
            (r'<h5[^>]*>(.*?)</h5>', r'##### \1'),
            (r'<h6[^>]*>(.*?)</h6>', r'###### \1'),
            
            # Text formatting
            (r'<strong[^>]*>(.*?)</strong>', r'**\1**'),
            (r'<b[^>]*>(.*?)</b>', r'**\1**'),
            (r'<em[^>]*>(.*?)</em>', r'*\1*'),
            (r'<i[^>]*>(.*?)</i>', r'*\1*'),
            (r'<code[^>]*>(.*?)</code>', r'`\1`'),
            
            # Lists
            (r'<ul[^>]*>', ''),
            (r'</ul>', ''),
            (r'<ol[^>]*>', ''),
            (r'</ol>', ''),
            (r'<li[^>]*>(.*?)</li>', r'- \1'),
            
            # Links
            (r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', r'[\2](\1)'),
            
            # Line breaks and paragraphs
            (r'<br[^>]*/?>', '\n'),
            (r'<p[^>]*>', '\n'),
            (r'</p>', '\n'),
            
            # Divs (just remove tags)
            (r'<div[^>]*>', ''),
            (r'</div>', ''),
            
            # Remove any remaining HTML tags
            (r'<[^>]+>', ''),
        ]
        
        for pattern, replacement in conversions:
            content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.MULTILINE)
        
        # Clean up multiple newlines and spaces
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = re.sub(r'[ \t]+', ' ', content)
        
        return content.strip()
    
    def format_ticket(self, ticket: Dict[str, Any], **context) -> str:
        """Format ticket data as markdown.
        
        Args:
            ticket: Ticket data
            **context: Additional context (comments, custom_fields, etc.)
            
        Returns:
            Formatted markdown content
        """
        template = self.jinja_env.get_template('ticket')
        return template.render(ticket=ticket, **context)
    
    def format_user(self, user: Dict[str, Any], **context) -> str:
        """Format user data as markdown.
        
        Args:
            user: User data
            **context: Additional context
            
        Returns:
            Formatted markdown content
        """
        template = self.jinja_env.get_template('user')
        return template.render(user=user, **context)
    
    def format_organization(self, organization: Dict[str, Any], **context) -> str:
        """Format organization data as markdown.
        
        Args:
            organization: Organization data
            **context: Additional context
            
        Returns:
            Formatted markdown content
        """
        template = self.jinja_env.get_template('organization')
        return template.render(organization=organization, **context)
    
    def format_article(self, article: Dict[str, Any], **context) -> str:
        """Format knowledge base article as markdown.
        
        Args:
            article: Article data
            **context: Additional context
            
        Returns:
            Formatted markdown content
        """
        template = self.jinja_env.get_template('article')
        return template.render(article=article, **context)
    
    def format_macro(self, macro: Dict[str, Any], **context) -> str:
        """Format macro data as markdown.
        
        Args:
            macro: Macro data
            **context: Additional context
            
        Returns:
            Formatted markdown content
        """
        template = self.jinja_env.get_template('macro')
        return template.render(macro=macro, **context)
    
    def format_group(self, group: Dict[str, Any], **context) -> str:
        """Format group data as markdown.
        
        Args:
            group: Group data
            **context: Additional context
            
        Returns:
            Formatted markdown content
        """
        template = self.jinja_env.get_template('group')
        return template.render(group=group, **context) 