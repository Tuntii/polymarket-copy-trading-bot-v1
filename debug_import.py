import sys
import traceback

print(f"Python Executable: {sys.executable}")
print(f"Adding current dir to path...")
sys.path.append('.')

print("Attempting to import py_clob_client...")
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import OrderArgs, OrderType
    print("✅ SUCCESS: py_clob_client imported successfully!")
except ImportError as e:
    print(f"❌ ImportError: {e}")
    traceback.print_exc()
except Exception as e:
    print(f"❌ Unexpected Error: {e}")
    traceback.print_exc()
