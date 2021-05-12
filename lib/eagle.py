#!/usr/bin/python3
# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET
import re

def get_components(path, layer, ignore=None):
    
    compos = {}
    layers = {}
    board = ET.parse('{}'.format(path))
    
    for l in board.iter('layer'):
        layers[l.attrib['number']] = l.attrib['name']

    ignored_parts = []
    for component in board.iter('element'):
        value = component.attrib['value'].strip().upper()
        name = component.attrib['name'].strip().upper()
        package = component.attrib['package'].strip().upper()
        lcsc_prop = component.find(".//attribute[@name='LCSC#']")
        lcsc_pn = ''
        rot_prop = component.find(".//attribute[@name='ROT']")
        rot_offset = 0

        if lcsc_prop != None:
            lcsc_pn = lcsc_prop.attrib.get('value', '').strip().upper()

        if rot_prop != None:
            rot_offset = int(rot_prop.attrib.get('value', '').strip())

        if (not lcsc_pn and ignore and re.match(ignore, name)) or re.match('^N[CBP]$', value):
            ignored_parts.append(name)
            continue
        pos = (component.attrib['x'], component.attrib['y'])
        cpn_layer = 'Top'

        # Trim R/C/L
        if re.search(r'^C\d{4,5}', package, re.M):
            package = package[1:]
            desc = 'CAPACITOR'
        elif re.search(r'^R\d{4,5}', package, re.M):
            package = package[1:]
            desc = 'RESISTOR'
            if re.search(r'\d+R(\s\d%|$)', value, re.M):
                value = value.replace('R', 'Ω')
            elif re.search(r'\d+R\d+', value, re.M):
                value = value.replace('R', '.')
        elif re.search(r'^L\d{4,5}', package, re.M):
            package = package[1:]
            desc = 'INDUCTOR'
        elif re.search(r'^SOT-?\d{2,3}(-\d)?$', package, re.M):
            if re.search(r'SOT\d{2,3}', package, re.M):
                package = package.replace('SOT', 'SOT-')
        elif re.search(r'^(DO-?\d{3}.+|SM[ABC])$', package, re.M):
            desc = 'DIODE'
        elif len(package) < 8:
            pass
        else:
            package = ''  # Ignore most packages as they are too specific, see below
            m = re.search(r'^.*LED.*\d{4,5}', package, re.M)
            if m:
                package = m.group(1)
                desc = 'LED'


        index = (value, package, lcsc_pn)

        rot = component.attrib.get('rot', 'R0')
        if rot.startswith('MR'):
            cpn_layer = 'Bottom'
            rot = rot[1:]  # Remove M
        rot = rot[1:]  # Remove R

        # Fix rotation
        rot = int(rot) + 180 + rot_offset
        rot %= 360

        if cpn_layer != layer:
            continue

        if index not in compos:
            compos[index] = {'parts': [], 'jlc':
                             {'desc': '', 'basic': False, 'code': '', 'package': '', 'partName': ''}}
        compos[index]['parts'].append((name, cpn_layer, pos, rot))

    print('Ignored parts:', sorted(ignored_parts))

    return compos
