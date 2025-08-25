#!/bin/env python3
# -*- coding: utf-8 -*-

from argparse import ArgumentParser
from os.path import splitext, basename
from lib import *

parser = ArgumentParser(
	description='Generate JLCPCB bom and cpl files from a PCB file')
parser.add_argument('pcb', type=str, help='PCB board file. Can be Eagle (.brd) or Kicad (.kicad_pcb)')
parser.add_argument('-c', '--cache', action='store_true',
					help='Use cache to speed up searching')
parser.add_argument('-u', '--update', action='store_true',
					help='Update JLCPCB component database')
parser.add_argument('-o', '--offline', action='store_true',
					help='Use offline database')
parser.add_argument('-s', '--strict', action='store_true',
					help='Only use LCSC attribute')
parser.add_argument('-n', '--nostock', action='store_true',
					help='Select part even if no stock')
parser.add_argument('-i', '--ignore', type=str,
					help='Ignored parts (regex)')

if __name__ == '__main__':

	args = parser.parse_args()
	db = None

	if args.update:
		jlc.update_db()

	if args.offline:
		db = jlc.load_db()

	base_name = splitext(basename(args.pcb))[0]

	for layer in ('top', 'bottom'):
		print('**', layer, 'layer **')
		if args.pcb.endswith('.kicad_pcb'):
			components = kicad.get_components(args.pcb, layer, args.ignore)
		elif args.pcb.endswith('.brd'):
			components = eagle.get_components(args.pcb, layer, args.ignore)
		else:
			print('Unknown board file extension, use --help')
			exit(1)

		print('getting components...')
		parts = jlc.search(components, database=db, use_cache=args.cache, nostock=args.nostock, strict=args.strict, limit=1)

		if not parts:
			print('No components found, skipping')
			continue
		
		jlc.make_bom(parts, '{0}-{1}-bom.xlsx'.format(base_name, layer))
		jlc.make_cpl(parts, '{0}-{1}-cpl.xlsx'.format(base_name, layer))
