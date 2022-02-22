from pytest import mark

from hydra.core.plugins import Plugins
from hydra.plugins.launcher import Launcher
from hydra.test_utils.launcher_common_tests import (
    IntegrationTestSuite,
    LauncherTestSuite,
)


from hydra_plugins.hydra_clusterly.clusterly import Clusterly


def test_discovery() -> None:
    # Tests that this plugin can be discovered via the plugins subsystem when looking for Launchers
    assert Clusterly.__name__ in [
        x.__name__ for x in Plugins.instance().discover(Launcher)
    ]


@mark.parametrize("launcher_name, overrides", [("clusterly", [])])
class TestExampleLauncher(LauncherTestSuite):
    """
    Run the Launcher test suite on this launcher.
    Note that hydra/launcher/example.yaml should be provided by this launcher.
    """

    pass


@mark.parametrize(
    "task_launcher_cfg, extra_flags",
    [({}, ["-m", "hydra/launcher=clusterly"])],
)
class TestClusterlyLauncherIntegration(IntegrationTestSuite):
    """
    Run this launcher through the integration test suite.
    """

    pass