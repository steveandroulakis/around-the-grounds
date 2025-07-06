"""Configuration system for Temporal client connections.

Supports multiple authentication methods:
- Local development (default)
- Temporal Cloud with API key
- mTLS certificate authentication
"""

import os
from temporalio.client import Client
from temporalio.service import TLSConfig

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    # dotenv is optional, fall back to os.environ
    pass

# Temporal connection settings
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "food-truck-task-queue")

# Authentication settings
TEMPORAL_TLS_CERT = os.getenv("TEMPORAL_TLS_CERT", "")
TEMPORAL_TLS_KEY = os.getenv("TEMPORAL_TLS_KEY", "")
TEMPORAL_API_KEY = os.getenv("TEMPORAL_API_KEY", "")


async def get_temporal_client() -> Client:
    """
    Creates a Temporal client based on environment configuration.
    Supports local server, mTLS, and API key authentication methods.
    
    Returns:
        Client: Configured Temporal client
        
    Raises:
        Exception: If connection fails or configuration is invalid
    """
    # Default to no TLS for local development
    tls_config = False
    
    # Debug logging for connection details
    print(f"🔗 Connecting to Temporal server:")
    print(f"   Address: {TEMPORAL_ADDRESS}")
    print(f"   Namespace: {TEMPORAL_NAMESPACE}")
    print(f"   Task Queue: {TEMPORAL_TASK_QUEUE}")
    
    if TEMPORAL_ADDRESS == "localhost:7233":
        print("   Mode: Local development (no authentication)")
    else:
        print("   Mode: Remote server")

    # Configure mTLS if certificate and key are provided
    if TEMPORAL_TLS_CERT and TEMPORAL_TLS_KEY:
        print(f"   TLS Certificate: {TEMPORAL_TLS_CERT}")
        print(f"   TLS Key: {TEMPORAL_TLS_KEY}")
        print("   Authentication: mTLS")
        
        try:
            with open(TEMPORAL_TLS_CERT, "rb") as f:
                client_cert = f.read()
            with open(TEMPORAL_TLS_KEY, "rb") as f:
                client_key = f.read()
            tls_config = TLSConfig(
                client_cert=client_cert,
                client_private_key=client_key,
            )
        except FileNotFoundError as e:
            raise Exception(f"TLS certificate or key file not found: {e}")
        except Exception as e:
            raise Exception(f"Failed to load TLS configuration: {e}")

    # Use API key authentication if provided
    if TEMPORAL_API_KEY:
        print(f"   API Key: {TEMPORAL_API_KEY[:8]}...")
        print("   Authentication: API Key")
        
        try:
            return await Client.connect(
                TEMPORAL_ADDRESS,
                namespace=TEMPORAL_NAMESPACE,
                api_key=TEMPORAL_API_KEY,
                tls=True,  # Always use TLS with API key
            )
        except Exception as e:
            raise Exception(f"Failed to connect with API key: {e}")

    # Use mTLS or local connection
    try:
        return await Client.connect(
            TEMPORAL_ADDRESS,
            namespace=TEMPORAL_NAMESPACE,
            tls=tls_config,
        )
    except Exception as e:
        if TEMPORAL_ADDRESS == "localhost:7233":
            raise Exception(f"Failed to connect to local Temporal server. Is it running? Error: {e}")
        else:
            raise Exception(f"Failed to connect to Temporal server: {e}")


def validate_configuration() -> None:
    """
    Validates the current configuration for common issues.
    
    Raises:
        Exception: If configuration is invalid
    """
    # Check for conflicting authentication methods
    has_mtls = bool(TEMPORAL_TLS_CERT and TEMPORAL_TLS_KEY)
    has_api_key = bool(TEMPORAL_API_KEY)
    
    if has_mtls and has_api_key:
        raise Exception("Cannot use both mTLS and API key authentication. Please set only one.")
    
    # Check for incomplete mTLS configuration
    if TEMPORAL_TLS_CERT and not TEMPORAL_TLS_KEY:
        raise Exception("TLS certificate provided but key is missing. Both TEMPORAL_TLS_CERT and TEMPORAL_TLS_KEY are required.")
    
    if TEMPORAL_TLS_KEY and not TEMPORAL_TLS_CERT:
        raise Exception("TLS key provided but certificate is missing. Both TEMPORAL_TLS_CERT and TEMPORAL_TLS_KEY are required.")
    
    # Check certificate files exist
    if TEMPORAL_TLS_CERT and not os.path.exists(TEMPORAL_TLS_CERT):
        raise Exception(f"TLS certificate file not found: {TEMPORAL_TLS_CERT}")
    
    if TEMPORAL_TLS_KEY and not os.path.exists(TEMPORAL_TLS_KEY):
        raise Exception(f"TLS key file not found: {TEMPORAL_TLS_KEY}")
    
    print("✅ Configuration validation passed")


def get_configuration_summary() -> dict:
    """
    Returns a summary of the current configuration for debugging.
    
    Returns:
        dict: Configuration summary (sensitive values masked)
    """
    return {
        "address": TEMPORAL_ADDRESS,
        "namespace": TEMPORAL_NAMESPACE,
        "task_queue": TEMPORAL_TASK_QUEUE,
        "auth_method": (
            "api_key" if TEMPORAL_API_KEY else
            "mtls" if TEMPORAL_TLS_CERT and TEMPORAL_TLS_KEY else
            "none"
        ),
        "tls_cert_path": TEMPORAL_TLS_CERT or None,
        "tls_key_path": TEMPORAL_TLS_KEY or None,
        "api_key_set": bool(TEMPORAL_API_KEY),
    }