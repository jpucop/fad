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

## Add python dep to requirements.txt

```sh
pip freeze > requirements.txt
```

## AWS Tags

ucop:group FinApps
ucop:application alert-notification-api
ucop:environment DEV
ucop:createdBy jkirton@ucop.edu

## FinApps AWS Accounts List

```sh
[default]
region = us-west-2
output = json
# jp aws
[524006177124_jp]
# finapps-poc
[403230261384_rw]
# finapps-dev
[872008829419_rw]
# finapps-prod
[836626524524_rw]
# fis-dev
[999860890886_rw]
# fis-prod
[702425941516_rw]
# fdw-dev
[613074250484_rw]
# fdw-prod
[280181752709_rw]
# mf-dev
[627602613099_rw]
# mf-prod
[261032852138_rw]
# ppers-poc
[586982855061_full]
# ppersdev
[030333339593_rw]
# ppersprod
[503759735250_rw]
# ucop-setdev
[469462193597_rw]
```
