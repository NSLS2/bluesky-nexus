# ---
# jupyter:
#   jupytext:
#     formats: py:percent,ipynb
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.0
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# ### Dowload and convert all definitions

# %% jupyter={"outputs_hidden": true}
# Convert and save all nxdl.xml -> nxdl.yml files
# %load_ext autoreload
# %autoreload 2
import os
from pathlib import Path

from nyaml.nxdl2nyaml import Nxdl2yaml

directories = ["base_classes", "applications", "contributed_definitions"]

for dirname in directories:
    with os.scandir(Path("../definitions") / dirname) as it:
        for entry in it:
            if (
                not entry.name.startswith(".")
                and entry.is_file()
                and entry.name.endswith("nxdl.xml")
            ):
                ### Convert nxml to yaml
                xml_fpath = entry.path
                yml_fpath = (
                    Path("../definitions_yml") / dirname / f"{Path(xml_fpath).stem}.yml"
                )
                yml_fpath.parent.mkdir(parents=True, exist_ok=True)
                converter = Nxdl2yaml([], [])
                converter.print_yml(xml_fpath, yml_fpath, verbose=False)

import yaml

# %%
# Convert nxdl.yml to nexusformat-compatible yml files
from bluesky_nexus.convert_nexus import convert_nxyaml

for dirname in directories:
    with os.scandir(Path("../definitions_yml") / dirname) as it:
        for entry in it:
            if (
                not entry.name.startswith(".")
                and entry.is_file()
                and entry.name.endswith("nxdl.yml")
            ):
                print(entry.name)
                ### Convert to nexusformat yml
                res_fpath = (
                    Path("../converted_yml")
                    / dirname
                    / f"{entry.name.split('.')[0]}.yml"
                )
                res_fpath.parent.mkdir(parents=True, exist_ok=True)

                converted = convert_nxyaml(entry.path, reduce=False, keep_docs=True)
                with open(res_fpath, "w") as _file:
                    yaml.dump(converted, _file, sort_keys=False)

# %% [markdown]
# ### Download and convert a single NeXus definition

# %%
import requests

suffix = "base_classes/NXsource.nxdl.xml"

### Download the most recent nxdl.xml file
url = f"https://raw.githubusercontent.com/nexusformat/definitions/main/{suffix}"
xml_file = f"../definitions_xml/{suffix}"
Path(xml_file).parent.mkdir(parents=True, exist_ok=True)

response = requests.get(url)
with open(xml_file, "w") as f:
    f.write(response.text)

### Convert nxdl.xml to nxdl.yml
yml_file = (
    Path("../definitions_yml") / Path(suffix).parent / f"{Path(xml_file).stem}.yml"
)
yml_file.parent.mkdir(parents=True, exist_ok=True)
converter = Nxdl2yaml([], [])
converter.print_yml(xml_file, yml_file, verbose=True)

### Convert nxdl.yml to nexusformat-compatible yaml
converted = convert_nxyaml(yml_file, reduce=False, keep_docs=True)

res_fpath = (
    Path("../converted_yml") / Path(suffix).parent / f"{Path(xml_file).stem}.yml"
)
res_fpath.parent.mkdir(parents=True, exist_ok=True)
with open(res_fpath, "w") as _file:
    yaml.dump(converted, _file, sort_keys=False)
