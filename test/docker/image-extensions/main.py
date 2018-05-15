#!/usr/bin/env python3

import json
import os.path
import numpy

with open(os.environ['CONFIGURATION_FILE']) as c:
    config = json.load(c)
parameters = config['parameters']

a = numpy.matrix(parameters['a'])
b = numpy.matrix(parameters['b'])
result = a * b

print(result)
