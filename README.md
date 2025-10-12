# On the Impact of Frequency Scaling on the Energy Efficiency of Microservices

This repository contains the replication package for the study "On the Impact of Frequency Scaling on the Energy Efficiency of Microservices", conducted as part of the Green Lab 2025/2026 course at Vrije Universiteit Amsterdam.

The study investigates how the [six Linux CPU governors](https://www.kernel.org/doc/Documentation/cpu-freq/governors.txt) influence energy efficiency and performance of microservice-based applications under different workload types. The goal is to provide empirical evidence and practical insights into energy–performance trade-offs in microservice deployments.

# Experiment Architecture Overview

![TODO: Architecture Diagram](architecture_diagram.png)

The experiment uses two machines:

- **Testbed Machine**: Hosts the microservice application ([DeathStarBench – Social Network](https://github.com/delimitrou/DeathStarBench/tree/master/socialNetwork)) and runs the energy measurement tools.
- **Orchestration Machine**: This machine orchestrates the experiment, generating workloads, managing testbed machine's CPU governors, collecting data, and storing results.

# Software and Tool Requirements

Please make sure you have the following software installed on your systems.

## Testbed Machine

- Docker & Docker compose
- [EnergiBridge](https://github.com/tdurieux/EnergiBridge)
- [Scaphandre](https://github.com/hubblo-org/scaphandre)
- Python 3.12+

## Orchestration Machine

- Python 3.9+

# Setting Up the Experiment

## Testbed Machine

```sh
git clone https://github.com/EDChui/GreenLab.git
cd GreenLab
source ./setup_testbed.sh
```

## Orchestration Machine

```sh
git clone --recursive https://github.com/EDChui/GreenLab.git
cd GreenLab
source ./setup_orc.sh
nano .env # (Optional) Edit .env to set the correct parameters
```

# Running the Experiment

## Orchestration Machine

```sh
python experiment-runner/experiment-runner orc/RunnerConfig.py
```

The results will be stored in the `orc/experiments/cpu_governor_on_social_network/run_table.csv`.

# Teardown

## Testbed Machine

```sh
./teardown_testbed.sh
```

## Orchestration Machine

```sh
deactivate
```
