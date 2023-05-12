# -*- coding: utf-8 -*-
{
    'name': "auto_backup_odoosh",

    'summary': """
        Auto backup for ODOO.sh""",

    'description': """
        This is an addon for auto_backup that adds functionality for ODOO.sh
    """,

    'author': "Guru d.o.o.",
    'website': "https://www.guru.si",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Technical',
    'version': '15.0.0.1.0',
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['base', 'auto_backup'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/backup_view.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
