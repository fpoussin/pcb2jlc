#!/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
from kiutils.board import Board

def get_components(path, layer, ignore=None):

    pcb = Board().from_file(path)

    if layer == 'top':
        kicad_layer = 'F.Cu'
    elif layer == 'bottom':
        kicad_layer = 'B.Cu'
    else:
        print('Unknown layer:', layer)
        exit(1)

    compos = {}
    ignored_parts = []
    for footprint in pcb.footprints:
        # if not hasattr(footprint, 'property'): continue
        value = ''
        name = ''

        if footprint.layer == kicad_layer:
            library = footprint.libraryNickname
            package = footprint.entryName
            if layer == 'top':
                pos = (footprint.position.X, -footprint.position.Y)
            else:
                pos = (-footprint.position.X, -footprint.position.Y)
            rot = footprint.position.angle or 0.0
            lcsc_pn = ''
            for k, v in footprint.properties.items():
                  if k == 'Reference':
                      name = v.upper()
                  elif k == 'Value':
                      value = v.upper()
                  elif 'LCSC' in k:
                      lcsc_pn = v.upper()
                  elif 'ROT' in k:
                      rot += float(v)

            rot += 180.0
            rot %= 360.0

            if layer == 'bottom':
                rot = -rot

            if (not lcsc_pn and ignore and re.match(ignore, name)) \
            or re.match('^N[CBP]$', value) \
            or footprint.attributes.excludeFromBom or footprint.attributes.doNotPopulate:
                ignored_parts.append(name)
                continue

            # Trim packages
            if re.search(r'^Capacitor', library, re.M):
                package = package.split('_')[1]
                desc = 'CAPACITOR'
            elif re.search(r'^LED', library, re.M):
                package = package.split('_')[1]
                desc = 'LED'
            elif re.search(r'^Resistor', library, re.M):
                package = package.split('_')[1]
                desc = 'RESISTOR'
                if re.search(r'\d+R(\s\d%|$)', value, re.M):
                    value = value.replace('R', 'Ω')
                elif re.search(r'\d+R\d+', value, re.M):
                    value = value.replace('R', '.')
                if not value.endswith('Ω') and not value.endswith('%'):
                    value += 'Ω'
            elif re.search(r'^Inductor', library, re.M):
                m = re.search(r'L_(\d{4})_\d+', package, re.M)
                if m:
                    package = m.group(1)
                m = re.search(r'L_(\w+)+-(\d{4})', package, re.M)
                if m:
                    package = m.group(2)
                desc = 'INDUCTOR'
            elif re.search(r'(Package_(TO|SO(N)?|BGA|DFN_QFN|QFP))', library, re.M):
                m = re.search(r'(\w+-\d+)', package, re.M)
                if m:
                    package = m.group(1)
            elif re.search(r'Crystal', library, re.M):
                m = re.search(r'^Crystal.*(\d{4}|\d+\.?x\d+\.?\d+(mm)?)', package, re.M)
                if m:
                    package = m.group(1)
                else:
                    package = package
                desc = 'CRYSTAL'

            elif re.search(r'^D\d+', name, re.M):
                package = package.split('_')[1]
                desc = 'DIODE'
            elif re.search(r'^FL\d+', name, re.M):
                package = package.split('_')[1]
                desc = 'FILTER'
            else:
                m = re.search(r'^(\w+-\d+)_', package, re.M)
                if m:
                    package = m.group(1)

            if value and package:
                index = (str(value), package, lcsc_pn)

                if index not in compos:
                    compos[index] = {'parts': [], 'jlc':
                                    {'desc': '', 'basic': False, 'code': '', 'package': '', 'partName': ''}}
                compos[index]['parts'].append((name, layer, pos, str(rot)))

    return compos
