# Template & Prompt Library System Documentation

## Overview

The Template & Prompt Library System provides a comprehensive solution for managing reusable templates, prompt templates, and Architecture Decision Records (ADRs). This system enables teams to create, share, and reuse code patterns, documentation templates, and architectural decisions across projects.

## Features

### 🏗️ Module Templates
- **Reusable Code Modules**: Pre-built, configurable code templates for common functionality
- **Parameter Customization**: Dynamic parameter substitution for customization
- **File Structure Generation**: Complete file structure with proper organization
- **Multiple Tech Stacks**: Support for various technology stacks (Express.js, FastAPI, Laravel, Next.js, etc.)
- **Dependency Management**: Automatic dependency resolution and conflict detection

### 📝 Prompt Templates
- **LLM Prompt Engineering**: Structured prompts for code generation and documentation
- **Variable Substitution**: Dynamic variable replacement in prompts
- **Context Management**: Required context validation for prompts
- **Output Format Control**: Support for different output types (code, documentation, schemas)
- **Usage Analytics**: Track template usage and effectiveness

### 📋 Architecture Decision Records (ADR)
- **Decision Tracking**: Document and track architectural decisions
- **Status Management**: Track proposal, acceptance, deprecation, and supersession
- **Relationship Mapping**: Link related ADRs for better context
- **Timeline Views**: Visual timeline of architectural decisions
- **Workspace Integration**: ADR management within workspace context

### 🏪 Template Marketplace
- **Public Templates**: Community-shared templates
- **Private Templates**: Organization-specific templates
- **Rating & Reviews**: Community ratings and feedback
- **Usage Statistics**: Popularity metrics and trends
- **Search & Discovery**: Advanced search and filtering

## Quick Start

### 1. List Available Templates

```python
from backend.services.templates.template_manager import TemplateManager

# Initialize template manager
manager = TemplateManager()

# List authentication templates
modules, total = await manager.list_module_templates(
    category=TemplateCategory.AUTHENTICATION,
    limit=10
)

print(f"Found {total} authentication templates")
for module in modules:
    print(f"- {module.name}: {module.description}")
```

### 2. Apply a Module Template

```python
from backend.services.templates.template_manager import TemplateManager

manager = TemplateManager()

# Apply JWT authentication template
result = await manager.apply_module_template(
    module_id="jwt-auth-template-id",
    parameters={
        "jwtSecret": "your-secure-secret-key-here",
        "tokenExpiry": 3600,
        "enableRefreshTokens": True
    },
    output_path="./generated-project/src/auth"
)

print(f"Generated {result['files_generated']} files")
for file_info in result['files']:
    print(f"- {file_info['path']}")
```

### 3. Generate a Prompt

```python
from backend.services.templates.template_manager import TemplateManager

manager = TemplateManager()

# Generate REST API design prompt
prompt = await manager.generate_prompt(
    template_id="rest-api-design-template-id",
    variables={
        "resource_type": "User",
        "endpoints": ["GET", "POST", "PUT", "DELETE"],
        "auth_type": "JWT",
        "rate_limit": "1000/min",
        "data_format": "JSON",
        "tech_stack": "Node.js + Express + TypeScript"
    }
)

print("Generated Prompt:")
print(prompt)
```

### 4. Create an ADR

```python
from backend.services.templates.template_manager import TemplateManager
from backend.db.models.enums import ADRStatus

manager = TemplateManager()

# Create a new ADR
adr = await manager.create_adr(
    workspace_id="workspace-123",
    title="Use JWT for API Authentication",
    context="We need to secure our REST API endpoints. Current system uses session-based auth which doesn't work well with mobile clients.",
    decision="Implement JWT-based authentication for all API endpoints using RS256 algorithm.",
    consequences="+ Better support for mobile and SPA applications\n+ Stateless authentication\n- More complex token management\n- Requires careful secret key management",
    status=ADRStatus.PROPOSED,
    alternatives_considered=[
        "Session-based authentication",
        "OAuth 2.0 with external provider",
        "API keys with rate limiting"
    ],
    tags=["authentication", "security", "api"]
)

print(f"Created ADR: {adr.title} (ID: {adr.id})")
```

## API Endpoints

### Module Template Endpoints

#### List Module Templates
```http
GET /api/templates/modules
```

**Query Parameters:**
- `category` (optional): Filter by category (authentication, commerce, admin, infrastructure, api_design, database, testing, documentation, workflow, security)
- `tech_stack` (optional): Filter by technology stack
- `search` (optional): Search in name, description, and author
- `tags` (optional): Filter by tags (multiple values allowed)
- `limit` (optional): Number of results (default: 50, max: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "items": [
    {
      "id": "template-id",
      "name": "jwt-auth",
      "category": "authentication",
      "description": "JWT-based authentication module",
      "version": "1.0.0",
      "tech_stacks": ["express-ts", "fastapi"],
      "rating": 4.5,
      "usage_count": 150,
      "visibility": "public",
      "created_at": "2024-12-18T10:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0,
  "template_type": "module"
}
```

#### Create Module Template
```http
POST /api/templates/modules
```

**Request Body:**
```json
{
  "name": "custom-auth",
  "category": "authentication",
  "description": "Custom authentication module",
  "version": "1.0.0",
  "tech_stacks": ["express-ts"],
  "dependencies": ["passport", "bcrypt"],
  "documentation": "Custom authentication module with OAuth2",
  "parameters": [
    {
      "name": "oauthProvider",
      "type": "string",
      "description": "OAuth provider",
      "required": false,
      "default": "google"
    }
  ],
  "files": [
    {
      "path": "src/auth/oauth.ts",
      "content": "import { {{oauthProvider}}Strategy } from 'passport-{{oauthProvider}}';",
      "language": "typescript",
      "priority": 1
    }
  ],
  "visibility": "private",
  "tags": ["oauth", "social-login"]
}
```

#### Get Module Template Details
```http
GET /api/templates/modules/{module_id}
```

**Response:**
```json
{
  "module": { /* Module template data */ },
  "files": [
    {
      "id": "file-id",
      "path": "src/auth/controller.ts",
      "content": "...",
      "language": "typescript",
      "is_test": false,
      "priority": 1
    }
  ],
  "parameters": [
    {
      "id": "param-id",
      "name": "jwtSecret",
      "type": "string",
      "description": "JWT secret",
      "required": true,
      "validation_rules": {"minLength": 32}
    }
  ],
  "total_files": 1,
  "total_parameters": 1
}
```

#### Apply Module Template
```http
POST /api/templates/modules/{module_id}/apply
```

**Request Body:**
```json
{
  "project_id": "project-123",
  "parameters": {
    "jwtSecret": "secure-secret-key",
    "tokenExpiry": 3600,
    "enableRefreshTokens": true
  }
}
```

### Prompt Template Endpoints

#### List Prompt Templates
```http
GET /api/templates/prompts
```

#### Generate Prompt
```http
POST /api/templates/prompts/{template_id}/generate
```

**Request Body:**
```json
{
  "variables": {
    "resource_type": "User",
    "endpoints": ["GET", "POST", "DELETE"],
    "auth_type": "JWT",
    "rate_limit": "500/min"
  }
}
```

**Response:**
```json
{
  "prompt": "You are designing a User REST API...",
  "template_id": "template-id",
  "variables_used": {
    "resource_type": "User",
    "endpoints": ["GET", "POST", "DELETE"]
  }
}
```

### ADR Endpoints

#### List Workspace ADRs
```http
GET /api/templates/workspaces/{workspace_id}/adrs
```

#### Create ADR
```http
POST /api/templates/workspaces/{workspace_id}/adrs
```

**Request Body:**
```json
{
  "title": "Use GraphQL for Complex Queries",
  "context": "Our current REST API requires multiple requests for complex data relationships, causing performance issues.",
  "decision": "Implement GraphQL API for complex data fetching while maintaining REST API for simple operations.",
  "consequences": "+ Reduced number of requests for complex queries\n- Increased implementation complexity\n- Learning curve for team\n- Need for GraphQL-specific tooling",
  "status": "proposed",
  "alternatives_considered": [
    "Implement comprehensive REST endpoints",
    "Use complex JOIN queries",
    "Implement caching layer"
  ],
  "tags": ["graphql", "performance", "api-design"]
}
```

#### Get ADR Timeline
```http
GET /api/templates/workspaces/{workspace_id}/adrs/timeline
```

**Response:**
```json
{
  "timeline": [
    {
      "id": "adr-id-1",
      "title": "Use JWT for Authentication",
      "status": "accepted",
      "date": "2024-12-01T10:00:00Z",
      "summary": "Implement JWT-based authentication for better mobile support..."
    }
  ]
}
```

### Search & Marketplace

#### Search Templates
```http
GET /api/templates/search?query=auth&template_type=module
```

#### Get Marketplace
```http
GET /api/templates/marketplace?limit=10
```

## Template Structure

### Module Template File Structure

```
module-name/
├── src/
│   ├── auth/
│   │   ├── routes/
│   │   ├── controllers/
│   │   ├── services/
│   │   └── middleware/
│   └── config/
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
└── package.json (for Node.js projects)
```

### File Template Format

Each file in a module template supports:

- **Path**: Relative path with parameter substitution
- **Content**: Template content with `{{parameter}}` placeholders
- **Language**: Programming language (typescript, python, php, etc.)
- **Type**: Whether it's a test file, config file, or regular code
- **Priority**: Generation order (higher numbers first)

### Parameter Types

- **string**: Text values
- **number**: Numeric values
- **boolean**: True/false values
- **array**: List of values
- **object**: JSON objects

### Validation Rules

Parameters can include validation rules:

```json
{
  "name": "jwtSecret",
  "type": "string",
  "required": true,
  "validation": {
    "minLength": 32,
    "pattern": "^[a-zA-Z0-9]+$"
  }
}
```

## Creating Custom Templates

### 1. Module Template Structure

```python
from backend.services.templates.template_manager import TemplateManager
from backend.db.models.enums import TemplateCategory, TemplateVisibility

manager = TemplateManager()

# Create module template
module = await manager.create_module_template(
    name="my-custom-module",
    category=TemplateCategory.INFRASTRUCTURE,
    description="Custom logging and monitoring module",
    tech_stacks=["express-ts", "fastapi"],
    dependencies=["winston", "prom-client"],
    documentation="""
# Custom Monitoring Module

This module provides comprehensive logging and monitoring features:
- Structured logging with Winston
- Prometheus metrics collection
- Health check endpoints
- Performance monitoring
    """.strip(),
    parameters=[
        {
            "name": "logLevel",
            "type": "string",
            "description": "Application log level",
            "required": False,
            "default": "info",
            "validation": {
                "enum": ["debug", "info", "warn", "error"]
            }
        },
        {
            "name": "metricsPort",
            "type": "number",
            "description": "Port for Prometheus metrics",
            "required": False,
            "default": 9090,
            "validation": {
                "min": 1000,
                "max": 65535
            }
        }
    ],
    files=[
        {
            "path": "src/logger/logger.ts",
            "content": """import winston from 'winston';
import { createPrometheusMetrics } from 'prom-client';

const logger = winston.createLogger({
  level: '{{logLevel}}',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: 'logs/app.log' })
  ]
});

const metrics = createPrometheusMetrics();
const metricsServer = require('express')();

metricsServer.get('/metrics', (req, res) => {
  res.set('Content-Type', metrics.register.contentType);
  res.end(metrics.register.metrics());
});

metricsServer.listen({{metricsPort}}, () => {
  logger.info(`Metrics server listening on port {{metricsPort}}`);
});

export { logger, metrics, metricsServer };""",
            "language": "typescript",
            "priority": 1
        }
    ],
    author="Your Name",
    visibility=TemplateVisibility.PUBLIC,
    tags=["logging", "monitoring", "metrics"]
)
```

### 2. Prompt Template Structure

```python
from backend.services.templates.template_manager import TemplateManager
from backend.db.models.enums import PromptOutputFormat

manager = TemplateManager()

# Create prompt template
prompt = await manager.create_prompt_template(
    name="react-component",
    category=TemplateCategory.TESTING,
    template="""Create a React component for {{component_type}}.

Requirements:
- Component name: {{component_name}}
- Props: {{props}}
- Styling: {{styling_library}}
- TypeScript: {{use_typescript}}

Please generate:
1. Component file with proper TypeScript types
2. PropTypes or TypeScript interface
3. Unit tests using {{testing_library}}
4. Storybook story for component documentation
5. CSS/SCSS styles using {{styling_library}}

Component should follow best practices for:
- Accessibility (ARIA attributes)
- Performance optimization
- Error handling
- Loading states

Technology stack: React {{react_version}}, {{styling_library}}, {{testing_library}}""",
    output_format=PromptOutputFormat.CODE,
    context_required=[
        "component_type", "component_name", "props", 
        "styling_library", "use_typescript", "testing_library", "react_version"
    ],
    examples=[
        "Create a Button component with loading state and accessibility features",
        "Create a DataTable component with sorting and pagination"
    ],
    author="Template System",
    tags=["react", "component", "typescript", "testing"]
)
```

### 3. ADR Template Format

```markdown
# ADR-001: Use GraphQL for Complex Queries

## Status: Accepted

## Context
Our current REST API requires multiple round trips for complex data relationships. This causes:
- Poor performance for dashboard views
- Increased network latency
- Higher bandwidth usage
- Complex client-side data aggregation

## Decision
Implement GraphQL API for complex data fetching while maintaining REST API for:
- Simple CRUD operations (keep REST for caching benefits)
- File uploads (better with REST)
- Authentication endpoints (REST is fine)

## Consequences

### Positive
- Reduced number of requests for complex views
- Better performance for data-heavy operations
- Client can request exactly what it needs
- Strong typing with GraphQL schema

### Negative
- Increased implementation complexity
- Learning curve for development team
- Need for GraphQL-specific tooling and monitoring
- More complex caching strategies required

## Alternatives Considered

1. **Comprehensive REST Endpoints**
   - Rejected: Would create API endpoint explosion
   - Each new view would require new endpoints

2. **Complex JOIN Queries**
   - Rejected: Database performance concerns
   - Difficult to optimize for different use cases

3. **Aggressive Caching Layer**
   - Rejected: Cache invalidation complexity
   - Real-time data requirements make caching difficult

## Implementation Plan
1. Set up Apollo Server alongside existing REST API
2. Create GraphQL schema for complex queries
3. Implement GraphQL resolvers using existing REST endpoints
4. Update frontend to use GraphQL for complex views
5. Monitor performance and adjust as needed

## Related ADRs
- ADR-002: API Authentication Strategy
- ADR-003: Database Optimization Strategy
```

## Best Practices

### Template Development

1. **Start Simple**: Begin with basic templates and iterate
2. **Use Parameters Wisely**: Only make configurable what users actually need to customize
3. **Document Everything**: Include clear documentation and examples
4. **Test Thoroughly**: Test your templates with different parameter combinations
5. **Follow Conventions**: Respect coding standards and best practices for each tech stack

### Parameter Design

1. **Sensible Defaults**: Provide reasonable default values
2. **Validation**: Implement proper validation rules
3. **Clear Names**: Use descriptive parameter names
4. **Group Related Options**: Organize parameters logically

### Security Considerations

1. **Validate Inputs**: Always validate template parameters
2. **Secure Defaults**: Use secure default values (e.g., strong JWT secrets)
3. **Document Security Requirements**: Clearly document security considerations
4. **Regular Updates**: Keep templates updated with security patches

### Performance Tips

1. **Efficient File Generation**: Minimize file I/O during template generation
2. **Cache Templates**: Cache frequently used templates
3. **Optimize Searches**: Use proper database indexing for template searches
4. **Batch Operations**: Group related database operations

## Integration Examples

### With Project Generator

```python
from backend.services.templates.template_manager import TemplateEnhancer

enhancer = TemplateEnhancer()

# Enhance a generated project with templates
result = await enhancer.apply_templates_to_project(
    project_id="generated-project-123",
    modules=["jwt-auth", "product-catalog", "shopping-cart"],
    parameters={
        "jwt-auth": {
            "jwtSecret": "generated-secret",
            "tokenExpiry": 7200
        },
        "product-catalog": {
            "enableInventoryTracking": True,
            "currency": "EUR"
        },
        "shopping-cart": {
            "enableDiscounts": True,
            "sessionTimeout": 60
        }
    }
)
```

### With CI/CD Pipeline

```bash
# Apply templates during build process
curl -X POST "http://localhost:8000/api/templates/enhance" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "build-123",
    "modules": ["jwt-auth", "api-rate-limiting"],
    "parameters": {
      "jwt-auth": {
        "jwtSecret": "'$JWT_SECRET'",
        "enableRefreshTokens": true
      }
    }
  }'
```

### With Development Tools

```javascript
// CLI tool integration
const templates = await fetch('/api/templates/search?query=auth&template_type=module');
const authTemplates = await templates.json();

console.log('Available auth templates:');
authTemplates.results.forEach(template => {
  console.log(`${template.name} (${template.rating}/5, ${template.usage_count} uses)`);
});
```

## Troubleshooting

### Common Issues

1. **Template Not Found**
   - Verify template ID is correct
   - Check template visibility (public vs private)
   - Ensure template is active

2. **Parameter Substitution Errors**
   - Check parameter names match exactly
   - Verify all required parameters are provided
   - Validate parameter types and formats

3. **File Generation Failures**
   - Check output directory permissions
   - Verify file paths don't contain invalid characters
   - Ensure sufficient disk space

4. **Database Connection Issues**
   - Verify database service is running
   - Check database connection configuration
   - Review database permissions

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now template operations will show detailed debug information
```

### Performance Monitoring

Monitor template system performance:

```sql
-- Check popular templates
SELECT name, usage_count, rating 
FROM reusable_modules 
WHERE visibility = 'public' 
ORDER BY usage_count DESC 
LIMIT 10;

-- Monitor template generation time
SELECT 
  module_name,
  AVG(duration) as avg_duration,
  COUNT(*) as total_uses
FROM template_usage_logs 
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY module_name
ORDER BY avg_duration DESC;
```

## Contributing

### Adding New Templates

1. Follow the template creation guidelines
2. Test thoroughly with different parameter combinations
3. Include comprehensive documentation
4. Submit for review through the marketplace

### Template Quality Standards

- **Code Quality**: Follow language-specific best practices
- **Documentation**: Include clear usage examples
- **Testing**: Provide test coverage
- **Security**: Follow security best practices
- **Performance**: Optimize for performance

### Community Guidelines

- **Respectful Communication**: Be respectful in all interactions
- **Quality Contributions**: Maintain high quality standards
- **Knowledge Sharing**: Share knowledge and help others
- **Open Source Spirit**: Contribute back to the community

## Support

For questions, issues, or contributions:

1. Check the documentation above
2. Review existing templates for examples
3. Contact the development team
4. Submit issues through the project repository

---

This documentation covers the main features and usage patterns of the Template & Prompt Library System. For specific API details, see the OpenAPI documentation at `/docs` when running the application.