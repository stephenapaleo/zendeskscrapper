# Zendesk Data Collector

A comprehensive Python tool to collect all data from your Zendesk instance via REST API and export it as organized markdown files.

## Features

✅ **Complete Data Collection**
- 🎫 Support tickets with comments and attachments
- 👥 Users (agents, admins, end-users) with profiles and statistics
- 🏢 Organizations with associated users
- 📚 Knowledge base articles, sections, and categories
- ⚡ Macros and automation rules
- 👥 Groups and team assignments

✅ **Smart Organization**
- Files organized by category/type in separate directories
- Cross-referenced markdown files with proper linking
- Automatic index files for easy navigation
- Sanitized filenames for cross-platform compatibility

✅ **Advanced Features**
- Rate limiting to respect Zendesk API limits (700 requests/minute)
- Rich progress bars and real-time feedback
- Comprehensive error handling and retry logic
- Flexible filtering options (date range, status, role, etc.)
- Statistics and summary reporting

## Installation

### Prerequisites

- Python 3.8 or higher
- Zendesk API credentials (subdomain, email, API token)

### Setup

1. **Clone or download this repository**
   ```bash
   git clone <repository-url>
   cd zendeskscrapper
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your Zendesk credentials**
   ```bash
   # Copy the example environment file
   copy .env.example .env
   
   # Edit .env with your credentials
   notepad .env
   ```

   Add your Zendesk credentials to `.env`:
   ```env
   ZENDESK_SUBDOMAIN=your-subdomain
   ZENDESK_EMAIL=your-email@company.com
   ZENDESK_API_TOKEN=your-api-token
   ```

4. **Test your connection**
   ```bash
   python main.py test
   ```

## Getting Your Zendesk API Token

1. Log in to your Zendesk instance as an admin
2. Go to **Admin Center** → **Apps and integrations** → **APIs** → **Zendesk API**
3. Enable **Token access** if not already enabled
4. Click **Add API token**
5. Copy the generated token to your `.env` file

**Note**: API tokens use the format `{email_address}/token:{api_token}` for authentication as specified in the [Zendesk API documentation](https://developer.zendesk.com/api-reference/introduction/security-and-auth/#api-token). Our tool handles this formatting automatically using your email and token from the `.env` file.

## Usage

### Quick Start - Export Everything

```bash
# Export all your Zendesk data
python main.py all
```

### Individual Data Types

```bash
# Export only tickets
python main.py tickets

# Export only users
python main.py users

# Export only organizations
python main.py organizations

# Export knowledge base articles
python main.py knowledge-base

# Export macros
python main.py macros

# Export groups
python main.py groups
```

### Advanced Filtering

```bash
# Export tickets with filters
python main.py tickets --status open --date-range "2023-01-01,2023-12-31"

# Export only agents and admins
python main.py users --role agent

# Export only active macros
python main.py macros --active-only

# Export including deleted groups
python main.py groups --include-deleted
```

### Complete Options

```bash
# Export everything with all options
python main.py all \
    --status solved \
    --date-range "2023-01-01,2023-12-31" \
    --user-role agent \
    --active-macros-only \
    --include-deleted-groups
```

## Output Structure

The tool creates organized markdown files in the `output/` directory:

```
output/
├── tickets/
│   ├── open/
│   │   ├── 12345-urgent-login-issue.md
│   │   └── index.md
│   ├── solved/
│   ├── closed/
│   └── index.md
├── users/
│   ├── agents/
│   │   ├── 123-john-doe.md
│   │   └── index.md
│   ├── end-users/
│   └── index.md
├── organizations/
│   ├── 456-acme-corp.md
│   └── index.md
├── knowledge-base/
│   ├── getting-started/
│   │   ├── 789-how-to-login.md
│   │   └── index.md
│   ├── troubleshooting/
│   └── index.md
├── macros/
│   ├── 321-close-ticket-macro.md
│   └── index.md
└── groups/
    ├── 654-support-team.md
    └── index.md
```

## Configuration

### Environment Variables (.env)

```env
ZENDESK_SUBDOMAIN=your-subdomain
ZENDESK_EMAIL=your-email@company.com
ZENDESK_API_TOKEN=your-api-token
```

### Configuration File (config/config.yaml)

You can customize the behavior by editing `config/config.yaml`:

```yaml
zendesk:
  subdomain: ${ZENDESK_SUBDOMAIN}
  email: ${ZENDESK_EMAIL}
  api_token: ${ZENDESK_API_TOKEN}

rate_limiting:
  requests_per_minute: 700  # Zendesk's limit
  retry_attempts: 3
  backoff_factor: 2

output:
  base_directory: "output"
  date_format: "%Y-%m-%d %H:%M:%S"

categories:
  tickets:
    directory: "tickets"
    subcategories: ["open", "solved", "closed", "pending"]
  users:
    directory: "users"
    subcategories: ["agents", "end-users"]
  # ... more categories
```

## Command Reference

### Main Commands

| Command | Description |
|---------|-------------|
| `all` | Export all data types |
| `tickets` | Export support tickets |
| `users` | Export users and agents |
| `organizations` | Export organizations |
| `knowledge-base` | Export help center articles |
| `macros` | Export macros and automation |
| `groups` | Export agent groups |
| `test` | Test API connection |
| `version` | Show version info |

### Tickets Options

| Option | Description |
|--------|-------------|
| `--status` | Filter by status (open, pending, solved, closed) |
| `--date-range` | Date range: YYYY-MM-DD,YYYY-MM-DD |
| `--no-comments` | Skip ticket comments (faster) |

### Users Options

| Option | Description |
|--------|-------------|
| `--role` | Filter by role (agent, admin, end-user) |

### Macros Options

| Option | Description |
|--------|-------------|
| `--active-only` | Only export active macros |

### Groups Options

| Option | Description |
|--------|-------------|
| `--include-deleted` | Include deleted groups |

## Markdown Output Examples

### Ticket Example

```markdown
# Ticket #12345: Urgent Login Issue

**Status:** Open  
**Priority:** High  
**Created:** 2023-12-01 14:30:00  
**Requester:** [John Doe](../users/123-john-doe.md)  
**Assignee:** [Jane Smith](../users/456-jane-smith.md)  
**Organization:** [Acme Corp](../organizations/789-acme-corp.md)  

## Description
User cannot log in to the application...

## Comments
### Comment by Jane Smith - 2023-12-01 15:00:00
I'm looking into this issue...

## Custom Fields
| Field | Value |
|-------|-------|
| Severity | High |
| Product | Web App |

## Tags
- login
- urgent
- web-app
```

### User Example

```markdown
# John Doe

**Email:** john.doe@acme.com  
**Role:** Agent  
**Created:** 2023-01-15 09:00:00  
**Organization:** [Acme Corp](../organizations/789-acme-corp.md)  

## Groups
- Support Team
- Escalation Team

## Statistics
- **Tickets Requested:** 5
- **Tickets Solved:** 127
- **Tickets Assigned:** 23
```

## Performance and Rate Limiting

- **Respects Zendesk's 700 requests/minute limit**
- **Automatic retry with exponential backoff**
- **Progress tracking with ETAs**
- **Memory efficient with streaming for large datasets**

## Troubleshooting

### Common Issues

**Authentication Error (401)**
```
❌ Authentication failed. Check your API credentials.
```
- Verify your email and API token in `.env`
- Ensure your user has API access permissions

**Rate Limit Exceeded (429)**
```
Rate limit exceeded. Waiting 60 seconds...
```
- The tool handles this automatically
- No action needed, just wait

**Permission Denied (403)**
```
❌ Access forbidden. Check your permissions.
```
- Your user may not have access to certain data
- Contact your Zendesk admin for proper permissions

### Getting Help

1. **Check the logs** - Error messages are detailed and actionable
2. **Test connection** - Run `python main.py test` to verify setup
3. **Verify permissions** - Ensure your API user has access to all required endpoints

## Advanced Usage

### Custom Output Directory

```bash
python main.py all --output-dir "custom-export-$(date +%Y%m%d)"
```

### Partial Updates

```bash
# Only export recent tickets
python main.py tickets --date-range "2023-12-01,2023-12-31"

# Only export active items
python main.py macros --active-only
python main.py users --role agent
```

### Scripting and Automation

Create a batch script for regular exports:

```batch
@echo off
echo Starting Zendesk export...
python main.py all --date-range "2023-01-01,2023-12-31"
echo Export completed!
pause
```

## Security Notes

- API tokens are stored in `.env` file (not committed to version control)
- All requests use HTTPS
- No sensitive data is logged
- Rate limiting prevents API abuse

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or feature requests, please open an issue on the project repository.

---

**Built with ❤️ using Python, Click, Rich, and the Zendesk REST API** 
Cat fact: A house cat’s genome is 95.6 percent tiger, and they share many behaviors with their jungle ancestors, says Layla Morgan Wilde, a cat behavior expert and the founder of Cat Wisdom 101. These behaviors include scent marking by scratching, prey play, prey stalking, pouncing, chinning, and urine marking.
