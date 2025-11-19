#!/usr/bin/env python3
"""Check PyRevm 0.3.3 API."""

from pyrevm import EVM, AccountInfo, BlockEnv
import inspect

print("="*60)
print("PyRevm 0.3.3 API Check")
print("="*60)

print("\n1. AccountInfo signature:")
print(inspect.signature(AccountInfo))

print("\n2. EVM methods:")
for name in dir(EVM):
    if not name.startswith('_'):
        print(f"  - {name}")

print("\n3. Try creating AccountInfo:")
try:
    # Test with bytes
    acc = AccountInfo(balance=100, nonce=0, code=b"test")
    print(f"   ✅ AccountInfo with bytes: {acc}")
except Exception as e:
    print(f"   ❌ Failed with bytes: {e}")

try:
    # Test with hex string
    acc = AccountInfo(balance=100, nonce=0, code="0x60806040")
    print(f"   ✅ AccountInfo with hex: {acc}")
except Exception as e:
    print(f"   ❌ Failed with hex: {e}")

print("\n4. Try creating EVM:")
try:
    evm = EVM()
    print(f"   ✅ EVM created: {evm}")
    print(f"   EVM methods: {[m for m in dir(evm) if not m.startswith('_')]}")
except Exception as e:
    print(f"   ❌ Failed: {e}")
