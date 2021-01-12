# -*- coding: utf-8 -*-

import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, AccessError
from xlrd import open_workbook
import base64
import openpyxl
from tempfile import TemporaryFile


class BoxPackage(models.Model):
    _name = 'box.package'
    _description='Box Packaging'
    _rec_name = 'name'
    _order = 'id desc'

    @api.model
    def default_get(self, fields):
        res = super(BoxPackage, self).default_get(fields)
        res['filename'] = None
        return res


    @api.model
    def _get_default_date_planned_start(self):
        if self.env.context.get('default_date_deadline'):
            return fields.Datetime.to_datetime(self.env.context.get('default_date_deadline'))
        return datetime.datetime.now()

    @api.model
    def _get_default_picking_type(self):
        company_id = self.env.context.get('default_company_id', self.env.company.id)
        return self.env['stock.picking.type'].search([
            ('code', '=', 'mrp_operation'),
            ('warehouse_id.company_id', '=', company_id),
        ], limit=1).id

    @api.model
    def _get_default_location_src_id(self):
        location = False
        company_id = self.env.context.get('default_company_id', self.env.company.id)
        if self.env.context.get('default_picking_type_id'):
            location = self.env['stock.picking.type'].browse(self.env.context['default_picking_type_id']).default_location_src_id
        if not location:
            location = self.env['stock.warehouse'].search([('company_id', '=', company_id)], limit=1).lot_stock_id
        return location and location.id or False

    @api.model
    def _get_default_location_dest_id(self):
        location = False
        company_id = self.env.context.get('default_company_id', self.env.company.id)
        if self._context.get('default_picking_type_id'):
            location = self.env['stock.picking.type'].browse(self.env.context['default_picking_type_id']).default_location_dest_id
        if not location:
            location = self.env['stock.warehouse'].search([('company_id', '=', company_id)], limit=1).lot_stock_id
        return location and location.id or False
    
    name = fields.Char('Reference', readonly=True, default=lambda x: _('New'), copy=False)
    product_id = fields.Many2one('product.product', 'Product', domain="[('id', 'in', allowed_product_ids)]")
    allowed_product_ids = fields.Many2many('product.product', compute='_compute_allowed_product_ids')
    product_qty = fields.Float('Quantity To Produce', default=1.0, digits='Product Unit of Measure')
    bom_id = fields.Many2one('mrp.bom', 'Bill of Material', domain="""[
        '&',
            '|',
                ('company_id', '=', False),
                ('company_id', '=', company_id),
            '&',
                '|',
                    ('product_id','=',product_id),
                    '&',
                        ('product_tmpl_id.product_variant_ids','=',product_id),
                        ('product_id','=',False),
        ('type', '=', 'normal')]""",
        check_company=True)
    product_uom_id = fields.Many2one('uom.uom', 'Product Unit of Measure', readonly=True, required=True,
        states={'draft': [('readonly', False)]}, domain="[('category_id', '=', product_uom_category_id)]")
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')        
    date_planned_start = fields.Datetime('Scheduled Date',default=_get_default_date_planned_start)
    product_tmpl_id = fields.Many2one('product.template', 'Product Template', related='product_id.product_tmpl_id')
    user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self.env.user, states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        domain=lambda self: [('groups_id', 'in', self.env.ref('mrp.group_mrp_user').id)])
    upload_file = fields.Binary('Upload File', states={'done': [('readonly', True)], 'cancel': [('readonly', True)]} ,copy=False)
    filename = fields.Char(copy=False)
    move_raw_ids = fields.One2many('box.package.move', 'raw_material_box_package_id', string='Components', copy=True)
    picking_type_id = fields.Many2one(
        'stock.picking.type', 'Operation Type',default=_get_default_picking_type, domain="[('code', '=', 'mrp_operation'), ('company_id', '=', company_id)]", required=True)
    origin = fields.Char('Source', copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Canceled')], string='State',copy=False, default="draft")
    company_id = fields.Many2one(
        'res.company', 'Company', default=lambda self: self.env.company,
        index=True, required=True)
    location_src_id = fields.Many2one(
        'stock.location', 'Components Location',
        default=_get_default_location_src_id,
        readonly=True, required=True,
        domain="[('usage','=','internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        states={'draft': [('readonly', False)]}, check_company=True)
    location_dest_id = fields.Many2one(
        'stock.location', 'Finished Products Location',
        default=_get_default_location_dest_id,
        readonly=True, required=True,
        domain="[('usage','=','internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        states={'draft': [('readonly', False)]}, check_company=True)
    mo_count = fields.Integer(compute='compute_mo_count')

    @api.onchange('upload_file', 'filename')
    def _onchange_upload_file(self):
        if not self.state == 'draft':            
            mo_objs = self.env['mrp.production'].search([('box_package_id', '=', self.name),('state','not in',('draft','cancel'))])            
            if mo_objs:
                for mo in mo_objs:
                    if mo.unreserve_visible == True or mo.state in ('to_close','progress','confirm'):
                        ans = mo.button_unreserve()
                        for move in mo.move_raw_ids:                            
                            for move_line in move.move_line_ids:                                
                                move_line.write({
                                    'qty_done': move_line.product_uom_qty
                                })
                        if mo.product_id.tracking == 'serial':
                            mo.write({'qty_producing': 0 })
                
    def action_view_mo(self):
        mo_obj = self.env['mrp.production'].search([('box_package_id', '=', self.id)])
        mo_ids = []
        view_id = self.env.ref('mrp.mrp_production_form_view').id
        for each in mo_obj:
            mo_ids.append(each.id)
        if len(mo_ids) <= 1:
            return {
                'name': _('Manufacturing Orders'),
                'res_model': 'mrp.production',
                'view_mode': 'form',
                'view_type': 'form',
                'view_id': view_id,                 
                'type': 'ir.actions.act_window',
                'domain': [('box_package_id','=',self.id)],
                'res_id': mo_ids and mo_ids[0]
            }
        else:
            return {
                'name': _('Manufacturing Orders'),
                'res_model': 'mrp.production',
                'type': 'ir.actions.act_window',
                'view_mode': 'tree,form',
                'domain': [('box_package_id','=',self.id)],
            }

    def compute_mo_count(self):
        for record in self:
            record.mo_count = self.env['mrp.production'].search_count(
                [('box_package_id', '=', self.id)])
    
    @api.onchange('picking_type_id')
    def onchange_picking_type(self):
        location = self.env.ref('stock.stock_location_stock')
        try:
            location.check_access_rule('read')
        except (AttributeError, AccessError):
            location = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1).lot_stock_id
        self.location_src_id = self.picking_type_id.default_location_src_id.id or location.id
        self.location_dest_id = self.picking_type_id.default_location_dest_id.id or location.id


    @api.depends('product_id', 'bom_id', 'company_id')
    def _compute_allowed_product_ids(self):
        for record in self:
            product_domain = [
                ('type', 'in', ['product', 'consu']),
                '|',
                    ('company_id', '=', False),
                    ('company_id', '=', record.company_id.id)
            ]
            if record.bom_id:
                if record.bom_id.product_id:
                    product_domain += [('id', '=', record.bom_id.product_id.id)]
                else:
                    product_domain += [('id', 'in', record.bom_id.product_tmpl_id.product_variant_ids.ids)]
            record.allowed_product_ids = self.env['product.product'].search(product_domain)

    @api.onchange('bom_id')
    def _onchange_bom_id(self):
        if not self.product_id and self.bom_id:
            self.product_id = self.bom_id.product_id or self.bom_id.product_tmpl_id.product_variant_ids[0]
        self.product_qty = self.bom_id.product_qty or 1.0
        self.product_uom_id = self.bom_id and self.bom_id.product_uom_id.id or self.product_id.uom_id.id
        self.move_raw_ids = [(2, move.id) for move in self.move_raw_ids.filtered(lambda m: m.bom_line_id)]
        self.picking_type_id = self.bom_id.picking_type_id or self.picking_type_id

    @api.onchange('product_id', 'picking_type_id', 'company_id')
    def onchange_product_id(self):
        """ Finds UoM of changed product. """
        if not self.product_id:
            self.bom_id = False
        elif not self.bom_id or self.bom_id.product_tmpl_id != self.product_tmpl_id or (self.bom_id.product_id and self.bom_id.product_id != self.product_id):
            bom = self.env['mrp.bom']._bom_find(product=self.product_id, picking_type=self.picking_type_id, company_id=self.company_id.id, bom_type='normal')
            if bom:
                self.bom_id = bom.id
                self.product_qty = self.bom_id.product_qty
                self.product_uom_id = self.bom_id.product_uom_id.id
            else:
                self.bom_id = False
                self.product_uom_id = self.product_id.uom_id.id

    @api.onchange('bom_id', 'product_id', 'product_qty', 'product_uom_id')
    def _onchange_move_raw(self):
        if not self.bom_id and not self._origin.product_id:
            return
        # Clear move raws if we are changing the product. In case of creation (self._origin is empty),
        # we need to avoid keeping incorrect lines, so clearing is necessary too.
        if self.product_id != self._origin.product_id:
            self.move_raw_ids = [(5,)]
        if self.bom_id and self.product_qty > 0:
            # keep manual entries
            list_move_raw = [(4, box_move.id) for box_move in self.move_raw_ids.filtered(lambda m: not m.bom_line_id)]            
            moves_raw_values = self._get_moves_raw_values()            
            move_raw_dict = {move.bom_line_id.id: move for move in self.move_raw_ids.filtered(lambda m: m.bom_line_id)}            
            for move_raw_values in moves_raw_values:
                if move_raw_values['bom_line_id'] in move_raw_dict:
                    # update existing entries
                    list_move_raw += [(1, move_raw_dict[move_raw_values['bom_line_id']].id, move_raw_values)]
                else:
                    # add new entries
                    list_move_raw += [(0, 0, move_raw_values)]            
            self.move_raw_ids = list_move_raw
        else:
            self.move_raw_ids = [(2, move.id) for move in self.move_raw_ids.filtered(lambda m: m.bom_line_id)]

    def _get_moves_raw_values(self):
        moves = []
        for production in self:
            factor = production.product_uom_id._compute_quantity(production.product_qty, production.bom_id.product_uom_id) / production.bom_id.product_qty
            boms, lines = production.bom_id.explode(production.product_id, factor, picking_type=production.bom_id.picking_type_id)
            for bom_line, line_data in lines:
                if bom_line.child_bom_id and bom_line.child_bom_id.type == 'phantom' or\
                        bom_line.product_id.type not in ['product', 'consu']:
                    continue
                operation = bom_line.operation_id.id or line_data['parent_line'] and line_data['parent_line'].operation_id.id
                moves.append(production._get_move_raw_values(
                    bom_line.product_id,
                    line_data['qty'],
                    bom_line.product_uom_id,
                    operation,
                    bom_line
                ))
        return moves

    def _get_move_raw_values(self, product_id, product_uom_qty, product_uom, operation_id=False, bom_line=False):
        data = {
            'bom_line_id': bom_line.id if bom_line else False,
            'product_id': product_id.id,
            'product_uom_qty': product_uom_qty,
            'product_uom': product_uom.id,
            'raw_material_box_package_id': self.id,
            'origin': self.name,
            'company_id': self.company_id.id,
        }
        return data
    
    @api.model
    def create(self,vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('box.package') or _('New')
        result = super(BoxPackage, self).create(vals)
        return result

    def button_done(self):
        if not self.state == 'draft':
            mo_objs = self.env['mrp.production'].search([('box_package_id', '=', self.name),('state','in',('confirmed','progress','to_close'))])            
            if mo_objs:
                if any(production.reservation_state != 'assigned' for production in mo_objs):
                    raise UserError(_('Please first reserve stock for all the manufacturing order using "Check Availability" feature.'))
                if all(production.reservation_state == 'assigned' for production in mo_objs):
                    for mo in mo_objs:
                        wiz_act = mo.button_mark_done()
                        # print("wiz_act",wiz_act)
                         # if wiz_act:
                    #     wiz = self.env[wiz_act['res_model']].browse(wiz_act['context']['params']['id'])
                    #     ans = wiz.process()
                    #     print("ans",wiz_act, wiz, ans)

                if all(production.state == 'done' for production in mo_objs):
                    self.write({'state': 'done'})
                   
    def action_cancel(self):
        mo_obj = self.env['mrp.production'].search([('box_package_id', '=', self.id)])
        if mo_obj:
           for rec in mo_obj:
               rec.update({'state':'cancel'})
        return self.write({'state': 'cancel'})

    def action_confirm(self):
        list_create_mo = []
        for rec in range(int(self.product_qty)):
            rec=rec+1
            lst = []
            for i in self.move_raw_ids:
                lst.append((0, 0, {
                        'name': self.name,
                        'product_id': i.product_id.id,
                        'product_uom_qty': i.product_uom_qty / self.product_qty,
                        'product_uom': i.product_uom.id,
                        'company_id': i.company_id.id,
                        'location_id': self.location_src_id.id,
                        'location_dest_id': self.product_id.with_company(self.company_id).property_stock_production.id,
                        'bom_line_id': i.bom_line_id.id if i.bom_line_id else False,
                        'warehouse_id': self.location_src_id.get_warehouse().id,
                        'procure_method': 'make_to_stock',
                }))
            mrp_vales = {
                    'product_id': self.product_id.id,
                    'product_uom_id': self.product_id.uom_id.id,
                    'company_id': self.company_id.id,
                    'bom_id': self.bom_id.id,
                    'product_qty': 1,
                    'picking_type_id': self.picking_type_id.id,
                    'user_id': self.user_id.id,
                    'date_planned_start': self.date_planned_start,
                    'origin': self.origin,
                    'box_package_id': self.id,
                    'location_src_id': self.location_src_id.id,
                    'location_dest_id': self.location_dest_id.id,
                    'move_raw_ids': lst
            }
            list_create_mo.append(mrp_vales)
        mp = self.env['mrp.production'].create(list_create_mo)        
        for record in mp:
            record._onchange_move_finished()
            ans = record.action_confirm()

        return self.write({'state':'confirm'})

    def action_assign(self):
        mo_objs = self.env['mrp.production'].search([('box_package_id', '=', self.id)])
        self._check_filename()
        data = self.import_data_form_file()
        if data:
            index = 0                        
            list_keys = list(data.keys())            
            unique_list = []
            for key_data in list_keys:                
                dup_found = self.env['stock.production.lot'].search([('name','=', key_data)])
                if not dup_found:
                    unique_list.append(key_data)
            for production in mo_objs:
                if not production.lot_producing_id:
                    if len(unique_list) > index:                       
                        lot = self.env['stock.production.lot'].create({
                            'name': unique_list[index],
                            'product_id': self.product_id.id,
                            'company_id': self.env.company.id,
                        })                        
                        index += 1
                        production.write({
                            'lot_producing_id': lot.id,
                        })
                    else:
                        raise UserError(_('File lot is not enough Please upload another lots.'))
                if production.lot_producing_id:
                    production.move_raw_ids._action_assign()
                    for move in production.move_raw_ids:                        
                        for move_line in move.move_line_ids:                            
                            move_line.write({
                                'qty_done': move_line.product_uom_qty
                            })
                    if production.product_id.tracking == 'serial':
                        result = production._set_qty_producing()                        
        return True

    def import_data_form_file(self):        
        # Generating of the excel file to be read by openpyxl
        file = base64.decodebytes(self.upload_file)
        # file = self.upload_file.decode('base64')
        excel_fileobj = TemporaryFile('wb+')
        excel_fileobj.write(file)
        excel_fileobj.seek(0)
        # Create workbook
        workbook = openpyxl.load_workbook(excel_fileobj, data_only=True)
        # Get the first sheet of excel file
        sheet = workbook[workbook.get_sheet_names()[0]]        
        if sheet.max_column != 2 and sheet.min_column != 2:
            raise ValidationError(_("Please upload 2 Columns NFC tag and Lot information."))        
        data = {}
        for row in sheet.rows:
            # Get value
            data[row[0].value] = row[1].value        
        return data


    def _check_filename(self):
        if self.upload_file:
            if not self.filename:
                raise ValidationError(_("There is no file"))
            else:
                # Check the file's extension
                tmp = self.filename.split('.')
                ext = tmp[len(tmp)-1]
                if ext != 'xlsx':
                    raise ValidationError(_("The file must be a xlsx file"))
        else:
            raise ValidationError(_("Please upload NFC tag and Lot information."))


    def unlink(self):
        for record in self:
            if record.state in ('confirm', 'cancel','done'):
                raise UserError(_("You can delete only draft state record!"))
        return super(BoxPackage, self).unlink()


class BoxPackageMove(models.Model):
    _name = 'box.package.move'

    raw_material_box_package_id = fields.Many2one(
        'box.package', 'Box Packaging components', check_company=True, index=True)
    bom_line_id = fields.Many2one('mrp.bom.line', 'BoM Line', check_company=True)
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.company,
        index=True, required=True)
    product_id = fields.Many2one(
        'product.product', 'Product',
        check_company=True,
        domain="[('type', 'in', ['product', 'consu']), '|', ('company_id', '=', False), ('company_id', '=', company_id)]", index=True, required=True)
    product_uom_qty = fields.Float(
        'Demand',
        digits='Product Unit of Measure',
        default=0.0, required=True)
    product_uom = fields.Many2one('uom.uom', 'Unit of Measure', required=True, domain="[('category_id', '=', product_uom_category_id)]")
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    origin = fields.Char("Source Document")
    quantity_done = fields.Float('Quantity Done', digits='Product Unit of Measure')
