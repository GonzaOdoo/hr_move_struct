from odoo import fields, models
import logging

_logger = logging.getLogger(__name__)
class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    additional_debit_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de débito adicional',
        check_company=True,
    )

    additional_credit_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de crédito adicional',
        check_company=True,
    )

    additional_percentage = fields.Float(
        string='Porcentaje adicional (%)',
        digits=(16, 4),
    )



class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _prepare_slip_lines(self, date, line_ids):
        self.ensure_one()
        # Generar primero las líneas contables originales de Odoo.
        new_lines = super()._prepare_slip_lines(date, line_ids)

        structure = self.struct_id
        percentage = structure.additional_percentage

        if not percentage:
            return new_lines

        # Obtener el imponible GROSS del recibo.
        gross_lines = self.line_ids.filtered(
            lambda line: line.code == 'GROSS'
        )
        gross_amount = sum(gross_lines.mapped('total'))

        if not gross_amount:
            return new_lines

        # Calcular el concepto adicional.
        amount = gross_amount * percentage / 100.0

        if not amount:
            return new_lines

        # El concepto adicional no debe modificar el cálculo del NET.
        # Solo afecta al asiento contable.
        all_lines = line_ids + new_lines

        concept_name = 'Concepto adicional de nomina'

        debit_account = structure.additional_debit_account_id
        credit_account = structure.additional_credit_account_id
        
        if amount > 0:
            debit = amount
            credit = 0.0
        else:
            debit = 0.0
            credit = abs(amount)
        
        # Buscar una línea adicional previamente generada para este asiento.
        # line_ids contiene las líneas de los recibos procesados anteriormente.
        all_lines = line_ids + new_lines
        
        
        def add_additional_line(account, line_debit, line_credit):
            if not account:
                return
        
            existing_line = next(
                (
                    line for line in all_lines
                    if line['name'] == concept_name
                    and line['account_id'] == account.id
                    and (
                        (line_debit > 0 and line['debit'] > 0)
                        or
                        (line_credit > 0 and line['credit'] > 0)
                    )
                ),
                None,
            )
        
            if existing_line:
                existing_line['debit'] += line_debit
                existing_line['credit'] += line_credit
            else:
                new_line = {
                    'name': concept_name,
                    'partner_id': False,
                    'account_id': account.id,
                    'journal_id': structure.journal_id.id,
                    'date': date,
                    'debit': line_debit,
                    'credit': line_credit,
                    'analytic_distribution': False,
                    'tax_tag_ids': [],
                    'tax_ids': [],
                }
                new_lines.append(new_line)
                all_lines.append(new_line)
        
        
        add_additional_line(debit_account, debit, credit)
        add_additional_line(credit_account, credit, debit)

        return new_lines