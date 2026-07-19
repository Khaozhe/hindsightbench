"""Single source of the repo root for every hindsight script.

Resolution order:
1. $HINDSIGHT_ROOT, if set (server migrations, CI);
2. auto-detect from this file's location (<root>/hindsight/scripts/).

Keeps every script runnable from any checkout location with zero config;
the env var exists for layouts where scripts are copied away from the repo.
"""

import os
from pathlib import Path

REPO = Path(os.environ.get("HINDSIGHT_ROOT",
                           Path(__file__).resolve().parents[2]))
