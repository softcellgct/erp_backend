import time

start_time = time.time()
for i in range(1,100000000):
    pass
end_time = time.time()

print("Time taken:", end_time - start_time)