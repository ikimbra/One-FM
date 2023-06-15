# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from __future__ import print_function

import os.path

import csv
import os
import re
import json

import frappe
import datetime
import frappe.permissions
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.utils import cint, cstr, format_datetime, format_duration, formatdate, parse_json
from frappe.utils.csvutils import UnicodeWriter
import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient import discovery
import gspread
from frappe.utils import get_site_name
from google.oauth2 import service_account

#initialize Google Sheet Service

SERVICE_ACCOUNT_FILE = os.getcwd()+"/"+cstr(frappe.local.site) + frappe.local.conf.google_sheet

SCOPES = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

service = discovery.build('sheets', 'v4', credentials=credentials)
drive_api = build('drive', 'v3', credentials=credentials)

def data_from_query():
    feb_start = datetime.date(2023, 2, 1)
    feb_end = datetime.date(2023, 2, 28)
    mar_start = datetime.date(2023, 3, 1)
    mar_end = datetime.date(2023, 3, 31)
    apr_start = datetime.date(2023, 4, 1)
    apr_end = datetime.date(2023, 4, 30)
    may_start = datetime.date(2023, 5, 1)
    may_end = datetime.date(2023, 5, 31)
    temp = {}
    data = frappe.db.sql(f"""SELECT at.employee,
										COUNT(CASE WHEN at.attendance_date >= '{feb_start}' AND at.attendance_date <= '{feb_end}' THEN 1 END) AS Feb,
										COUNT(CASE WHEN at.attendance_date >= '{mar_start}' AND at.attendance_date <= '{mar_end}' THEN 1 END) AS Mar,
										COUNT(CASE WHEN at.attendance_date >= '{apr_start}' AND at.attendance_date <= '{apr_end}' THEN 1 END) AS Apr,
										COUNT(CASE WHEN at.attendance_date >= '{may_start}' AND at.attendance_date <= '{may_end}' THEN 1 END) AS May
                    FROM `tabAttendance` at 
                    WHERE at.status IN ('Present', 'Day Off', 'Work From Home')
                    AND employee = 'HR-EMP-01868'
                    GROUP BY at.employee
                    """, as_dict=1)
    for d in data:
        employee = d['employee']
        temp[employee] = {'Feb':d['Feb'],'Mar':d['Mar'],'Apr':d['Apr'],'May':d['May']}
    data = temp
    return data

def get_data():
    sheetID = "1CevLx2ZOsCqP5-6fLNgxSEuVS_AMuRcsP-mBY3gBGjk"
    rangeName = 'Data'

    data = data_from_query()
    
    employee_list = get_values(sheetID, rangeName)
    del employee_list[0]
    data_emp = list(data.keys())
    # print(employee_list)
    for emp in employee_list:
      employee = emp[0]
      if employee in data_emp:
          if int(data[employee].get('Feb')) > int(emp[1]):
              print(employee, int(data[employee].get('Feb')) , int(emp[1]))

def find_duplicate():
    duplicate_att = frappe.db.sql(f""" DELETE at1 FROM `tabAttendance` at1 
          INNER JOIN `tabAttendance` at2 ON
                at1.employee = at2.employee
                AND at1.attendance_date = at2.attendance_date
                AND at1.roster_type = at2.roster_type
                AND at1.name != at2.name
            WHERE
                at1.attendance_date >= '2023-02-01' AND at1.attendance_date <= '2023-05-31' 
                AND at1.status = 'Absent'""", as_dict=1)
                

#Fetch data from the sheet.
def get_values(sheetID, rangeName):
    """
    Creates the batch_update the user has access to.
    Load pre-authorized user credentials from the environment.
    TODO(developer) - See https://developers.google.com/identity
    for guides on implementing OAuth2 for the application.
        """
    # pylint: disable=maybe-no-member
    try:
        service = build('sheets', 'v4', credentials=credentials)

        result = service.spreadsheets().values().get(
            spreadsheetId=sheetID, range=rangeName).execute()
        rows = result.get('values', [])
        
        return rows
        
    except HttpError as error:
        print(f"An error occurred: {error}")
        return error


# # for each_row in sheet:

# SELECT DISTINCT employee_id, attendance_date
# FROM attendance_table
# WHERE attendance_status IN ('Present', 'Day Off','Holiday', 'OnLeave'
#   AND attendance_date >= [start_date]
#   AND attendance_date <= [end_date]
# GROUP BY employee_id
# HAVING COUNT(DISTINCT attendance_date) = [required_present_count]


# CREATE TEMPORARY TABLE temp_duplicates AS
# SELECT employee_id, attendance_date, COUNT(*) AS duplicate_count
# FROM attendance_table
# GROUP BY employee_id, attendance_date
# HAVING COUNT(*) > 1;

# DELETE FROM attendance_table
# WHERE (employee_id, attendance_date) IN (
#     SELECT employee_id, attendance_date
#     FROM temp_duplicates
# );