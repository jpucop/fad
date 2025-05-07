# FAD - FastAPI AWS Dashboard

Financial Applications UCOP group aggregate dashboard widget.

## backend

```sh
resetenv.sh
```

```sh
tree -I "venv|.git|.gitignore|.gitmodules"
```

```sh
pip freeze > requirements.txt
```

### requirements\[-test\].txt

```sh
pip-compile requirements.in
pip-compile requirements-test.in

pip-sync
```

### pydantic - generate models for app

By convention, have a **generate.py** file that creates all pydantic model definitions for the runtime of this web app 
models/init/ 1st level sub-dirs are to be the org and group business wise isolated in their model structures.

## frontend

use npm and vite to optimze js/css files since tailwind and svgs and largeness comes with it
we only take what is needed and gzip it basically 

## AWS Tags

- ucop:group FinApps
- ucop:application fad
- ucop:environment dev
- ucop:createdBy jkirton@ucop.edu

## FinApps AWS Accounts List

```sh
[default]
region = us-west-2
output = json
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
