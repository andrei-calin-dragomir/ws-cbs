# ws-cbs

This repository contains the assignments of Web Services and Cloud-Based Systems as part of the Computer Science Msc degree.

## Setup

1. Initialize a python environment using:

```bash
python3 -m venv venv
```

2. Activate the python environment using:

```bash
source ./venv/bin/activate
```

3. Install the dependencies using:

```bash
pip install -r requirements.txt
```

## Running

1. Activate the python venv

```bash
source ./venv/bin/activate
```

2. Start the Authentication service

```bash
python3 login.py # (PORT : 5001)
```

3. Start the URL Shortner service

```bash
python3 app.py # (PORT : 5000)
```
