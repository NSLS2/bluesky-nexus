# bluesky-nexus
WIP for writing NeXus metadata into Bluesky documents.

### Istallation

This repo uses [pixi](https://pixi.sh/dev/) to manage the Python dependencies and run basic commands. Runing the following commands will install all necessary dependencies in the local pixi environment, clone the oficial NeXus definitions into a subfolder, and synchronize `.ipynb` and `.py` versions of Jupyter notebooks with [Jupytext](https://jupytext.readthedocs.io/en/latest/).

```bash
pixi install
pixi run clone
pixi sync
```

### Converting NeXus .nxdl.xml definitions to .yml

The code in `/src/conversion` allows one to convert any official NeXus definition or application file from its original `.nxdl.xml` format into a `.yml` file formatted to be compatible with `nexus_writer` -- a convenient package for saving NeXus data files. The conversion is a two-step process: first, the `.nxdl.xml` files are converted into an equivalent `.nxdl.yml` representation using a third party tool [nyaml](https://pypi.org/project/nyaml/0.0.8/). The resulting definitions are parsed and normalized with classes and data types becoming values at corresponding keys; this also allows one to declare additional key-value pairs, such as `value`, `reference`, etc. if desired. This process is illustrated in the notebook `/notebooks/xml-conversion.ipynb` and can be run for all files in batch or each file individually.

The intermediate `.nxdl.yml` and the resulting `nexus_writer`-compatible `.yml` definitions allow one to reference external files and so build a nested representation for a complex NeXus schema form its simpler components (details TBD).
