odoo.define('trivicity_erp.basic_fields', function (require) {
"use strict";

/**
 * This module contains most of the basic (meaning: non relational) field
 * widgets. Field widgets are supposed to be used in views inheriting from
 * BasicView, so, they can work with the records obtained from a BasicModel.
 */

var AbstractField = require('web.AbstractField');
var config = require('web.config');
var core = require('web.core');
var datepicker = require('web.datepicker');
var deprecatedFields = require('web.basic_fields.deprecated');
var dom = require('web.dom');
var Domain = require('web.Domain');
var DomainSelector = require('web.DomainSelector');
var DomainSelectorDialog = require('web.DomainSelectorDialog');
var framework = require('web.framework');
var py_utils = require('web.py_utils');
var session = require('web.session');
var utils = require('web.utils');
var view_dialogs = require('web.view_dialogs');
var field_utils = require('web.field_utils');
var time = require('web.time');
const {ColorpickerDialog} = require('web.Colorpicker');
var FieldChar = require('web.basic_fields');

let FieldBoolean = deprecatedFields.FieldBoolean;

require("web.zoomodoo");

var qweb = core.qweb;
var _t = core._t;
var _lt = core._lt;

FieldChar.FieldChar.include({
    _onKeydown: function (ev) {
        switch (ev.which) {
            case $.ui.keyCode.TAB:
                var event = this.trigger_up('navigation_move', {
                    direction: ev.shiftKey ? 'previous' : 'next',
                });
                if (event.is_stopped()) {
                    ev.preventDefault();
                    ev.stopPropagation();
                }
                break;
            case $.ui.keyCode.ENTER:
                // We preventDefault the ENTER key because of two coexisting behaviours:
                // - In HTML5, pressing ENTER on a <button> triggers two events: a 'keydown' AND a 'click'
                // - When creating and opening a dialog, the focus is automatically given to the primary button
                // The end result caused some issues where a modal opened by an ENTER keypress (e.g. saving
                // changes in multiple edition) confirmed the modal without any intentionnal user input.
//                ev.preventDefault();
                ev.stopPropagation();
                this.trigger_up('navigation_move', {direction: 'next_line'});
                break;
            case $.ui.keyCode.ESCAPE:
                this.trigger_up('navigation_move', {direction: 'cancel', originalEvent: ev});
                break;
            case $.ui.keyCode.UP:
                ev.stopPropagation();
                this.trigger_up('navigation_move', {direction: 'up'});
                break;
            case $.ui.keyCode.RIGHT:
                ev.stopPropagation();
                this.trigger_up('navigation_move', {direction: 'right'});
                break;
            case $.ui.keyCode.DOWN:
                ev.stopPropagation();
                this.trigger_up('navigation_move', {direction: 'down'});
                break;
            case $.ui.keyCode.LEFT:
                ev.stopPropagation();
                this.trigger_up('navigation_move', {direction: 'left'});
                break;
        }
    },
});
return {
    FieldChar: FieldChar.FieldChar
};
});