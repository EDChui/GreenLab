# On the Impact of Frequency Scaling on the Energy Efficiency of Microservices

This repository contains the replication package for the study "On the Impact of Frequency Scaling on the Energy Efficiency of Microservices".

# Pre-requirements

Please make sure you have the following software installed on your system.

- Docker
- Docker-compose
- Python
- [EnergiBridge](https://github.com/tdurieux/EnergiBridge)

# Installation

## Orchestration Machine

```sh
git clone --recursive https://github.com/EDChui/GreenLab.git
./setup_orc.sh
python experiment-runner/experiment-runner orc/RunnerConfig.py
```
