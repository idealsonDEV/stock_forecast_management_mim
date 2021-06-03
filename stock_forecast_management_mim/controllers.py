# -*- coding: utf-8 -*-
from openerp import http

# class StockForecastManagementMim(http.Controller):
#     @http.route('/stock_forecast_management_mim/stock_forecast_management_mim/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/stock_forecast_management_mim/stock_forecast_management_mim/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('stock_forecast_management_mim.listing', {
#             'root': '/stock_forecast_management_mim/stock_forecast_management_mim',
#             'objects': http.request.env['stock_forecast_management_mim.stock_forecast_management_mim'].search([]),
#         })

#     @http.route('/stock_forecast_management_mim/stock_forecast_management_mim/objects/<model("stock_forecast_management_mim.stock_forecast_management_mim"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('stock_forecast_management_mim.object', {
#             'object': obj
#         })