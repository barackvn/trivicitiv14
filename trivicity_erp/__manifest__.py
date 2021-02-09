{
    # App information
    'name': 'Trivicity ERP',
    'version': '14.0.0',
    'license': 'OPL-1',    
    'author': u'Silentinfotech Pvt. Ltd.',
    'website': '',
    # Dependencies
    'depends': ['base', 'sale', 'account_asset', 'account_check_printing','mrp', 'mrp_workorder', 'shopify_ept'],
    
    # Views
    'init_xml': [],
    'data': [
        'security/ir.model.access.csv',
        # 'security/security.xml',
        'data/ir_sequence.xml',
        'data/ir_cron_data.xml',
        'view/assets.xml',
        'view/crm_tag_view.xml',
        'view/res_partner_view.xml',
        'view/asset_type_view.xml',
        'view/account_asset_view.xml',
        'view/account_payment_view.xml',
        'view/box_package_view.xml',
        'view/mrp_production_view.xml',
        'view/mrp_workcenter_view.xml',
        'view/mrp_workorder_view.xml',
        'view/stock_scrap_views.xml',
        'view/stock_picking_view.xml',
        
             ],
    'demo_xml': [],
    
    # Odoo Store Specific
    'images': [],
    
    'installable': True,
    'auto_install': False,
    'application' : True,
}
