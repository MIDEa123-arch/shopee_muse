"""Compatibility entry point for the current full retail audit.

python -m scripts.verify_merchandise --output docs/retail_audit.json
Reads real catalog/checkpoint; does not create orders, carts or behavior.
"""
from scripts.audit_retail import main

if __name__ == '__main__':
    main()
