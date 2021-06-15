#!/usr/bin/python
# -*- coding: utf-8 -*-

from openerp import netsvc
from openerp.osv import osv, fields
from openerp import api
from datetime import datetime, date, timedelta, time
from collections import OrderedDict as ord

from openerp import SUPERUSER_ID

#from openerp.addons.product import _common
from openerp import tools
from openerp.tools.safe_eval import safe_eval

import re
import numpy as np

import linearsolver
import rectsolver
import prevision
import operational_research
import graph2img
import base64

def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days)):
        yield start_date + timedelta(n)

# Récoler les données sur les historique des commandes
## à partir du module MRP

class ArticleClass(osv.osv):
    _name = 'stock.data.article.list'
    _columns = {
        'product_id': fields.many2one('product.product', string="Arcticle", required=True),
        'name': fields.char(string="Nom"),
        'qu_no_month': fields.float(string="Quantité désaisonnalisée mensuelle"),
        'qu_month': fields.float(string="Quantité saisonniée prévue mensuelle"),
        'qu_no_season': fields.float(string="Quantité désaisonnalisée trimestrille"),
        'qu_season': fields.float(string="Quantité saisonniée trimestrille"),
        'access': fields.boolean(string="Accessoire"),
        'linker': fields.many2one('stock.data.range.day', string="Prévison")
    }

class ExistingClass(osv.osv):
    _name = 'stock.data.existing.list'
    _columns = {
        'product_id': fields.many2one('product.product', string="Arcticle", required=True),
        'name': fields.char(string="Nom"),
        'stock': fields.float(string="Stock Actuelle"),
        'quantite': fields.float(string="Quantité Nécessaire"),
        'access': fields.boolean(string="accessoire"),
        'linker': fields.many2one('stock.data.range.day', string="Prévison")
    }

class FinishClass(osv.osv):
    _name = 'stock.data.finish.list'
    _columns = {
        'product_id': fields.many2one('product.product', string="Arcticle", required=True),
        'name': fields.char(string="Nom"),
        'quantite': fields.float(string="Quantité"),
        'occurency': fields.integer(string="occurence"),
        'linker': fields.many2one('stock.data.range.day', string="Prévison")
    }

class GraphFinish(osv.osv):
    _name = 'stock.data.finish.graph'
    _rec_name = 'name'
    _columns = {
        'finish_id' : fields.many2one('stock.data.finish.forecast', string="A produire"),
        'name': fields.char(string="Nom"),
        'trimestre' : fields.integer(string="Numero de trimestre"),
        'quantite' : fields.float(string="Quantité"),
        'mean' : fields.float(string="Moyenne"),
        'mobile': fields.float(string="Moyenne Mobile")
    }

class ForecasteFinishClass(osv.osv):
    _name = 'stock.data.finish.forecast'
    _columns = {
        'product_id': fields.many2one('product.product', string="Arcticle", required=True),
        'name': fields.char(string="Nom"),
        'tms': fields.boolean(string="T-MS"),
        'q_no_season': fields.float(string="Quantité désaisonnalisée prévue"),
        'q_season': fields.float(string="Quantité saisonniée prévue"),
        'hauteur': fields.float(string="Hauteur moyenne"),
        'largeur': fields.float(string="Largeur moyenne"),
        'div2': fields.float(string="Division % = 2"),
        'div3': fields.float(string="Division % > 3"),
        'style': fields.float(string="Style EN"),
        'moust': fields.float(string="Pourcentage Moustiquaire"),
        'inter': fields.float(string="Pourcentage Intermediaire"),
        'linker': fields.many2one('stock.data.range.day', string="Prévison"),
        'graph': fields.one2many('stock.data.finish.graph', 'finish_id' , string="Graphique trimestrille"),
        'state' : fields.binary(string="Graphique"),
    }

class MultiProduct(osv.osv):
    _name = 'stock.data.multi.product'
    _rec_name = 'product_id'
    _columns = {
        'product_id': fields.many2one('product.product', string="Articles", required=True),
        'reverse_id': fields.many2one('stock.data.setting.profile', string="Reverse")
    }

class SettingProfile(osv.osv):
    _name = 'stock.data.setting.profile'
    _rec_name = 'product_id'
    _columns = {
        'product_id': fields.many2one('product.product', string="Articles", required=True),
        'product_ids': fields.one2many('stock.data.multi.product', 'reverse_id', string="Articles alternatifs"),
        'unity' : fields.many2one('product.uom', string="Unité"),
        'weight': fields.float(string="Poids unitaire"),
        'minimal': fields.float(string="Quantité Minimal de sécurité"),
        'minimal_in': fields.float(string="Quantité Minimal à acheter"),
        'minimal_out': fields.float(string="Quantité Minimal à consommer"),
        'ratio': fields.float(string="Ratio par rapport à T60-KB"),
        'tonnage': fields.float(string="Tonnage en Kg"),
        'graph' : fields.binary(string="Graphique achats"),
        'graph2' : fields.binary(string="Graphique consommation"),
    }
    _defaults = {
        'unity' : 12
    }

    @api.one
    def compute_tonnage(self):
        cr = self._cr
        uid = self._uid
        ids = self._ids
        context = {}
        properties = []
        profile = self.pool.get('stock.data.setting.profile')
        sea_pro = profile.search(cr,uid,[('product_id.id','=',516)])
        brow = profile.browse(cr,uid,sea_pro,context=context)
        if brow:
            numerateur = brow[0].minimal
            if numerateur == 0.0:
                numerateur = 500
        else:
            numerateur = 500
        self.write({'tonnage' : self.weight * self.minimal,
                    'ratio' : self.minimal/numerateur,})

    @api.one
    def compute_mean_quantite(self):
        cr = self._cr
        uid = self._uid
        ids = self._ids
        context = {}
        properties = []
        date_start = datetime.today()
        stock_move = self.pool.get('stock.move')
        end_d = date_start
        stt_d = date_start - timedelta(days=90)
        data16_out = [0] * 16
        data16 = [0] * 16
        daterange = [0] * 16

        id_list = []
        for ids in self.product_ids:
            id_list.append(ids.product_id.id)

        for index in range(16)[::-1]:
            qty = 0
            date = stt_d.strftime("%Y-%m-%d %H:%M:%S")
            date_fx = (end_d + timedelta(hours=23,minutes=59,seconds=59)).strftime("%Y-%m-%d %H:%M:%S")
            search = stock_move.search(cr, uid, [
                ('date', '>=', date),
                ('date', '<=', date_fx),
                ('picking_id.picking_type_id.code', '=', 'incoming'),
                ('location_id.usage', '!=', 'internal'),
                ('location_dest_id.usage', '=', 'internal'),
                ('product_id.id' ,'in', id_list)
                ],
                context={'product_receive': True}
                )
            for unite in stock_move.browse(cr,uid,search,context=context):
                qty += unite.product_uom_qty
            data16[index]=qty

            qty_out =0
            search2 = stock_move.search(cr, uid, [
                ('create_date', '>=', date),
                ('create_date', '<=', date_fx),
                ('state', '=', 'done'),
                ('raw_material_production_id', '!=', False),
                ('production_id', '=', False),
                ('location_id', '=', 12),
                ('product_uom', '=', 12),
                ('product_id.id' ,'in', id_list)
                ])

            for unite in stock_move.browse(cr,uid,search2,context=context):
                qty_out += unite.product_uom_qty
            data16_out[index]=qty_out
            daterange[index] = end_d.strftime("%d\n%m")
            end_d = stt_d
            stt_d = stt_d - timedelta(days=90)
        #raise osv.except_osv("qty", data16)

        oqty, sqty =  prevision.predict(data16)
        mm = prevision.get_moyenne_mobile(data16)
        x1,y1,x2,y2 = prevision.get_tendency(data16)
        binimg = graph2img.tobinary(data16,mm[2:14],[x1,x2],[y1,y2],daterange,"Courbes des achats")

        oqty_out, sqty_out =  prevision.predict(data16_out)
        mm_out = prevision.get_moyenne_mobile(data16_out)
        x1_o,y1_o,x2_o,y2_o = prevision.get_tendency(data16_out)
        binimg_out = graph2img.tobinary(data16_out,mm_out[2:14],[x1_o,x2_o],[y1_o,y2_o],daterange,"Coubes de consommation")



        self.write({'minimal' : oqty_out,
                    'minimal_in' : oqty,
                    'minimal_out': oqty_out,
                    'graph' : base64.b64encode(binimg),
                    'graph2' : base64.b64encode(binimg_out)})

        #raise osv.except_osv("Error unit", (x1,y1,x2,y2))

class NextProfile(osv.osv):
    _name = 'stock.data.next.profile'
    _columns = {
        'product_id': fields.many2one('product.product', string="Articles", required=True),
        'unity' : fields.many2one('product.uom', string="Unité"),
        'current_qty': fields.float(string="Quantité Actuelle"),
        'necessary_qty' : fields.float(string="Quantité Nécessaire"),
        'security_qty': fields.float(string="Quantité de sécurité"),
        'complet_qty' : fields.float(string="Quantité d'ajustement"),
        'future_qty' : fields.float(string="Quantité optimale"),
        'linker': fields.many2one('stock.data.range.day', string="Prévison")
    }

class stockDayRange(osv.osv):
    _name = 'stock.data.range.day'
    _columns = {
        'date_start': fields.date(string="Date Debut"),
        'date_end': fields.date(string="Date Fin"),
        'ratio': fields.float(string="Ratio entre (T60-KB, T88-PKJ et P60-K, P60-K-R)"),
        'tonnage': fields.float(string="Tonnage des profilées"),
        'real_tonnage' : fields.float(string="Tonnage réel"),
        'data_article_last': fields.one2many('stock.data.article.list', 'linker'),
        'data_article_exist': fields.one2many('stock.data.existing.list', 'linker'),
        'data_finish_last': fields.one2many('stock.data.finish.forecast', 'linker'),
        'data_next_profile': fields.one2many('stock.data.next.profile', 'linker')
    }
    _defaults = {
        'date_start' : date.today(),
        'date_end' : date.today() + timedelta(days=90),
        'tonnage' : 10.0
    }

    @api.multi
    def name_get(self):
        result = []
        for isst in self:
            name = "de " + isst.date_start + " à " + isst.date_end
            result.append((isst.id, name))
        return result


    @api.multi
    def next_profile(self):
        cr = self._cr
        uid = self._uid
        ids = self._ids
        context = {}
        min_data = self.pool.get('stock.data.setting.profile')
        min_sh = min_data.search(cr, uid,[])
        min_brw = min_data.browse(cr, uid, min_sh, context=context)
        min_dic = {}
        nextprofile = self.pool.get('stock.data.next.profile')
        nextprofile.unlink(cr, SUPERUSER_ID, [line.id for line in self.data_next_profile], context=context)
        for min_pc in min_brw:
            min_u = {}
            #min_u['product_id'] = min_pc.product_id
            min_u['name'] = min_pc.product_id.name
            min_u['weight'] = min_pc.weight
            min_u['minimal'] = min_pc.minimal
            min_u['quant'] = min_pc.product_id.virtual_available
            min_u['ratio'] = min_pc.ratio
            min_dic[min_pc.product_id.id] = min_u
        for exist in self.data_article_exist:
            if exist.product_id.id in min_dic.keys():
                min_dic[exist.product_id.id]['exist'] = exist.quantite
        for idx in min_dic:
            if 'exist' not in min_dic[idx].keys():
                min_dic[idx]['exist'] = 0.0
            if min_dic[idx]['quant'] >= - min_dic[idx]['exist'] + min_dic[idx]['minimal']:
                min_dic[idx]['reste'] = min_dic[idx]['quant'] + min_dic[idx]['exist'] - min_dic[idx]['minimal']
                min_dic[idx]['com_ex'] = 0
            elif min_dic[idx]['quant'] < - min_dic[idx]['exist'] + min_dic[idx]['minimal']:
                min_dic[idx]['reste'] = 0
                min_dic[idx]['com_ex'] = - min_dic[idx]['exist'] + min_dic[idx]['minimal'] - min_dic[idx]['quant']
        tonnage = self.tonnage * 1000
        tonnage_rest = tonnage
        for idx in min_dic:
            tonnage_rest -= min_dic[idx]['com_ex'] * min_dic[idx]['weight']

        if tonnage_rest < 0:
            raise osv.except_osv("Tonnage insuffisant", "Le poids Actuelle est de "+ str(round(tonnage-tonnage_rest,1)+" Kg"))
        #raise osv.except_osv("min", (tonnage_rest,str(viwzer)))
        poids , min_dic = operational_research.op_solver(tonnage_rest, min_dic)
        
        #raise osv.except_osv("min_dic", str(min_dic2))
        for idx in min_dic:
            self.write({ 'data_next_profile': [(0, 0, {
                                'product_id': idx,
                                'unity' : 12,
                                'current_qty': min_dic[idx]['quant'],
                                'necessary_qty' : min_dic[idx]['exist'],
                                'security_qty': (min_dic[idx]['minimal'] - min_dic[idx]['exist']),
                                'complet_qty' : min_dic[idx]['com_ex'],
                                'future_qty' : (min_dic[idx]['com_ex'] + min_dic[idx]['optim'])
                                })]
                        })
        real_tonnage = poids + tonnage - tonnage_rest
        self.write({'real_tonnage' : real_tonnage})
        return True



    @api.multi
    def get_data_day_last(self):
        cr = self._cr
        uid = self._uid
        ids = self._ids
        context = {}
        prod_obj = self.pool.get('mrp.production')
        consummed_dic = ord()
        finish_dic = ord()
        date_start = datetime.strptime(self.date_start + " 00:00:00", "%Y-%m-%d %H:%M:%S")
        date_end = datetime.strptime(self.date_end + " 00:00:00", "%Y-%m-%d %H:%M:%S")
        for single_date in daterange(date_start, date_end):
            date = single_date.strftime("%Y-%m-%d %H:%M:%S")
            date_fx = (single_date + timedelta(hours=23,minutes=59,seconds=59)).strftime("%Y-%m-%d %H:%M:%S")
            search = prod_obj.search(cr, uid, [
                ('date_planned', '>=', date),
                ('date_planned', '<=', date_fx),
                ('state', '=', 'done'),
                ])
            for prd in prod_obj.browse(cr, uid, search, context=context):

                for line2 in prd.move_lines2:
                    prod_id = line2.product_id
                    if prod_id not in consummed_dic.keys():
                        consummed_dic[prod_id] = {}
                        consummed_dic[prod_id]['name'] = prod_id.name
                        consummed_dic[prod_id]['quantite'] = line2.product_uom_qty
                        consummed_dic[prod_id]['occurency'] = 1
                    elif prod_id in consummed_dic.keys():
                        consummed_dic[prod_id]['quantite'] += line2.product_uom_qty
                        consummed_dic[prod_id]['occurency'] += 1

                for line in prd.product_lines:
                    prod_id = line.product_id
                    if prod_id in consummed_dic.keys():
                        consummed_dic[prod_id]['access'] = line.is_accessory

                for fin in prd.move_created_ids2:
                    fini_id = fin.product_id
                    if fini_id not in finish_dic.keys():
                        finish_dic[fini_id] = {}
                        finish_dic[fini_id]['name'] = fini_id.name
                        finish_dic[fini_id]['quantite'] = fin.product_uom_qty
                        finish_dic[fini_id]['occurency'] = 1
                    elif fini_id in finish_dic.keys():
                        finish_dic[fini_id]['quantite'] += fin.product_uom_qty
                        finish_dic[fini_id]['occurency'] += 1

                    
        for prod_id in consummed_dic:
            self.write({ 'data_article' : [( 0, 0, {
                                'product_id': prod_id,
                                'name' : consummed_dic[prod_id]['name'],
                                'quantite': consummed_dic[prod_id]['quantite'],
                                'access': consummed_dic[prod_id]['access'],
                                'occurency': consummed_dic[prod_id]['occurency']
                            })]
                        })

        for fini_id in finish_dic:
            self.write({ 'data_finish' : [( 0, 0, {
                                'product_id': fini_id,
                                'name' :  finish_dic[fini_id]['name'],
                                'quantite': finish_dic[fini_id]['quantite'],
                                'occurency': finish_dic[fini_id]['occurency']
                            })]
                        })
        return True

    @api.one
    def get_data_day_future(self):
        cr = self._cr
        uid = self._uid
        ids = self._ids
        context = {}
        properties = []
        prod_obj = self.pool.get('mrp.production')
        date_start = datetime.strptime(self.date_start + " 00:00:00", "%Y-%m-%d %H:%M:%S")
        date_end = datetime.strptime(self.date_end + " 00:00:00", "%Y-%m-%d %H:%M:%S")
        profile = {}
        profile_name = {}
        vitre = {}
        vitre_name = {}
        accessoire = {}
        accessoire_name = {}
        quantite_future = ord()
        quantite_name = {}
        is_accessory = {}
        list_out_mo = []
        list_out_mo_no = []
        list_out_so = []
        existing_obj = self.pool.get('stock.data.existing.list')
        existing_obj.unlink(cr, SUPERUSER_ID, [line.id for line in self.data_article_exist], context=context)
        for single_date in daterange(date_start, date_end):
            date = single_date.strftime("%Y-%m-%d %H:%M:%S")
            date_fx = (single_date + timedelta(hours=23,minutes=59,seconds=59)).strftime("%Y-%m-%d %H:%M:%S")
            search = prod_obj.search(cr, uid, [
                ('date_planned', '>=', date),
                ('date_planned', '<=', date_fx),
                ('state', '!=', 'cancel'),
                ('state', '!=', 'done'),
                ('bom_id', '!=', False)
                ])
            for product in prod_obj.browse(cr, uid, search, context=context):
                res = prod_obj._prepare_lines(cr, uid, product, properties=properties, context=context)
                results = res[0] # product_lines
                results2 = res[1] # workcenter_lines
            
                #ando Calcul dynamique de la quatité des composants
                parent_id = product.product_id.id
                qty = product.product_qty
                largeur = product.largeur
                hauteur = product.hauteur
                if largeur > 0 and hauteur > 0:
                    list_out_mo.append(product.name)
                elif largeur == 0.0 and hauteur == 0.0:
                    list_out_mo_no.append(product.name)
                    if u'Dimension : ' in product.description:
                        ext1 = re.match(r'.*Dimension : ([0-9]*) x ([0-9]*) HT', product.description)
                    else:
                        ext1 = re.match(r'.*\s([0-9]*) x ([0-9]*) HT', product.description)
                    if ext1:
                        largeur = float(ext1.group(1))
                        hauteur = float(ext1.group(2))
                if largeur == 0 or hauteur == 0:
                    raise osv.except_osv("Error 228", "Erreur de convertion de la chaine avec larngeur et hauteur avec RegEx")
                tms = product.tms
                localdict = {}
                localdict['largeur'] = largeur
                localdict['hauteur'] = hauteur
                localdict['tms'] = tms
                localdict['result'] = None
                localdict['style'] = product.style
                localdict['vitre'] = product.remplissage_vitre
                
                #Mise à jour
                if not product.vitre :
                    localdict['type_vitre'] = 0
                else:localdict['type_vitre'] = product.vitre.id
                
                localdict['inter'] = product.intermediaire
                localdict['moust'] = product.moustiquaire
                
                localdict['div'] = product.division
                
                if not product.nb_division :
                    localdict['nb_div'] = 1.0
                else:localdict['nb_div'] = product.nb_division
                
                if not product.type_intermediaire or product.type_intermediaire=='vert':
                    localdict['type_inter'] = 'vert'
                else:localdict['type_inter'] = 'horiz'
                
                localdict['batis'] = product.batis_id.name
                
                component = self.pool.get('mrp.component')
                #all_component = []
                l = {}
                for line in results:
                    line_id = line['line_id']
                    list_id = component.search(cr, uid, [('line_id','=',line_id)])
                    if list_id:
                        for c in component.browse(cr, uid, list_id, context=context):
                            total1 = 0.0
                            total2 = 0.0
                            
                            len_total0 = 0.0
                            len_unit0 =0.0
                            qty_total0 = 0.0
                            #Insértion de tous les sous-composants pour l'impression
                            for s in c.sub_component_ids:
                                localdict['Q'] = qty
                                
                                safe_eval(s.python_product_qty, localdict, mode='exec', nocopy=True)
                                product_qty = float(localdict['result'])
                                ##################################
                                #l['production_id'] = production.id
                                l['product_qty'] = product_qty
                                
                                localdict['QU'] = product_qty
                                
                                product_qty0 = product_qty
                                
                                safe_eval(s.python_product_qty_total, localdict, mode='exec', nocopy=True)
                                product_qty_total = float(localdict['result'])
                                
                                l['product_qty_total'] = product_qty_total
                                #l['product_qty_total'] = qty * l['product_qty']
                                
                                qty_total0 = product_qty_total
                                
                                localdict['QT'] = l['product_qty_total']
                                
                                total2 = total2 + l['product_qty_total']
                                if not line['is_accessory']:
                                    l['ref'] = c.product_parent_id
                                    safe_eval(s.python_len_unit, localdict, mode='exec', nocopy=True)
                                    len_unit = float(localdict['result'])
                                    l['len_unit'] = len_unit
                                    
                                    localdict['LU'] = l['len_unit']
                                    
                                    #l['len_total'] = l['len_unit'] * l['product_qty_total']
                                    
                                    safe_eval(s.python_len_total, localdict, mode='exec', nocopy=True)
                                    len_total = float(localdict['result'])
                                    
                                    l['len_total'] = len_total
                                    
                                    len_total0 = len_total
                                    
                                    total1 = total1 + l['len_total']
                                    
                                    LU = l['len_unit']
                                    LT = l['len_total']
                                    
                                    len_unit0 = l['len_unit']
                                    
                                    if l['len_total']!=0.0:
                                        if s.name in ['VITRE','Vitre','vitre']:
                                            if l['ref'] not in vitre.keys():
                                                vitre[l['ref']] = []
                                                vitre_name[l['ref']] = c.product_parent_id.name
                                            vitre[l['ref']].append((l['len_unit'],l['len_total'],l['product_qty_total']))
                                        else:
                                            if l['ref'] not in profile.keys():
                                                profile[l['ref']] = []
                                                profile_name[l['ref']] = c.product_parent_id.name
                                            profile[l['ref']].append((l['len_unit'],l['product_qty_total']))
                                else:
                                    if l['product_qty_total']!=0.0:
                                        l['ref'] = c.product_parent_id
                                        if l['ref'] not in accessoire.keys():
                                            accessoire[l['ref']] = []
                                            accessoire_name[l['ref']] = c.product_parent_id.name
                                        accessoire[l['ref']].append(l['product_qty_total'])
                                l = {}

        bom = self.pool.get("mrp.bom")
        stock_obj = self.pool.get('stock.picking')
        sale_order = self.pool.get('sale.order')
        sale_order_line = self.pool.get('sale.order.line')

        for single_date in daterange(date_start, date_end):
            date = single_date.strftime("%Y-%m-%d %H:%M:%S")
            date_fx = (single_date + timedelta(hours=23,minutes=59,seconds=59)).strftime("%Y-%m-%d %H:%M:%S")
            search = stock_obj.search(cr, uid, [
                ('date', '>=', date),
                ('date', '<=', date_fx),
                ('state', '!=', 'cancel'),
                ('state', '!=', 'done'),
                ])
            for stock in stock_obj.browse(cr, uid, search, context=context):
                sale_sh = sale_order.search(cr, uid, [('name', '=', stock.origin)])
                sale_br = sale_order.browse(cr, uid, sale_sh, context=context)
                if len(sale_br) > 0:
                    sale_id = sale_br[0].id
                if u'IN' in stock.name:
                    continue
                if u'PO' in stock.origin:
                    continue
                for move in stock.move_lines:
                    if not move.is_mo_created:
                        component_id_list = []
                        bom_sr = bom.search(cr, uid, [('product_id','=',move.product_id.id)])
                        bom_br = bom.browse(cr, uid, bom_sr, context=context)
                        if len(bom_br) > 0 :
                            bom_lines = bom_br[0].bom_line_ids
                            for line in bom_lines:
                                component_id_list.append(line.component_id)
                            list_id = component.search(cr, uid, [('id','in',component_id_list)])
                        else:
                            continue
                        
                        product_id = move.product_id.id
                        if move.product_id.name == 'Coulissante 1VTL':
                            product_id = int(721)
                        order_line_sh = sale_order_line.search(cr, uid, [('product_id','=', product_id),
                                                                         ('product_uom_qty', '=', move.product_uom_qty),
                                                                         ('order_id', '=', sale_id)])
                        order_line_br = sale_order_line.browse(cr, uid, order_line_sh, context=context)
                        if order_line_br:
                            line = order_line_br[0]
                            if stock.origin not in list_out_so:
                                list_out_so.append(stock.origin)
                        else:
                            raise osv.except_osv("STOCK.PICKING", stock.name)
                        #raise osv.except_osv("STOCK.PICKING", (move.name,line.name))
                        largeur = 0
                        hauteur = 0
                        localdict = {}
                        if move.hauteur > 0 or move.largeur > 0:
                            largeur = move.largeur
                            hauteur = move.hauteur
                        elif line.hauteur > 0 or line.largeur > 0:
                            largeur = line.largeur
                            hauteur = line.hauteur
                        else:
                            desc = move.name.replace(u'\n', u' ')
                            ext1 = re.match(r'.*\s([0-9]*) x ([0-9]*) HT', desc)
                            if ext1:
                                largeur = float(ext1.group(1))
                                hauteur = float(ext1.group(2))
                        if largeur == 0 or hauteur == 0:
                            raise osv.except_osv("Error 405", "Erreur de convertion de la chaine avec larngeur et hauteur avec RegEx")
                        localdict['largeur'] = largeur
                        localdict['hauteur'] = hauteur
                        localdict['tms'] = line.tms
                        localdict['result'] = None
                        localdict['style'] = 'fr'
                        if u'anglais' in move.name:
                            localdict['style'] = 'en'
                        localdict['vitre'] = line.vitre.id
                        localdict['type_vitre'] = line.type_vitre
                        localdict['inter'] = line.intermediaire
                        if line.intermediaire == 'avec':
                            if localdict['largeur'] > localdict['hauteur']:
                                localdict['type_inter'] = 'vert'
                            else:
                                localdict['type_inter'] = 'horiz'
                        localdict['moust'] = line.moustiquaire
                        localdict['div'] = line.division
                        if line.division:
                            localdict['nb_div'] = line.nb_division
                        else:
                            localdict['nb_div'] = 1.0
                        localdict['batis'] = u'T 60 K B'

                        l = {}
                        for c in component.browse(cr, uid, list_id, context=context):
                                        total1 = 0.0
                                        total2 = 0.0
                                        
                                        len_total0 = 0.0
                                        len_unit0 =0.0
                                        qty_total0 = 0.0
                                        #Insértion de tous les sous-composants pour l'impression
                                        for s in c.sub_component_ids:
                                            localdict['Q'] = move.product_uom_qty
                                            
                                            safe_eval(s.python_product_qty, localdict, mode='exec', nocopy=True)
                                            product_qty = float(localdict['result'])
                                            ##################################
                                            #l['production_id'] = production.id
                                            l['product_qty'] = product_qty
                                            
                                            localdict['QU'] = product_qty
                                            
                                            product_qty0 = product_qty
                                            
                                            safe_eval(s.python_product_qty_total, localdict, mode='exec', nocopy=True)
                                            product_qty_total = float(localdict['result'])
                                            
                                            l['product_qty_total'] = product_qty_total
                                            #l['product_qty_total'] = qty * l['product_qty']
                                            
                                            qty_total0 = product_qty_total
                                            
                                            localdict['QT'] = l['product_qty_total']
                                            
                                            total2 = total2 + l['product_qty_total']

                                            if not c.line_id.is_accessory:
                                                l['ref'] = c.product_parent_id
                                                safe_eval(s.python_len_unit, localdict, mode='exec', nocopy=True)
                                                len_unit = float(localdict['result'])
                                                l['len_unit'] = len_unit
                                                
                                                localdict['LU'] = l['len_unit']
                                                
                                                #l['len_total'] = l['len_unit'] * l['product_qty_total']
                                                
                                                safe_eval(s.python_len_total, localdict, mode='exec', nocopy=True)
                                                len_total = float(localdict['result'])
                                                
                                                l['len_total'] = len_total
                                                
                                                len_total0 = len_total
                                                
                                                total1 = total1 + l['len_total']
                                                
                                                LU = l['len_unit']
                                                LT = l['len_total']
                                                
                                                len_unit0 = l['len_unit']
                                                
                                                if l['len_total']!=0.0:
                                                    if s.name in ['VITRE','Vitre','vitre']:
                                                        if l['ref'] not in vitre.keys():
                                                            vitre[l['ref']] = []
                                                            vitre_name[l['ref']] = c.product_parent_id.name
                                                        vitre[l['ref']].append((l['len_unit'],l['len_total'],l['product_qty_total']))
                                                    else:
                                                        if l['ref'] not in profile.keys():
                                                            profile[l['ref']] = []
                                                            profile_name[l['ref']] = c.product_parent_id.name
                                                        profile[l['ref']].append((l['len_unit'],l['product_qty_total']))
                                            else:
                                                if l['product_qty_total']!=0.0:
                                                    l['ref'] = c.product_parent_id
                                                    if l['ref'] not in accessoire.keys():
                                                        accessoire[l['ref']] = []
                                                        accessoire_name[l['ref']] = c.product_parent_id.name
                                                    accessoire[l['ref']].append(l['product_qty_total'])
                                            l = {}
                                            #raise osv.except_osv("l",(stock.name,move.name,str(l)))
        for i in profile:
            quantite_future[i] = linearsolver.optimise(profile[i],5800)
            quantite_name[i] = profile_name[i]
            is_accessory[i] = False
        for j in vitre:
            quantite_future[j] = rectsolver.optimise(vitre_name[j],vitre[j])
            quantite_name[j] = vitre_name[j]
            is_accessory[j] = False
        for k in accessoire:
            quantite_future[k] = linearsolver.sum(accessoire[k])
            quantite_name[k] = accessoire_name[k]
            is_accessory[k] = True
        for q_id in quantite_future:
            self.write({ 'data_article_exist': [(0, 0, {
                                'product_id': q_id.id,
                                'name' :  quantite_name[q_id],
                                'stock': q_id.virtual_available,
                                'quantite': quantite_future[q_id],
                                'access': is_accessory[q_id]
                            })]
                        })
        #raise osv.except_osv("Error",str([(0, 0, x) for x in line_exist]))
        #raise osv.except_osv("Affichage",(list_out_mo,list_out_mo_no,list_out_so))
        return True

    @api.one
    def last_data_state(self):
        cr = self._cr
        uid = self._uid
        ids = self._ids
        context = {}
        properties = []
        prod_obj = self.pool.get('mrp.production')
        finish_obj = self.pool.get('stock.data.finish.forecast')
        finish_obj.unlink(cr, SUPERUSER_ID, [line.id for line in self.data_finish_last], context=context)
        graph_obj = self.pool.get('stock.data.finish.graph')
        graph_srh = graph_obj.search(cr, uid, [])
        list_graph = []
        for item in graph_obj.browse(cr, uid, graph_srh, context=context):
            list_graph.append(item)
        graph_obj.unlink(cr, SUPERUSER_ID, [line.id for line in list_graph], context=context)
        data_state16 = {}
        data_state = {}
        item_list = []
        item_list_tms = []
        length_mean = {}
        date_start = datetime.strptime(self.date_start + " 00:00:00", "%Y-%m-%d %H:%M:%S")
        end_d = date_start
        stt_d = date_start - timedelta(days=90)
        for index in range(16)[::-1]:
            finish_dic = {}
            finish_dic_tms = {}
            for single_date in daterange(stt_d, end_d):
                date = single_date.strftime("%Y-%m-%d %H:%M:%S")
                date_fx = (single_date + timedelta(hours=23,minutes=59,seconds=59)).strftime("%Y-%m-%d %H:%M:%S")
                search = prod_obj.search(cr, uid, [
                    ('date_planned', '>=', date),
                    ('date_planned', '<=', date_fx),
                    ('state', '=', 'done'),
                    ])
                for prd in prod_obj.browse(cr, uid, search, context=context):
                    largeur = prd.largeur
                    hauteur = prd.hauteur
                    if prd.nb_division == 2:
                        div2 = 1.0 * prd.product_qty
                    else:
                        div2 = 0.0
                    if prd.nb_division >= 3:
                        div3 = 1.0 * prd.product_qty
                    else:
                        div3 = 0.0
                    if prd.intermediaire == 'avec':
                        inter = 1 * prd.product_qty
                    else:
                        inter = 0
                    if prd.moustiquaire == True:
                        moust = 1 * prd.product_qty
                    else:
                        moust = 0
                    if prd.style == 'en':
                        style = 1 * prd.product_qty
                    else:
                        style = 0
                    if prd.tms == 0.0:
                        for fin in prd.move_created_ids2:
                            fini_id = fin.product_id.id
                            if fini_id not in finish_dic.keys():
                                finish_dic[fini_id] = {}
                                finish_dic[fini_id]['name'] = fin.product_id.name
                                finish_dic[fini_id]['quantite'] = fin.product_uom_qty
                                finish_dic[fini_id]['occurency'] = 1
                            elif fini_id in finish_dic.keys():
                                finish_dic[fini_id]['quantite'] += fin.product_uom_qty
                                finish_dic[fini_id]['occurency'] += 1
                            if (fini_id,False) not in length_mean.keys():
                                length_mean[fini_id, False] = {}
                                length_mean[fini_id, False]['hauteur'] = hauteur
                                length_mean[fini_id, False]['largeur'] = largeur
                                length_mean[fini_id, False]['div2'] = div2
                                length_mean[fini_id, False]['div3'] = div3
                                length_mean[fini_id, False]['style'] = style
                                length_mean[fini_id, False]['quantite'] = fin.product_uom_qty
                                length_mean[fini_id, False]['moust'] = moust
                                length_mean[fini_id, False]['inter'] = inter
                            elif (fini_id,False) in length_mean.keys():
                                length_mean[fini_id, False]['hauteur'] = (length_mean[fini_id, False]['hauteur'] + hauteur)/2
                                length_mean[fini_id, False]['largeur'] = (length_mean[fini_id, False]['largeur']+ largeur)/2
                                length_mean[fini_id, False]['div2'] += div2
                                length_mean[fini_id, False]['div3'] += div3
                                length_mean[fini_id, False]['style'] += style
                                length_mean[fini_id, False]['quantite'] += fin.product_uom_qty
                                length_mean[fini_id, False]['moust'] += moust
                                length_mean[fini_id, False]['inter'] += inter


                    else:
                        for fin in prd.move_created_ids2:
                            fini_id = fin.product_id.id
                            if fini_id not in finish_dic_tms.keys():
                                finish_dic_tms[fini_id] = {}
                                finish_dic_tms[fini_id]['name'] = fin.product_id.name
                                finish_dic_tms[fini_id]['quantite'] = fin.product_uom_qty
                                finish_dic_tms[fini_id]['occurency'] = 1
                            elif fini_id in finish_dic_tms.keys():
                                finish_dic_tms[fini_id]['quantite'] += fin.product_uom_qty
                                finish_dic_tms[fini_id]['occurency'] += 1
                            if (fini_id,True) not in length_mean.keys():
                                length_mean[fini_id, True] = {}
                                length_mean[fini_id, True]['hauteur'] = hauteur
                                length_mean[fini_id, True]['largeur'] = largeur
                                length_mean[fini_id, True]['div2'] = div2
                                length_mean[fini_id, True]['div3'] = div3
                                length_mean[fini_id, True]['style'] = style
                                length_mean[fini_id, True]['quantite'] = fin.product_uom_qty
                                length_mean[fini_id, True]['moust'] = moust
                                length_mean[fini_id, True]['inter'] = inter
                            elif (fini_id,True) in length_mean.keys():
                                length_mean[fini_id, True]['hauteur'] = (length_mean[fini_id, True]['hauteur'] + hauteur)/2
                                length_mean[fini_id, True]['largeur'] = (length_mean[fini_id, True]['largeur']+ largeur)/2
                                length_mean[fini_id, True]['div2'] += div2
                                length_mean[fini_id, True]['div3'] += div3
                                length_mean[fini_id, True]['style'] += style
                                length_mean[fini_id, True]['quantite'] += fin.product_uom_qty
                                length_mean[fini_id, True]['moust'] += moust
                                length_mean[fini_id, True]['inter'] += inter
            data_state16[index] = finish_dic
            data_state[index] = finish_dic_tms
            end_d = stt_d
            stt_d = stt_d - timedelta(days=90)
        # pour les article normail
        for da in data_state16:
            for idx in data_state16[da].keys():
                if idx not in item_list:
                    item_list.append((idx,data_state16[da][idx]['name']))
        render_data = {}
        for idx,idname in item_list:
            render_data[(idx,idname)] = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
        for data in data_state16:
            for idx in data_state16[data]:
                idxname = data_state16[data][idx]['name']
                render_data[(idx,idxname)][data] = data_state16[data][idx]['quantite']

        mean_data = {}
        for data in render_data:
            mean_data[data] = prevision.get_moblile_data(render_data[data])

        mobile_data = {}
        for data in render_data:
            mobile_data[data] = prevision.get_moyenne_mobile(render_data[data])

        # pour les article avec tms
        for da in data_state:
            for idx in data_state[da].keys():
                if idx not in item_list_tms:
                    item_list_tms.append((idx,data_state[da][idx]['name']))
        render_data_tms = {}
        for idx,idname in item_list_tms:
            render_data_tms[(idx,idname)] = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
        for data in data_state:
            for idx in data_state[data]:
                idxname = data_state[data][idx]['name']
                render_data_tms[(idx,idxname)][data] = data_state[data][idx]['quantite']

        mean_data_tms = {}
        for data in render_data_tms:
            mean_data_tms[data] = prevision.get_moblile_data(render_data_tms[data])

        mobile_data_tms = {}
        for data in render_data_tms:
            mobile_data_tms[data] = prevision.get_moyenne_mobile(render_data_tms[data])
            

        # Réglage pourcentage de moustiquare de intermediaère

        for un in length_mean:
            quant = length_mean[un]['quantite']
            moust = length_mean[un]['moust']
            inter = length_mean[un]['inter']
            div2 = length_mean[un]['div2']
            div3 = length_mean[un]['div3']
            style = length_mean[un]['style']
            length_mean[un]['moust'] = (moust*100)/quant
            length_mean[un]['inter'] = (inter*100)/quant
            length_mean[un]['div2'] = (div2*100)/quant
            length_mean[un]['div3'] = (div3*100)/quant
            length_mean[un]['style'] = (style*100)/quant

        # prediction
        forecast_data = {}
        line_tendency = {}
        for idx,idname in render_data:
            prediction1, prediction2 = prevision.predict(render_data[(idx,idname)])
            x1,y1,x2,y2 = prevision.get_tendency(render_data[(idx,idname)])
            line_tendency[(idx,idname)] = [x1,x2,y1,y2]
            mean_data[(idx,idname)].append(prediction1)
            render_data[(idx,idname)].append(prediction2)
            mobile_data[(idx,idname)].append(0)
            if prediction1 > 0 or prediction2 > 0:
                forecast_data[(idx,idname)] = prediction1, prediction2
            elif prediction1 <= 0 or prediction2 <= 0:
                pass

        forecast_data_tms = {}
        line_tendency_tms = {}
        for idx,idname in render_data_tms:
            prediction1, prediction2 = prevision.predict(render_data_tms[(idx,idname)])
            x1,y1,x2,y2 = prevision.get_tendency(render_data_tms[(idx,idname)])
            line_tendency_tms[(idx,idname)] = [x1,x2,y1,y2]
            mean_data_tms[(idx,idname)].append(prediction1)
            render_data_tms[(idx,idname)].append(prediction2)
            mobile_data_tms[(idx,idname)].append(0)
            if prediction1 > 0 or prediction2 > 0:
                forecast_data_tms[(idx,idname)] = prediction1, prediction2
            elif prediction1 <= 0 or prediction2 <= 0:
                pass


        for f_id, f_name in forecast_data:
            q_no_season, q_season = forecast_data[(f_id, f_name)]
            #binimg = graph2img.tobinary(render_data[f_id, f_name],mobile_data[f_id, f_name][2:14],line_tendency[2:],line_tendency[:2])
            self.write({ 'data_finish_last' : [( 0, 0, {
                                'product_id': f_id,
                                'name' :  f_name,
                                'tms' : False,
                                'q_no_season': q_no_season,
                                'q_season': q_season,
                                'hauteur': length_mean[f_id,False]['hauteur'],
                                'largeur': length_mean[f_id,False]['largeur'],
                                'div2': length_mean[f_id,False]['div2'],
                                'div3': length_mean[f_id,False]['div3'],
                                'style': length_mean[f_id,False]['style'],
                                'moust': length_mean[f_id,False]['moust'],
                                'inter': length_mean[f_id,False]['inter'],
                                #'state': base64.b64encode(binimg)
                            })]
                        })
        for f_id, f_name in forecast_data_tms:
            q_no_season, q_season = forecast_data_tms[(f_id, f_name)]
            #binimg = graph2img.tobinary(render_data_tms[f_id, f_name],mobile_data_tms[f_id, f_name][2:14],line_tendency_tms[2:],line_tendency_tms[:2])
            self.write({ 'data_finish_last' : [( 0, 0, {
                                'product_id': f_id,
                                'name' :  f_name,
                                'tms' : True,
                                'q_no_season': q_no_season,
                                'q_season': q_season,
                                'hauteur': length_mean[f_id,True]['hauteur'],
                                'largeur': length_mean[f_id,True]['largeur'],
                                'div2': length_mean[f_id,True]['div2'],
                                'div3': length_mean[f_id,True]['div3'],
                                'style': length_mean[f_id,True]['style'],
                                'moust': length_mean[f_id,True]['moust'],
                                'inter': length_mean[f_id,True]['inter'],
                                #'state': base64.b64encode(binimg)
                            })]
                        })

        for fin in self.data_finish_last:
            for i in range(17):
                if fin.tms == False:
                    fin.write( {'graph': [(0, 0, {
                                    'finish_id': fin.id,
                                    'name': fin.name,
                                    'trimestre': i+1,
                                    'quantite' : render_data[fin.product_id.id,fin.name][i],
                                    'mean' : mean_data[fin.product_id.id,fin.name][i],
                                    'mobile' : mobile_data[fin.product_id.id,fin.name][i]
                                })]
                        })
                elif fin.tms == True:
                    fin.write( {'graph': [(0, 0, {
                                    'finish_id': fin.id,
                                    'name' : u'Porte ' + fin.name,
                                    'trimestre': i+1,
                                    'quantite' : render_data_tms[fin.product_id.id,fin.name][i],
                                    'mean' : mean_data_tms[fin.product_id.id,fin.name][i],
                                    'mobile' : mobile_data_tms[fin.product_id.id,fin.name][i]
                                })]
                        })

        return True

    @api.one
    def last_data_state2(self):
        cr = self._cr
        uid = self._uid
        ids = self._ids
        context = {}
        properties = []
        data_state16 = {}
        data_obj = self.pool.get('data_article_last')
        data_obj.unlink(cr, SUPERUSER_ID, [line.product_id for line in self.data_article_exist], context=context)
        prod_obj = self.pool.get('mrp.production')
        date_start = datetime.strptime(self.date_start + " 00:00:00", "%Y-%m-%d %H:%M:%S")
        end_d = date_start
        stt_d = date_start - timedelta(days=90)
        for index in range(16)[::-1]:
            consummed_dic = {}
            for single_date in daterange(stt_d, end_d):
                date = single_date.strftime("%Y-%m-%d %H:%M:%S")
                date_fx = (single_date + timedelta(hours=23,minutes=59,seconds=59)).strftime("%Y-%m-%d %H:%M:%S")
                search = prod_obj.search(cr, uid, [
                    ('date_planned', '>=', date),
                    ('date_planned', '<=', date_fx),
                    ('state', '=', 'done'),
                    ])
                for prd in prod_obj.browse(cr, uid, search, context=context):
                    for line2 in prd.move_lines2:
                        prod_id = line2.product_id
                        name = prod_id.name
                        if u'Vitre' not in name:
                            if prod_id not in consummed_dic.keys():
                                consummed_dic[prod_id] = {}
                                consummed_dic[prod_id]['name'] = prod_id.name
                                consummed_dic[prod_id]['quantite'] = line2.product_uom_qty
                            elif prod_id in consummed_dic.keys():
                                consummed_dic[prod_id]['quantite'] += line2.product_uom_qty
            data_state16[index] = consummed_dic
            end_d = stt_d
            stt_d = stt_d - timedelta(days=90)

        # pour les article normail
        item_list = []
        for da in data_state16:
            for idx in data_state16[da].keys():
                if idx not in item_list:
                    item_list.append((idx,data_state16[da][idx]['name']))
        render_data = {}
        for idx,idname in item_list:
            render_data[(idx,idname)] = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
        for data in data_state16:
            for idx in data_state16[data]:
                idxname = data_state16[data][idx]['name']
                render_data[(idx,idxname)][data] = data_state16[data][idx]['quantite']

        # prediction
        forecast_data = {}
        for idx,idname in render_data:
            prediction1, prediction2 = prevision.predict(render_data[(idx,idname)])
            if prediction1 > 0 and prediction2 > 0:
                forecast_data[(idx,idname)] = prediction1, prediction2
            elif prediction1 <= 0 or prediction2 <= 0:
                pass

        for f_id, f_name in forecast_data:
            q_no_season, q_season = forecast_data[(f_id, f_name)]
            self.write({ 'data_article_last' : [( 0, 0, {
                                'product_id': f_id,
                                'name' :  f_name,
                                'qu_no_season': q_no_season,
                                'qu_season': q_season,
                            })]
                        })

    @api.one
    def product2articles(self):
        cr = self._cr
        uid = self._uid
        ids = self._ids
        context = {}
        properties = []
        bom = self.pool.get("mrp.bom")
        component = self.pool.get('mrp.component')
        product_no_season = []
        product_season = []
        profile_no = {}
        vitre_no = {}
        accessoire_no = {}
        profile = {}
        vitre = {}
        accessoire = {}
        quantite_future = ord()
        quantite_name = {}
        article_obj = self.pool.get('stock.data.article.list')
        article_obj.unlink(cr, SUPERUSER_ID, [line.id for line in self.data_article_last], context=context)
        for product in self.data_finish_last:
            qty = product.q_no_season
            qty_s = product.q_season
            if product.name in [u'Projetant',u'A soufflet',u'A soufflet',u'Naco']:
                div2 = int(round((product.div2/100)*qty,0))
                div2_s = int(round((product.div2/100)*qty_s,0))
                qty -= div2
                qty_s -= div2_s
                if div2 > 0 or div2_s > 0:
                    localdict = {}
                    localdict['largeur'] = round(product.largeur, 2)
                    localdict['hauteur'] = round(product.hauteur, 2)
                    localdict['tms'] = 15.0 if product.tms else 0.0
                    localdict['result'] = None
                    localdict['style'] = 'fr'
                    localdict['vitre'] = False
                    localdict['type_vitre'] = 0
                    localdict['inter'] = 'sans'
                    localdict['moust'] = False
                    localdict['nb_div'] = 2.0
                    localdict['div'] = True
                    localdict['type_inter'] = 'vert'
                    localdict['batis'] = False
                    if div2 > 0:
                        product_no_season.append((product.product_id.id,product.name,localdict,div2))
                    if div2_s > 0:
                        product_season.append((product.product_id.id,product.name,localdict,div2_s))
            if product.name in [u'Projetant',u'A soufflet',u'A soufflet',u'Naco']:
                div3 = int(round((product.div3/100)*qty,0))
                div3_s = int(round((product.div3/100)*qty_s,0))
                qty -= div3
                qty_s -= div3_s
                if div3 > 0 or div3_s > 0:
                    localdict = {}
                    localdict['largeur'] = round(product.largeur, 2)
                    localdict['hauteur'] = round(product.hauteur, 2)
                    localdict['tms'] = 15.0 if product.tms else 0.0
                    localdict['result'] = None
                    localdict['style'] = 'fr'
                    localdict['vitre'] = False
                    localdict['type_vitre'] = 0
                    localdict['inter'] = 'sans'
                    localdict['moust'] = False
                    localdict['nb_div'] = 3.0
                    localdict['div'] = True
                    localdict['type_inter'] = 'vert'
                    localdict['batis'] = False
                    if div3 > 0:
                        product_no_season.append((product.product_id.id,product.name,localdict,div3))
                    if div3_s > 0:
                        product_season.append((product.product_id.id,product.name,localdict,div3_s))
            if product.name in [u'Coulissante 1VTL',u'Coulissante 2VTX',u'Coulissante 3VTX',u'Coulissante 4VTX',u'A soufflet',u'Naco',u'Fenêtre ouvrante 1VTL',u'Fenêtre ouvrante 2VTX']:
                moustqt = int(round((product.moust/100)*qty,0))
                qty -= moustqt
                moustqt_s = int(round((product.moust/100)*qty_s,0))
                qty_s -= moustqt_s
                if moustqt > 0 or moustqt_s > 0:
                    localdict = {}
                    localdict['largeur'] = round(product.largeur, 2)
                    localdict['hauteur'] = round(product.hauteur, 2)
                    localdict['tms'] = 15.0 if product.tms else 0.0
                    localdict['result'] = None
                    localdict['style'] = 'fr'
                    localdict['vitre'] = False
                    localdict['type_vitre'] = 0
                    localdict['inter'] = 'sans'
                    localdict['moust'] = True
                    localdict['nb_div'] = 1.0
                    localdict['div'] = False
                    localdict['type_inter'] = 'vert'
                    localdict['batis'] = u'T 60 K B'
                    if moustqt > 0:
                        product_no_season.append((product.product_id.id,product.name,localdict,moustqt))
                    if moustqt_s > 0:
                        product_season.append((product.product_id.id,product.name,localdict,moustqt_s))
            if product.name in [u'Porte ouvrante 1VTL',u'Porte ouvrante 2VTX',u'Coulissante 1VTL',u'Coulissante 2VTX',u'Coulissante 4VTX']:
                interqt = int(round((product.inter/100)*qty,0))
                qty -= interqt
                interqt_s = int(round((product.inter/100)*qty_s,0))
                qty_s -= interqt_s
                if interqt > 0 or interqt_s > 0:
                    localdict = {}
                    localdict['largeur'] = round(product.largeur, 2)
                    localdict['hauteur'] = round(product.hauteur, 2)
                    localdict['tms'] = 15.0 if product.tms else 0.0
                    localdict['result'] = None
                    localdict['style'] = 'fr'
                    localdict['vitre'] = False
                    localdict['type_vitre'] = 0
                    localdict['inter'] = 'avec'
                    localdict['moust'] = False
                    localdict['nb_div'] = 1.0
                    localdict['div'] = False
                    localdict['type_inter'] = 'horiz'
                    localdict['batis'] = False
                    if interqt > 0:
                        product_no_season.append((product.product_id.id,product.name,localdict,interqt))
                    if interqt_s > 0:
                        product_season.append((product.product_id.id,product.name,localdict,interqt_s))
            if product.name in [u'Porte ouvrante 1VTL',u'Porte ouvrante 2VTX',u'Fenêtre ouvrante 1VTL',u'Fenêtre ouvrante 2VTX']:
                styleqt = int(round((product.style/100)*qty,0))
                qty -= styleqt
                styleqt_s = int(round((product.style/100)*qty_s,0))
                qty_s -= styleqt_s
                if styleqt > 0 or styleqt_s > 0:
                    localdict = {}
                    localdict['largeur'] = round(product.largeur, 2)
                    localdict['hauteur'] = round(product.hauteur, 2)
                    localdict['tms'] = 15.0 if product.tms else 0.0
                    localdict['result'] = None
                    localdict['style'] = 'en'
                    localdict['vitre'] = False
                    localdict['type_vitre'] = 0
                    localdict['inter'] = 'avec'
                    localdict['moust'] = False
                    localdict['nb_div'] = 1.0
                    localdict['div'] = False
                    localdict['type_inter'] = 'horiz'
                    localdict['batis'] = False
                    if styleqt > 0:
                        product_no_season.append((product.product_id.id,product.name,localdict,styleqt))
                    if styleqt_s > 0:
                        product_season.append((product.product_id.id,product.name,localdict,styleqt_s))
            if qty > 0 or qty_s > 0:
                localdict = {}
                localdict['largeur'] = round(product.largeur, 2)
                localdict['hauteur'] = round(product.hauteur, 2)
                localdict['tms'] = 15.0 if product.tms else 0.0
                localdict['result'] = None
                localdict['style'] = 'fr'
                localdict['vitre'] = False
                localdict['type_vitre'] = 0
                localdict['inter'] = 'sans'
                localdict['moust'] = False
                localdict['nb_div'] = 1.0
                localdict['div'] = True
                localdict['type_inter'] = 'vert'
                localdict['batis'] = u'T 60 K B'
                if qty > 0:
                    product_no_season.append((product.product_id.id,product.name,localdict,qty))
                if qty_s > 0:
                    product_season.append((product.product_id.id,product.name,localdict,qty_s))

        for idx,xname,localdict,qty in product_no_season:
            component_id_list = []
            bom_sr = bom.search(cr, uid, [('product_id','=',idx)])
            bom_br = bom.browse(cr, uid, bom_sr, context=context)
            if bom_br:
                bom_lines = bom_br[0].bom_line_ids
                for line in bom_lines:
                    component_id_list.append(line.component_id)
                list_id = component.search(cr, uid, [('id','in',component_id_list)])
            else:
                if xname != 'Coulissante 1VTL':
                    raise osv.except_osv("bom_br",xname)
            l = {}
            for c in component.browse(cr, uid, list_id, context=context):
                            total1 = 0.0
                            total2 = 0.0
                            
                            len_total0 = 0.0
                            len_unit0 =0.0
                            qty_total0 = 0.0
                            #Insértion de tous les sous-composants pour l'impression
                            for s in c.sub_component_ids:
                                localdict['Q'] = qty
                                
                                safe_eval(s.python_product_qty, localdict, mode='exec', nocopy=True)
                                product_qty = float(localdict['result'])
                                ##################################
                                #l['production_id'] = production.id
                                l['product_qty'] = product_qty
                                
                                localdict['QU'] = product_qty
                                
                                product_qty0 = product_qty
                                
                                safe_eval(s.python_product_qty_total, localdict, mode='exec', nocopy=True)
                                product_qty_total = float(localdict['result'])
                                
                                l['product_qty_total'] = product_qty_total
                                #l['product_qty_total'] = qty * l['product_qty']
                                
                                qty_total0 = product_qty_total
                                
                                localdict['QT'] = l['product_qty_total']
                                
                                total2 = total2 + l['product_qty_total']
                                if not c.line_id.is_accessory:
                                    l['ref'] = c.product_parent_id
                                    safe_eval(s.python_len_unit, localdict, mode='exec', nocopy=True)
                                    len_unit = float(localdict['result'])
                                    l['len_unit'] = len_unit
                                    
                                    localdict['LU'] = l['len_unit']
                                    
                                    #l['len_total'] = l['len_unit'] * l['product_qty_total']
                                    
                                    safe_eval(s.python_len_total, localdict, mode='exec', nocopy=True)
                                    len_total = float(localdict['result'])
                                    
                                    l['len_total'] = len_total
                                    
                                    len_total0 = len_total
                                    
                                    total1 = total1 + l['len_total']
                                    
                                    LU = l['len_unit']
                                    LT = l['len_total']
                                    
                                    len_unit0 = l['len_unit']

                                    if l['len_total']!=0.0:
                                        if s.name in ['VITRE','Vitre','vitre']:
                                            if l['ref'].id not in vitre_no.keys():
                                                vitre_no[l['ref'].id] = []
                                                quantite_name[l['ref'].id] = c.product_parent_id.name
                                            vitre_no[l['ref'].id].append((l['len_unit'],l['len_total'],l['product_qty_total']))
                                        else:
                                            if l['ref'].id not in profile_no.keys():
                                                profile_no[l['ref'].id] = []
                                                quantite_name[l['ref'].id] = c.product_parent_id.name
                                            profile_no[l['ref'].id].append((l['len_unit'],l['product_qty_total']))
                                else:
                                    if l['product_qty_total']!=0.0:
                                        l['ref'] = c.product_parent_id
                                        if l['ref'].id not in accessoire_no.keys():
                                            accessoire_no[l['ref'].id] = []
                                            quantite_name[l['ref'].id] = c.product_parent_id.name
                                        accessoire_no[l['ref'].id].append(l['product_qty_total'])
                                l = {}

        for idx,xname,localdict,qty in product_season:
            component_id_list =[]
            bom_sr = bom.search(cr, uid, [('product_id','=',idx)])
            bom_br = bom.browse(cr, uid, bom_sr, context=context)
            if bom_br:
                bom_lines = bom_br[0].bom_line_ids
                for line in bom_lines:
                    component_id_list.append(line.component_id)
                list_id = component.search(cr, uid, [('id','in',component_id_list)])
            l = {}
            for c in component.browse(cr, uid, list_id, context=context):
                            total1 = 0.0
                            total2 = 0.0
                            
                            len_total0 = 0.0
                            len_unit0 =0.0
                            qty_total0 = 0.0
                            #Insértion de tous les sous-composants pour l'impression
                            for s in c.sub_component_ids:
                                localdict['Q'] = qty
                                
                                safe_eval(s.python_product_qty, localdict, mode='exec', nocopy=True)
                                product_qty = float(localdict['result'])
                                ##################################
                                #l['production_id'] = production.id
                                l['product_qty'] = product_qty
                                
                                localdict['QU'] = product_qty
                                
                                product_qty0 = product_qty
                                
                                safe_eval(s.python_product_qty_total, localdict, mode='exec', nocopy=True)
                                product_qty_total = float(localdict['result'])
                                
                                l['product_qty_total'] = product_qty_total
                                #l['product_qty_total'] = qty * l['product_qty']
                                
                                qty_total0 = product_qty_total
                                
                                localdict['QT'] = l['product_qty_total']
                                
                                total2 = total2 + l['product_qty_total']

                                if not c.line_id.is_accessory:
                                    l['ref'] = c.product_parent_id
                                    safe_eval(s.python_len_unit, localdict, mode='exec', nocopy=True)
                                    len_unit = float(localdict['result'])
                                    l['len_unit'] = len_unit
                                    
                                    localdict['LU'] = l['len_unit']
                                    
                                    #l['len_total'] = l['len_unit'] * l['product_qty_total']
                                    
                                    safe_eval(s.python_len_total, localdict, mode='exec', nocopy=True)
                                    len_total = float(localdict['result'])
                                    
                                    l['len_total'] = len_total
                                    
                                    len_total0 = len_total
                                    
                                    total1 = total1 + l['len_total']
                                    
                                    LU = l['len_unit']
                                    LT = l['len_total']
                                    
                                    len_unit0 = l['len_unit']
                                    
                                    if l['len_total']!=0.0:
                                        if s.name in ['VITRE','Vitre','vitre']:
                                            if l['ref'].id not in vitre.keys():
                                                vitre[l['ref'].id] = []
                                                quantite_name[l['ref'].id] = c.product_parent_id.name
                                            vitre[l['ref'].id].append((l['len_unit'],l['len_total'],l['product_qty_total']))
                                        else:
                                            if l['ref'].id not in profile.keys():
                                                profile[l['ref'].id] = []
                                                quantite_name[l['ref'].id] = c.product_parent_id.name
                                            profile[l['ref'].id].append((l['len_unit'],l['product_qty_total']))
                                else:
                                    if l['product_qty_total']!=0.0:
                                        l['ref'] = c.product_parent_id
                                        if l['ref'].id not in accessoire.keys():
                                            accessoire[l['ref'].id] = []
                                            quantite_name[l['ref'].id] = c.product_parent_id.name
                                        accessoire[l['ref'].id].append(l['product_qty_total'])
                                l = {}
        quantite_future['no_season'] = ord()
        quantite_future['season'] = ord()
        for i in profile_no:
            quantite_future['no_season'][i] = linearsolver.optimise(profile_no[i],5800)
        for j in vitre_no:
            quantite_future['no_season'][j] = rectsolver.optimise(quantite_name[j],vitre_no[j])
        for k in accessoire_no:
            quantite_future['no_season'][k] = linearsolver.sum(accessoire_no[k])
        for i in profile:
            quantite_future['season'][i] = linearsolver.optimise(profile[i],5800)
        for j in vitre:
            quantite_future['season'][j] = rectsolver.optimise(quantite_name[j],vitre[j])
        for k in accessoire:
            quantite_future['season'][k] = linearsolver.sum(accessoire[k])
        #raise osv.except_osv("Error", (str(quantite_future),str(quantite_name)))
        vals = []
        for q_id in quantite_future['no_season']:
            val = {
                'product_id': q_id,
                'name' :  quantite_name[q_id],
                'qu_no_season': float(quantite_future['no_season'][q_id]),
                'qu_no_month': float(quantite_future['no_season'][q_id])/3,
                'qu_season': float(quantite_future['season'][q_id]) if q_id in quantite_future['season'].keys() else 0.0,
                'qu_month' : (float(quantite_future['season'][q_id]) if q_id in quantite_future['season'].keys() else 0.0)/3,
                'access': True if q_id in accessoire.keys() or q_id in accessoire_no.keys() else False
            }
            vals.append(val)
        self.write({ 'data_article_last': [(0, 0, val) for val in vals]})




