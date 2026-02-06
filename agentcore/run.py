import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "agentcore.main:create_app",
        host="0.0.0.0",
        port=7860,
        reload=True,
        factory=True,
        log_level="debug"
    )
