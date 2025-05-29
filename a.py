import requests

# Azure AD configuration
tenant_id = "XX"
client_id = "XX"
client_secret = "XX"
scope = "https://graph.microsoft.com/.default"

# Construct token endpoint URL
token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

# Request parameters
data = {
    "grant_type": "client_credentials",
    "client_id": client_id,
    "client_secret": client_secret,
    "scope": scope
}

# Send POST request to get token
response = requests.post(token_url, data=data)

if response.status_code == 200:
    token = response.json().get("access_token")
    print("Successfully obtained token:", token)
else:
    print("Failed to get token:", response.text)
