import inspect
import os
import shutil
import time
from dataclasses import dataclass

import logging
from pathlib import Path
from typing import Optional, Sequence, Any, List, Dict

from hydra.types import HydraContext
from hydra.core.config_store import ConfigStore
from hydra.core.singleton import Singleton
from hydra.core.utils import (
    JobReturn,
    configure_log,
    filter_overrides,
    run_job,
    setup_globals,
)
from hydra.plugins.launcher import Launcher
from hydra.types import TaskFunction
from hydra_plugins.hydra_submitit_launcher.config import BaseQueueConf, SlurmQueueConf
from hydra_plugins.hydra_submitit_launcher.submitit_launcher import SlurmLauncher
from omegaconf import DictConfig, open_dict, OmegaConf

from hydra.core.utils import JobReturn, setup_globals, configure_log

log = logging.getLogger(__name__)


@dataclass
class ClusterlyConf(SlurmQueueConf):
    _target_: str = (
        "hydra_plugins.hydra_clusterly.clusterly.Clusterly"
    )

    # output: Optional[str] = "job_%j.log"
    # error: Optional[str] = None


ConfigStore.instance().store(
    group="hydra/launcher", name="clusterly", node=ClusterlyConf
)


class Clusterly(SlurmLauncher):
    def __init__(self, **params) -> None:
        super().__init__(**params)
        self.code_path: Optional[Path] = None

    def setup(
        self,
        *,
        hydra_context: HydraContext,
        task_function: TaskFunction,
        config: DictConfig,
    ) -> None:
        super().setup(hydra_context=hydra_context,task_function=task_function,config=config)

        # Determine common path prefix
        task_function_path = Path(inspect.getsourcefile(task_function))  # from task function
        config_path = Path(self.config.hydra.runtime.config_sources[1].path)   # from config
        common_prefix = Path(os.path.commonpath([task_function_path, config_path]))
        log.info(f"Clusterly: Determined source code path: {common_prefix}")

        self.code_path = Path(config.hydra.run.dir) / "code"
        # self.code_path.mkdir(exist_ok=True, parents=True)
        log.info(f"Clusterly: Determined destination code path: {self.code_path}")

        log.info("Clusterly: Copy source files...")
        # iterate over all folders, copy them if not ignored

        # for element in common_prefix.iterdir():
        shutil.copytree(common_prefix, self.code_path, dirs_exist_ok=True)

        # log.info("sleeping...")
        # time.sleep(5)
        # log.info("done...")

    def submit_single_job(
            self,
            sweep_overrides: List[str],
            job_dir_key: str,
            job_num: int,
            job_id: str,
            singleton_state: Dict[type, Singleton],
    ) -> JobReturn:
        # lazy import to ensure plugin discovery remains fast
        import submitit

        assert self.hydra_context is not None
        assert self.config is not None
        assert self.task_function is not None

        Singleton.set_state(singleton_state)
        setup_globals()
        sweep_config = self.hydra_context.config_loader.load_sweep_config(
            self.config, sweep_overrides
        )

        with open_dict(sweep_config.hydra.job) as job:
            # Populate new job variables
            job.id = submitit.JobEnvironment().job_id  # type: ignore
            sweep_config.hydra.job.num = job_num

        return run_job(
            hydra_context=self.hydra_context,
            task_function=self.task_function,
            config=sweep_config,
            job_dir_key=job_dir_key,
            job_subdir_key=job_dir_key,
        )

    def submit_multi_job(
        self,
        sweep_overrides: List[str],
        job_dir_key: str,
        job_num: int,
        job_id: str,
        singleton_state: Dict[type, Singleton],
    ) -> JobReturn:
        # lazy import to ensure plugin discovery remains fast
        import submitit

        assert self.hydra_context is not None
        assert self.config is not None
        assert self.task_function is not None

        Singleton.set_state(singleton_state)
        setup_globals()
        sweep_config = self.hydra_context.config_loader.load_sweep_config(
            self.config, sweep_overrides
        )

        with open_dict(sweep_config.hydra.job) as job:
            # Populate new job variables
            job.id = submitit.JobEnvironment().job_id  # type: ignore
            sweep_config.hydra.job.num = job_num

        return run_job(
            hydra_context=self.hydra_context,
            task_function=self.task_function,
            config=sweep_config,
            job_dir_key=job_dir_key,
            job_subdir_key="hydra.sweep.subdir",
        )

    def launch(
        self, job_overrides: Sequence[Sequence[str]], initial_job_idx: int
    ) -> Sequence[JobReturn]:
        import submitit
        assert self.config is not None

        num_jobs = len(job_overrides)
        assert num_jobs > 0
        params = self.params
        # build executor
        init_params = {"folder": self.params["submitit_folder"]}
        specific_init_keys = {"max_num_timeout"}

        init_params.update(
            **{
                f"{self._EXECUTOR}_{x}": y
                for x, y in params.items()
                if x in specific_init_keys
            }
        )
        init_keys = specific_init_keys | {"submitit_folder"}
        executor = submitit.AutoExecutor(cluster=self._EXECUTOR, **init_params)

        # specify resources/parameters
        baseparams = set(OmegaConf.structured(BaseQueueConf).keys())
        params = {
            x if x in baseparams else f"{self._EXECUTOR}_{x}": y
            for x, y in params.items()
            if x not in init_keys
        }
        executor.update_parameters(**params)

        # distinguish between single and multi run
        if len(job_overrides) == 1:
            return self.launch_single_run(executor, job_overrides, initial_job_idx)
        else:
            return self.launch_multi_run(executor, job_overrides, initial_job_idx)

    def launch_single_run(self, executor, job_overrides, initial_job_idx):
        log.info(f"Clusterly: Use '{self._EXECUTOR}', run output dir : {self.config.hydra.run.dir}")

        job_params: List[Any] = [
            job_overrides[0],
            "hydra.run.dir",
            initial_job_idx,
            f"job_id_for_{initial_job_idx}",
            Singleton.get_state(),
        ]

        job = executor.submit(self.submit_single_job, *job_params)
        log.info(f"Clusterly: Submitted single job as {job.job_id}")

        return [job.result()]

    def launch_multi_run(self, executor, job_overrides, initial_job_idx):
        log.info(f"Clusterly: Use '{self._EXECUTOR}', sweep output dir : {self.config.hydra.sweep.dir}")

        sweep_dir = Path(str(self.config.hydra.sweep.dir))
        sweep_dir.mkdir(parents=True, exist_ok=True)
        if "mode" in self.config.hydra.sweep:
            mode = int(str(self.config.hydra.sweep.mode), 8)
            os.chmod(sweep_dir, mode=mode)

        job_params: List[Any] = []
        for idx, overrides in enumerate(job_overrides):
            idx = initial_job_idx + idx
            lst = " ".join(filter_overrides(overrides))
            log.info(f"\t#{idx} : {lst}")
            job_params.append(
                (
                    list(overrides),
                    "hydra.sweep.dir",
                    idx,
                    f"job_id_for_{idx}",
                    Singleton.get_state(),
                )
            )

        jobs = executor.map_array(self.submit_multi_job, *zip(*job_params))
        for j in jobs:
            log.info(f"Clusterly: Submitting child job of {initial_job_idx}: {j.job_id}")
        return [j.results()[0] for j in jobs]
