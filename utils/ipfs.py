import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Kaleido IPFS API endpoint
KALEIDO_IPFS_URL = "https://u0zivz3dd7-u0yb1q9rn5-ipfs.us0-aws.kaleido.io/api/v0/add"

# App ID and Password for Kaleido's IPFS service
KALEIDO_APP_ID = "u0h9j1qe7l"
KALEIDO_APP_PASSWORD = "zs8iVJFnHup6pOHE2bSK1st0xWQXUcYlIO_X0CAIJ34"

def upload_to_ipfs(file_path):
    try:
        # Open the file in binary mode
        with open(file_path, 'rb') as file:
            # Set up authentication using Kaleido App ID and Password
            auth = (KALEIDO_APP_ID, KALEIDO_APP_PASSWORD)

            # Upload the file to Kaleido's IPFS service with the form entry 'path'
            response = requests.post(
                KALEIDO_IPFS_URL,
                files={'path': file},  # Kaleido requires the form entry to be named 'path'
                auth=auth  # Add authentication
            )

            # Check if the request was successful
            if response.status_code == 200:
                # Print the entire JSON response for debugging
                print(f"Full response JSON: {response.json()}")

                # Try to return the IPFS hash (CID) of the uploaded file
                response_json = response.json()
                if 'Hash' in response_json:
                    return response_json['Hash']
                else:
                    print("Hash not found in the response.")
                    return None
            else:
                print(f"Failed to upload file to IPFS: {response.text}")
                return None
    except Exception as e:
        print(f"Error while uploading file to IPFS: {e}")
        return None










#KALEIDO_APP_ID = "u0h9j1qe7l"
#KALEIDO_APP_PASSWORD = "zs8iVJFnHup6pOHE2bSK1st0xWQXUcYlIO_X0CAIJ34"