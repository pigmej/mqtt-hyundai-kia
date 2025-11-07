"""Main entry point for Hyundai MQTT integration service."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.main import main

if __name__ == "__main__":
    asyncio.run(main())
