# FAD - FastAPI AWS Dashboard

## Overview

Financial Applications UCOP group aggregate dashboard widget.

## Setup

1. Navigate to the **backend** dir and make that the cwd for fastapi app startup.

2. Run the command line project script resetenv.sh|bat

```sh
resetenv.sh
```

```bat
resetenv.bat
```

## Features

```sh
tree -I "venv|.git|.gitignore|.gitmodules"
```

## re-generate requirements.txt and requirements-test.txt

pip-compile requirements.in
pip-compile requirements-test.in

pip-sync

## pydantic - generate models.py 

Generate the pydantic types from the datamodel codegen tool of theirs using app.config-template.json and the other sourcing model files (mostly json file types).

```sh
datamodel-codegen --input ~/dev/fad/backend/model/app.config-template.json --input-file-type json --output ~/dev/fad/backend/app/models.py

datamodel-codegen --input ~/dev/fad/backend/model/app_config_schema.json --input-file-type jsonschema --output ~/dev/fad/backend/app/models.py

```