from odoo import fields, models


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

        def add_or_merge_line(account, debit, credit):
            if not account:
                return

            # Buscar una línea de la misma cuenta y del mismo sentido.
            # Se agrupa por cuenta, independientemente del nombre.
            existing_line = next(
                (
                    line for line in all_lines
                    if line['account_id'] == account.id
                    and (
                        (debit > 0 and line['debit'] > 0)
                        or
                        (credit > 0 and line['credit'] > 0)
                    )
                    and line['name'] != self.env._('Adjustment Entry')
                ),
                None,
            )

            if existing_line:
                existing_line['debit'] += debit
                existing_line['credit'] += credit
                return

            # No existe una línea compatible: crear una nueva.
            new_line = {
                'name': 'Concepto adicional de nómina',
                'partner_id': False,
                'account_id': account.id,
                'journal_id': structure.journal_id.id,
                'date': date,
                'debit': debit,
                'credit': credit,
                'analytic_distribution': False,
                'tax_tag_ids': [],
                'tax_ids': [],
            }

            new_lines.append(new_line)
            all_lines.append(new_line)

        debit_account = structure.additional_debit_account_id
        credit_account = structure.additional_credit_account_id

        # Aplicar la misma convención de signos que utiliza Odoo:
        # un importe negativo invierte el sentido del movimiento.
        if debit_account:
            add_or_merge_line(
                debit_account,
                debit=amount if amount > 0 else 0.0,
                credit=-amount if amount < 0 else 0.0,
            )

        if credit_account:
            add_or_merge_line(
                credit_account,
                debit=-amount if amount < 0 else 0.0,
                credit=amount if amount > 0 else 0.0,
            )

        return new_lines