# netlist.py
#
# Dependencies:
#     - numpy
#         Required for cascading s-matrices together.
#     - jsons
#         Similar to GSON in Java, serializes and deserializes custom models.
#         Required to convert the ObjectModelNetlist to a file that can be saved 
#         and read later.
#         API: https://jsons.readthedocs.io/en/latest/index.html
#     - copy
#         Some objects are deep copied during circuit matrix cascading.
#
# This file contains everything related to netlist generation and modeling.

# from simphony.components import BaseComponent, create_component_by_name

import jsons
import json
import copy
import numpy as np
from typing import List

from simphony.core import ComponentModel, ComponentInstance
from simphony.core import connect as rf

class Netlist:
    """Represents a netlist.

    Has component_set, a set, and instance_list, a list.
    """

    def __init__(self, components: List[ComponentInstance]=None):

        self.components = [] if components is None else components

    def add_component(self, component: ComponentInstance):
        self.components.append(component)

    def get_external_components(self):
        return [component for component in self.components if (any(int(x) < 0 for x in component.nets))]

    def toJSON(self) -> str:
        return jsons.dump(self, verbose=True, strip_privates=True)

    @property
    def net_count(self):
        """Returns the number of internal nets in the Netlist.

        Finds the number of internal nets by iterating through the components
        and finding the max net number. Since internal net id's are assigned 
        beginning from '0', the total number of nets is always max(nets) + 1.

        Returns
        -------
        int
            The total count of internal nets.
        """
        # https://stackoverflow.com/a/29244327/11530613
        nets = [net for sublist in [comp.nets for comp in self.components] for net in sublist]
        return max(nets) + 1

    @staticmethod
    def save(filename, netlist):
        with open(filename, 'w') as outfile:
            json.dump(netlist.toJSON(), outfile, indent=2)

    @staticmethod
    def load(filename):
        obj = None
        with open(filename) as jsonfile:
            try:
                data = json.load(jsonfile)
                obj = jsons.load(data)
                obj.components = jsons.load(obj.components)
                if obj is not None:
                    return obj
                else:
                    raise RuntimeError("Netlist could not load successfully.")
            except:
                raise RuntimeError("Netlist could not load successfully.")


class CircuitConnector:
    def __init__(self, netlist=None):
        self.netlist = netlist

    # def _match_ports(net_id: str, component_list: list) -> list:
    #     """
    #     Finds the components connected together by the specified net_id (string) in
    #     a list of components provided by the caller (even if the component is 
    #     connected to itself).

    #     Parameters
    #     ----------
    #     net_id : str
    #         The net id or name to which the components being searched for are 
    #         connected.
    #     component_list : list
    #         The complete list of components to be searched.

    #     Returns
    #     -------
    #     [comp1, netidx1, comp2, netidx2]
    #         A list (length 4) of integers with the following meanings:
    #         - comp1: Index of the first component in the list with a matching 
    #             net id.
    #         - netidx1: Index of the net in the ordered net list of 'comp1' 
    #             (corresponds to its column or row in the s-parameter matrix).
    #         - comp2: Index of the second component in the list with a matching 
    #             net id.
    #         - netidx1: Index of the net in the ordered net list of 'comp2' 
    #             (corresponds to its column or row in the s-parameter matrix).
    #     """
    #     filtered_comps = [component for component in component_list if net_id in component.nets]
    #     comp_idx = [component_list.index(component) for component in filtered_comps]
    #     net_idx = []
    #     for comp in filtered_comps:
    #         net_idx += [i for i, x in enumerate(comp.nets) if x == net_id]
    #     if len(comp_idx) == 1:
    #         comp_idx += comp_idx
        
    #     return [comp_idx[0], net_idx[0], comp_idx[1], net_idx[1]]

    # def connect_circuit(self) -> (ComponentSimulation, list):
    #     """
    #     Connects the s-matrices of a photonic circuit given its ObjectModelNetlist
    #     and returns a single 'ComponentSimulation' object containing the frequency
    #     array, the assembled s-matrix, and a list of the external nets (strings of
    #     negative numbers).

    #     Returns
    #     -------
    #     ComponentSimulation
    #         After the circuit has been fully connected, the result is a single 
    #         ComponentSimulation with fields f (frequency), s (s-matrix), and nets 
    #         (external ports: negative numbers, as strings).
    #     list
    #         A list of ComponentModel objects that contain an external port.
    #     """
    #     if netlist.net_count == 0:
    #         return

    #     component_list = [ComponentSimulation(component) for component in netlist.component_list]
    #     for n in range(0, netlist.net_count + 1):
    #         ca, ia, cb, ib = _match_ports(str(n), component_list)

    #         #if pin occurances are in the same Cell
    #         if ca == cb:
    #             component_list[ca].s = rf.innerconnect_s(component_list[ca].s, ia, ib)
    #             del component_list[ca].nets[ia]
    #             if ia < ib:
    #                 del component_list[ca].nets[ib-1]
    #             else:
    #                 del component_list[ca].nets[ib]

    #         #if pin occurances are in different Cells
    #         else:
    #             combination = ComponentSimulation()
    #             combination.f = component_list[0].f
    #             combination.s = rf.connect_s(component_list[ca].s, ia, component_list[cb].s, ib)
    #             del component_list[ca].nets[ia]
    #             del component_list[cb].nets[ib]
    #             combination.nets = component_list[ca].nets + component_list[cb].nets
    #             del component_list[ca]
    #             if ca < cb:
    #                 del component_list[cb-1]
    #             else:
    #                 del component_list[cb]
    #             component_list.append(combination)

    #     return component_list[0], netlist.get_external_components()


    # def strToSci(number) -> float:
    #     """
    #     Converts string representations of numbers written with abbreviated 
    #     prefixes into a float with the proper exponent (e.g. '3u' -> 3e-6).

    #     Parameters
    #     ----------
    #     number : str
    #         The number to be converted, represented as a string.
        
    #     Returns
    #     -------
    #     float
    #         The string converted to a float.
    #     """
    #     ex = number[-1]
    #     base = float(number[:-1])
    #     if(ex == 'm'):
    #         return base * 1e-3
    #     elif(ex == 'u'):
    #         return base * 1e-6
    #     elif(ex == 'n'):
    #         return base * 1e-9
    #     else:
    #         return float(number(base) + ex)

    # def get_sparameters(netlist: ObjectModelNetlist):
    #     """
    #     Gets the s-parameters matrix from a passed in ObjectModelNetlist by 
    #     connecting all components.

    #     Parameters
    #     ----------
    #     netlist: ObjectModelNetlist
    #         The netlist to be connected and have parameters extracted from.

    #     Returns
    #     -------
    #     s, f, externals, edge_components: np.array, np.array, list(str)
    #         A tuple in the following order: 
    #         ([s-matrix], [frequency array], [external port list], [edge components])
    #         - s-matrix: The s-parameter matrix of the combined component.
    #         - frequency array: The corresponding frequency array, indexed the same
    #             as the s-matrix.
    #         - external port list: Strings of negative numbers representing the 
    #             ports of the combined component. They are indexed in the same order
    #             as the columns/rows of the s-matrix.
    #         - edge components: list of ComponentModel objects, which are the external
    #             components.
    #     """
    #     combined, edge_components = connect_circuit(netlist)
    #     f = combined.f
    #     s = combined.s
    #     externals = combined.nets
    #     return (s, f, externals, edge_components)

    class ComponentSimulation:
        """
        This class is a simplified version of a ComponentModel in that it only contains
        an ordered list of nets, the frequency array, and the s-parameter matrix. 
        It can be initialized with or without a ComponentModel model, allowing its 
        attributes to be set after object creation.

        Attributes
        ----------
        nets : list(str)
            An ordered list of the nets connected to the ComponentModel
        f : np.array
            A numpy array of the frequency values in its simulation.
        s : np.array
            A numpy array of the s-parameter matrix for the given frequency range.
        """
        nets: list
        f: np.array
        s: np.array

        def __init__(self, component=None):
            """
            Instantiates an object from a ComponentModel if provided; empty, if not.

            Parameters
            ----------
            component : ComponentModel, optional
                A component to initialize the data members of the object.
            """
            if component:
                self.nets = copy.deepcopy(component.nets)
                self.f, self.s = component.get_s_parameters()


def create_component_by_name(comp):
    return None

class ObjectModelNetlist:
    """
    The Parser class reads a netlist generated by the SiEPIC toolbox and uses 
    various classes which inherit from 'models.components.ComponentModel' to create 
    an object based model of a photonic circuit. 
    
    Each derived class is connected to a component model in 'models' that 
    exposes a 'get_s_params' method with its appropriate arguments to the 
    derived model. These s_params are the s-matrices of the component, which 
    are then used to simulate the circuit's transmission behavior.

    Attributes
    ----------
    component_list : list
        A list of objects derived from 'models.components.ComponentModel' 
        representing the photonic circuit.
    net_count : int
        A counter keeping track of the total number of nets in the circuit 
        (0-indexed).
    """

    def __init__(self):
        self.component_list = []
        self.instance_list = []
        self.net_count = 0

    def parse_file(self, filepath: str) -> list:
        """Converts a netlist to an object model of the circuit.

        Parses through the netlist (given a filename) to identify components 
        and organize them into objects. Objects are connected with their data 
        models, allowing them to retrieve any available parameters.

        Parameters
        ----------
        filepath : str
            The name of the file to be parsed.

        Returns
        -------
        component_list : list
            A list of all components found in the netlist, with their 
            accompanying properties and values.
        """
        with open(filepath) as fid:
            text = fid.read()
            return self.parse_text(text)

    def parse_text(self, text: str) -> list:
        """
        Parses the string format of the netlist. Instead of requiring a file, 
        string representations of netlists can also be converted into an object
        model.

        Parameters
        ----------
        text : str
            The text of the netlist.
        
        Returns
        -------
        component_list : list
            A list of all components found in the netlist, with their 
            accompanying properties and values.
        """
        lines = text.splitlines()
        for line in lines:
                elements = line.split()
                if len(elements) > 0:
                    if (".ends" in elements[0]):
                        break
                    elif ("." in elements[0]) or ("*" in elements[0]):
                        continue
                    else:
                        self._parse_line(elements)
        return self.component_list

    def _parse_line(self, line_elements: list):
        """ Parses a line from the netlist, already split into individual 
        elements, and converts it into a new ComponentModel object.

        Reads the elements on a line of the netlist (already delimited before 
        passed to _parse_line) and creates the appropriate object. Appends the 
        newly created object to the Parser's component_list.
        
        Parameters
        ----------
        line_elements : list
            A list of all the elements on a line (already split by some 
            delimiter).
        """

        # TODO: Consider having each component parse its own line, rather than
        # needing to add more case statements if new parameters show up.
        component = None
        nets = []
        for item in line_elements[1:]:
            if "N$" in item:
                net = str(item).replace("N$", '')
                nets.append(net)
                if int(net) > self.net_count:
                    self.net_count = int(net)
                continue
            elif component is None:
                component = create_component_by_name(item)
            elif "lay_x=" in item:
                component.lay_x = float(str(item).replace("lay_x=", ''))
            elif "lay_y=" in item:
                component.lay_y = float(str(item).replace("lay_y=", ''))
            elif "radius=" in item:
                component.radius = float(str(item).replace("radius=", ''))
            elif "wg_length=" in item:
                lenth = str(item).replace("wg_length=", '')
                component.length = strToSci(lenth)
            elif "wg_width=" in item:
                width = str(item).replace("wg_width=", '')
                # Width needs to be stored in microns (um)
                component.width = strToSci(width)*1e6
            elif "points=" in item:
                # The regex, in case you ever need it: /(\[[\d]+[\,][\d]+\])/g
                points = str(item).replace("points=", '')
                points = points.replace("\"[[", '')
                points = points.replace("]]\"", '')
                point_list = points.split('],[')
                for point in point_list:
                    out = point.split(',')
                    component.points.append((float(out[0]), float(out[1])))
        component.nets = nets
        self.component_list.append(component)

    def add_component(self, component):
        self.component_list.append(component)

    def get_external_components(self):
        return [component for component in self.component_list if (any(int(x) < 0 for x in component.nets))]

    def toJSON(self) -> str:
        return jsons.dump(self, verbose=True, strip_privates=True)

    @staticmethod
    def save(filename, netlist):
        with open(filename, 'w') as outfile:
            json.dump(netlist.toJSON(), outfile, indent=2)

    @staticmethod
    def load(filename):
        obj = None
        with open(filename) as jsonfile:
            try:
                data = json.load(jsonfile)
                obj = jsons.load(data)
                obj.component_list = jsons.load(obj.component_list)
                if obj is not None:
                    return obj
                else:
                    raise RuntimeError("Netlist could not load successfully.")
            except:
                raise RuntimeError("Netlist could not load successfully.")
            
        

