#!/usr/bin/env python3

import sys
import time

n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000

for i in range(n):
    print(i, flush=True)
    time.sleep(1)
