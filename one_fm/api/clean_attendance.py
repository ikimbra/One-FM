# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from __future__ import print_function

import os.path

import csv
import os
import re
import json

import frappe
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

def initialize_service(self):
    #initialize Google Sheet Service

    SERVICE_ACCOUNT_FILE = os.getcwd()+"/"+cstr(frappe.local.site) + frappe.local.conf.google_sheet

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    service = discovery.build('sheets', 'v4', credentials=credentials)
    drive_api = build('drive', 'v3', credentials=credentials)
    
    return {"credentials":credentials, "service": service, "drive_api": drive_api}

#Fetch data from the sheet.
# for each_row in sheet:

SELECT DISTINCT employee_id, attendance_date
FROM attendance_table
WHERE attendance_status IN ('Present', 'Day Off','Holiday', 'OnLeave'
  AND attendance_date >= [start_date]
  AND attendance_date <= [end_date]
GROUP BY employee_id
HAVING COUNT(DISTINCT attendance_date) = [required_present_count]


CREATE TEMPORARY TABLE temp_duplicates AS
SELECT employee_id, attendance_date, COUNT(*) AS duplicate_count
FROM attendance_table
GROUP BY employee_id, attendance_date
HAVING COUNT(*) > 1;

DELETE FROM attendance_table
WHERE (employee_id, attendance_date) IN (
    SELECT employee_id, attendance_date
    FROM temp_duplicates
);