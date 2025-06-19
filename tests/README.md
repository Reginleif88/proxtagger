# ProxTagger Test Suite

This directory contains the comprehensive test suite for ProxTagger, covering both unit and integration tests for all core functionality.

## Test Structure

```
tests/
├── conftest.py                 # Shared pytest fixtures and configuration
├── unit/                       # Unit tests (isolated component testing)
│   ├── test_tag_utils.py      # Tag parsing, formatting, extraction
│   ├── test_proxmox_api.py    # Proxmox API integration
│   ├── test_backup_utils.py   # Backup/restore functionality
│   ├── test_conditional_models.py      # Conditional tagging models
│   ├── test_conditional_engine.py      # Rule evaluation engine
│   └── test_conditional_storage.py     # Rule persistence and history
├── integration/                # Integration tests (end-to-end workflows)
│   ├── test_tag_workflow.py   # Complete tag management workflows
│   └── test_conditional_tagging.py     # Conditional tagging workflows
└── fixtures/                   # Test data and utilities
    └── conditional_tags.py     # Fixtures for conditional tagging tests
```

## Running Tests

### Prerequisites

Install test dependencies:
```bash
pip install -r requirements.txt
```

### Quick Start

Run all tests:
```bash
python3 run_tests.py
```

Run with coverage report:
```bash
python3 run_tests.py --coverage --html
```

### Specific Test Categories

**Unit tests only:**
```bash
python3 run_tests.py --unit
```

**Integration tests only:**
```bash
python3 run_tests.py --integration
```

**Specific test pattern:**
```bash
python3 run_tests.py -k "test_parse_tags"
```

**Verbose output:**
```bash
python3 run_tests.py --verbose
```

**Stop on first failure:**
```bash
python3 run_tests.py --failfast
```

### Using pytest directly

You can also run pytest directly for more control:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific file
pytest tests/unit/test_tag_utils.py

# Run specific test
pytest tests/unit/test_tag_utils.py::TestParseTags::test_parse_tags_basic

# Run tests matching pattern
pytest -k "parse_tags"

# Run with specific markers
pytest -m "unit"
pytest -m "integration"
```

## Test Categories

### Unit Tests

Unit tests focus on testing individual functions and classes in isolation:

- **Tag Utils**: Test tag parsing, formatting, and extraction functions
- **Proxmox API**: Test API communication with mocked responses
- **Backup Utils**: Test backup creation and restoration logic
- **Conditional Models**: Test rule data models and validation
- **Conditional Engine**: Test rule evaluation and condition matching
- **Conditional Storage**: Test rule persistence and execution history

### Integration Tests

Integration tests verify that components work correctly together:

- **Tag Workflow**: Test complete tag management operations end-to-end
- **Conditional Tagging**: Test full conditional rule lifecycle and execution

## Test Features

### Mocking Strategy

Tests use comprehensive mocking to avoid external dependencies:

- **Proxmox API calls** are mocked to simulate various response scenarios
- **File system operations** use temporary files for safe testing
- **Configuration loading** is mocked with test data
- **Time-sensitive operations** can be frozen for consistent testing

### Test Data

Realistic test data is provided through fixtures:

- Sample VM configurations with various states and tag combinations
- Sample conditional rules with different complexity levels
- Mock API responses for various scenarios
- Test configuration data

### Coverage Goals

The test suite aims for high code coverage:

- **Target**: 85%+ overall coverage
- **Unit tests**: Cover all core logic paths
- **Integration tests**: Cover key user workflows
- **Error handling**: Test exception scenarios and edge cases

## Test Fixtures

### Core Fixtures (`conftest.py`)

- `mock_config`: Mock Proxmox configuration
- `sample_vms`: Sample VM data for testing
- `temp_storage_file`: Temporary file for storage tests
- `mock_requests_*`: Mocked HTTP requests
- `freeze_time`: Frozen timestamps for consistent testing

### Conditional Tags Fixtures (`fixtures/conditional_tags.py`)

- `sample_rule_condition`: Basic rule condition
- `sample_conditional_rule`: Complete conditional rule
- `complex_rule_conditions`: Advanced rule scenarios
- `vm_data_for_evaluation`: VM data for rule testing

## Writing New Tests

### Test Naming Conventions

- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>`
- Test methods: `test_<what_is_being_tested>`

### Test Structure

```python
class TestFeatureName:
    """Test the FeatureName functionality"""
    
    @pytest.mark.unit  # or @pytest.mark.integration
    def test_specific_behavior(self, fixture_name):
        """Test specific behavior with clear description"""
        # Arrange
        setup_data = ...
        
        # Act
        result = function_under_test(setup_data)
        
        # Assert
        assert result == expected_value
```

### Best Practices

1. **Use descriptive test names** that explain what is being tested
2. **Follow AAA pattern**: Arrange, Act, Assert
3. **Test edge cases** and error conditions
4. **Use appropriate fixtures** to minimize setup code
5. **Mock external dependencies** to ensure test isolation
6. **Include both positive and negative test cases**
7. **Add integration tests** for critical user workflows

## CI/CD Integration

The test suite is designed to work well in CI/CD environments:

- **Fast execution**: Unit tests run quickly for rapid feedback
- **Comprehensive coverage**: Integration tests ensure system reliability
- **Clear reporting**: Coverage reports help identify gaps
- **Flexible execution**: Can run subsets of tests as needed

## Troubleshooting

### Common Issues

**Import errors**: Make sure you're running tests from the project root directory

**Missing dependencies**: Install test dependencies with `pip install -r requirements.txt`

**Permission errors**: Ensure test files are writable (temporary files)

**Slow tests**: Use `--unit` flag to run only fast unit tests during development

### Debug Mode

For debugging failing tests:

```bash
# Run with debugging output
pytest -v -s tests/unit/test_specific.py::test_function

# Run with pdb on failures
pytest --pdb tests/unit/test_specific.py::test_function
```

## Continuous Improvement

The test suite should be continuously improved:

- **Add tests** for new features
- **Update tests** when refactoring code
- **Monitor coverage** and add tests for uncovered code
- **Review and update** test data and fixtures regularly
- **Performance test** critical paths as the application grows