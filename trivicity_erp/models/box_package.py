# -*- coding: utf-8 -*-

import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, AccessError
from xlrd import open_workbook
from itertools import groupby
from operator import itemgetter
import base64
import openpyxl
from odoo.tools.float_utils import float_compare, float_is_zero, float_repr, float_round
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
            self.with_context(assign_lot=1).action_assign()
            mo_objs = self.env['mrp.production'].search([('box_package_id', '=', self.name),('state','in',('confirmed','progress','to_close'))])            
            if mo_objs:
                if any(production.reservation_state != 'assigned' for production in mo_objs):
                    raise UserError(_('Please first reserve stock for all the manufacturing order using "Check Availability" feature.'))
                if all(production.reservation_state == 'assigned' for production in mo_objs):
                    for mo in mo_objs:
                        wiz_act = mo.button_mark_done()

                if all(production.state == 'done' for production in mo_objs):
                    if mo_objs:
                        for line in self.move_raw_ids:
                            line.quantity_done = sum([move.quantity_done for move in mo_objs.mapped('move_raw_ids').filtered(lambda m: m.product_id.id == line.product_id.id)])
                    self.write({'state': 'done'})
                   
    def action_cancel(self):
        mo_obj = self.env['mrp.production'].search([('box_package_id', '=', self.id)])
        if mo_obj:
           for rec in mo_obj:
               rec.action_cancel()
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
            mo_have_lot = mo_objs.mapped('lot_producing_id').mapped('name')
            already_assigned = []
            for key_data in list_keys:
                dup_found = self.env['stock.production.lot'].search([('name','=', key_data)])
                if not dup_found or key_data in mo_have_lot:
                    unique_list.append(key_data)
                else:
                    already_assigned.append(key_data)
            for production in mo_objs:
                if len(unique_list) > index:
                    lot_name = data.get(unique_list[index])
                    self._action_assign(production, lot_name)
                    index += 1
                else:
                    note = ''
                    if len(list_keys) != len(mo_objs):
                        note = 'Found only ' + str(len(list_keys)) + ' NFC tags, but required ' + str(len(mo_objs)) + ' NFC tag information.\n'
                    if already_assigned:
                        note = note + ", ".join(l for l in already_assigned) + ' NFC tags are already assigned to existing box. Please verify uploaded information. '
                    if note:
                        raise UserError(_(note))
            if self._context.get('assign_lot'):
                index = 0
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
                            production._onchange_producing()
                            production._onchange_lot_producing()
                            for line in production.move_raw_ids.mapped('move_line_ids'):
                                if line.product_uom_qty != line.qty_done:
                                    line.qty_done = line.product_uom_qty

        else:
            raise ValidationError(_("Please upload 2 Columns NFC tag and Lot information with data."))
        return True

    def _action_assign(self, mo_obj, lot_name):
        move_ids = mo_obj.move_raw_ids
        assigned_moves = self.env['stock.move']
        partially_available_moves = self.env['stock.move']
        # Read the `reserved_availability` field of the moves out of the loop to prevent unwanted
        # cache invalidation when actually reserving the move.
        reserved_availability = {move: move.reserved_availability for move in move_ids}
        roundings = {move: move.product_id.uom_id.rounding for move in move_ids}
        move_line_vals_list = []
        not_available_list = []
        for move in move_ids.filtered(lambda m: m.state != 'cancel'):
            rounding = roundings[move]
            missing_reserved_uom_quantity = move.product_uom_qty - reserved_availability[move]
            missing_reserved_quantity = move.product_uom._compute_quantity(missing_reserved_uom_quantity,
                                                                           move.product_id.uom_id,
                                                                           rounding_method='HALF-UP')
            if move._should_bypass_reservation():
                # create the move line(s) but do not impact quants
                if move.product_id.tracking == 'serial' and (
                        move.picking_type_id.use_create_lots or move.picking_type_id.use_existing_lots):
                    for i in range(0, int(missing_reserved_quantity)):
                        move_line_vals_list.append(move._prepare_move_line_vals(quantity=1))
                else:
                    to_update = move.move_line_ids.filtered(lambda ml: ml.product_uom_id == move.product_uom and
                                                                       ml.location_id == move.location_id and
                                                                       ml.location_dest_id == move.location_dest_id and
                                                                       ml.picking_id == move.picking_id and
                                                                       not ml.lot_id and
                                                                       not ml.package_id and
                                                                       not ml.owner_id)
                    if to_update:
                        to_update[0].product_uom_qty += missing_reserved_uom_quantity
                    else:
                        move_line_vals_list.append(move._prepare_move_line_vals(quantity=missing_reserved_quantity))
                assigned_moves |= move
            else:
                if float_is_zero(move.product_uom_qty, precision_rounding=move.product_uom.rounding):
                    assigned_moves |= move
                elif not move.move_orig_ids:
                    if move.procure_method == 'make_to_order':
                        continue
                    # If we don't need any quantity, consider the move assigned.
                    need = missing_reserved_quantity
                    lot_id = None
                    if move.product_id.tracking == 'none':
                        if float_is_zero(need, precision_rounding=rounding):
                            assigned_moves |= move
                            continue
                    else:
                        move_line = move.move_line_ids
                        if move_line and move_line.filtered(lambda m: m.lot_id.name == lot_name or m.lot_name == lot_name):
                            if float_is_zero(need, precision_rounding=rounding):
                                assigned_moves |= move
                                continue
                            lot_id = move_line[0].lot_id
                        else:
                            move_line.unlink()
                            need = move.product_uom_qty
                    # Reserve new quants and create move lines accordingly.
                    if not lot_id and move.product_id.tracking != 'none':
                        lot_id = self.env['stock.production.lot'].search([('product_id', '=', move.product_id.id), ('name', '=', lot_name), ('product_qty', '>=', need)])
                        if not lot_id:
                            not_available_list.append(lot_name)
                            continue
                    forced_package_id = move.package_level_id.package_id or None
                    available_quantity = move._get_available_quantity(move.location_id, lot_id=lot_id, package_id=forced_package_id)
                    if available_quantity < need:
                        not_available_list.append(lot_name)
                        continue
                    taken_quantity = move._update_reserved_quantity(need, available_quantity, move.location_id, lot_id=lot_id,
                                                                    package_id=forced_package_id, strict=False)
                    if float_is_zero(taken_quantity, precision_rounding=rounding):
                        continue
                    if float_compare(need, taken_quantity, precision_rounding=rounding) == 0:
                        assigned_moves |= move
                    else:
                        partially_available_moves |= move
                else:
                    # Check what our parents brought and what our siblings took in order to
                    # determine what we can distribute.
                    # `qty_done` is in `ml.product_uom_id` and, as we will later increase
                    # the reserved quantity on the quants, convert it here in
                    # `product_id.uom_id` (the UOM of the quants is the UOM of the product).
                    move_lines_in = move.move_orig_ids.filtered(lambda m: m.state == 'done').mapped('move_line_ids')
                    keys_in_groupby = ['location_dest_id', 'lot_id', 'result_package_id', 'owner_id']

                    def _keys_in_sorted(ml):
                        return (ml.location_dest_id.id, ml.lot_id.id, ml.result_package_id.id, ml.owner_id.id)

                    grouped_move_lines_in = {}
                    for k, g in groupby(sorted(move_lines_in, key=_keys_in_sorted), key=itemgetter(*keys_in_groupby)):
                        qty_done = 0
                        for ml in g:
                            qty_done += ml.product_uom_id._compute_quantity(ml.qty_done, ml.product_id.uom_id)
                        grouped_move_lines_in[k] = qty_done
                    move_lines_out_done = (move.move_orig_ids.mapped('move_dest_ids') - move) \
                        .filtered(lambda m: m.state in ['done']) \
                        .mapped('move_line_ids')
                    # As we defer the write on the stock.move's state at the end of the loop, there
                    # could be moves to consider in what our siblings already took.
                    moves_out_siblings = move.move_orig_ids.mapped('move_dest_ids') - move
                    moves_out_siblings_to_consider = moves_out_siblings & (assigned_moves + partially_available_moves)
                    reserved_moves_out_siblings = moves_out_siblings.filtered(
                        lambda m: m.state in ['partially_available', 'assigned'])
                    move_lines_out_reserved = (reserved_moves_out_siblings | moves_out_siblings_to_consider).mapped(
                        'move_line_ids')
                    keys_out_groupby = ['location_id', 'lot_id', 'package_id', 'owner_id']

                    def _keys_out_sorted(ml):
                        return (ml.location_id.id, ml.lot_id.id, ml.package_id.id, ml.owner_id.id)

                    grouped_move_lines_out = {}
                    for k, g in groupby(sorted(move_lines_out_done, key=_keys_out_sorted),
                                        key=itemgetter(*keys_out_groupby)):
                        qty_done = 0
                        for ml in g:
                            qty_done += ml.product_uom_id._compute_quantity(ml.qty_done, ml.product_id.uom_id)
                        grouped_move_lines_out[k] = qty_done
                    for k, g in groupby(sorted(move_lines_out_reserved, key=_keys_out_sorted),
                                        key=itemgetter(*keys_out_groupby)):
                        grouped_move_lines_out[k] = sum(
                            self.env['stock.move.line'].concat(*list(g)).mapped('product_qty'))
                    available_move_lines = {key: grouped_move_lines_in[key] - grouped_move_lines_out.get(key, 0) for key
                                            in grouped_move_lines_in.keys()}
                    # pop key if the quantity available amount to 0
                    available_move_lines = dict((k, v) for k, v in available_move_lines.items() if v)

                    if not available_move_lines:
                        continue
                    for move_line in move.move_line_ids.filtered(lambda m: m.product_qty):
                        if available_move_lines.get((move_line.location_id, move_line.lot_id,
                                                     move_line.result_package_id, move_line.owner_id)):
                            available_move_lines[(move_line.location_id, move_line.lot_id, move_line.result_package_id,
                                                  move_line.owner_id)] -= move_line.product_qty
                    for (location_id, lot_id, package_id, owner_id), quantity in available_move_lines.items():
                        need = move.product_qty - sum(move.move_line_ids.mapped('product_qty'))
                        # `quantity` is what is brought by chained done move lines. We double check
                        # here this quantity is available on the quants themselves. If not, this
                        # could be the result of an inventory adjustment that removed totally of
                        # partially `quantity`. When this happens, we chose to reserve the maximum
                        # still available. This situation could not happen on MTS move, because in
                        # this case `quantity` is directly the quantity on the quants themselves.
                        available_quantity = move._get_available_quantity(location_id, lot_id=lot_id,
                                                                          package_id=package_id, owner_id=owner_id,
                                                                          strict=True)
                        if float_is_zero(available_quantity, precision_rounding=rounding):
                            continue
                        taken_quantity = move._update_reserved_quantity(need, min(quantity, available_quantity),
                                                                        location_id, lot_id, package_id, owner_id)
                        if float_is_zero(taken_quantity, precision_rounding=rounding):
                            continue
                        if float_is_zero(need - taken_quantity, precision_rounding=rounding):
                            assigned_moves |= move
                            break
                        partially_available_moves |= move
            if move.product_id.tracking == 'serial':
                move.next_serial_count = move.product_uom_qty
        if not_available_list:
            raise UserError(_(' Lot %s added in uploaded file is not available in stock.', (", ".join(a for a in set(not_available_list)))))

        self.env['stock.move.line'].create(move_line_vals_list)
        partially_available_moves.write({'state': 'partially_available'})
        assigned_moves.write({'state': 'assigned'})
        move_ids.mapped('picking_id')._check_entire_pack()

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
            raise ValidationError(_("Please upload NFC tag and Lot information file."))

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
    forecast_availability = fields.Float('Forecast Availability', compute='_compute_forecast_information',
                                         digits='Product Unit of Measure')

    def _compute_forecast_information(self):
        for record in self:
            mo_obj = self.env['mrp.production'].search([('box_package_id', '=', record.raw_material_box_package_id.id)])
            forecast_availability = 0
            if mo_obj:
                forecast_availability = sum([data.reserved_availability for data in mo_obj.mapped('move_raw_ids').filtered(lambda m: m.product_id.id == record.product_id.id)])
            record.forecast_availability = forecast_availability

