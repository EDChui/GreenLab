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
import math
import re
import numpy as np
import json

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
TARGET_SERVICES = ["media_service", "home_timeline_service", "compose_post_service"]

class EnergibridgeOutputParser:
    target_columns = ['TOTAL_MEMORY', 'TOTAL_SWAP', 'USED_MEMORY', 'USED_SWAP'] + [f'CPU_USAGE_{i}' for i in range(CPU_COUNT)] + [f'CPU_FREQUENCY_{i}' for i in range(CPU_COUNT)]

    delta_target_columns = [
        'DRAM_ENERGY (J)', 'PACKAGE_ENERGY (J)', 'PP0_ENERGY (J)'
    ]

    energy_trapz_columns = [
        "PACKAGE_POWER_energy_joules", "DRAM_POWER_energy_joules", "PP0_POWER_energy_joules",
    ]

    @classmethod
    def data_columns(cls) -> list:
        return cls.target_columns + cls.delta_target_columns + cls.energy_trapz_columns

    @classmethod
    def parse_output(cls, file_path) -> dict:
        """
        Parses the energibridge CSV output file to compute average values for specified metrics.
        This code is adapted from: https://github.com/S2-group/python-compilers-rep-pkg
        """
        # Read the file into a pandas DataFrame
        df = pd.read_csv(file_path).apply(pd.to_numeric, errors='coerce')

        # Calculate column-wise averages, ignoring NaN values and deltas from start of experiment to finish
        averages = df[cls.target_columns].mean().to_dict()
        
        # Account and mitigate potential RAPL overflow during metric collection
        deltas = {}
        for column in cls.delta_target_columns:
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

        # Compute total energy from power time series
        power_cols = [c for c in df.columns if "(W)" in c]
        energy_trapz = {}
        if power_cols and "TIMESTAMP" in df.columns:
            times = pd.to_datetime(df["TIMESTAMP"]).astype(np.int64) / 1e9  # convert ns → seconds
            for col in power_cols:
                P = df[col].to_numpy(float)
                # Integrate power over time (Joules)
                E = float(np.trapz(P, times))
                energy_trapz[col.replace("(W)", "_energy_joules")] = round(E, 2)

        return dict(averages.items() | deltas.items() | energy_trapz.items())

class ScaphandreOutputParser:
    @classmethod
    def data_columns(cls) -> list:
        return [f"{service}_energy_joules" for service in TARGET_SERVICES]

    @staticmethod
    def _iso_to_epoch(ts: str) -> float:
        # "2025-10-06T13:15:24Z" -> seconds since epoch
        from datetime import datetime, timezone
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()

    @classmethod
    def parse_output(cls, file_path: str) -> dict:
        rows = []

        with open(file_path, "r") as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    data = [data]
            except json.JSONDecodeError:
                # Handle line-delimited JSON entries
                data = [json.loads(line) for line in f if line.strip()]

        # Flattening
        for entry in data:
            t = cls._iso_to_epoch(entry.get("timestamp"))
            for sensor in entry.get("sensors", []):
                for c in sensor.get("containers", []):
                    rows.append({
                        "t": t,
                        "container": c.get("container_name"),
                        "power_w": c.get("power_watts", 0.0),
                        "energy_j": c.get("energy_joules", 0.0),
                    })

        if not rows:
            return {f"{s}_energy_joules": None for s in cls.target_services}

        df = pd.DataFrame(rows).dropna(subset=["name"])
        df["name_norm"] = df["name"].str.replace("-", "_")

        result = {}
        for service in cls.target_services:
            # match e.g. "media_service" to "media-service"
            m = df[df["name_norm"] == service]
            if m.empty:
                result[f"{service}_energy_joules"] = None
                continue

            t = m["t"].to_numpy(dtype=float)

            if m["p"].notna().any():
                # integrate power directly (J = ∫ P dt)
                p = m["p"].fillna(method="ffill").fillna(0.0).to_numpy(dtype=float)
                E = float(np.trapz(p, t))
            else:
                # derive power from energy series if available:
                # if energy is per-interval, trapz over (e, t) == sum(e) when dt=1
                e = m["e"].fillna(method="ffill").fillna(0.0).to_numpy(dtype=float)
                # assume e is interval energy; approximate power = e/dt on intervals; integrate back to be robust
                if len(e) >= 2:
                    dt = np.diff(t)
                    p = np.diff(e) / dt  # if e is cumulative; if e is interval, this becomes noisy but small
                    # If p contains NaNs (constant e), fall back to sum of interval energies:
                    if np.isnan(p).any() or np.allclose(p, 0):
                        E = float(np.sum(e))
                    else:
                        E = float(np.trapz(p, t[1:]))
                else:
                    E = float(np.sum(e))

            result[f"{service}_energy_joules"] = round(E, 2)

        return result

class DockerStatsOutputParser:
    @staticmethod
    def _mem_to_bytes(mem_usage_str: str) -> float:
        """
        Convert the 'used' part of docker's MemUsage to bytes.
        Example: '824.3MiB / 2.00GiB' -> 824.3 * 1024**2
        """
        if not isinstance(mem_usage_str, str):
            return math.nan
        # Only the "used" side before the slash
        used = mem_usage_str.split('/', 1)[0].strip()
        m = re.match(r'^\s*([0-9]+(?:\.[0-9]+)?)\s*([KMGT]?i?B)\s*$', used, re.IGNORECASE)
        if not m:
            parts = used.split()
            if len(parts) != 2:
                return math.nan
            val_str, unit = parts[0].replace(',', '.'), parts[1]
            try:
                val = float(val_str)
            except Exception:
                return math.nan
            unit = unit.upper()
        else:
            val = float(m.group(1))
            unit = m.group(2).upper()

        mult = {
            'B': 1,
            'KB': 1000,
            'MB': 1000**2,
            'GB': 1000**3,
            'TB': 1000**4,
            'KIB': 1024,
            'MIB': 1024**2,
            'GIB': 1024**3,
            'TIB': 1024**4,
        }
        return val * mult.get(unit, 1)

    @staticmethod
    def _cpu_to_float(cpu_str: str) -> float:
        """Convert '5.23%' -> 5.23"""
        if not isinstance(cpu_str, str):
            return math.nan
        s = cpu_str.strip().rstrip('%').replace(',', '.')
        try:
            return float(s)
        except Exception:
            return math.nan

    @staticmethod
    def _p95(series: pd.Series) -> float:
        x = pd.to_numeric(series, errors='coerce').dropna()
        return float(np.percentile(x, 95)) if not x.empty else math.nan

    @classmethod
    def data_columns(cls):
        base_metrics = [
            "cpu_usage_mean", "cpu_usage_p95", "cpu_usage_max", "cpu_usage_samples",
            "mem_usage_mean", "mem_usage_p95", "mem_usage_max", "mem_usage_samples"
        ]
        return [f"{service}_{metric}" for service in TARGET_SERVICES for metric in base_metrics]

    @classmethod
    def parse_output(cls, file_path: str) -> dict:
        """
        Parse CSV with header: ts,Container,CPU%,MemUsage
        Aggregate per service type (strip numeric suffixes).
        """
        df = pd.read_csv(file_path)

        expected = {'ts', 'Container', 'CPU%', 'MemUsage'}
        if not expected.issubset(df.columns):
            raise ValueError(
                f"Expected header {sorted(expected)} in {file_path}, found {list(df.columns)}"
            )

        # Parse numeric columns
        df['cpu_pct']   = df['CPU%'].map(cls._cpu_to_float)
        df['mem_bytes'] = df['MemUsage'].map(cls._mem_to_bytes)

        # Remove suffix like -1, -2, ...
        df['Service'] = df['Container'].str.replace(r'-\d+$', '', regex=True)

        include = [f"socialnetwork-{service.replace('_', '-')}" for service in TARGET_SERVICES]
        df = df[df['Service'].isin(include)]

        if df.empty:
            return {}

        # Aggregate by Service (not by instance)
        grp = df.groupby('Service', as_index=True)
        metrics = {
            "cpu_usage_mean":    grp['cpu_pct'].mean().to_dict(),
            "cpu_usage_p95":     grp['cpu_pct'].apply(cls._p95).to_dict(),
            "cpu_usage_max":     grp['cpu_pct'].max().to_dict(),
            "cpu_usage_samples": grp['cpu_pct'].count().astype(int).to_dict(),
            "mem_usage_mean":    grp['mem_bytes'].mean().to_dict(),
            "mem_usage_p95":     grp['mem_bytes'].apply(cls._p95).to_dict(),
            "mem_usage_max":     grp['mem_bytes'].max().to_dict(),
            "mem_usage_samples": grp['mem_bytes'].count().astype(int).to_dict(),
        }
        result = {}
        for metric, service_map in metrics.items():
            for service, val in service_map.items():
                short_service = service.replace("socialnetwork-", "").replace("-", "_")
                result[f"{short_service}_{metric}"] = (
                    None if (isinstance(val, float) and math.isnan(val)) else val / CPU_COUNT
                )

        return result

class LocustStatsOutputParser:
    @classmethod
    def data_columns(cls) -> list:
        return ['throughput', 'latency_p50', 'latency_p90', 'latency_p95', 'latency_p99'] 

    @classmethod
    def parse_output(cls, locust_stats) -> dict:
        return {
            "throughput": locust_stats.num_requests / locust_stats.total_response_time,
            "latency_p50": locust_stats.get_response_time_percentile(0.50),
            "latency_p90": locust_stats.get_response_time_percentile(0.90),
            "latency_p95": locust_stats.get_response_time_percentile(0.95),
            "latency_p99": locust_stats.get_response_time_percentile(0.99)
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

        self.testbed_project_directory = "~/GreenLab/testbed"
        self.external_run_dir = f'{self.testbed_project_directory}/experiments'
        self.energibridge_csv_filename = "energibridge.csv"
        self.scaphandre_json_filename = "scaphandre_energy.json"
        self.docker_stats_csv_filename = "docker_stats.csv"

        self.energibridge_metric_capturing_interval : int = 1000                        # milliseconds
        self.warmup_time                            : int = 60 if not DEBUG_MODE else 5 # seconds
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
            factor1 = FactorModel("cpu_governor", ['performance'])
            # factor2 = FactorModel("load_type", ['media', 'home_timeline', 'compose_post'])
            # factor3 = FactorModel("load_level", ['debug'])
            factor2 = FactorModel("load_type", ['compose_post'])
            factor3 = FactorModel("load_level", ['debug'])
        # TODO: Data columns for measurement results of run_table.csv
        energybridge_data_columns = EnergibridgeOutputParser.data_columns()
        scaphandre_data_columns = ScaphandreOutputParser.data_columns()
        docker_stats_data_columns = DockerStatsOutputParser.data_columns()
        client_metric_data_columns = LocustStatsOutputParser.data_columns()  
        run_table_data_columns = ["run_time"] + energybridge_data_columns + scaphandre_data_columns + docker_stats_data_columns + client_metric_data_columns
        self.run_table_model = RunTableModel(
            factors=[factor1, factor2, factor3],
            repetitions=5 if not DEBUG_MODE else 1,
            shuffle=True if not DEBUG_MODE else False,
            data_columns=run_table_data_columns
        )
        return self.run_table_model

    def before_experiment(self) -> None:
        """Perform any activity required before starting the experiment here
        Invoked only once during the lifetime of the program."""
        ssh = ExternalMachineAPI()
        ssh.execute_remote_command(f"mkdir -p {self.external_run_dir}")
        output.console_log_OK(f"Created experiment directory at {self.external_run_dir} on remote machine.")
        del ssh

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
        # Server-level energy measurement with EnergiBridge
        sleep_duration_seconds = 300 # Long enough for the whole workload generation to finish
        self.energibridge_command = f"energibridge --interval {self.energibridge_metric_capturing_interval} --summary --output {self.external_run_dir}/{self.energibridge_csv_filename} --command-output {self.external_run_dir}/output.txt sleep {sleep_duration_seconds}"
        # TODO: Container-level energy measurement tools with scaphandre, interval: 2s
        self.scaphandre_start = (
            f"bash -lc 'DIR={self.external_run_dir}; FILE={self.scaphandre_json_filename}; "
            f"mkdir -p \"$DIR\"; sudo scaphandre json -t 2 -n 0 -f \"$DIR/$FILE\" & echo $! > \"$DIR/scaphandre.pid\"'"
        )
        self.scaphandre_stop = (
            f"bash -lc 'DIR={self.external_run_dir}; "
            f"[ -f \"$DIR/scaphandre.pid\" ] && sudo kill -SIGINT $(cat \"$DIR/scaphandre.pid\") && rm -f \"$DIR/scaphandre.pid\" || true'"
        )

        # Commands for collecting container-level CPU and memory usage on host machine: samples per second
        self.docker_stats_start = (
            f"bash -lc 'DIR={self.external_run_dir}; FILE={self.docker_stats_csv_filename}; INT=1; "
            f"mkdir -p \"$DIR\"; echo \"ts,Container,CPU%,MemUsage\" > \"$DIR/$FILE\"; "
            f"( while :; do docker stats --no-stream --format \"{{{{.Name}}}},{{{{.CPUPerc}}}},{{{{.MemUsage}}}}\" "
            f"| awk -v ts=\"$(date +%s)\" -F, '\\''{{print ts\",\"$0}}'\\'' >> \"$DIR/$FILE\"; "
            f"sleep \"$INT\"; done ) & echo $! > \"$DIR/docker_stats.pid\"'")
        self.docker_stats_stop = (
            f"bash -lc 'DIR={self.external_run_dir}; "
            f"[ -f \"$DIR/docker_stats.pid\" ] && kill -TERM \"$(cat \"$DIR/docker_stats.pid\")\" && rm -f \"$DIR/docker_stats.pid\" || true'")
        output.console_log_OK('Run configuration is successful.')

    def start_measurement(self, context: RunnerContext) -> None:
        """Perform any activity required for starting measurements."""
        # Separate SSH client for energibridge to avoid blocking
        ssh_energibridge = ExternalMachineAPI()
        ssh_scaphandre = ExternalMachineAPI()
        ssh_docker_stats = ExternalMachineAPI()
        workloadGenerator = WorkloadGenerator()
        self.run_time = time.time()

        # SSH execute measurement commands
        ssh_energibridge.execute_remote_command(f"{self.energibridge_command} & pid=$!; echo $pid")
        energibridge_pid = ssh_energibridge.stdout.readline().strip()
        output.console_log_OK(f"EnergiBridge started with PID {energibridge_pid}")
        ssh_scaphandre.execute_remote_command(self.scaphandre_start)
        output.console_log_OK("Scaphandre started for container-level energy measurement.")
        ssh_docker_stats.execute_remote_command(self.docker_stats_start)
        output.console_log_OK("Docker stats collection started.")

        # Fire workload with Locust
        load_type = LoadType[context.execute_run['load_type'].upper()]
        load_level = LoadLevel[context.execute_run['load_level'].upper()]
        output.console_log(f"Firing workload: {load_type.name} at {load_level.name} level...")
        # Locust performance metrics
        self.workload_result = workloadGenerator.fire_load(load_type, load_level)

        output.console_log_OK('Run has successfully started.')

        # Kill energibridge after workload is done
        ssh_energibridge.execute_remote_command(f"kill {energibridge_pid}")
        output.console_log_OK("EnergiBridge stopped.")

        # Stop Scaphandre
        ssh_scaphandre.execute_remote_command(self.scaphandre_stop)
        output.console_log_OK("Scaphandre stopped.")

        # Stop docker stats collection
        ssh_docker_stats.execute_remote_command(self.docker_stats_stop)
        output.console_log_OK("Docker stats collection stopped.")
        
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

        ssh = ExternalMachineAPI()
        # Copy output files from remote to local
        remote_energibridge_csv = f"{self.external_run_dir}/{self.energibridge_csv_filename}"
        remote_docker_stats_csv = f"{self.external_run_dir}/{self.docker_stats_csv_filename}"
        remote_scaphandre_json = f"{self.external_run_dir}/{self.scaphandre_json_filename}"
        local_energibridge_csv = context.run_dir / self.energibridge_csv_filename
        local_docker_stats_csv = context.run_dir / self.docker_stats_csv_filename
        local_scaphandre_json = context.run_dir / self.scaphandre_json_filename
        
        ssh.copy_file_from_remote(remote_energibridge_csv, str(local_energibridge_csv))
        ssh.copy_file_from_remote(remote_docker_stats_csv, str(local_docker_stats_csv))
        ssh.copy_file_from_remote(remote_scaphandre_json, str(local_scaphandre_json))
        
        # Parse the output to populate run data
        energibridge_data = EnergibridgeOutputParser.parse_output(local_energibridge_csv)
        docker_stats_data = DockerStatsOutputParser.parse_output(local_docker_stats_csv)
        scaphandre_data = ScaphandreOutputParser.parse_output(local_scaphandre_json)
        locust_stats_data = LocustStatsOutputParser.parse_output(self.workload_result)

        return {
            "run_time": self.run_time, 
            **energibridge_data, 
            **docker_stats_data, 
            **scaphandre_data,
            **locust_stats_data
        }

    def after_experiment(self) -> None:
        """Perform any activity required after stopping the experiment here
        Invoked only once during the lifetime of the program."""
        ssh = ExternalMachineAPI()
        
        # TODO: Cleanup resources
        output.console_log("Cleaning up resources...")
        output.console_log_OK("Resources cleaned up.")

        # Remove measurements files from remote machine
        output.console_log("Removing measurement files from remote machine...")
        ssh.execute_remote_command(f"rm -rf {self.external_run_dir}")
        output.console_log_OK("Measurement files removed from remote machine.")

        pass

    # ================================ DO NOT ALTER BELOW THIS LINE ================================
    experiment_path:            Path             = None
