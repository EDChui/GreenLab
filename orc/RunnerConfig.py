from EventManager.Models.RunnerEvents import RunnerEvents
from EventManager.EventSubscriptionController import EventSubscriptionController
from ConfigValidator.Config.Models.RunTableModel import RunTableModel
from ConfigValidator.Config.Models.FactorModel import FactorModel
from ConfigValidator.Config.Models.RunnerContext import RunnerContext
from ConfigValidator.Config.Models.OperationType import OperationType
from ExtendedTyping.Typing import SupportsStr
from ProgressManager.Output.OutputProcedure import OutputProcedure as output

import time
from typing import Dict, List, Any, Optional
from pathlib import Path
from os import getenv
from os.path import dirname, realpath
from dotenv import load_dotenv

# Add the current directory to Python path to allow local imports
import sys
from pathlib import Path
config_dir = str(Path(__file__).parent.resolve())
if config_dir not in sys.path:
    sys.path.insert(0, config_dir)
from ExternalMachineAPI import ExternalMachineAPI

# Load environment variables from .env file
load_dotenv()

DEBUG_MODE = getenv("DEBUG_MODE", "False").lower() in ("true", "1", "t")

class RunnerConfig:
    ROOT_DIR = Path(dirname(realpath(__file__)))

    # ================================ USER SPECIFIC CONFIG ================================
    """The name of the experiment."""
    name:                       str             = "cpu_governor_on_social_network"

    """The path in which Experiment Runner will create a folder with the name `self.name`, in order to store the
    results from this experiment. (Path does not need to exist - it will be created if necessary.)
    Output path defaults to the config file's path, inside the folder 'experiments'"""
    results_output_path:        Path            = ROOT_DIR / 'experiments'

    """Experiment operation type. Unless you manually want to initiate each run, use `OperationType.AUTO`."""
    operation_type:             OperationType   = OperationType.AUTO

    """The time Experiment Runner will wait after a run completes.
    This can be essential to accommodate for cooldown periods on some systems."""
    time_between_runs_in_ms:    int             = 90_000 if not DEBUG_MODE else 1_000  # milliseconds

    # Dynamic configurations can be one-time satisfied here before the program takes the config as-is
    # e.g. Setting some variable based on some criteria
    def __init__(self):
        """Executes immediately after program start, on config load"""

        EventSubscriptionController.subscribe_to_multiple_events([
            (RunnerEvents.BEFORE_EXPERIMENT, self.before_experiment),
            (RunnerEvents.BEFORE_RUN       , self.before_run       ),
            (RunnerEvents.START_RUN        , self.start_run        ),
            (RunnerEvents.START_MEASUREMENT, self.start_measurement),
            (RunnerEvents.INTERACT         , self.interact         ),
            (RunnerEvents.STOP_MEASUREMENT , self.stop_measurement ),
            (RunnerEvents.STOP_RUN         , self.stop_run         ),
            (RunnerEvents.POPULATE_RUN_DATA, self.populate_run_data),
            (RunnerEvents.AFTER_EXPERIMENT , self.after_experiment )
        ])
        self.run_table_model = None  # Initialized later
        self.warmup_time                : int = 90 if not DEBUG_MODE else 5 # seconds
        self.post_warmup_cooldown_time  : int = 30 if not DEBUG_MODE else 1 # seconds

        output.console_log("Custom config loaded")
        output.console_log("Current environment: " + ("DEBUG" if DEBUG_MODE else "PRODUCTION"))

    def create_run_table_model(self) -> RunTableModel:
        """Create and return the run_table model here. A run_table is a List (rows) of tuples (columns),
        representing each run performed"""
        factor1 = FactorModel("example_factor1", ['example_treatment1', 'example_treatment2', 'example_treatment3'])
        factor2 = FactorModel("example_factor2", [True, False])
        self.run_table_model = RunTableModel(
            factors=[factor1, factor2],
            exclude_combinations=[
                {factor1: ['example_treatment1']},                   # all runs having treatment "example_treatment1" will be excluded
                {factor1: ['example_treatment2'], factor2: [True]},  # all runs having the combination ("example_treatment2", True) will be excluded
            ],
            data_columns=['avg_cpu', 'avg_mem']
        )
        return self.run_table_model

    def before_experiment(self) -> None:
        """Perform any activity required before starting the experiment here
        Invoked only once during the lifetime of the program."""
        pass

    def before_run(self) -> None:
        """Perform any activity required before starting a run.
        No context is available here as the run is not yet active (BEFORE RUN)"""
        self.run_time = None

    def start_run(self, context: RunnerContext) -> None:
        """Perform any activity required for starting the run here.
        For example, starting the target system to measure.
        Activities after starting the run should also be performed here."""
        
        # TODO: SSH Set CPU governor

        # Warmup machine
        output.console_log(f"Warming up machine for {self.warmup_time} seconds...")
        # TODO: SSH start fibonacci
        time.sleep(self.warmup_time)
        # TODO: SSH stop fibonacci

        # Cooldown a bit after warmup
        time.sleep(self.post_warmup_cooldown_time)
        output.console_log_OK("Warmup finished. Experiment is starting now!")

        # TODO: Prepare machine for measurement
        self.execution_command = "echo 'TODO: command here'"
        output.console_log_OK('Run configuration is successful.')

    def start_measurement(self, context: RunnerContext) -> None:
        """Perform any activity required for starting measurements."""
        output.console_log(f'Running command through energibridge with:\n{self.execution_command}')
        self.run_time = time.time()

        # TODO: SSH execute remote command

        output.console_log_OK('Run has successfuly started.')

        # TODO: Read EnergiBridge output
        
        self.run_time = time.time() - self.run_time
        output.console_log_OK(f'Run has completed in {self.run_time:.2f} seconds.')

    def interact(self, context: RunnerContext) -> None:
        """Perform any interaction with the running target system here, or block here until the target finishes."""
        pass

    def stop_measurement(self, context: RunnerContext) -> None:
        """Perform any activity here required for stopping measurements."""
        pass

    def stop_run(self, context: RunnerContext) -> None:
        """Perform any activity here required for stopping the run.
        Activities after stopping the run should also be performed here."""
        pass

    def populate_run_data(self, context: RunnerContext) -> Optional[Dict[str, SupportsStr]]:
        """Parse and process any measurement data here.
        You can also store the raw measurement data under `context.run_dir`
        Returns a dictionary with keys `self.run_table_model.data_columns` and their values populated"""

        output.console_log("Config.populate_run_data() called!")
        return None

    def after_experiment(self) -> None:
        """Perform any activity required after stopping the experiment here
        Invoked only once during the lifetime of the program."""
        # TODO: Cleanup resources
        pass

    # ================================ DO NOT ALTER BELOW THIS LINE ================================
    experiment_path:            Path             = None
