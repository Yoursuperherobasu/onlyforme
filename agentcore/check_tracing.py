#!/usr/bin/env python3
"""
Diagnostic script to check Langfuse tracing configuration
"""
import sys
import os

# Add the backend to path
sys.path.insert(0, 'src/backend/base')

print("=" * 60)
print("LANGFUSE TRACING DIAGNOSTIC")
print("=" * 60)

# Check environment variables
print("\n1. Environment Variables:")
print("-" * 40)
env_vars = ['DEACTIVATE_TRACING', 'LANGFUSE_SECRET_KEY', 'LANGFUSE_PUBLIC_KEY', 'LANGFUSE_BASE_URL', 'LANGFUSE_HOST']
for var in env_vars:
    value = os.getenv(var)
    if var in ['LANGFUSE_SECRET_KEY', 'LANGFUSE_PUBLIC_KEY']:
        display = f"{'present' if value else 'missing'} ({value[:15]}...)" if value else 'missing'
    else:
        display = value if value else 'not set'
    print(f"  {var}: {display}")

# Try loading settings
print("\n2. Settings Check:")
print("-" * 40)
try:
    from dotenv import load_dotenv, find_dotenv
    env_file = find_dotenv()
    print(f"  .env file found: {env_file}")
    load_dotenv(env_file)
    
    from agentcore.services.settings.base import Settings
    settings = Settings()
    print(f"  ✅ Settings loaded successfully")
    print(f"  deactivate_tracing: {settings.deactivate_tracing}")
    print(f"  config_dir: {settings.config_dir}")
except Exception as e:
    print(f"  ❌ Error loading settings: {e}")
    import traceback
    traceback.print_exc()

# Test Langfuse connection
print("\n3. Langfuse Connection Test:")
print("-" * 40)
try:
    from langfuse import Langfuse
    
    secret = os.getenv('LANGFUSE_SECRET_KEY')
    public = os.getenv('LANGFUSE_PUBLIC_KEY')
    base_url = os.getenv('LANGFUSE_BASE_URL') or os.getenv('LANGFUSE_HOST')
    
    if not all([secret, public, base_url]):
        print(f"  ❌ Missing credentials")
    else:
        print(f"  Connecting to: {base_url}")
        client = Langfuse(secret_key=secret, public_key=public, host=base_url)
        
        if hasattr(client, 'auth_check'):
            result = client.auth_check()
            if result:
                print(f"  ✅ Auth check passed")
            else:
                print(f"  ⚠️ Auth check failed but client created")
        else:
            print(f"  ℹ️ No auth_check method (SDK v2?)")
        
        # Try fetching traces
        if hasattr(client, 'fetch_traces'):
            print(f"  Testing fetch_traces...")
            traces = client.fetch_traces(limit=1, page=1)
            trace_count = len(traces.data) if hasattr(traces, 'data') else len(traces) if isinstance(traces, list) else 0
            print(f"  ✅ Fetch traces worked (found {trace_count} traces)")
        
        print(f"  ✅ Langfuse connection successful")
        
except ImportError as e:
    print(f"  ❌ Langfuse not installed: {e}")
except Exception as e:
    print(f"  ❌ Connection failed: {e}")
    import traceback
    traceback.print_exc()

# Test tracer initialization
print("\n4. Tracer Initialization Test:")
print("-" * 40)
try:
    from agentcore.services.tracing.langfuse import LangFuseTracer
    from uuid import uuid4
    
    tracer = LangFuseTracer(
        trace_name="test_trace",
        trace_type="chain",
        project_name="test_project",
        trace_id=uuid4(),
        user_id="test_user",
        session_id="test_session",
        agent_id="test_agent",
        flow_name="test_flow",
    )
    
    print(f"  Tracer created: ready={tracer.ready}")
    if tracer.ready:
        print(f"  ✅ Tracer is ready to record traces")
    else:
        print(f"  ⚠️ Tracer not ready - traces will not be recorded")
        
except Exception as e:
    print(f"  ❌ Tracer initialization failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("DIAGNOSIS COMPLETE")
print("=" * 60)
