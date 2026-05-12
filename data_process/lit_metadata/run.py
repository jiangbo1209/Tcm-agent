from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent)
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    from app.main import main

    asyncio.run(main())
