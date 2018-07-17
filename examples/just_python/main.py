import sys
import time

#######################################
# Minimal plz example using only python
#######################################
# We are trying to learn the value k for the function
# f(x) = k*x
# minimising
# (x - 3 * f(x))^2 .
# (Shhh, I'll tell you a secret: it's 1/3.)

num_iterations = int(sys.argv[1])

data = [900, 15, 27, 10, 1, 0.0003, -270, 33]

k = 0.0
for i in range(0, num_iterations):
    print(f'k: {k:.4}')
    x = data[i % len(data)]
    loss = pow(x - 3 * k * x, 2)
    update = -6 * pow(x, 2) + 18 * k * pow(x, 2)
    # Weight the learning rate by x
    k = k - 0.0001/x * update
    # Simulate that this took some time
    time.sleep(0.5)
