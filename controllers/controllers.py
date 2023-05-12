# -*- coding: utf-8 -*-
# from odoo import http


# class AutoBackupOdoosh(http.Controller):
#     @http.route('/auto_backup_odoosh/auto_backup_odoosh/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/auto_backup_odoosh/auto_backup_odoosh/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('auto_backup_odoosh.listing', {
#             'root': '/auto_backup_odoosh/auto_backup_odoosh',
#             'objects': http.request.env['auto_backup_odoosh.auto_backup_odoosh'].search([]),
#         })

#     @http.route('/auto_backup_odoosh/auto_backup_odoosh/objects/<model("auto_backup_odoosh.auto_backup_odoosh"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('auto_backup_odoosh.object', {
#             'object': obj
#         })
