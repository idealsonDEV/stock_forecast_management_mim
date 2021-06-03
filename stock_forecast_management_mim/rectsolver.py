# -*- coding: utf-8 -*-

from Rect2DPackLib import newPacker

def setItem(result, decoupe):
    for res in result:
        larg = res[0]
        haut = res[1]
        qty = res[2]
        for _ in range(int(round(qty,0))):
            decoupe.append((larg, haut))

def setVitre(vitre,result):
        if vitre.find(u' mm') != -1:
            vitre = vitre.replace(u' mm', u'mm')
        if vitre.find(u'cathédrale') != -1:
            vitre = vitre.replace(u'cathédrale', u'cathedrale')
        if vitre.find(u'crépi') != -1:
            vitre = vitre.replace(u'crépi', u'crepi')
        if vitre.find(u'antélio') != -1:
            vitre = vitre.replace(u'antélio', u'antelio')
        if vitre == '':
            vitre = 'Vitre claire 5mm standard'
        elif vitre.find(u"Vitre claire 5mm") != -1:
            vitre = 'Vitre claire 5mm standard'

def setDataModel(decoupe, dim):
    data = {} 
    dwidth, dheight = dim
    data['morceau'] = decoupe
    data['bins'] = [(dwidth, dheight, 500)]
    return data

def solver2D(morceaux, plans):
    # Nouvelle empacteur
    packer = newPacker()
    # Ajouter à la fil des rectangle à placer
    for r in morceaux:
        packer.add_rect(*r)
    # Ajouter un plan
    for p in plans:
        packer.add_bin(*p)
    # Resoudre
    packer.pack()
    return (len(packer))
        
def optimise(vitre,data_raw):
    decoupe = []
    setVitre(vitre,data_raw)
    setItem(data_raw, decoupe)
    rep = 0
    if vitre not in [u'Vitre cathedrale 6mm', u'Vitre cathedrale 5mm', u'Vitre crepi clair 5mm', u'Vitre crepi clair 6mm', u'Vitre crepi clair 4mm']:
            dim = (3300, 2140)
    else:
            dim = (2440, 1830)
    data = setDataModel(decoupe, dim)
    rep = solver2D(data['morceau'], data['bins'])
    return rep


#print optimise('', [(300,295,800)])
    
