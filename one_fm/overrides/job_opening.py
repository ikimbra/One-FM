import frappe
from frappe import _
from frappe.utils import (
    get_timestamp
)
from one_fm import linked_in

@frappe.whitelist()
def create_linked_in_job_post(job_opening):
	job_opening_obj = frappe.get_doc('Job Opening', job_opening)
	# TODO: employement type needs to be defined in Job Opening
	# FULL_TIME, PART_TIME, CONTRACT, INTERNSHIP, TEMPORARY, VOLUNTEER
	employment_status = 'FULL_TIME'
	work_location = 'Kuwait'
	workplace_types = ['Remote', 'Hybrid', 'On-site']
	if 'Hybrid' in workplace_types or 'On-Site' in workplace_types:
		'''
			work_location in either of the following formats "CITY, STATE, COUNTRY", "CITY, STATE", "CITY, PROVINCE",
			"CITY, COUNTRY" or "POSTALCODE, COUNTRYCODE"
		'''
		work_location = 'Kuwait, Hwalli'

	# The date is epoch timestamp in milliseconds (UTC) and should not be a future time
	listed_at = get_timestamp(job_opening_obj.one_fm_job_opening_created)*1000

	job_application_url = f"{frappe.utils.get_url()}/careers/opening/{job_opening_obj.name}"

	company_id = "2414183" # TODO: Need to find the company id
	integration_context = f"urn:li:organization:{company_id}"

	# alternateLocations can be added, Maximum up to seven alternate locations are allowed, String Array
	# countryCode, postalCode - Only if location is not provided
	# experienceLevel - Available options are: ENTRY_LEVEL, MID_SENIOR_LEVEL, DIRECTOR, EXECUTIVE, INTERNSHIP, ASSOCIATE, NOT_APPLICABLE

	elements = [
		{
			"integrationContext": integration_context,
			"companyApplyUrl": job_application_url,
			"description": _(job_opening_obj.description),
			"employmentStatus": employment_status,
			"externalJobPostingId": job_opening_obj.name,
			"listedAt": listed_at,
			"jobPostingOperationType": "CREATE", # CREATE, UPDATE, RENEW, CLOSE
			"title": job_opening_obj.designation,
			"location": work_location,
			"workplaceTypes": workplace_types
		}
	]

	response = linked_in.create_simple_job_post(elements)

	response_details = {}
	if response['status']:
		response_details['linked_in_job_post_status_code'] = response['status']
	if response['message']:
		response_details['linked_in_job_post_response_message'] = response['message']
	if response['id']:
		response_details['linked_in_job_id'] = response['id']
	if response_details:
		job_opening_obj.db_set(response_details)
	return response
