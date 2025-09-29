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
import pandas as pd

# Add the current directory to Python path to allow local imports
import sys
from pathlib import Path
config_dir = str(Path(__file__).parent.resolve())
if config_dir not in sys.path:
    sys.path.insert(0, config_dir)
from ExternalMachineAPI import ExternalMachineAPI
from WorkloadGenerator import WorkloadGenerator, LoadType, LoadLevel

# Load environment variables from .env file
load_dotenv()

DEBUG_MODE = getenv("DEBUG_MODE", "False").lower() in ("true", "1", "t")
CPU_COUNT = 32
RAPL_OVERFLOW_VALUE = 262143.328850 # Found via `cat /sys/class/powercap/intel-rapl:0/max_energy_range_uj` in uJ

class OutputParser:
    def parse_energibridge_output(file_path):
        """
        Parses the energibridge CSV output file to compute average values for specified metrics.
        This code is adapted from: https://github.com/S2-group/python-compilers-rep-pkg
        """
        # Define target columns
        target_columns = [
            'TOTAL_MEMORY', 'TOTAL_SWAP', 'USED_MEMORY', 'USED_SWAP'] + [f'CPU_USAGE_{i}' for i in range(CPU_COUNT)] + [f'CPU_FREQUENCY_{i}' for i in range(CPU_COUNT)]

        delta_target_columns = [
            'DRAM_ENERGY (J)', 'PACKAGE_ENERGY (J)', 'PP0_ENERGY (J)'
        ]

        # Read the file into a pandas DataFrame
        df = pd.read_csv(file_path).apply(pd.to_numeric, errors='coerce')

        # Calculate column-wise averages, ignoring NaN values and deltas from start of experiment to finish
        averages = df[target_columns].mean().to_dict()
        deltas = {}

        # Account and mitigate potential RAPL overflow during metric collection
        for column in delta_target_columns:
            overflow_counter = 0
            # Iterate and adjust values in the array
            column_data = df[column].to_numpy()
            for i in range(1, len(column_data)):
                # Motivation behind Section IV-B from https://arxiv.org/pdf/2401.15985
                if column_data[i] < column_data[i - 1]:
                    output.console_log_WARNING(f"RAPL Overflow found:\nReading {i-1}: {column_data[i-1]}\nReading {i}: {column_data[i]}")
                    overflow_counter += 1
                    column_data[i:] += overflow_counter * RAPL_OVERFLOW_VALUE
            deltas[column] = column_data[-1] - column_data[0]

        return dict(averages.items() | deltas.items())

    def parse_docker_stats_output(file_path):
        """
        Parses the docker stats output file to compute average CPU and memory usage.
        """
        df = pd.read_csv(file_path, names=['Container', 'CPU%', 'MemUsage'])
        
        # Clean and convert CPU% to float
        avg_cpu = df['CPU%'].str.rstrip('%').astype(float).mean()
        
        # Clean and convert MemUsage to float (in MiB)
        avg_mem = df["MemUsage"].str.split('/').str[0].str.rstrip('MiB').astype(float).mean()
        
        return {
            'avg_cpu': avg_cpu,
            'avg_mem': avg_mem
        }

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

        self.testbed_project_directory = "~/GreenLab/testbed/"

        self.energibridge_metric_capturing_interval : int = 200                         # milliseconds
        self.warmup_time                            : int = 90 if not DEBUG_MODE else 5 # seconds
        self.post_warmup_cooldown_time              : int = 30 if not DEBUG_MODE else 1 # seconds

        output.console_log("Custom config loaded")
        output.console_log("Current environment: " + ("DEBUG" if DEBUG_MODE else "PRODUCTION"))

    def create_run_table_model(self) -> RunTableModel:
        """Create and return the run_table model here. A run_table is a List (rows) of tuples (columns),
        representing each run performed"""
        if not DEBUG_MODE:
            factor1 = FactorModel("cpu_governor", ['performance', 'powersave', 'userspace', 'ondemand', 'conservative', 'schedutil'])
            factor2 = FactorModel("load_type", ['media', 'home_timeline', 'compose_post'])
            factor3 = FactorModel("load_level", ['low', 'medium', 'high'])
        else:
            factor1 = FactorModel("cpu_governor", ['performance', 'powersave'])
            factor2 = FactorModel("load_type", ['media', 'home_timeline', 'compose_post'])
            factor3 = FactorModel("load_level", ['low'])
        self.run_table_model = RunTableModel(
            factors=[factor1, factor2, factor3],
            repetitions=5 if not DEBUG_MODE else 1,
            shuffle=True if not DEBUG_MODE else False,
            data_columns=['avg_cpu', 'avg_mem']     # TODO: Data columns for measurement results
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
        self.workload_result = None

    def start_run(self, context: RunnerContext) -> None:
        """Perform any activity required for starting the run here.
        For example, starting the target system to measure.
        Activities after starting the run should also be performed here."""
        ssh = ExternalMachineAPI()

        # SSH Set CPU governor
        cpu_governor = context.execute_run['cpu_governor']
        ssh.execute_remote_command(f"sudo set-governor.sh {cpu_governor}")
        output.console_log_OK(f"Set CPU governor to {cpu_governor}")

        # Warmup machine
        output.console_log(f"Warming up machine for {self.warmup_time} seconds...")
        # SSH start warmup task
        ssh.execute_remote_command(f"python3 {self.testbed_project_directory}/warmup.py 1000 & pid=$!; echo $pid")
        warmup_pid = ssh.stdout.readline().strip()
        time.sleep(self.warmup_time)
        # SSH stop warmup task
        ssh.execute_remote_command(f"kill {warmup_pid}")
        # Cooldown a bit after warmup
        time.sleep(self.post_warmup_cooldown_time)
        del ssh
        output.console_log_OK("Warmup finished. Experiment is starting now!")
        
        # Prepare commands for measurement
        self.external_run_dir = f'{self.testbed_project_directory}/experiments/'
        # Server-level energy measurement with EnergiBridge
        self.energibridge_csv_filename = "energibridge.csv"
        sleep_duration_seconds = 300 # Long enough for the whole workload generation to finish
        self.energibridge_command = f"energibridge --interval {self.energibridge_metric_capturing_interval} --summary --output {self.external_run_dir}/{self.energibridge_csv_filename} --command-output {self.external_run_dir}/output.txt sleep {sleep_duration_seconds}"
        # TODO: Pending response from TA. Container-level energy measurement tools

        # TODO: Docker stats command for collecting container-level CPU and memory usage
        self.docker_stats_csv_filename = "docker_stats.csv"
        self.docker_stats_command = f"docker stats --no-stream --format \"{{{{.Container}}}},{{{{.CPUPerc}}}},{{{{.MemUsage}}}}\" > {self.external_run_dir}/{self.docker_stats_csv_filename}"
        output.console_log_OK('Run configuration is successful.')

    def start_measurement(self, context: RunnerContext) -> None:
        """Perform any activity required for starting measurements."""
        ssh = ExternalMachineAPI()
        workloadGenerator = WorkloadGenerator()
        self.run_time = time.time()

        # SSH execute measurement commands
        ssh.execute_remote_command(f"{self.energibridge_command} & pid=$!; echo $pid")
        energibridge_pid = ssh.stdout.readline().strip()
        output.console_log_OK(f"EnergiBridge started with PID {energibridge_pid}")
        ssh.execute_remote_command(self.docker_stats_command)
        output.console_log_OK("Docker stats collected.")

        # Fire workload with Locust
        load_type = LoadType[context.execute_run['load_type'].upper()]
        load_level = LoadLevel[context.execute_run['load_level'].upper()]
        output.console_log(f"Firing workload: {load_type.name} at {load_level.name} level...")
        self.workload_result = workloadGenerator.fire_load(load_type, load_level)

        output.console_log_OK('Run has successfully started.')

        # Kill energibridge after workload is done
        ssh.execute_remote_command(f"kill {energibridge_pid}")
        output.console_log_OK("EnergiBridge stopped.")
        
        self.run_time = time.time() - self.run_time
        output.console_log_OK(f'Run has completed in {self.run_time:.2f} seconds.')

        # Collect Locust performance metrics
        locust_stats = self.workload_result
        self.client_metrics = {
            "throughput": locust_stats.num_requests / locust_stats.total_response_time,
            "latency_p50": locust_stats.get_response_time_percentile(0.50),
            "latency_p90": locust_stats.get_response_time_percentile(0.90),
            "latency_p95": locust_stats.get_response_time_percentile(0.95),
            "latency_p99": locust_stats.get_response_time_percentile(0.99)
        }

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

        ssh = ExternalMachineAPI()
        # TODO: Copy output files from remote to local
        remote_energibridge_csv = f"{self.external_run_dir}/{self.energibridge_csv_filename}"
        remote_docker_stats_csv = f"{self.external_run_dir}/{self.docker_stats_csv_filename}"
        local_energibridge_csv = context.run_dir / self.energibridge_csv_filename
        local_docker_stats_csv = context.run_dir / self.docker_stats_csv_filename
        
        ssh.copy_remote_to_local(remote_energibridge_csv, str(local_energibridge_csv))
        output.console_log_OK(f"Copied {remote_energibridge_csv} to {local_energibridge_csv}")
        ssh.copy_remote_to_local(remote_docker_stats_csv, str(local_docker_stats_csv))
        output.console_log_OK(f"Copied {remote_docker_stats_csv} to {local_docker_stats_csv}")
        
        # TODO: Parse the output to populate run data
        energibridge_data = OutputParser.parse_energibridge_output(local_energibridge_csv)
        docker_stats_data = OutputParser.parse_docker_stats_output(local_docker_stats_csv)

        return {**energibridge_data, **docker_stats_data, **self.client_metrics}

    def after_experiment(self) -> None:
        """Perform any activity required after stopping the experiment here
        Invoked only once during the lifetime of the program."""
        ssh = ExternalMachineAPI()
        
        # TODO: Cleanup resources
        output.console_log("Cleaning up resources...")
        output.console_log_OK("Resources cleaned up.")

        # TODO: Remove measurements files from remote machine
        output.console_log("Removing measurement files from remote machine...")
        ssh.execute_remote_command(f"rm -f {self.external_run_dir}/{self.energibridge_csv_filename}")
        ssh.execute_remote_command(f"rm -f {self.external_run_dir}/{self.docker_stats_csv_filename}")
        output.console_log_OK("Measurement files removed from remote machine.")

        pass

    # ================================ DO NOT ALTER BELOW THIS LINE ================================
    experiment_path:            Path             = None
