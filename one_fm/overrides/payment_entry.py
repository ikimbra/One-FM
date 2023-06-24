import frappe,erpnext
from frappe import _
from frappe.utils import flt,getdate,nowdate
from functools import reduce
from frappe import  scrub

from hrms.hr.doctype.expense_claim.expense_claim import get_outstanding_amount_for_claim
from erpnext.accounts.doctype.payment_entry.payment_entry import (
    PaymentEntry,
    get_reference_details,
    get_outstanding_reference_documents,
    set_party_type,
    set_party_account,
    apply_early_payment_discount,
    set_pending_discount_loss,
    get_bank_cash_account,
    split_early_payment_discount_loss,
    update_accounting_dimensions,
    set_paid_amount_and_received_amount,
    set_payment_type,
    set_grand_total_and_outstanding_amount,
    set_party_account_currency,
    get_reference_as_per_payment_terms
)
from erpnext.accounts.doctype.bank_account.bank_account import (
    get_bank_account_details,
    get_party_bank_account,
)



@frappe.whitelist()
def get_payment_entry_(
    dt,
    dn,
    party_amount=None,
    bank_account=None,
    bank_amount=None,
    party_type=None,
    payment_type=None,
    reference_date=None,
):
    reference_doc = None   
    doc = frappe.get_doc(dt, dn)
    over_billing_allowance = frappe.db.get_single_value("Accounts Settings", "over_billing_allowance")
    if dt in ("Sales Order", "Purchase Order") and flt(doc.per_billed, 2) >= (
        100.0 + over_billing_allowance
    ):
        frappe.throw(_("Can only make payment against unbilled {0}").format(dt))

    if not party_type:
        party_type = set_party_type(dt)

    party_account = set_party_account(dt, dn, doc, party_type)
    party_account_currency = set_party_account_currency(dt, party_account, doc)

    if not payment_type:
        payment_type = set_payment_type(dt, doc)

    grand_total, outstanding_amount = set_grand_total_and_outstanding_amount(
        party_amount, dt, party_account_currency, doc
    )

    # bank or cash
    bank = get_bank_cash_account(doc, bank_account)

    # if default bank or cash account is not set in company master and party has default company bank account, fetch it
    if party_type in ["Customer", "Supplier"] and not bank:
        party_bank_account = get_party_bank_account(party_type, doc.get(scrub(party_type)))
        if party_bank_account:
            account = frappe.db.get_value("Bank Account", party_bank_account, "account")
            bank = get_bank_cash_account(doc, account)

    paid_amount, received_amount = set_paid_amount_and_received_amount(
        dt, party_account_currency, bank, outstanding_amount, payment_type, bank_amount, doc
    )

    reference_date = getdate(reference_date)
    paid_amount, received_amount, discount_amount, valid_discounts = apply_early_payment_discount(
        paid_amount, received_amount, doc, party_account_currency, reference_date
    )

    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = payment_type
    pe.company = doc.company
    pe.cost_center = doc.get("cost_center")
    pe.posting_date = nowdate()
    pe.reference_date = reference_date
    pe.mode_of_payment = doc.get("mode_of_payment")
    pe.party_type = party_type
    pe.party = doc.get(scrub(party_type))
    pe.contact_person = doc.get("contact_person")
    pe.contact_email = doc.get("contact_email")
    pe.ensure_supplier_is_not_blocked()

    pe.paid_from = party_account if payment_type == "Receive" else bank.account
    pe.paid_to = party_account if payment_type == "Pay" else bank.account
    pe.paid_from_account_currency = (
        party_account_currency if payment_type == "Receive" else bank.account_currency
    )
    if doc.get('employee_advance'):
        try:
            advance_account = frappe.get_value("Employee Advance",doc.employee_advance,'advance_account')
            pe.paid_from = advance_account
        except:
            frappe.log_error("An Error Occurred while creating the payment entry",frappe.get_traceback())
    pe.paid_to_account_currency = (
        party_account_currency if payment_type == "Pay" else bank.account_currency
    )
    pe.paid_amount = paid_amount
    pe.received_amount = received_amount
    pe.letter_head = doc.get("letter_head")

    if dt in ["Purchase Order", "Sales Order", "Sales Invoice", "Purchase Invoice"]:
        pe.project = doc.get("project") or reduce(
            lambda prev, cur: prev or cur, [x.get("project") for x in doc.get("items")], None
        )  # get first non-empty project from items

    if pe.party_type in ["Customer", "Supplier"]:
        bank_account = get_party_bank_account(pe.party_type, pe.party)
        pe.set("bank_account", bank_account)
        pe.set_bank_account_data()

    # only Purchase Invoice can be blocked individually
    if doc.doctype == "Purchase Invoice" and doc.invoice_is_blocked():
        frappe.msgprint(_("{0} is on hold till {1}").format(doc.name, doc.release_date))
    else:
        if doc.doctype in (
            "Sales Invoice",
            "Purchase Invoice",
            "Purchase Order",
            "Sales Order",
        ) and frappe.get_cached_value(
            "Payment Terms Template",
            {"name": doc.payment_terms_template},
            "allocate_payment_based_on_payment_terms",
        ):

            for reference in get_reference_as_per_payment_terms(
                doc.payment_schedule, dt, dn, doc, grand_total, outstanding_amount, party_account_currency
            ):
                pe.append("references", reference)
        else:
            if dt == "Dunning":
                pe.append(
                    "references",
                    {
                        "reference_doctype": "Sales Invoice",
                        "reference_name": doc.get("sales_invoice"),
                        "bill_no": doc.get("bill_no"),
                        "due_date": doc.get("due_date"),
                        "total_amount": doc.get("outstanding_amount"),
                        "outstanding_amount": doc.get("outstanding_amount"),
                        "allocated_amount": doc.get("outstanding_amount"),
                    },
                )
                pe.append(
                    "references",
                    {
                        "reference_doctype": dt,
                        "reference_name": dn,
                        "bill_no": doc.get("bill_no"),
                        "due_date": doc.get("due_date"),
                        "total_amount": doc.get("dunning_amount"),
                        "outstanding_amount": doc.get("dunning_amount"),
                        "allocated_amount": doc.get("dunning_amount"),
                    },
                )
            else:
                pe.append(
                    "references",
                    {
                        "reference_doctype": dt,
                        "reference_name": dn,
                        "bill_no": doc.get("bill_no"),
                        "due_date": doc.get("due_date"),
                        "total_amount": grand_total,
                        "outstanding_amount": outstanding_amount,
                        "allocated_amount": outstanding_amount,
                    },
                )

    pe.setup_party_account_field()
    pe.set_missing_values()
    pe.set_missing_ref_details()

    update_accounting_dimensions(pe, doc)

    if party_account and bank:
        pe.set_exchange_rate(ref_doc=reference_doc)
        pe.set_amounts()

        if discount_amount:
            base_total_discount_loss = 0
            if frappe.db.get_single_value("Accounts Settings", "book_tax_discount_loss"):
                base_total_discount_loss = split_early_payment_discount_loss(pe, doc, valid_discounts)

            set_pending_discount_loss(
                pe, doc, discount_amount, base_total_discount_loss, party_account_currency
            )

        pe.set_difference_amount()

    return pe



def fetch_employee_advances(doc):
    pack = []
    for each in doc.get("references"):
        if each.reference_doctype == "Employee Advance":
            #get open advances for this employee
            if doc.party_type == "Employee":
                open_advances = frappe.get_all("Employee Advance",{'docstatus':1,'status':'Unpaid'},['posting_date','name','advance_amount','pending_amount','paid_amount'])
                if open_advances:
                    for each in open_advances:
                        pack.append({
                            'voucher_no':each.name,
                            'voucher_type':'Employee Advance',
                            'posting_date':each.posting_date,
                            'invoice_amount':each.advance_amount,
                            'payment_amount':each.advance_amount - each.paid_amount,
                            'outstanding_amount':each.advance_amount - each.paid_amount,
                            'due_date':each.posting_date,
                            'currency':"KWD",
                            'exchange_rate':1
                            
                        })
    return pack
    
def validate_allocated_amount_(self):
        if self.payment_type == "Internal Transfer":
            return

        latest_references = get_outstanding_reference_documents(
            {
                "posting_date": self.posting_date,
                "company": self.company,
                "party_type": self.party_type,
                "payment_type": self.payment_type,
                "party": self.party,
                "party_account": self.paid_from if self.payment_type == "Receive" else self.paid_to,
            }
        )
        latest_references += fetch_employee_advances(self) 
        # Group latest_references by (voucher_type, voucher_no)
        latest_lookup = {}
        for d in latest_references:
            d = frappe._dict(d)
            latest_lookup.update({(d.voucher_type, d.voucher_no): d})

        for d in self.get("references").copy():
            latest = latest_lookup.get((d.reference_doctype, d.reference_name))

            # The reference has already been fully paid
            if not latest:
                
                frappe.throw(
                    _("{0} {1} has already been fully paid.").format(d.reference_doctype, d.reference_name)
                )
            # The reference has already been partly paid
            elif (
                latest.outstanding_amount < latest.invoice_amount
                and d.outstanding_amount != latest.outstanding_amount
            ):
                frappe.throw(
                    _(
                        "{0} {1} has already been partly paid. Please use the 'Get Outstanding Invoice' button to get the latest outstanding amount."
                    ).format(d.reference_doctype, d.reference_name)
                )

            d.outstanding_amount = latest.outstanding_amount

            fail_message = _("Row #{0}: Allocated Amount cannot be greater than outstanding amount.")

            if (flt(d.allocated_amount)) > 0:
                if flt(d.allocated_amount) > flt(d.outstanding_amount):
                    frappe.throw(fail_message.format(d.idx))

            # Check for negative outstanding invoices as well
            if flt(d.allocated_amount) < 0:
                if flt(d.allocated_amount) < flt(d.outstanding_amount):
                    frappe.throw(fail_message.format(d.idx))



def get_total_amount_and_exchange_rate(ref_doc, party_account_currency, company_currency):
    total_amount = exchange_rate = None

    if ref_doc.doctype == "Expense Claim":
        total_amount = flt(ref_doc.total_sanctioned_amount) + flt(ref_doc.total_taxes_and_charges)
    elif ref_doc.doctype == "Employee Advance":
        total_amount = ref_doc.advance_amount
        exchange_rate = ref_doc.get("exchange_rate")
        if party_account_currency != ref_doc.currency:
            total_amount = flt(total_amount) * flt(exchange_rate)
        if party_account_currency == company_currency:
            exchange_rate = 1

    elif ref_doc.doctype == "Gratuity":
        total_amount = ref_doc.amount

    if not total_amount:
        if party_account_currency == company_currency:
            total_amount = ref_doc.base_grand_total
            exchange_rate = 1
        else:
            total_amount = ref_doc.grand_total

    if not exchange_rate:
        # Get the exchange rate from the original ref doc
        # or get it based on the posting date of the ref doc.
        exchange_rate = ref_doc.get("conversion_rate") or get_exchange_rate(
            party_account_currency, company_currency, ref_doc.posting_date
        )

    return total_amount, exchange_rate

@frappe.whitelist()
def get_payment_reference_details(reference_doctype, reference_name, party_account_currency):
    if reference_doctype in ("Expense Claim", "Employee Advance", "Gratuity"):
        return get_reference_details_for_employee(
            reference_doctype, reference_name, party_account_currency
        )
    else:
        return get_reference_details(reference_doctype, reference_name, party_account_currency)


@frappe.whitelist()
def get_reference_details_for_employee(reference_doctype, reference_name, party_account_currency):
    """
    Returns payment reference details for employee related doctypes:
    Employee Advance, Expense Claim, Gratuity
    """
    total_amount = outstanding_amount = exchange_rate = None

    ref_doc = frappe.get_doc(reference_doctype, reference_name)
    company_currency = ref_doc.get("company_currency") or erpnext.get_company_currency(
        ref_doc.company
    )

    total_amount, exchange_rate = get_total_amount_and_exchange_rate(
        ref_doc, party_account_currency, company_currency
    )

    if reference_doctype == "Expense Claim":
        outstanding_amount = get_outstanding_amount_for_claim(ref_doc)
    elif reference_doctype == "Employee Advance":
        outstanding_amount = flt(ref_doc.advance_amount) - flt(ref_doc.paid_amount)
        if party_account_currency != ref_doc.currency:
            outstanding_amount = flt(outstanding_amount) * flt(exchange_rate)
    elif reference_doctype == "Gratuity":
        outstanding_amount = ref_doc.amount - flt(ref_doc.paid_amount)
    else:
        outstanding_amount = flt(total_amount) - flt(ref_doc.advance_paid)

    return frappe._dict(
        {
            "due_date": ref_doc.get("due_date"),
            "total_amount": flt(total_amount),
            "outstanding_amount": flt(outstanding_amount),
            "exchange_rate": flt(exchange_rate),
        }
    )


def set_missing_ref_details(
        self, force: bool = False, update_ref_details_only_for: list | None = None
    ) -> None:
        for d in self.get("references"):
            if d.allocated_amount:
                if update_ref_details_only_for and (
                    not (d.reference_doctype, d.reference_name) in update_ref_details_only_for
                ):
                    continue

                ref_details = get_payment_reference_details(
                    d.reference_doctype, d.reference_name, self.party_account_currency
                )

                for field, value in ref_details.items():
                    if d.exchange_gain_loss:
                        # for cases where gain/loss is booked into invoice
                        # exchange_gain_loss is calculated from invoice & populated
                        # and row.exchange_rate is already set to payment entry's exchange rate
                        # refer -> `update_reference_in_payment_entry()` in utils.py
                        continue

                    if field == "exchange_rate" or not d.get(field) or force:
                        d.db_set(field, value)



def get_valid_reference_doctypes_(self):
        if self.party_type == "Customer":
            return ("Sales Order", "Sales Invoice", "Journal Entry", "Dunning")
        elif self.party_type == "Supplier":
            return ("Purchase Order", "Purchase Invoice", "Journal Entry")
        elif self.party_type == "Shareholder":
            return ("Journal Entry",)
        elif self.party_type == "Employee":
            return ("Expense Claim", "Journal Entry", "Employee Advance", "Gratuity")

def add_party_gl_entries_(self, gl_entries):
    if self.party_account:
        if self.payment_type == "Receive":
            against_account = self.paid_to
        else:
            against_account = self.paid_from

        party_gl_dict = self.get_gl_dict(
            {
                "account": self.party_account,
                "party_type": self.party_type,
                "party": self.party,
                "against": against_account,
                "account_currency": self.party_account_currency,
                "cost_center": self.cost_center,
            },
            item=self,
        )

        dr_or_cr = (
            "credit" if erpnext.get_party_account_type(self.party_type) == "Receivable" else "debit"
        )

        for d in self.get("references"):
            cost_center = self.cost_center
            if d.reference_doctype == "Sales Invoice" and not cost_center:
                cost_center = frappe.db.get_value(d.reference_doctype, d.reference_name, "cost_center")
            gle = party_gl_dict.copy()
            gle.update(
                {
                    "against_voucher_type": d.reference_doctype,
                    "against_voucher": d.reference_name,
                    "cost_center": cost_center,
                }
            )

            allocated_amount_in_company_currency = self.calculate_base_allocated_amount_for_reference(d)

            gle.update(
                {   
                    
                    dr_or_cr + "_in_account_currency": d.allocated_amount,
                    dr_or_cr: allocated_amount_in_company_currency,
                }
            )

            gl_entries.append(gle)

        if self.unallocated_amount:
            try:
                customer_advance_account=frappe.get_value('Accounts Additional Settings',None,'customer_advance_account')                    
            except:
                frappe.log_error("Error while fetching advance account",frappe.get_traceback())
                frappe.throw("An Error occured while fetching advance account, Please review the error logs")
            exchange_rate = self.get_exchange_rate()
            base_unallocated_amount = self.unallocated_amount * exchange_rate

            gle = party_gl_dict.copy()
            if customer_advance_account:
                gle.update(
                    {   
                        "account": customer_advance_account,
                        "party_type": self.party_type,
                        "party": self.party,
                        "against": against_account,
                        "account_currency": self.party_account_currency,
                        "cost_center": self.cost_center,
                        dr_or_cr + "_in_account_currency": self.unallocated_amount,
                        dr_or_cr: base_unallocated_amount,
                    }
                )
            else:
                gle.update(
                    {   
                        
                        dr_or_cr + "_in_account_currency": self.unallocated_amount,
                        dr_or_cr: base_unallocated_amount,
                    }
                )
                

            gl_entries.append(gle)