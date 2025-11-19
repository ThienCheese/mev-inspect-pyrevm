#!/usr/bin/env python3
"""Check if PyRevm is properly installed and importable."""

print("Testing PyRevm import...")
print("-" * 50)

try:
    from pyrevm import EVM, AccountInfo, BlockEnv, TransactTo, HexBytes
    print("✅ PyRevm imported successfully!")
    print(f"   Evm: {EVM}")
    print(f"   AccountInfo: {AccountInfo}")
    print(f"   BlockEnv: {BlockEnv}")
    print(f"   TransactTo: {TransactTo}")
    print(f"   HexBytes: {HexBytes}")
    
    # Try creating an EVM instance
    try:
        evm = EVM()
        print("\n✅ EVM instance created successfully!")
        print(f"   Instance: {evm}")
    except Exception as e:
        print(f"\n❌ Failed to create EVM instance: {e}")
        
except ImportError as e:
    print(f"❌ Failed to import PyRevm: {e}")
    print("\nTry installing: pip install pyrevm>=0.3.0")

print("\nChecking pip list...")
import subprocess
result = subprocess.run(['pip', 'list'], capture_output=True, text=True)
lines = [line for line in result.stdout.split('\n') if 'pyrevm' in line.lower()]
if lines:
    print("Found in pip:")
    for line in lines:
        print(f"  {line}")
else:
    print("  PyRevm NOT found in pip list")
