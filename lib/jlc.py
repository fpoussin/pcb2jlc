#!/usr/bin/python3
# -*- coding: utf-8 -*-

import xlsxwriter
import requests
import json
import time
import gzip
import os


DB_FILE = 'jlcdb.json.gz'

CATEGORIES = 'https://jlcpcb.com/componentSearch/getFirstSortAndChilds'
SORT = 'https://jlcpcb.com/componentSearch/getSortAndCount'

API = 'https://jlcpcb.com/shoppingCart/smtGood/selectSmtComponentList'
DB_URL = 'https://jlcpcb.com/componentSearch/uploadComponentInfo'
PN_ULR = 'https://jlcpcb.com/shoppingCart/smtGood/getComponentDetail?componentCode='


def update_db():
    print('Downloading components list...')
    database = []

    step = 100
    r = requests.post(CATEGORIES, json={})
    if r.status_code == 200:
        categories = r.json()
        for category in categories:
            cat_data = []
            print('Importing', category['sortName'])
            for subcategory in category['childSortList']:
                # Download a list of all components
                subCategoryName = subcategory['sortName']
                print('- {}... '.format(subCategoryName), end='', flush=True)
                page = 0
                subcat_data = []
                while True:
                    r = requests.post(API, json={'currentPage': page, 'pageSize': step, 'searchSource': 'search', 'firstSortName': '', 'secondeSortName': subCategoryName})
                    if r.status_code == 200:
                        try:
                            data = r.json()['data']['list']
                            data_len = len(data)
                            if data_len:
                                for part in data:
                                    if not len(part['componentPrices']):
                                        part['componentPrices'] = [{'productPrice': 0}]
                                subcat_data += data
                                if data_len < step:
                                    break
                                page += 1
                                time.sleep(0.1)
                            else:
                                break
                        except Exception as e:
                            print(e)
                            print(r.text)
                            break
                print(len(subcat_data))
                cat_data += subcat_data
            print('Total', len(cat_data), '\n\r')
            database += sorted(cat_data, key=lambda x: x['componentPrices'][0]['productPrice'])
    else:
        print('Update failed')
        return

    with gzip.open(DB_FILE, 'w') as f:
        f.write(json.dumps(database, indent=2).encode('utf-8'))


def load_db():
    if not os.path.exists(DB_FILE):
        print('Database not found, creating it...')
        update_db()
    with gzip.open(DB_FILE, 'r') as f:
        database = json.load(f)
        print('loaded {0} components from cache'.format(len(database)))
    return database


def search(compos: dict(), database=None, nostock=False, match=False):
    missing = list()
    bom = list()
    for c, v in compos.items():
        value = c[0]
        package = c[1]
        lcscpn = c[2]
        names = []
        for n in v['parts']:
            names.append(n[0])

        if not database:
            if lcscpn:
                keyword = lcscpn
            else:
                keyword = ''
                if package:
                    keyword += '{} '.format(package)
                keyword += '{}'.format(value)
            keyword = keyword.strip()

            if not keyword:
                continue

            print('Searching for', keyword, '... ', end="", flush=True)

            post_data = {'keyword': keyword,
                         'firstSortName': '',
                         'secondeSortName': '',
                         'currentPage': 1, 
                         'pageSize': 100,
                         'searchSource': 'search',
                         'stockFlag': not nostock}
            r = requests.post(API, json=post_data, headers={'content-type': 'application/json', 'referer': 'https://jlcpcb.com/parts/componentSearch'})
            r_data = []
            for part in r.json()['data']['list']:
                if not len(part['componentPrices']):
                    part['componentPrices'] = [{'productPrice': 0}]
                r_data.append(part)
            parts = sorted(r_data, key=lambda x: x['componentPrices'][0]['productPrice'])
            print(len(parts) or 'Not', 'found')
        else:
            parts = database

        found = False
        for entry in parts:
            # Check part number (LCSC# property) before anything else
            if lcscpn == entry['componentCode']:
                v['jlc']['desc'] = entry['describe']
                v['jlc']['code'] = entry['componentCode']
                v['jlc']['basic'] = entry['componentLibraryType'] == 'base'
                v['jlc']['package'] = entry['componentSpecificationEn']
                v['jlc']['partName'] = entry['componentModelEn']
                v['jlc']['unitPrice'] = entry['componentPrices'][0]['productPrice']
                found = True
                break

        # Skip the rest if we are in strict matching mode or already found it using part code
        if not match and not found:
            for entry in parts:
                # Ignore if the required quantity isn't available
                if entry['stockCount'] < len(names) and nostock == False:
                    continue
                if package and package not in entry['describe'] and package != entry['componentSpecificationEn'].upper():
                    continue
                all_words_found = True
                for word in value.split(' '):
                    if word.upper() not in entry['describe'].upper():
                        all_words_found = False
                        break
                if not all_words_found and value not in entry['componentModelEn'].upper():
                    continue

                v['jlc']['desc'] = entry['describe']
                v['jlc']['code'] = entry['componentCode']
                v['jlc']['basic'] = entry['componentLibraryType'] == 'base'
                v['jlc']['package'] = entry['componentSpecificationEn']
                v['jlc']['partName'] = entry['componentModelEn']
                v['jlc']['unitPrice'] = entry['componentPrices'][0]['productPrice']
                if v['jlc']['basic']:  # We have found a matching "basic" part, skip the rest
                    break

        if v['jlc']['code']:
            bom.append((sorted(names), v['jlc']))
        else:
            missing.append((sorted(names), value, package))

    print('Found parts ({}):'.format(len(bom)))
    for part in sorted(bom):
        print(part)

    print('Missing parts ({}):'.format(len(missing)))
    for m in sorted(missing):
        print(m)

    return compos


def make_bom(parts, path='bom.xlsx'):
    workbook = xlsxwriter.Workbook(path)
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
    for part, data in parts.items():

        value = part[0]
        package = part[1]

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

def make_cpl(parts, path='cpm.xlsx'):
    workbook = xlsxwriter.Workbook(path)
    cpl = workbook.add_worksheet()
    cpl.set_column('A:E', 15)

    cpl.write('A1', 'Designator')
    cpl.write('B1', 'Mid X')
    cpl.write('C1', 'Mid Y')
    cpl.write('D1', 'Layer')
    cpl.write('E1', 'Rotation')

    line = 2
    for part, data in parts.items():
        for n in data['parts']:

            cpl.write('A'+str(line), n[0])
            cpl.write('B'+str(line), str(n[2][0])+'mm')
            cpl.write('C'+str(line), str(n[2][1])+'mm')
            cpl.write('D'+str(line), n[1])
            cpl.write('E'+str(line), n[3])
            line += 1

    workbook.close()
