"""
Timing utilities for the trading bot
Contains countdown timers and other time-related utilities
"""

import asyncio
from tqdm import tqdm


async def countdown_timer(duration):
    """
    Display countdown timer with progress bar
    
    Args:
        duration: Duration in seconds to count down
    """
    for remaining in tqdm(range(duration, 0, -1), desc="Attesa ciclo successivo", ncols=80, ascii=True):
        await asyncio.sleep(1)
    print()
