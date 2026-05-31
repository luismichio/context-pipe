# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.
import asyncio
import sys

if sys.platform != "win32":
    # Use ThreadedChildWatcher to prevent asyncio.run() subprocess deadlocks in pytest on Unix/Linux
    asyncio.get_event_loop_policy().set_child_watcher(asyncio.ThreadedChildWatcher())
