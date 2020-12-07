{
    # App information
    'name': 'Trivicity ERP',
    'version': '14.0.0',
    'license': 'OPL-1',    
    'author': u'Silentinfotech Pvt. Ltd.',
    'website': '',
    # Dependencies
    'depends': ['base', 'sale', 'account_asset', 'account_check_printing'],
    
    # Views
    'init_xml': [],
    'data': [
        'security/ir.model.access.csv',
        'view/crm_tag_view.xml',
        'view/res_partner_view.xml',
        'view/asset_type_view.xml',
        'view/account_asset_view.xml',
        'view/account_payment_view.xml',
             ],
    'demo_xml': [],
    
    # Odoo Store Specific
    'images': [],
    
    'installable': True,
    'auto_install': False,
    'application' : True,
}
