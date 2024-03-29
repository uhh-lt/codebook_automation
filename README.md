[![Build Status](https://travis-ci.com/uhh-lt/codebook_automation.svg?token=H1oV8zP1gyPKLnzBsppc&branch=main)](https://travis-ci.com/uhh-lt/codebook_automation)

# Codebook Automation

Modern NuxtJS WebApp build on top of FastAPI REST API to facilitate using state-of-the-art NLP models to predict Codebooks for CodeAnno.


## How to add models
Coming soon...

## How to run locally

_Assuming that your in the root folder of this repository_
```
pip install -r requirements.txt
CBA_API_DATA_ROOT=/tmp CBA_API_REDIS_HOST=localhost CBA_API_REDIS_PORT=6379 uvicorn main:app --host 0.0.0.0 --port 8081
```


## How to run with docker
**Make sure to set the correct environment variables in the .env file!**

```
docker-compose up -d
```
Docker images will be pulled from docker-hub if not available on the system.
To manually and locally build the image run:
```
docker build -t uhhlt/codebook_automation_api:latest .
docker build -t uhhlt/codebook_automation_app:latest ./cba_webapp/
```

## How to run tests

_Assuming that_
 - _PWD is root folder of this repository_
 - _config.backend.data_root_env_var == "CBA_API_DATA_ROOT"_
 - _clean redis instance is running on `localhost:6379`_

```
PYTHONPATH=${PWD} CBA_API_DATA_ROOT=/tmp CBA_API_REDIS_HOST=localhost CBA_API_REDIS_PORT=6379 pytest
```
