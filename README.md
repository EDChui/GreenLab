# On the Impact of Frequency Scaling on the Energy Efficiency of Microservices

This repository contains the replication package for the study "On the Impact of Frequency Scaling on the Energy Efficiency of Microservices".

# Pre-requirements

Please make sure you have the following software installed on your systems.

## Testbed Machine

- Docker
- Docker compose
- [EnergiBridge](https://github.com/tdurieux/EnergiBridge)
- [scaphandre](https://github.com/hubblo-org/scaphandre)

## Orchestration Machine

- Python 3.12+

# Running the Experiment

## Testbed Machine

```sh
git clone --recursive https://github.com/EDChui/GreenLab.git
cd GreenLab
source ./setup_testbed.sh
```

## Orchestration Machine

```sh
git clone --recursive https://github.com/EDChui/GreenLab.git
cd GreenLab
source ./setup_orc.sh
nano .env # (Optional) Edit .env to set the correct parameters
python experiment-runner/experiment-runner orc/RunnerConfig.py
```

# Teardown

## Testbed Machine

```sh
./teardown_testbed.sh
```

## Orchestration Machine

```sh
deactivate
```
