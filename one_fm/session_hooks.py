import frappe

def on_session_creation(login_manager):
    print(login_manager)
    try:
        frappe.local.session.employee = frappe.db.get_value('Employee', {'user_id':frappe.session.user}, 'name')
        frappe.local.employee = frappe.session.employee
        frappe.local.user.employee = frappe.session.employee
        frappe.local.user_defaults = frappe.session.employee
        frappe.local.boot.user.employee = frappe.session.employee
        # print(frappe.session.employee)
    except Exception as e:
        print(str(e))
        frappe.session['employee'] = ''
    
    print('\n\n')