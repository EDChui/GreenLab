# On the Impact of Frequency Scaling on the Energy Efficiency of Microservices

This repository contains the replication package for the study "On the Impact of Frequency Scaling on the Energy Efficiency of Microservices".

# Pre-requirements

Please make sure you have the following software installed on your system.

- Docker
- Docker-compose
- Python
- [EnergiBridge](https://github.com/tdurieux/EnergiBridge)

# Installation

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
