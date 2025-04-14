"""
Parse a NeXus definition yaml file into a Python-native representation (dict of lists of dicts) and then convert
it to a simplified yaml representation acceptable by nexusfile writing routines
"""

import re
from pathlib import Path
from typing import Union

import numpy as np
import yaml

NX_DTYPES = {
    "NX_FLOAT": "float32",
    "NX_INT": "int16",
    "NX_BOOLEAN": "bool",
    "NX_CHAR": "str",
    "NX_NUMBER": "float32",
    "NX_DATE_TIME": "datetime64",
}

RE_FIELD = r"^([\w]+)(?:\((NX_[A-Z_]+)\))?$"  # e.g. `start_time(NX_DATE_TIME)` or `start_type` -- splitting into name and type (None if type is unknown)  # noqa
RE_GROUP = r"^([\w]*)\((NX[^_][a-z_]+)\)([\w]*)$"  # e.g. efficiency(NXdata), (NXdata), or (NXdata)efficiency
RE_ATTRIBUTE = r"^\\{0,2}\@([\w]+)(?:\((NX_[A-Z_]+)\))?$"  # e.g. \@default(NX_TYPE), @default, or \\@default
RE_LINK = r"^([\w]+)\(link\)$"
RE_CHOICE = r"^([\w]+)\(choice\)$"


def deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def parse_nxdlyml_level(level: dict[str, Union[str, dict, list]]):
    """Parse a level in the NeXus nxdl.yml dictionary; split and collect groups, fields, attributes, and links

    Returns:
        A dictionary with (some of) the following keys: {groups, fields, attributes, links}, each containing a list
        of the specific NeXus objects of any other simple key-value pairs, where the values are strings.
    """
    groups = []
    fields = []
    attributes = []
    links = []
    result = {}
    for key, val in level.items():
        subdict = {}
        key = str(key)
        if match := re.match(RE_GROUP, key):
            # It is a Nexus Group
            subdict["nx_term"] = "group"
            nx_name_beg, nx_class, nx_name_end = match.groups()
            nx_name = nx_name_beg or nx_name_end or nx_class[2:]
            if nx_class == "NXobject" and nx_name.startswith("NX"):
                # Top level NX class definition in the yml file
                nx_class = nx_name
                nx_name = nx_name[2:]
            subdict["nx_name"] = nx_name
            subdict["nx_class"] = nx_class
            subdict.update(parse_nxdlyml_level(val or {}))
            groups.append(subdict)
            # print(key, match.groups(), f"{nx_name=}, {nx_class=}")
        elif match := re.match(RE_FIELD, key):
            # It is a NeXus Field
            nx_name, nx_type = match.groups()
            if (nx_type is None) and not isinstance(val, dict):
                # Simple descriptive field/"attribute", e.g. `doc`, `deprecated`, 'unit', etc
                result[key] = val
            elif nx_name == "enumeration":
                # It is a NeXus enumeration specified as a dictionary
                result[key] = list(val.keys())
            else:
                # A fully specified NeXus Field
                subdict["nx_term"] = "field"
                subdict["nx_name"] = nx_name
                subdict["nx_type"] = nx_type  # None if absent in the key string
                subdict.update(parse_nxdlyml_level(val or {}))
                fields.append(subdict)
                # print(key, match.groups(), f"{nx_name=}, {nx_type=}")
        elif match := re.match(RE_ATTRIBUTE, key):
            # It is a NeXus Attribute
            subdict["nx_term"] = "attribute"
            nx_name, nx_type = match.groups()
            subdict["nx_name"] = nx_name
            subdict["nx_type"] = nx_type
            subdict.update(parse_nxdlyml_level(val or {}))
            attributes.append(subdict)
            # print(key, match.groups(), f"{nx_name=}")
        elif match := re.match(RE_LINK, key):
            # It is a NeXus Link
            subdict["nx_term"] = "link"
            (nx_name,) = match.groups()
            subdict["nx_name"] = nx_name
            subdict["nx_type"] = None
            subdict.update(parse_nxdlyml_level(val or {}))
            links.append(subdict)
        elif match := re.match(RE_CHOICE, key):
            # It is a NeXus field/group with a choice of type
            subdict["nx_term"] = "field"
            (nx_name,) = match.groups()
            subdict["nx_name"] = nx_name
            sub = parse_nxdlyml_level(val or {})
            subdict["nx_class"] = " | ".join([v.get("nx_class") for v in sub["groups"]])
            subdict["doc"] = "\n".join(
                [f"{v.get('nx_class')}: {v.get('doc')}" for v in sub["groups"]]
            )
            groups.append(subdict)
        elif key.startswith("$"):
            # It is a user-specified value -- should be treated just as a string
            result[key] = val
            (nx_name,) = match.groups()
        else:
            raise ValueError(f"Unknown NeXus term: {key}")

    if groups:
        result["groups"] = groups
    if fields:
        result["fields"] = fields
    if attributes:
        result["attributes"] = attributes
    if links:
        result["links"] = links
    return result


def convert_nxyaml(
    fpath: Union[str, Path], reduce=True, sort=True, keep_docs=False
) -> dict:
    """Parse and convert an entire nxyaml file obtained from an official nxdl.xml file, and possibly modified with
    user-defined templated values.

    This function supports idempotency, i.e. it can be called multiple times to the converted (simplified) result.

    Returns:
        A dictionary in the simplified form ready to be suplied to nexus_writer.
    """

    with open(fpath) as f:
        fdict = yaml.safe_load(f)

    if category := fdict.pop("category", None):  # noqa: F841
        # This is an original uncoverted nxdl.yml file
        # TODO: Apply symbols, check type, deprecated, etc. For noew, just pop them out
        nx_type = fdict.pop("type")  # noqa: F841
        symbols = fdict.pop("symbols", {})  # noqa: F841
        deprecated = fdict.pop("deprecated", None)  # noqa: F841
        ignore_extra_fields = fdict.pop("ignoreExtraFields", True)  # noqa: F841
        ignore_extra_attributes = fdict.pop("ignoreExtraAttributes", True)  # noqa: F841
        ignore_extra_groups = fdict.pop("ignoreExtraGroups", True)  # noqa: F841
        doc = fdict.pop("doc", None)  # noqa: F841

        if len(fdict) != 1:
            print(fdict.keys())
            raise ValueError(
                "Unexpected or missing keys on the root level of nxdl.yml specification."
            )

        parsed = parse_nxdlyml_level(fdict)
        # TODO: convert fields? raise an error if there are any fields or attributes in the root?
        result = convert_groups(
            parsed.get("groups", []), root_dir=str(Path(fpath).parent), reduce=reduce
        )
    else:
        # This is an already converted simplified yml file
        result = resolve_nxdlrefs(fdict, root_dir=str(Path(fpath).parent))

    if reduce:
        result = reduce_converted(result)

    if sort:
        result = sort_converted(result)

    result = clean_docs(result, keep_docs=keep_docs)

    return result


def resolve_nxdlrefs(grp_dict: dict, root_dir: str = "./") -> dict:
    """Resolve references to other nxdl.yml and nxmeta.yml files"""

    if fname := grp_dict.pop("$nxdlref", None):
        # TODO: Handle multiple NXGroups, either passed as a list or in a single file
        refgrp = convert_nxyaml(fpath=Path(root_dir) / fname, reduce=False)
        if len(refgrp) != 1:
            raise ValueError(
                "A referenced nxdl file %s can only include a single NXGroup object",
                fname,
            )
        refgrp_name, refgrp_dict = list(refgrp.items())[0]
        if refgrp_dict["nxclass"] != grp_dict["nxclass"]:
            raise RuntimeError(
                "Incompatible NX class %s of a referenced object",
                refgrp_dict["nxclass"],
            )

        grp_dict = deep_update(refgrp_dict, grp_dict)

    # Apply recursively to all subgroups, if any
    for key, val in grp_dict.items():
        if isinstance(val, dict):
            grp_dict[key] = resolve_nxdlrefs(val, root_dir)

    return grp_dict


def convert_attributes(attributes: list) -> dict:
    result = {}
    for attr in attributes:
        attr_dict = {}
        if val := attr.get("$value"):
            attr_dict["value"] = val
        if dtype := NX_DTYPES.get(attr.get("type", attr.get("nx_type")), None):
            attr_dict["dtype"] = dtype
        if enum := attr.get("enumeration"):
            attr_dict["enumeration"] = enum
            attr_dict["dtype"] = attr_dict.get("dtype") or np.array(enum).dtype.name
            attr_dict["dtype"] = (
                "char" if attr_dict["dtype"].startswith("str") else attr_dict["dtype"]
            )
        if doc := attr.get("doc"):
            attr_dict["doc"] = doc

        result[attr["nx_name"]] = attr_dict or None

    return result


def convert_fields(fields: list, reduce=True) -> dict:
    result = {}
    for fld in fields:
        fld_dict = {"nxclass": "NXfield"}
        if val := fld.get("$value"):
            fld_dict["value"] = val
        elif reduce:
            continue

        if dtype := NX_DTYPES.get(fld.get("type", fld.get("nx_type")), None):
            fld_dict["dtype"] = dtype

        # Check if it is an enumeration
        if enum := fld.get("enumeration"):
            fld_dict["enumeration"] = enum
            fld_dict["dtype"] = fld_dict.get("dtype") or np.array(enum).dtype.name
            fld_dict["dtype"] = (
                "char" if fld_dict["dtype"].startswith("str") else fld_dict["dtype"]
            )

        # Add attributes (if any)
        atr_dict = {}
        if attrs := fld.get("attributes"):
            atr_dict.update(convert_attributes(attrs))
        if units := fld.get("$units"):
            atr_dict["units"] = units
        if atr_dict:
            fld_dict["attrs"] = atr_dict

        # Keep the docs / comments
        if doc := fld.get("doc"):
            fld_dict["doc"] = doc

        result[fld["nx_name"]] = fld_dict
    return result


def convert_links(links: list[dict]) -> dict:
    result = {}
    for lnk in links:
        # TODO: Do we need to normalize links `/NXentry/NXinstrument/NXetc` to `/entry/instrument/etc`?
        #       This is better to be done outside of this function as a final pass over the constructed metadata.
        target = lnk.get("$value", lnk.get("target"))
        lnk_dict = {"nxclass": "NXlink", "target": target}

        # Keep the docs / comments
        if doc := lnk.get("doc"):
            lnk_dict["doc"] = doc

        result[lnk["nx_name"]] = lnk_dict
    return result


def convert_groups(groups: list, root_dir: str = "./", reduce=True) -> dict:
    result = {}
    for grp in groups:
        grp_dict = {"nxclass": grp["nx_class"], "$nxdlref": grp.get("$nxdlref")}
        grp_dict = resolve_nxdlrefs(grp_dict, root_dir)

        # Add/overwrite (sub-groups)
        if sub_groups := grp.get("groups"):
            grp_dict = deep_update(
                grp_dict, convert_groups(sub_groups, root_dir, reduce=reduce)
            )

        # Add/overwrite fields (if any)
        if fields := grp.get("fields"):
            grp_dict = deep_update(grp_dict, convert_fields(fields, reduce=reduce))

        # Add/overwrite attributes (if any)
        if attrs := convert_attributes(grp.get("attributes", [])):
            grp_dict["attrs"] = deep_update(grp_dict.get("attrs", {}), attrs)

        # Add/overwrite links (if any)
        if links := grp.get("links"):
            grp_dict = deep_update(grp_dict, convert_links(links))

        # Keep the docs / comments
        if doc := grp.get("doc"):
            grp_dict["doc"] = doc

        result[grp["nx_name"]] = grp_dict
    return result


def reduce_converted(dinput: dict) -> dict:
    """Remove trivial definitions from a converted nxyaml representation"""
    result = {}

    for key, val in dinput.items():
        if isinstance(val, dict):
            if reduced := reduce_converted(val):
                result[key] = reduced
        else:
            result[key] = val

    if set(result.keys()) == {"nxclass"}:
        return {}

    return result


def clean_docs(dinput: dict, keep_docs=False) -> dict:
    """Reformat or remove all doctrings in a converted nxyaml representation"""
    result = {}

    for key, val in dinput.items():
        if isinstance(val, dict):
            result[key] = clean_docs(val, keep_docs)
        else:
            if key == "doc":
                if keep_docs:
                    result[key] = val.replace("\n", " ").strip()
            else:
                result[key] = val

    return result


def sort_converted(dinput: dict) -> dict:
    """(Attempt to) sort the keys in the converted dictionary"""

    for key, val in dinput.items():
        if isinstance(val, dict):
            dinput[key] = sort_converted(val)

    first_keys = [k for k in ["nxclass"] if k in dinput.keys()]
    last_keys = [k for k in ["attrs"] if k in dinput.keys()]
    string_keys = [
        k
        for k, v in dinput.items()
        if not isinstance(v, dict) and (k not in first_keys + last_keys)
    ]
    group_keys = [
        k
        for k, v in dinput.items()
        if (k not in first_keys + last_keys + string_keys)
        and (v.get("nxclass") != "NXfield")
    ]
    other_keys = [
        k
        for k in dinput.keys()
        if k not in first_keys + last_keys + string_keys + group_keys
    ]
    sorted_keys = (
        first_keys
        + sorted(string_keys)
        + sorted(group_keys)
        + sorted(other_keys)
        + last_keys
    )

    return {k: dinput[k] for k in sorted_keys}
