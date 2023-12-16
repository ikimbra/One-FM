from itertools import chain

import frappe
from frappe.utils import getdate, add_days, get_url_to_form
from frappe.permissions import remove_user_permission
from hrms.overrides.employee_master import *
from one_fm.hiring.utils import (
    employee_after_insert, employee_before_insert, set_employee_name,
    employee_validate_attendance_by_timesheet, set_mandatory_feilds_in_employee_for_Kuwaiti,
)
from one_fm.processor import sendemail
from one_fm.utils import get_domain

class EmployeeOverride(EmployeeMaster):
    def validate(self):
        from erpnext.controllers.status_updater import validate_status
        validate_status(self.status, ["Active", "Court Case", "Absconding", "Left","Vacation"])

        self.employee = self.name
        self.set_employee_name()
        set_employee_name(self, method=None)
        self.validate_date()
        self.validate_email()
        self.validate_status()
        self.validate_reports_to()
        self.validate_preferred_email()
        validate_employee_status_access(self=self)
        update_user_doc(self)
        if self.job_applicant:
            self.validate_onboarding_process()

        if self.user_id:
            self.validate_user_details()
        else:
            existing_user_id = frappe.db.get_value("Employee", self.name, "user_id")
            if existing_user_id:
                remove_user_permission(
                    "Employee", self.name, existing_user_id)
        employee_validate_attendance_by_timesheet(self, method=None)
        validate_leaves(self)

    def before_save(self):
        self.assign_role_profile_based_on_designation()
        if self.under_company_residency=='1':
            self.employee_id = get_new_employee_id(self.employee_id)

    def after_insert(self):
        employee_after_insert(self, method=None)
        self.assign_role_profile_based_on_designation()

    @frappe.whitelist()
    def run_employee_id_generation(self):
        employee_after_insert(self, method=None)

    def before_insert(self):
        employee_before_insert(self, method=None)

    def validate_onboarding_process(self):
        validate_onboarding_process(self)

    def assign_role_profile_based_on_designation(self):
        previous_designation = frappe.db.get_value("Employee", self.name, "designation")
        if self.designation and self.user_id and self.designation != previous_designation:
            role_profile = frappe.db.get_value("Designation", self.designation, "role_profile")
            if role_profile:
                user = frappe.get_doc("User", self.user_id)
                user.role_profile_name = role_profile
                user.save()
            else:
                frappe.msgprint("Role profile not set in Designation, please set default.")

    def on_update(self):
        super(EmployeeOverride, self).on_update()
        set_mandatory_feilds_in_employee_for_Kuwaiti(self, method=None)
        try:
            current_doc = frappe.get_doc("Employee", self.name)
            if (self.shift != current_doc.shift) and (self.shift_working != current_doc.shift_working):
                frappe.db.sql(f"""
                    DELETE FROM `tabEmployee Schedule` WHERE employee='{self.employee}'
                    AND date>'{getdate()}'
                """)
        except:
            pass

        # clear future employee schedules
        self.clear_schedules()
        self.update_subcontract_onboard()
        self.notify_attendance_manager_on_status_change()
        

    def update_subcontract_onboard(self):
        subcontract_onboard = frappe.db.exists("Onboard Subcontract Employee", {"employee": self.name, "enrolled": ['!=', '1']})
        if subcontract_onboard and self.enrolled:
            frappe.db.set_value("Onboard Subcontract Employee", subcontract_onboard, "enrolled", self.enrolled)
            
    def notify_attendance_manager_on_status_change(self):
        NotifyAttendanceManagerOnStatusChange(employee_object=self).notify_authorities()

    def clear_schedules(doc):
        # clear future employee schedules
        if doc.status == 'Left':
            frappe.db.sql(f"""
                DELETE FROM `tabEmployee Schedule` WHERE employee='{doc.name}'
                AND date>'{doc.relieving_date}'
            """)
            frappe.msgprint(f"""
                Employee Schedule cleared for {doc.employee_name} starting from {add_days(doc.relieving_date, 1)}
            """)

def validate_leaves(self):
    if self.status=='Vacation':
        if not frappe.db.sql(f"""
                SELECT name FROM `tabLeave Application` WHERE employee="{self.name}" AND docstatus IN (0,1)
                AND
                '{getdate()}' BETWEEN from_date AND to_date
            """, as_dict=1):
            frappe.throw(f"Status cannot be 'Vacation' when no Leave Application exists for {self.employee_name} today {getdate()}.")


def validate_employee_status_access(self):
    if self.status:
        if self.is_new():
            pass
        else:
            if self.status != self.get_doc_before_save().status:
                if not check_employee_access(email=frappe.session.user):
                    frappe.throw("You are not allowed to make changes to an employee's status.")


@frappe.whitelist()
def check_employee_access(email: str) -> bool:
    employee_setting = frappe.get_doc("ONEFM General Setting").get("employee_access")
    return frappe.db.get_value("Employee", {"user_id": email}) in [obj.employee for obj in employee_setting]

@frappe.whitelist()
def get_new_employee_id(employee_id):
    length = len(employee_id)
    num = employee_id[length-3] #get the third-last character.
    if num == '0':
        new_emp_id = employee_id[:length-3] + '1' + employee_id[length-2:]
        return new_emp_id

def update_user_doc(doc):
    if not doc.is_new():
        old_self = doc.get_doc_before_save().status
        if doc.status in ['Left','Absconding','Court Case'] and doc.status not in [old_self] and doc.user_id:
            user_doc = frappe.get_doc('User',doc.user_id)
            if user_doc.enabled == 1:
                user_doc.enabled = 0
                user_doc.save(ignore_permissions=1)
                frappe.msgprint(f"User {doc.user_id} disabled",alert=1)
                frappe.db.commit()
        elif doc.status == "Active" and doc.status not in [old_self] and doc.user_id:
            user_doc = frappe.get_doc('User',doc.user_id)
            if user_doc.enabled == 0:
                user_doc.enabled = 1
                user_doc.save(ignore_permissions=1)
                frappe.msgprint(f"User {doc.user_id} enabled",alert=1)
                frappe.db.commit()



class NotifyAttendanceManagerOnStatusChange:
    
    def __init__(self, employee_object: EmployeeOverride) -> None:
        self.employee_object = employee_object
        
    @property
    def _operations_shift_supervisor(self) -> list():
        operation_shifts = frappe.db.sql(""" SELECT name from `tabOperations Shift` WHERE supervisor = %s """, (self.employee_object.name), as_list=1)
        return list(chain.from_iterable(operation_shifts)) if operation_shifts else list()
    
    @property
    def _operations_site_supervisor(self) -> list:
        operation_sites = frappe.db.sql(""" SELECT name from `tabOperations Site` WHERE account_supervisor = %s """, (self.employee_object.name), as_list=1)
        return list(chain.from_iterable(operation_sites)) if operation_sites else list()
    
    @property
    def _projects_manager(self) -> list:
        projects = frappe.db.sql(""" SELECT name from `tabProject` WHERE account_manager = %s""", (self.employee_object.name), as_list=1)
        return list(chain.from_iterable(projects)) if projects else list()
    
    @property
    def _employee_reports_to(self) -> list:
        reports_to = frappe.db.sql(""" SELECT name, employee_name from `tabEmployee` where reports_to = %s AND status= 'Active' """, (self.employee_object.name), as_dict=1)
        return reports_to 
    
    @property
    def _to_do(self) -> str:
        try:
            result = frappe.db.sql("""
                                    SELECT EXISTS (
                                        SELECT 1
                                        FROM `tabToDo`
                                        WHERE allocated_to = %s AND status = 'Open'
                                    ) AS record_exists
                                    """, (self.user_id,))
            is_to_do = result[0][0]
            return f"{get_domain()}/app/todo?status=Open&allocated_to={self.employee_object.user_id}" if is_to_do else ""
        except Exception as e:
            return ""
    
    @property
    def _operation_manager(self) -> str | None:
        return frappe.db.get_single_value("Operation Settings", "default_operation_manager")
    
    @property
    def _attendance_manager_user_id(self) -> str:
        attendance_manager = frappe.db.get_single_value('ONEFM General Setting', 'attendance_manager')
        if attendance_manager:
            return frappe.db.get_value("Employee", {"name": attendance_manager}, "user_id")
        return ""
    
    @property
    def _directors(self) -> list:
        return frappe.db.get_list("User", filters={"role_profile_name": "Director"}, pluck="name")
    
    
    def generate_data(self) -> dict:
        try:
            data_dict = dict()
            operations_shift = self._operations_shift_supervisor
            if operations_shift:
                data_dict.update({"operations_shift": dict()})
                for obj in operations_shift:
                    data_dict.get("operations_shift").update({obj: get_url_to_form("Operations Shift", obj)})
                
            
            operations_site = self._operations_site_supervisor
            if operations_site:
                data_dict.update({"operations_site": dict()})
                for obj in operations_site:
                    data_dict.get("operations_site").update({obj: get_url_to_form("Operations Site", obj)})
                    
            
            projects = self._projects_manager
            if projects:
                data_dict.update({"projects": dict()})
                for obj in projects:
                    data_dict.get("projects").update({obj: get_url_to_form("Projects", obj)})
            
            reports_to = self._employee_reports_to
            if reports_to:
                data_dict.update({"reports_to": dict()})
                for obj in reports_to:
                    data_dict.get("reports_to").update(dict(name=obj.get("name"), employee_name=obj.get("employee_name"), url=get_url_to_form("EMployee", obj.get("name"))))
                    
            if self._operation_manager:
                data_dict.update({"operations_manager": True})
                
            if self.employee_object.user_id == self._attendance_manager_user_id:
                data_dict.update({"attendance_manager": True})
                
            if self._to_do:
                data_dict.update({"to_do": self._to_do})
            print(data_dict)
            
            return data_dict
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Employee Status Change Notification")
            return dict()
            
            
    def notify_authorities(self):
        data = self.generate_data()
        if data:
            is_att_man = self.employee_object.user_id == self._attendance_manager_user_id
            the_recipient = self._attendance_manager_user_id if not is_att_man else self._directors
            the_cc = self._directors if is_att_man else list()
            data_update = dict(
                employee_name=self.employee_object.employee_name,
                employee_id=self.employee_object.employee_id
            )
            data.update(data_update)
            title = f"Immediate Attention Required: Employee {self.employee_object.name} Status Change and Reassignment is required"
            msg = frappe.render_template('one_fm/templates/emails/notify_authorities_employee_status_change.html', context=data)
            print("\n\n\n\n\n\n\n", msg, "\n\n\n\n\n\n\n\n")
            # sendemail(recipients=the_recipient, subject=title, content=msg, cc=the_cc)
        
        
        
        
        
        
        
    