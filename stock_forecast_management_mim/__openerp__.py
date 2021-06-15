# -*- coding: utf-8 -*-
{
    'name': "stock_forecast_management_mim",

    'summary': """
        Gestion des stocks prévisionnelle pour la société MIM""",

    'description': """
        Gestsion des stocks pour la société MIM:
         - Etablir des statistique sur la consommation journalière, monsuelle et annuelle
         - Etablir avec les commande en attente de production les quantités d'article à consommer sur 3 mois
         - Prévoir les quantités d'article à consommer sur 3 mois
    """,

    'author': "Ingenosya (RATSIMANANDOKA Andriamahery Idéalison)",
    'website': "http://www.mim-madagascar.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Manufacturing',
    'version': '1.0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','mrp','stock'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'sotck_data_view.xml',
        'data_minimal.xml'
        #'templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        #'demo.xml',
    ],
}