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

Please make sure you have the following software installed on the testbed machine for DeathStarBench social network application. (https://github.com/delimitrou/DeathStarBench/tree/master/socialNetwork)

- Docker
- Docker-compose
- Python 3.5+ (with asyncio and aiohttp)
- libssl-dev (apt-get install libssl-dev)
- libz-dev (apt-get install libz-dev)
- luarocks (apt-get install luarocks)
- luasocket (luarocks install luasocket)

Please make sure you have created and activated the virtual environment for installing the required python dependencies, and setting up the testbed machine.

```sh
python3 -m venv venv
source venv/bin/activate
pip install asyncio aiohttp
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
