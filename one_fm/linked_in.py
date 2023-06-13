import requests

def authenticate_linkedin():
	api_base_url = "https://www.linkedin.com/oauth/v2/accessToken"

	response = requests.post(
		api_base_url,
		{
			"grant_type": "client_credentials",
			"client_id":"86vlclxladnsmp",
			"client_secret":"GCNIvEyCYYRWlVJi"
		},
		headers={
			"Content-Type": "application/x-www-form-urlencoded",
		},
	)

	print(response.json())

def create_simple_job_post(elements):
	accessToken = f"AQVIEHTZZxEEHkLnp_bLKDFv7gpZV6mTq8hTPWZrR_uuDnDNUYtygkhNGHJTSa2iyvYiC4vAtYMsasxO07HbTv4DMI1ulKCBldvpJUJj1zaT0mdDKZslpQftr1DFHDo1egpGeLYPlrMbJpRRvRwGjLNdiARNTxWSM4K7YQ9eciL4thZrB87FjGuUPKUJsBvzRgLWz6boW24V18f_HlSwnjmTMEJ_vtgVM2LxiSnQJ_LrK_udSN7qJN4Omcm078l2Le-m5YjXHxuYKu7Bc0fEgVIF78FZW3uo6Uae_YUDSpSE5p-S7eQDFWpYtwS7vX7u24_b5CiBeCDcA-Vze-2beuI1OmwChA"
	api_base_url = "https://api.linkedin.com/v2/simpleJobPostings"

	response = requests.post(
		api_base_url,
		{"elements": elements},
		headers={
			"Authorization": "Bearer "+accessToken,
			"X-restli-method": "batch_create"
		},
	)

	print(response.json())
	return response.json()
