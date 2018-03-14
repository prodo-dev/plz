#!/usr/bin/env python
import time

for i in range(20):
    print(i, flush=True)
    if i > 15:
        time.sleep(1)

