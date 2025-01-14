# Copyright © Simphony Project Contributors
# Licensed under the terms of the MIT License
# (see simphony/__init__.py for details)

import os
from enum import Enum
from typing import Any, Dict

from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor

from simphony.tools import str2float


# The "dynamic list" isn't it's own class, but a regular
# list that uses these functions to perform operations.
def _dlist_insert(dlist, index, element):
    try:
        dlist[index] = element
        return dlist
    except IndexError:
        new = [None] * (index + 1)
        for i, v in enumerate(dlist):
            new[i] = v
        new[index] = element
        return new


# Typically instantiations of some kind
class SpiceObjects(Enum):
    DIRECTIVE = 1
    CIRCUIT = 2


# Typically actions of some kind
class Directives(Enum):
    ONA = 1
    INCLUDE = 2
    SUBCKT = 3


# ==============================================================================
# Grammar and NodeVisitor for *main.spi files generated by SiEPIC-Tools (KLayout)
# ==============================================================================

spi_grammar = Grammar(
    r"""
    file        = (directive / circuit / comment / emptyline)*
    directive   = (ona / include / subckt)

    ona         = ".ona" ws+ pair* newline (options newline)*
    options     = ws? "+" ws* pair*

    include     = ".INCLUDE" ws+ quoted newline

    subckt      = ".subckt" ws+ header param* component* footer
    header      = word ws+ (word ws*)* newline
    param       = ".param" ws+ pair newline
    component   = ws* word ws+ defunct? None? ports word ws+ pair* newline
    ports       = ((external / internal) ws?)+
    external    = ~r"((<defunct>[^\s]+)|([-\w$]+(detector|laser)[\d]?))"
    internal    = ~r"N\$[-\d]+"
    footer      = ".ends" ws+ word ws? newline
    defunct     = "<defunct>" word ws+
    None        = "None" ws+

    circuit     = word ws+ ports word ws* pair* newline

    pair        = key equal value ws*
    key         = list / word
    value       = quoted / number / word
    list        = word lpar number rpar

    quoted      = ~r'"[^\"]+"'
    number      = ~r"([-+]?[0-9]+[.]?[0-9]*((?:[eE][-+]?[0-9]+)|[a-zA-Z])?)"
    word        = ~r"[-\w,$<>]+"

    comment     = ~r"\*.*"
    equal       = ws? "=" ws?
    lpar        = "("
    rpar        = ")"
    ws          = ~r"(?:(?![\n\r])\s)+"
    emptyline   = ws* newline
    newline     = ~r"\n"
    """
)


class SpiceVisitor(NodeVisitor):
    """NodeVisitor object for internal program use only.

    If you're using this in one of your scripts, you're probably using
    Simphony wrong.
    """

    def visit_file(self, node, visited_children):
        """
        Grammar:
        file        = (directive / circuit / comment / emptyline)*

        Returns
        -------
        contents : dict
            Dictionary of all items within the spice file with the following keys:
            [`circuits`, `subcircuits`, `analyses`].
        """
        contents = {
            "circuits": [],
            "subcircuits": [],
            "analyses": [],
        }

        def sort_items(container, typ, payload):
            if type(typ) == Directives:
                if typ == Directives.SUBCKT:
                    container["subcircuits"].append(payload)
                elif typ == Directives.ONA:
                    container["analyses"].append(payload)
                elif typ == Directives.INCLUDE:
                    # container['circuits'].update(payload['circuits'])
                    container["circuits"] += payload["circuits"]
                    container["subcircuits"] += payload["subcircuits"]
                    # for a in payload['analyses']:
                    #     container['analyses'].append(a)
                    container["analyses"] += payload["analyses"]
            elif type(typ) == SpiceObjects:
                if typ == SpiceObjects.CIRCUIT:
                    container["circuits"].append(payload)

        items = [item[0] for item in visited_children if item[0] is not None]
        for item in items:
            typ, payload = item
            sort_items(contents, typ, payload)
        return contents

    def visit_directive(self, node, visited_children):
        # directive   = (ona / include / subckt)
        return visited_children[0]

    def visit_ona(self, node, visited_children):
        """
        Grammar:
        ona         = ".ona" ws+ pair* newline (options newline)*

        Returns
        -------
        typ : Directives.ONA
            Enum type for identification of the result.
        def : dict
            Dictionary of all items within the subcircuit with the following keys:
            [`definition`, `params`].
            `definition` is also a dictionary, with the following keys:
            [`input_unit`, `input_parameter`]
            `params` is also a dictionary, with the following keys:
            [`minimum_loss`, `analysis_type`, `multithreading`,
             `number_of_threads`, `orthogonal_identifier`, `start`, `stop`,
             `number_of_points`, `input`, `output`]
        """
        _, _, parameters, _, options = visited_children
        options = [opt[0] for opt in options]
        ona = {
            "definition": {},
            "params": {},
        }
        for param in parameters:
            ona["definition"][param["name"]] = param["value"]
        for optionset in options:
            for option in optionset:
                if "order" in option:
                    # Text file uses 1-based indexing, so express as
                    # option['order'] - 1
                    try:
                        l = ona["params"][option["name"]]
                        ona["params"][option["name"]] = _dlist_insert(
                            l, option["order"] - 1, option["value"]
                        )
                    except KeyError:
                        ona["params"][option["name"]] = _dlist_insert(
                            [], option["order"] - 1, option["value"]
                        )
                else:
                    ona["params"][option["name"]] = option["value"]
        return Directives.ONA, ona

    def visit_options(self, node, visited_children):
        # options     = ws? "+" ws* pair*
        _, _, _, pair = visited_children
        return pair

    def visit_include(self, node, visited_children):
        # include     = ".INCLUDE" ws+ quoted newline
        _, _, quoted, _ = visited_children
        return Directives.INCLUDE, load_spi_from_file(quoted)

    def visit_subckt(self, node, visited_children):
        """
        Grammar:
        subckt      = ".subckt" ws+ header param* component* footer

        Returns
        -------
        typ : Directives.SUBCKT
            Enum type for identification of the result.
        def : dict
            Dictionary of all items within the subcircuit with the following keys:
            [`name`, `ports`, `components`, `params`]
        """
        _, _, header, params, components, footer = visited_children
        if header["name"] != footer["name"]:
            raise ValueError(
                "Invalid netlist (name in header and footer does not match)."
            )
        name = header["name"]
        ports = header["externals"]
        params = {p["name"]: p["value"] for p in params}
        return (
            Directives.SUBCKT,
            {"name": name, "ports": ports, "components": components, "params": params},
        )

    def visit_header(self, node, visited_children):
        # header      = word ws+ (word ws*)* newline
        name, _, externals, _ = visited_children
        externals = [ext[0] for ext in externals]
        return {"name": name, "externals": externals}

    def visit_param(self, node, visited_children):
        # param       = ".param" ws+ pair newline
        _, _, param, _ = visited_children
        return param

    def visit_component(self, node, visited_children):
        """
        Grammar:
        component   = ws* word ws+ defunct? None? ports word ws+ pair* newline

        Returns
        -------
        def : dict
            Dictionary of all items within the component with the following keys:
            [`name`, `model`, `ports`, `params`]
        """
        _, name, _, _, _, ports, model, _, params, _ = visited_children
        params = {p["name"]: p["value"] for p in params}
        return {"name": name, "model": model, "ports": ports, "params": params}

    def visit_ports(self, node, visited_children):
        # ports       = ((external / internal) ws?)+
        ports = []
        for port in visited_children:
            ports.append(port[0][0])
        return ports

    def visit_external(self, node, visited_children):
        # external    = ~r"([-\w]+(detector|laser)[\d]?)"
        return node.text

    def visit_internal(self, node, visited_children):
        # internal    = ~r"N\$[-\d]+"
        return node.text

    def visit_footer(self, node, visited_children):
        # footer      = ".ends" ws+ word ws? newline
        _, _, name, *_ = visited_children
        return {"name": name}

    def visit_circuit(self, node, visited_children):
        """
        Grammar:
        circuit     = word ws+ ports word ws* pair* newline

        Developer's Note: We may consider changing the grammar for
        `subcircuits` so that it can pick up multiple.

        Returns
        -------
        typ : SpiceObjects.CIRCUIT
            Enum type for identification of the result.
        def : dict
            Dictionary of all items defining the circuit with the following keys:
            [`name`, `ports`, `subcircuits`, `params`]
        """
        cname, _, ports, subcircuits, _, params, _ = visited_children
        return (
            SpiceObjects.CIRCUIT,
            {
                "name": cname,
                "ports": ports,
                "subcircuits": subcircuits,
                "params": params,
            },
        )

    def visit_pair(self, node, visited_children):
        # pair        = key equal value ws?
        key, _, value, _ = visited_children
        pair = {}
        pair.update(key)
        pair.update(value)
        return pair

    def visit_key(self, node, visited_children):
        # key         = list / word
        name = visited_children[0]
        if type(name) == dict:
            return {"name": name["name"], "order": name["order"]}
        else:
            return {"name": name}

    def visit_value(self, node, visited_children):
        # value       = quoted / number / word
        value = visited_children
        return {"value": value[0]}

    def visit_list(self, node, visited_children):
        # list        = word lpar number rpar
        (
            name,
            _,
            pos,
            _,
        ) = visited_children
        return {"name": name, "order": int(pos)}

    def visit_quoted(self, node, visited_children):
        # quoted      = ~r'"[^\"]+"'
        return node.text[1:-1]

    def visit_number(self, node, visited_children):
        # number      = ~r"([-+]?[0-9]+[.]?[0-9]*((?:[eE][-+]?[0-9]+)|[a-zA-Z])?)"
        return str2float(node.text)

    def visit_word(self, node, visited_children):
        # word        = ~r"[-\w,$]+"
        return node.text

    def visit_comment(self, node, visited_children):
        # comment     = ~r"\*.*"
        pass

    def visit_equal(self, node, visited_children):
        # equal       = ws? "=" ws?
        pass

    def visit_lpar(self, node, visited_children):
        # lpar        = "("
        pass

    def visit_rpar(self, node, visited_children):
        # rpar        = ")"
        pass

    def visit_ws(self, node, visited_children):
        # ws          = ~r"(?:(?![\n\r])\s)+"
        pass

    def visit_emptyline(self, node, visited_children):
        # emptyline   = ws* newline
        pass

    def visit_newline(self, node, visited_children):
        # newline     = ~r"\n"
        pass

    def generic_visit(self, node, visited_children):
        """The generic visit method."""
        return visited_children or node


def load_spi_from_file(path: str) -> Dict[str, Any]:
    """Parses a spice file and returns the data as a dictionary in a form
    accepted by `build_circuit()`.

    Parameters
    ----------
    path : str
        Path to the spice file to be parsed.
    """
    cwd = os.getcwd()
    path, filename = os.path.split(path)
    if path != "":
        os.chdir(path)

    with open(filename, "r") as f:
        res = load_spi_from_string(f.read())
        f.close()

    os.chdir(cwd)
    return res


def load_spi_from_string(string: str) -> Dict[str, Any]:
    """Parses a spice string and returns the data as a dictionary in a form
    accepted by `build_circuit()`.

    Parameters
    ----------
    string :
        The string to be parsed.
    """
    return SpiceVisitor().visit(spi_grammar.parse(string))
