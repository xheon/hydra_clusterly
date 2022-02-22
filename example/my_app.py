# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
import inspect
import logging
import os
import sys
import time
from pathlib import Path

import hydra
import submitit
from omegaconf import DictConfig, OmegaConf

from debuggerly import Debugger

log = logging.getLogger(__name__)


@hydra.main(config_path="", config_name="config")
def my_app(cfg: DictConfig) -> None:
    env = submitit.JobEnvironment()
    log.info(env)
    log.info(f"Process ID {os.getpid()} executing task {cfg.task}, CWD: {os.getcwd()}, Path: {sys.path}, PYTHONPATH: {os.environ['PYTHONPATH']}")
    a = 10
    log.info(f"Value: before=10, after={a}")
    log.info(f"FUNCTION: {Path(inspect.getsourcefile(my_app))}")


if __name__ == "__main__":
    Debugger()
    print(os.getcwd())
    my_app()
