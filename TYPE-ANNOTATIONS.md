# Type Annotation Maintenance Guide

The project uses strict type checking with MyPy (`disallow_untyped_defs = true`) and Pylance. When fixing type annotation issues, follow this systematic approach for maximum efficiency and accuracy.

## Available Diagnostic Tools

### 1. MyPy File-Specific Analysis (Primary Tool)

```bash
uv run mypy path/to/specific_file.py --show-error-codes
```

**Example Output:**
```bash
$ uv run mypy tests/unit/test_models.py --show-error-codes
tests/unit/test_models.py:11: error: Function is missing a return type annotation  [no-untyped-def]
tests/unit/test_models.py:11: note: Use "-> None" if function does not return a value
tests/unit/test_models.py:22: error: Function is missing a return type annotation  [no-untyped-def]
tests/unit/test_models.py:22: note: Use "-> None" if function does not return a value
Found 7 errors in 1 file (checked 1 source file)
```

**Best For:** Non-temporal files, detailed error messages, immediate verification

### 2. VS Code Diagnostics API (Excellent for Complex Files)

```bash
mcp__ide__getDiagnostics --uri file:///absolute/path/to/file.py
```

**Example Output:**
```json
[{
  "uri": "file:///Users/.../schedule_manager.py",
  "diagnostics": [
    {
      "message": "Function is missing a return type annotation",
      "severity": "Error",
      "range": {
        "start": {"line": 35, "character": 4},
        "end": {"line": 36, "character": 26}
      },
      "source": "Mypy"
    }
  ]
}]
```

**Best For:** Temporal files with complex dependencies, exact line/character positions, both MyPy AND Pylance issues

**Note:** Pylance diagnostics are provided by pyright under the hood. The VS Code Diagnostics API can return issues from both MyPy (configured via settings) and Pylance/pyright, making it comprehensive for catching all type annotation problems.

## Systematic Fixing Workflow

### Phase 1: Critical Infrastructure Files

**Target**: Core application files, temporal modules, configuration

**Workflow per file:**
```bash
# 1. Identify issues
mcp__ide__getDiagnostics --uri file:///path/to/schedule_manager.py

# 2. Fix issues (use MultiEdit for batch operations)
# MultiEdit with multiple return type annotations

# 3. Verify fix immediately
mcp__ide__getDiagnostics --uri file:///path/to/schedule_manager.py
# Should show empty diagnostics array: []

# 4. Move to next file when clean
```

**Example Fixes:**
```python
# Missing return type annotations
def __init__(self):              →  def __init__(self) -> None:
async def connect(self):         →  async def connect(self) -> None:
async def main():               →  async def main() -> None:

# Temporal API attribute access issues (use type ignores)
action.scheduled_time           →  action.scheduled_time  # type: ignore

# Unused parameters (prefix with underscore)
def updater(input: Type):       →  def updater(_input: Type):
```

### Phase 2: Test Infrastructure

**Target**: `conftest.py` fixtures, base test classes

**Workflow:**
```bash
# 1. Check with both tools
uv run mypy tests/conftest.py --show-error-codes
mcp__ide__getDiagnostics --uri file:///path/to/conftest.py

# 2. Fix fixture return types systematically
# 3. Verify with MyPy (authoritative)
uv run mypy tests/conftest.py
# Expected: "Success: no issues found in 1 source file"
```

**Example Fixture Fixes:**
```python
@pytest.fixture
def sample_venue():                     →  def sample_venue() -> Venue:

@pytest.fixture
def sample_event():           →  def sample_event() -> Event:

@pytest.fixture
async def aiohttp_session():             →  async def aiohttp_session() -> AsyncGenerator[aiohttp.ClientSession, None]:

@pytest.fixture
def fixtures_dir():                      →  def fixtures_dir() -> Path:
```

### Phase 3: Systematic Test File Processing

**Target**: ~500+ test functions needing `-> None`

**Optimized Workflow:**
```bash
# 1. Quick scan per file
uv run mypy tests/unit/test_specific.py --show-error-codes

# 2. Batch fix with MultiEdit (10-15 functions per batch)
# 3. Verify fix immediately
uv run mypy tests/unit/test_specific.py
# Expected: "Success: no issues found in 1 source file"

# 4. Move to next file when clean
```

**Example Test Function Fixes:**
```python
def test_venue_creation(self):         →  def test_venue_creation(self) -> None:
def test_event(self):         →  def test_event(self) -> None:
async def test_vision_analysis(self, mock_client):  →  async def test_vision_analysis(self, mock_client: Mock) -> None:

# Parameter type annotations for better clarity
def test_parser(self, vision_analyzer):  →  def test_parser(self, vision_analyzer: VisionAnalyzer) -> None:
```

## Advanced Patterns

### Temporal Files with API Issues

```python
# Temporal SDK attributes may not be recognized by static analysis
# Use type ignores for legitimate API usage:
if hasattr(action, 'scheduled_time') and action.scheduled_time:  # type: ignore
    action_info["scheduled_time"] = action.scheduled_time.isoformat()  # type: ignore
```

### Test Files with Intentional Type Violations

```python
# When tests intentionally pass wrong types (e.g., testing error handling)
assert not vision_analyzer._is_valid_image_url(None)  # type: ignore
```

### Complex Generic Types

```python
# Fixture return types with generics
@pytest.fixture
async def aiohttp_session() -> AsyncGenerator[aiohttp.ClientSession, None]:
    async with aiohttp.ClientSession() as session:
        yield session
```

## Success Verification Examples

### MyPy Success

```bash
$ uv run mypy tests/unit/test_registry.py --show-error-codes
Success: no issues found in 1 source file
```

### VS Code Diagnostics Success (MyPy + Pylance/pyright)

```json
[{
  "uri": "file:///Users/.../temporal/worker.py",
  "diagnostics": []
}]
```

## Batch Operation Examples

### MultiEdit for Test Functions

```python
# Single operation to fix multiple similar issues:
MultiEdit([
  {"old_string": "def test_creation(self):", "new_string": "def test_creation(self) -> None:"},
  {"old_string": "def test_equality(self):", "new_string": "def test_equality(self) -> None:"},
  {"old_string": "def test_validation(self):", "new_string": "def test_validation(self) -> None:"}
])
```

## Tool Selection Guidelines

- **MyPy**: Use for non-temporal files, test files, utilities
- **VS Code API (MyPy + Pylance/pyright)**: Use for temporal files, complex dependency chains, comprehensive error detection
- **Both**: Use for verification and comprehensive coverage

## Progress Tracking

Keep systematic records of completed files:
```
✅ Phase 1 Complete: temporal/schedule_manager.py, temporal/worker.py, temporal/starter.py
✅ Phase 2 Complete: tests/conftest.py (12 fixtures)
🔄 Phase 3 In Progress: tests/unit/test_registry.py (8/8), tests/unit/test_vision_analyzer.py (11/11)
```

This approach provides **surgical precision** with **immediate verification**, making type annotation fixing systematic, efficient, and reliable.

## Common Patterns Reference

### Function Return Types

```python
# Void functions
def setup():                         →  def setup() -> None:
async def cleanup():                 →  async def cleanup() -> None:

# Functions returning values
def get_config():                    →  def get_config() -> Dict[str, Any]:
async def fetch_data():              →  async def fetch_data() -> List[Event]:

# Generator functions
def iterate():                       →  def iterate() -> Generator[str, None, None]:
async def async_iterate():           →  async def async_iterate() -> AsyncGenerator[str, None]:
```

### Parameter Types

```python
# Basic types
def process(data):                   →  def process(data: str) -> None:
def calculate(num):                  →  def calculate(num: int) -> float:

# Optional types
def format_name(name):               →  def format_name(name: Optional[str]) -> str:

# Complex types
def parse(items):                    →  def parse(items: List[Dict[str, Any]]) -> List[Event]:
```

### Class Methods

```python
# Instance methods
def __init__(self):                  →  def __init__(self) -> None:
def process(self):                   →  def process(self) -> None:

# Class methods
@classmethod
def create(cls):                     →  def create(cls) -> "ClassName":

# Static methods
@staticmethod
def validate(data):                  →  def validate(data: str) -> bool:

# Properties
@property
def name(self):                      →  def name(self) -> str:
```

### Test Fixtures

```python
# Simple fixtures
@pytest.fixture
def sample_data():                   →  def sample_data() -> Dict[str, str]:

# Fixtures with yield (generators)
@pytest.fixture
def temp_file():                     →  def temp_file() -> Generator[Path, None, None]:

# Async fixtures
@pytest.fixture
async def session():                 →  async def session() -> AsyncGenerator[ClientSession, None]:
```

## Troubleshooting

### Common Issues

**Issue**: MyPy complains about missing imports
```python
# Solution: Add proper import or use TYPE_CHECKING
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from module import Type
```

**Issue**: Circular import errors
```python
# Solution: Use string annotations
def process(self) -> "ClassName":
    pass
```

**Issue**: Complex nested types
```python
# Solution: Use type aliases
EventDict = Dict[str, Union[str, int, List[str]]]
def process(data: EventDict) -> None:
    pass
```

**Issue**: Third-party library without type stubs
```python
# Solution: Add type ignore comment
import untyped_library  # type: ignore
```

## Running Type Checks

```bash
# Check entire project
uv run mypy around_the_grounds/

# Check specific file
uv run mypy around_the_grounds/utils/vision_analyzer.py

# Check tests
uv run mypy tests/

# With verbose output
uv run mypy around_the_grounds/ --verbose

# With error codes
uv run mypy around_the_grounds/ --show-error-codes

# Strict mode (catches more issues)
uv run mypy around_the_grounds/ --strict
```
