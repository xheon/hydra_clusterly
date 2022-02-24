import subprocess
import time
from pathlib import Path
from typing import Iterator

import tailhead as tailhead
from debuggerly import Debugger


def follow_python_2(thefile, sleep_sec):
    while True:
        line = thefile.readline()
        if not line or not line.endswith('\n'):
            time.sleep(sleep_sec)
            continue
        yield line


def follow_python(file, sleep_sec):
    """ Yield each line from a file as they are written.
        `sleep_sec` is the time to sleep after empty reads. """
    line = ''
    while True:
        tmp = file.readline()
        # tmp = file.read().decode("ascii")
        if tmp is not None:
            line += tmp
            if line.endswith("\n"):
                yield line
                line = ''
        elif sleep_sec:
            time.sleep(sleep_sec)


def follow2(file, sleep_sec=0.1) -> Iterator[str]:
    """ Yield each line from a file as they are written.
    `sleep_sec` is the time to sleep after empty reads. """
    line = ''
    while True:
        lo = file.read() #.decode('ascii')


        if lo:
            end = ""
            read_end = lo[-1]
            if read_end == "\n":
                end = "n"
            elif read_end == "\r":
                end = "r"
            yield lo, end

        else:
            time.sleep(0.1)


def tail(file, sleep):
    f = subprocess.Popen(['tail', "-n1", '-f', file])

    while True:
        if f.stdout:
            line = f.stdout.readline()

            print(line, '')

        time.sleep(0.1)


def main_tail():
    print("hello")
    tail("sample.out", 0.1)


def main_follow():
    with open("sample.out", "r") as file:
        for line in follow_python(file, 0.1):
            print(line, end='\r')


def main_pygtail():
    from pygtail import Pygtail
    import sys
    for line in Pygtail("sample.out", ):
        sys.stdout.write(line)


def main_tailhead():
    for line in tailhead.follow_path("sample.out"):
        if line is not None:
            print(line, end="")
        else:
            time.sleep(1)

if __name__ == '__main__':
    # Debugger()
    main_tailhead()
