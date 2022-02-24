import sys
import time

from tqdm import trange

if __name__ == '__main__':
    print("hallo welt.")

    for i in trange(200, file=sys.stdout, position=0, ascii=False):
        # if i % 5 == 0:
        # print(i, flush=True)
        time.sleep(1)

    print("bye welt.")
