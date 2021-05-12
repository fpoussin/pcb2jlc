# jlcpcb-scripts

A collection of scripts to generate BOM and CPL files for the JLCPCB assembly service

Currently supports:
* Eagle 6.x+
* Kicad 5.x+

These scripts will query the JLC online database for each part, checking stock and sorting by cheapest price.  
It can also save the whole database locally for faster generation if your connection is slow.  

You can add the `LCSC` property to your components to specify a part number.  
By default, package, value and type will be used to search for a part.  

You can offset the rotation of a part with the `ROT` property. 
