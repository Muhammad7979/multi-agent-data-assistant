"""Single-process ownership boundary for policy persistence and answer requests."""
from threading import RLock

policy_operation_lock = RLock()
