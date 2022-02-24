import logging
import os
import sys
import time

import hydra
from debuggerly import Debugger
from omegaconf import DictConfig
from tqdm import trange

log = logging.getLogger(__name__)


@hydra.main(config_path="", config_name="config")
def my_app(cfg: DictConfig) -> None:
    log.info(f"Process ID {os.getpid()} executing task {cfg.sample_task}")
    log.info(f"CWD: {os.getcwd()}")
    log.info(f"Path: {sys.path}, PYTHONPATH: {os.environ['PYTHONPATH']}")

    a = 10
    log.info(f"Value: before=10, after={a}\n")

    iterations = 100

    for iteration in trange(iterations, position=0, leave=True):
        # log.info(f"{iteration}")
        # tqdm.write(f"{iteration}")
        time.sleep(0.5)

    time.sleep(1)
    log.info("Example finished\n")


if __name__ == "__main__":
    Debugger()
    my_app()
