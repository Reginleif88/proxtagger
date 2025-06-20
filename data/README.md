# ProxTagger Data Directory

This directory contains all persistent data for ProxTagger:

- `config.json` - ProxTagger configuration
- `conditional_rules.json` - Conditional tagging rules
- `rule_execution_history.json` - History of rule executions

These files are automatically created by the application when needed.

## Docker Usage

When using Docker, mount this directory as a volume:

```yaml
volumes:
  - ./data:/app/data
```

This ensures your data persists across container updates while allowing the application code to be updated when pulling new images.