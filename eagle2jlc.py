#!/usr/bin/python3
# -*- coding: utf-8 -*-

from os.path import dirname, abspath
from argparse import ArgumentParser
import xml.etree.ElementTree as ET
import xlsxwriter, xlrd
import requests
import re
import json


parser = ArgumentParser(description='Generate JLCPCB bom and cpl files from an eagle project')
parser.add_argument('project', type=str, help='Eagle board file')
parser.add_argument('-u', '--update', action='store_true', help='Update JLCPCB component cache')
parser.add_argument('-o', '--online', action='store_true', help='Query JLCPCB for each component (cache not used)')
parser.add_argument('-m', '--match', action='store_true', help='Only use LCSC# attribute')

API = 'https://jlcpcb.com/shoppingCart/smtGood/selectSmtComponentList'
DB_URL = 'https://jlcpcb.com/componentSearch/uploadComponentInfo'

if __name__ == '__main__':
  
  args = parser.parse_args()
  cur_path = dirname(abspath(__file__))
  
  compos = {}
  layers = {}
  board = ET.parse('{}'.format(args.project))
  jlc_compos = []
  
  if args.update and not args.online:
    print('Downloading components list...')
    r = requests.get(DB_URL)
    if r.status_code == 200:
      wb = xlrd.open_workbook(file_contents=r.content)
      sheet = wb.sheet_by_index(0)
      for i in range(sheet.nrows)[1:]:
        r = sheet.row(i)
        pn = r[0].value
        mfrn = r[1].value
        cat = r[2].value
        scat = r[3].value
        package = r[4].value
        mfr = r[6].value
        ltype = r[7].value
        jlc_compos.append(
          {'componentCode': pn,
           'describe': cat,
           'componentTypeEn': cat,
           'componentLibraryType': ltype,
           'stockCount': 1000, # No stock count in offline list
           'componentSpecificationEn': package,
           'componentBrandEn': mfr,
           'componentModelEn': mfrn
        })
      print('{} components added'.format(len(jlc_compos)))
        
    with open("jlcdb.txt", 'w') as f:
      json.dump(jlc_compos, f, indent=2)
  elif not args.online:
    with open("jlcdb.txt", 'r') as f:
      jlc_compos = json.load(f)
      print('loaded {0} components from cache'.format(len(jlc_compos)))
  
  for l in board.iter('layer'):
    layers[l.attrib['number']] = l.attrib['name']
  
  for component in board.iter('element'):
    
    value = component.attrib['value'].strip().upper()
    name = component.attrib['name'].strip().upper()
    package = component.attrib['package'].strip().upper()
    lcsc_prop = component.find(".//attribute[@name='LCSC#']")
    lcsc_pn = ''
    if lcsc_prop != None:
      lcsc_pn = lcsc_prop.attrib.get('value', '').strip().upper()
    pos = (component.attrib['x'], component.attrib['y'])
    layer = 'Top'
    index = '{0}/{1}/{2}'.format(value, package, lcsc_pn)
    
    rot = component.attrib.get('rot', 'R0')
    if rot.startswith('MR'):
      layer = 'Bottom'
      rot = rot[1:] # Remove M
    rot = rot[1:] # Remove R
    
    if layer is not 'Top':
      continue
    
    if index not in compos:
      compos[index] = {'parts': [], 'jlc': 
      {'desc': '', 'basic': False, 'code': '', 'package': '', 'partName': ''}}
    compos[index]['parts'].append((name, layer, pos, rot))
    
# Part numbers
  for c, v in compos.items():
    value = c.split('/')[0].upper()
    package = c.split('/')[1].upper()
    lcscpn = c.split('/')[2].upper()
    desc = ''
    # Trim R/C/L
    if re.search(r'^C\d{4,5}', package, re.M):
      package = package[1:]
      desc = 'CAPACITOR'
    elif re.search(r'^R\d{4,5}', package, re.M):
      package = package[1:]
      desc = 'RESISTOR'
    elif re.search(r'^L\d{4,5}', package, re.M):
      package = package[1:]
      desc = 'INDUCTOR'
    else:
      package = '' # Ignore most packages as they are too specific, see below
      m = re.search(r'^.*LED.*\d{4,5}', package, re.M)
      if m:
        package = m.group(1)
        desc = 'LED'

    names = []
    for n in v['parts']:
        names.append(n[0])

    if args.online:
      if lcscpn:
        keyword = lcscpn
      else:
        keyword = ''
        if package:
          keyword += '{} '.format(package)
        if desc:
          keyword += '{} '.format(desc)
        keyword += '{}'.format(value)
      keyword = keyword.strip()

      if not keyword.strip():
        continue

      post_data = {'keyword': keyword, 'currentPage': '1', 'pageSize': '40'}
      r = requests.post(API, data=post_data)
      jlc_compos = r.json()['data']['list']

    found = False
    for entry in jlc_compos:
      # Check part number (LCSC# property) before anything else
      if lcscpn == entry['componentCode']:
        v['jlc']['desc'] = entry['describe']
        v['jlc']['code'] = entry['componentCode']
        v['jlc']['basic'] = entry['componentLibraryType'] == 'base'
        v['jlc']['package'] = entry['componentSpecificationEn']
        v['jlc']['partName'] = entry['componentModelEn']
        found = True
        break

    # Skip the rest if we are in strict matching mode or already found it using part code
    if not args.match and not found:
      for entry in jlc_compos:

        if desc == 'RESISTOR' and value.endswith('R'):
          value = value.replace('R', 'OHM')
        elif desc == 'RESISTOR':
          value = value.replace('R', '.')
        if entry['stockCount'] < len(names): # Ignore if the required quantity isn't available
          continue
        if desc and desc not in entry['describe'].upper():
          continue
        if package and package not in entry['describe'] and package != entry['componentSpecificationEn'].upper():
          continue
        if value.upper() not in entry['describe'].upper() \
        and value.upper().strip() not in entry['componentModelEn'].upper():
          continue
          
        v['jlc']['desc'] = entry['describe']
        v['jlc']['code'] = entry['componentCode']
        v['jlc']['basic'] = entry['componentLibraryType'] == 'base'
        v['jlc']['package'] = entry['componentSpecificationEn']
        v['jlc']['partName'] = entry['componentModelEn']
        if v['jlc']['basic']: # We have found a matching "basic" part, skip the rest
          break

    print(names, v['jlc'])
    
# BOM
    
  workbook = xlsxwriter.Workbook('bom.xlsx')
  bom = workbook.add_worksheet()
  bom.set_column('A:A', 30)
  bom.set_column('B:B', 50)
  bom.set_column('C:C', 30)
  bom.set_column('D:D', 30)
  
  bom.write('A1', 'Comment')
  bom.write('B1', 'Designator')
  bom.write('C1', 'Footprint')
  bom.write('D1', 'LCSC Part #')
  bom.write('E1', 'Type')
    
  line = 2  
  for part, data in compos.items():
    
    value = part.split('/')[0]
    package = part.split('/')[1]
    
    try:
      reference = data['jlc']['code']
    except KeyError:
      reference = ''
      
    try:
      basic = data['jlc']['basic']
      if basic:
        basic = 'base'
      else:
        basic = 'extended'
    except KeyError:
      basic = 'N/A'
      
    try:
      package = data['jlc']['package']
    except KeyError:
      pass
      
    name_list = []
    for n in data['parts']:
      name_list.append(n[0])
    
    bom.write('A'+str(line), value)
    bom.write('B'+str(line), ','.join(name_list))
    bom.write('C'+str(line), package)
    bom.write('D'+str(line), reference)
    bom.write('E'+str(line), basic)
    line += 1

  workbook.close()
  
# CPL  
  
  workbook = xlsxwriter.Workbook('cpl.xlsx')
  cpl = workbook.add_worksheet()
  cpl.set_column('A:E', 15)
  
  cpl.write('A1', 'Designator')
  cpl.write('B1', 'Mid X')
  cpl.write('C1', 'Mid Y')
  cpl.write('D1', 'Layer')
  cpl.write('E1', 'Rotation')
    
  line = 2  
  for part, data in compos.items():
    for n in data['parts']:
      
      cpl.write('A'+str(line), n[0])
      cpl.write('B'+str(line), n[2][0]+'mm')
      cpl.write('C'+str(line), n[2][1]+'mm')
      cpl.write('D'+str(line), n[1])
      cpl.write('E'+str(line), n[3])
      line += 1

  workbook.close()
