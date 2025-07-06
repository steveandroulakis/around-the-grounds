# Temporal Cloud Support Implementation Plan

## Overview

Add Temporal Cloud support to the food truck tracking system to enable production deployment with cloud-hosted Temporal servers. This plan follows the pattern established in the reference project (`temporal-ai-agent`) to support multiple authentication methods including:

- Local development server (current default)
- Temporal Cloud with API key authentication
- mTLS certificate-based authentication
- Custom server endpoints

## Architecture Changes

### Current State
- Hardcoded `localhost:7233` server address in worker and starter
- No authentication mechanism
- No environment-based configuration

### Target State
- Flexible client configuration supporting multiple authentication methods
- Environment variable-based configuration
- Backward compatibility with existing local development setup
- Production-ready Temporal Cloud deployment

## Implementation Plan

### Phase 1: Core Configuration Infrastructure

#### 1.1 Create Environment Configuration System
**File:** `around_the_grounds/temporal/config.py`

Based on the reference project's `shared/config.py`, create a configuration module that:
- Loads environment variables with dotenv support
- Provides default values for local development
- Supports multiple authentication methods
- Includes debug logging for connection details

**Key Features:**
- `TEMPORAL_ADDRESS` - Server address (default: localhost:7233)
- `TEMPORAL_NAMESPACE` - Namespace (default: default)
- `TEMPORAL_TASK_QUEUE` - Task queue name (default: food-truck-task-queue)
- `TEMPORAL_TLS_CERT` - Path to TLS certificate file
- `TEMPORAL_TLS_KEY` - Path to TLS key file  
- `TEMPORAL_API_KEY` - API key for Temporal Cloud

**Function:**
```python
async def get_temporal_client() -> Client:
    """Creates a Temporal client based on environment configuration."""
    # Implementation supports:
    # - Local development (no auth)
    # - mTLS authentication (cert + key files)
    # - API key authentication (Temporal Cloud)
```

#### 1.2 Add Environment Dependencies
**File:** `pyproject.toml`

Add `python-dotenv` dependency for environment variable management:
```toml
[tool.poetry.dependencies]
python-dotenv = "^1.0.0"
```

#### 1.3 Create Environment Template
**File:** `.env.example`

Create template file with all Temporal configuration options:
```bash
# Temporal Configuration
# TEMPORAL_ADDRESS=your-namespace.acct.tmprl.cloud:7233
# TEMPORAL_NAMESPACE=default
# TEMPORAL_TASK_QUEUE=food-truck-task-queue
# TEMPORAL_TLS_CERT=path/to/cert.pem
# TEMPORAL_TLS_KEY=path/to/key.pem
# TEMPORAL_API_KEY=your-api-key

# Food Truck Configuration
# ANTHROPIC_API_KEY=your-anthropic-key
# VISION_ANALYSIS_ENABLED=true
```

### Phase 2: Worker and Starter Updates

#### 2.1 Update Worker Implementation
**File:** `around_the_grounds/temporal/worker.py`

Modify `FoodTruckWorker` class to:
- Import and use the new configuration system
- Replace hardcoded client creation with `get_temporal_client()`
- Add environment variable debugging on startup
- Maintain backward compatibility

**Key Changes:**
```python
from .config import get_temporal_client, TEMPORAL_TASK_QUEUE

class FoodTruckWorker:
    def __init__(self, temporal_address: str = None):
        # temporal_address parameter kept for backward compatibility
        # but actual client creation uses environment config
        pass
    
    async def start(self):
        client = await get_temporal_client()
        # Use TEMPORAL_TASK_QUEUE from config
```

#### 2.2 Update Starter Implementation
**File:** `around_the_grounds/temporal/starter.py`

Modify `FoodTruckStarter` class to:
- Import and use the new configuration system
- Replace hardcoded client creation with `get_temporal_client()`
- Support environment-based task queue configuration
- Add debug output for connection details

**Key Changes:**
```python
from .config import get_temporal_client, TEMPORAL_TASK_QUEUE

class FoodTruckStarter:
    async def run_workflow(self, ...):
        client = await get_temporal_client()
        # Use TEMPORAL_TASK_QUEUE from config
```

### Phase 3: Documentation and Testing

#### 3.1 Update CLAUDE.md
Add comprehensive Temporal Cloud configuration section:
- Environment variable reference
- Authentication method examples
- Temporal Cloud setup instructions
- mTLS certificate configuration
- Troubleshooting guide

#### 3.2 Update temporal/README.md
Add production deployment section:
- Temporal Cloud account setup
- Certificate generation for mTLS
- Environment variable configuration
- Production worker deployment
- Monitoring and logging setup

#### 3.3 Update Tests
**Files:** `tests/temporal/test_*.py`

Modify tests to:
- Use configurable client instead of hardcoded connections
- Mock `get_temporal_client()` function
- Test different authentication scenarios
- Ensure backward compatibility

### Phase 4: Validation and Documentation

#### 4.1 Configuration Validation
Add validation for:
- Conflicting authentication methods
- Required environment variables
- Certificate file existence
- Network connectivity

#### 4.2 Production Deployment Guide
Create comprehensive guide for:
- Temporal Cloud account setup
- Certificate generation
- Environment configuration
- Worker deployment strategies
- Monitoring and alerting

## Implementation Details

### Authentication Methods

#### 1. Local Development (Default)
```bash
# No environment variables needed
# Uses localhost:7233 by default
```

#### 2. Temporal Cloud with API Key
```bash
TEMPORAL_ADDRESS=your-namespace.acct.tmprl.cloud:7233
TEMPORAL_NAMESPACE=your-namespace
TEMPORAL_API_KEY=your-api-key
```

#### 3. mTLS Certificate Authentication
```bash
TEMPORAL_ADDRESS=your-server:7233
TEMPORAL_NAMESPACE=your-namespace
TEMPORAL_TLS_CERT=path/to/cert.pem
TEMPORAL_TLS_KEY=path/to/key.pem
```

### Configuration Priority
1. Environment variables (highest)
2. .env file
3. Default values (lowest)

### Backward Compatibility
- All existing commands continue to work without changes
- Local development remains the default
- No breaking changes to existing API

## Testing Strategy

### Unit Tests
- Test client creation with different configurations
- Test authentication method selection
- Test environment variable loading
- Test error handling for invalid configurations

### Integration Tests
- Test connection to local server
- Test connection to Temporal Cloud (with valid credentials)
- Test mTLS authentication (with test certificates)
- Test fallback behavior

### Manual Testing
- Local development workflow
- Temporal Cloud connection
- Worker and starter functionality
- Error scenarios

## Rollout Strategy

### Phase 1: Infrastructure (Week 1)
- Implement configuration system
- Update worker and starter
- Add environment template
- Basic testing

### Phase 2: Documentation (Week 2)
- Update all documentation
- Create deployment guides
- Add troubleshooting section
- Comprehensive testing

### Phase 3: Validation (Week 3)
- Production deployment testing
- Performance validation
- Security review
- User acceptance testing

## Success Criteria

### Functional Requirements
- ✅ Support local development (default)
- ✅ Support Temporal Cloud with API key
- ✅ Support mTLS authentication
- ✅ Maintain backward compatibility
- ✅ Zero breaking changes to existing workflows

### Technical Requirements
- ✅ Environment variable configuration
- ✅ Secure credential handling
- ✅ Comprehensive error handling
- ✅ Debug logging and troubleshooting
- ✅ Production-ready deployment

### Documentation Requirements
- ✅ Complete configuration reference
- ✅ Step-by-step deployment guide
- ✅ Authentication method examples
- ✅ Troubleshooting guide
- ✅ Security best practices

## Dependencies

### New Dependencies
- `python-dotenv` - Environment variable management
- `temporalio[tls]` - TLS support (if not already included)

### External Dependencies
- Temporal Cloud account (for cloud deployment)
- TLS certificates (for mTLS authentication)
- Production environment configuration

## Risk Mitigation

### Configuration Errors
- Comprehensive validation with clear error messages
- Debug logging for connection details
- Environment variable verification

### Authentication Issues
- Clear documentation for each authentication method
- Example configurations for common scenarios
- Step-by-step troubleshooting guide

### Production Deployment
- Staged rollout approach
- Comprehensive testing in staging environment
- Rollback procedures documented

## File Structure After Implementation

```
around_the_grounds/temporal/
├── __init__.py
├── config.py              # NEW: Environment configuration
├── activities.py
├── shared.py
├── starter.py             # UPDATED: Use new config
├── worker.py              # UPDATED: Use new config
├── workflows.py
└── README.md              # UPDATED: Production deployment

.env.example               # NEW: Environment template
TEMPORAL-CLOUD-PLAN.md     # NEW: This plan document
```

This plan provides a comprehensive approach to adding Temporal Cloud support while maintaining backward compatibility and following established patterns from the reference project.