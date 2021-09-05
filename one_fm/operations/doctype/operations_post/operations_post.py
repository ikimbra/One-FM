# -*- coding: utf-8 -*-
# Copyright (c) 2020, omar jaber and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.rename_doc import rename_doc
from frappe.utils import cstr, getdate, add_to_date
import pandas as pd

class OperationsPost(Document):
	def before_insert(self):
		start_date = None
		end_date = None

		if frappe.db.exists("Contracts", {'project': self.project}):
			contract, start_date, end_date = frappe.db.get_value("Contracts", {'project': self.project}, ["name", "start_date", "end_date"])
			if not start_date or not end_date:
				frappe.throw(_("Please set contract dates for contract: {contract}".format(contract=contract)))
		else:
			frappe.throw(_("No contract linked with project: {project}".format(project=self.project)))
		frappe.enqueue(set_post_active, post=self, start_date=start_date, end_date=end_date, is_async=True, queue="long")

	def on_update(self):
		self.validate_name()

	def validate_name(self):
		condition = self.post_name+"-"+self.gender+"|"+self.site_shift
		if condition != self.name:
			rename_doc(self.doctype, self.name, condition, force=True)
		

@frappe.whitelist()
def set_post_active(post, start_date, end_date):
	for date in	pd.date_range(start=start_date, end=end_date):
		sch = frappe.new_doc("Post Schedule")
		sch.post = post.name
		sch.date = cstr(date.date())
		sch.post_status = "Planned"
		sch.save()