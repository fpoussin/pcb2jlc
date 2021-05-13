#!/usr/bin/python3
# -*- coding: utf-8 -*-

import re
from .sexp_parser import *

__author__ = "Zheng, Lei"
__copyright__ = "Copyright 2016, Zheng, Lei"
__license__ = "MIT"
__version__ = "1.0.0"
__email__ = "realthunder.dev@gmail.com"
__status__ = "Prototype"


class KicadPCB_gr_text(SexpParser):
    __slots__ = ()
    _default_bools = 'hide'


class KicadPCB_drill(SexpParser):
    __slots__ = ()
    _default_bools = 'oval'


class KicadPCB_pad(SexpParser):
    __slots__ = ()
    _parse1_drill = KicadPCB_drill

    def _parse1_layers(self,data):
        if not isinstance(data,list) or len(data)<3:
            raise ValueError('expects list of more than 2 element')
        return Sexp(data[1],data[2:],data[0])


class KicadPCB_module(SexpParser):
    __slots__ = ()
    _default_bools = 'locked'
    _parse_fp_text = KicadPCB_gr_text
    _parse_pad = KicadPCB_pad
    

class KicadPCB(SexpParser):

    # To make sure the following key exists, and is of type SexpList
    _module = ['fp_text',
               'fp_circle',
               'fp_arc',
               'pad',
               'model']

    _defaults =('net',
                ('net_class','add_net'),
                'dimension',
                'gr_text',
                'gr_line',
                'gr_circle',
                'gr_arc',
                'gr_curve',
                'segment',
                'arc',
                'via',
                ['module'] + _module,
                ['footprint'] + _module,
                ('zone',
                    'filled_polygon'))

    _alias_keys = {'footprint' : 'module'}
    _parse_module = KicadPCB_module
    _parse_footprint = KicadPCB_module
    _parse_gr_text = KicadPCB_gr_text

    def export(self, out, indent='  '):
        exportSexp(self,out,'',indent)

    def getError(self):
        return getSexpError(self)

    @staticmethod
    def load(filename):
        with open(filename,'r') as f:
            return KicadPCB(parseSexp(f.read()))


def get_components(path, layer, ignore=None):

    pcb = KicadPCB.load(path)
    for e in pcb.getError():
        print('Error: {}'.format(e))

    if layer == 'F.Cu':
        cpl_layer = 'top'
    elif layer == 'B.Cu':
        cpl_layer = 'bottom'
    else:
        print('Unkown layer')
        exit(1)

    compos = {}
    ignored_parts = []
    for footprint in pcb.footprint:
        if footprint.layer.replace('"', '') == layer:
            package = footprint[0].replace('"', '')
            pos = (footprint.at[0], -footprint.at[1])
            if len(footprint.at) == 3:
                rot = footprint.at[2]
            else:
                rot = 0
            lcsc_pn = ''
            for p in footprint.fp_text:
                for idx in [x for x in p if type(x) is int]:
                    if p[idx] == 'reference':
                        name = p[idx+1].replace('"', '')
                    elif p[idx] == 'value':
                        value = p[idx+1].replace('"', '')
            for p in footprint.property:
                p = [x.replace('"', '') for x in p]
                if 'LCSC' in p[0].upper():
                    lcsc_pn = p[1]
                elif 'ROT' in p[0].upper():
                    rot += int(p[1])
                    rot %= 360

            if (not lcsc_pn and ignore and re.match(ignore, name)) or re.match('^N[CBP]$', value):
                ignored_parts.append(name)
                continue

            # Trim packages
            if re.search(r'^Capacitor', package, re.M):
                package = package.split(':')[1].split('_')[1]
                desc = 'CAPACITOR'
            elif re.search(r'^LED', package, re.M):
                package = package.split(':')[1].split('_')[1]
                desc = 'LED'
            elif re.search(r'^Resistor', package, re.M):
                package = package.split(':')[1].split('_')[1]
                desc = 'RESISTOR'
                if re.search(r'\d+R(\s\d%|$)', value, re.M):
                    value = value.replace('R', 'Ω')
                elif re.search(r'\d+R\d+', value, re.M):
                    value = value.replace('R', '.')
            elif re.search(r'^Inductor.*L_.*\d{4}', package, re.M):
                m = re.search(r'^Inductor.*L_.*(\d{4})', package, re.M)
                if m:
                    package = m.group(1)
                desc = 'INDUCTOR'
            elif re.search(r'(Package_(TO|SO|BGA))', package, re.M):
                m = re.search(r'(([TH]?SO(T|IC)|BGA)-\d+)', package, re.M)
                if m:
                    package = m.group(1)
                else:
                    package = package.split(':')[1]
            elif re.search(r'Crystal', package, re.M):
                m = re.search(r'^Crystal.*(\d{4}|\d+\.?x\d+\.?\d+(mm)?)', package, re.M)
                if m:
                    package = m.group(1)
                else:
                    package = package.split(':')[1]
                desc = 'CRYSTAL'
            elif re.search(r'^D\d+', name, re.M):
                package = package.split(':')[1].split('_')[1]
                desc = 'DIODE'
            else:
                package = package.split(':')[1]

            if value and package:
                index = (str(value), package, lcsc_pn)

                if index not in compos:
                    compos[index] = {'parts': [], 'jlc':
                                    {'desc': '', 'basic': False, 'code': '', 'package': '', 'partName': ''}}
                compos[index]['parts'].append((name, cpl_layer, pos, str(rot)))

    return compos
