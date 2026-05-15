# Data Analyst Agent

The Data Agent reads SQLite schema before planning SQL. The generated SQL is checked by `SQLSafetyChecker` before execution.

Safety controls:

- SELECT-only validation with `sqlparse`
- dangerous keyword blocklist
- multi-statement blocking
- read-only SQLite authorizer
- query timeout and row limit
- PII masking for email, phone, and ID-like fields

Useful commands:

```bash
python scripts/seed_demo_data.py
python scripts/demo_data_agent.py
```
