import datetime
import inspect
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Any, List, Dict, Tuple

import sysrsync
import tailhead
from hydra.core.config_store import ConfigStore
from hydra.core.singleton import Singleton
from hydra.core.utils import JobReturn, setup_globals
from hydra.core.utils import (
    filter_overrides,
    run_job,
)
from hydra.types import HydraContext
from hydra.types import TaskFunction
from hydra_plugins.hydra_submitit_launcher.config import BaseQueueConf, SlurmQueueConf
from hydra_plugins.hydra_submitit_launcher.submitit_launcher import SlurmLauncher
from omegaconf import DictConfig, open_dict, OmegaConf
from submitit import Executor, Job

log = logging.getLogger(__name__)


# Extend Slurm configuration with additional fields
@dataclass
class ClusterlyConf(SlurmQueueConf):
    _target_: str = (
        "hydra_plugins.hydra_clusterly.clusterly.Clusterly"
    )

    code_path: Optional[str] = None
    code_ignores: Optional[List[str]] = None
    code_ignore_file: Optional[str] = None

    print_output: bool = False
    wait_for_completion: bool = True


# Register as hydra launcher
ConfigStore.instance().store(
    group="hydra/launcher", name="clusterly", node=ClusterlyConf
)


class Clusterly(SlurmLauncher):
    def __init__(self, **params) -> None:
        super().__init__(**params)
        self.code_path = None

        if self.params["code_path"] is not None:
            self.code_path = Path(self.params["code_path"])

    def setup(self, *, hydra_context: HydraContext, task_function: TaskFunction, config: DictConfig) -> None:
        super().setup(hydra_context=hydra_context, task_function=task_function, config=config)

        if self.code_path is not None:
            self.copy_code(task_function)
        else:
            log.warning("Clusterly: Code is not copied.")

    def copy_code(self, task_function):
        # Determine common path prefix.
        task_function_path = Path(inspect.getsourcefile(task_function))  # from task function
        config_path = Path(self.config.hydra.runtime.config_sources[1].path)  # from config
        common_prefix = Path(os.path.commonpath([task_function_path, config_path]))
        log.info(f"Clusterly: Determined source code path: {common_prefix}")

        self.code_path.mkdir(exist_ok=True, parents=True)
        log.info(f"Clusterly: Determined destination code path: {self.code_path}")
        copy_info = f"Clusterly: Copy source files"

        # Read ignores from file.
        code_ignores = set()
        exclude_info = []

        if self.params["code_ignores"] is not None:
            code_ignores.update(self.params["code_ignores"])
            exclude_info.append(f" excluding {self.params['code_ignores']} ({len(self.params['code_ignores'])}) excludes")
        if self.params["code_ignore_file"] is not None:
            ignore_file = common_prefix / self.params["code_ignore_file"]

            if ignore_file.exists():
                ignores_from_file = [line.strip() for line in ignore_file.open().readlines() if
                                     not line.startswith("#") and line.strip() != ""]
                code_ignores.update(ignores_from_file)
                exclude_info.append(f"excluding from file \'{self.params['code_ignore_file']}\' " +
                                    f"({len(ignores_from_file)}) excludes.")
        log.info(copy_info + " and ".join(exclude_info))

        sysrsync.run(source=str(common_prefix),
                     destination=str(self.code_path),
                     exclusions=code_ignores,
                     options=["-r"])

    def submit_job(
            self, sweep_overrides: List[str],
            job_dir_key: str,
            job_subdir_key: str,
            job_num: int,
            _: str,
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
            job_subdir_key=job_subdir_key,
        )

    def launch(self, job_overrides: Sequence[Sequence[str]], initial_job_idx: int) -> Sequence[JobReturn]:
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

        init_keys = specific_init_keys | {"submitit_folder", "code_path", "code_ignores", "code_ignore_file",
                                          "print_output", "wait_for_completion"}

        executor = submitit.AutoExecutor(cluster=self._EXECUTOR, **init_params)

        # specify resources/parameters
        baseparams = set(OmegaConf.structured(BaseQueueConf).keys())
        params = {
            x if x in baseparams else f"{self._EXECUTOR}_{x}": y
            for x, y in params.items()
            if x not in init_keys
        }
        params["stderr_to_stdout"] = True
        executor.update_parameters(**params)

        # distinguish between single and multi run
        if len(job_overrides) == 1:
            return self.launch_single_run(executor, job_overrides, initial_job_idx)
        else:
            return self.launch_multi_run(executor, job_overrides, initial_job_idx)

    def launch_single_run(self, executor: Executor, job_overrides: Sequence[Sequence[str]],
                          initial_job_idx: int) -> Sequence[JobReturn]:
        log.info(f"Clusterly: Use '{self._EXECUTOR}', run output dir : {self.config.hydra.run.dir}")

        job_params: List[Any] = [
            job_overrides[0],
            "hydra.run.dir",
            "hydra.run.dir",
            initial_job_idx,
            f"job_id_for_{initial_job_idx}",
            Singleton.get_state(),
        ]

        job = executor.submit(self.submit_job, *job_params)

        log.info(f"Clusterly: Submitted single job as {job.job_id} [{job.state}]")

        if not self.params["wait_for_completion"]:
            log.info(f"Clusterly: Job as {job.job_id} is still running.")
            # return [JobReturn(_return_value="uncompleted")]
            return []

        last_state = job.state
        last_state_change = time.perf_counter()
        last_position_stdout = 0

        if self.params["print_output"]:
            printer = tailhead.follow_path(job.paths.stdout)

        while not job.done():
            try:
                if self.params["print_output"]:
                    next_line = next(printer)
                    if next_line is not None and next_line != "":
                        lines = next_line.split("\r")

                        if len(lines) == 1:
                            print(next_line)
                        else:
                            for line in lines:
                                if line != "":
                                    print(line, end="\r")

                # Display changes in job status
                state_has_changed, new_state, last_state_change, delta_seconds = self.check_state_change(job,
                                                                                                         last_state,
                                                                                                         last_state_change)
                if state_has_changed:
                    self.log_state_change(job.job_id, last_state, new_state, delta_seconds)
                    last_state = new_state

                time.sleep(0.2)
            except KeyboardInterrupt:
                log.info(f"Output stopped, job is still running at {job.job_id}")

                while True:
                    confirm = input("[r] Resume, [c] Cancel job, [q] Exit: ")
                    if confirm == "r":
                        log.info(f"Resume output...")
                        break
                    elif confirm == "c":
                        log.info(f"Cancelling job {job.job_id}...")
                        job.cancel()
                        log.info(f"Job {job.job_id} cancelled.")
                        return []
                    elif confirm == "q":
                        log.info(f"Exited, job is still running at {job.job_id}")
                        return []

        if self.params["print_output"]:
            # self.print_stdout(job, last_position_stdout)
            for next_line in printer:
                if next_line == "":
                    break

                if next_line is not None and next_line != "":
                    lines = next_line.split("\r")

                    if len(lines) == 1:
                        print(next_line)
                    else:
                        for line in lines[:-1]:
                            if line != "":
                                print(line, end="\r")
                        print(lines[-1])
        log.info(f"Clusterly: Job {job.job_id} done")
        new_state = job.watcher.get_state(job.job_id, mode="force")
        self.log_state_change(job.job_id, last_state, new_state, time.perf_counter() - last_state_change)

        return [job.result()]

    @staticmethod
    def print_stdout(job: Job, last_position_stdout: int) -> int:
        stdout_path = job.paths.stdout
        if stdout_path.exists():
            with stdout_path.open(encoding='utf-8') as stdout:
                stdout.seek(last_position_stdout)

                stdout_output = ""
                try:
                    stdout_output = stdout.readline()
                except UnicodeDecodeError:
                    print("Ignoring DecodeError")

                if stdout_output.strip():
                    lines_read = len(stdout_output)
                    last_position_stdout += lines_read

                    if lines_read > 0:
                        print(stdout_output, end="")

        return last_position_stdout

    @staticmethod
    def log_state_change(job_id: str, last_state: str, new_state: str, delta_seconds: float) -> None:
        delta_time = datetime.timedelta(seconds=round(delta_seconds, 0))
        log.info(f"Clusterly: Job {job_id} changed from [{last_state}] to [{new_state}] after {delta_time}")

    @staticmethod
    def check_state_change(job: Job, last_state: str, last_state_change: float) -> Tuple[bool, str, float, float]:
        has_changed = False
        delta_time_seconds = 0
        if job.state != last_state:
            delta_time_seconds = time.perf_counter() - last_state_change
            last_state = job.state
            last_state_change = time.perf_counter()
            has_changed = True

        return has_changed, last_state, last_state_change, delta_time_seconds

    def launch_multi_run(self, executor: Executor, job_overrides: Sequence[Sequence[str]],
                         initial_job_idx: int) -> Sequence[JobReturn]:
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
                    "hydra.sweep.subdir",
                    idx,
                    f"job_id_for_{idx}",
                    Singleton.get_state(),
                )
            )

        jobs = executor.map_array(self.submit_job, *zip(*job_params))
        for j in jobs:
            log.info(f"Clusterly: Submitting child job of {initial_job_idx}: {j.job_id}")
        return [j.results()[0] for j in jobs]
