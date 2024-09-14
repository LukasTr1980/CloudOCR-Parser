# vault_client.py
import hvac
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

def get_vault_secrets():
    # Set the Vault URL and AppRole credentials
    vault_url = os.getenv("vault_url")
    role_id = os.getenv("role_id")
    secret_id = os.getenv("secret_id")

    # Initialize the Vault client
    client = hvac.Client(url=vault_url)

    # Authenticate with Vault using AppRole
    auth_response = client.auth.approle.login(
        role_id=role_id,
        secret_id=secret_id
    )

    if 'auth' in auth_response:
        client_token = auth_response['auth']['client_token']
        print(f"Successfully authenticated with Vault! Token: {client_token}")
    else:
        print("Failed to authenticate with Vault!")
        exit()

    # Set the client token to be used in further requests
    client.token = client_token

    # Verify if the client is authenticated
    print(f"Is client authenticated: {client.is_authenticated()}")

    # Retrieve the project_id and processor_id from the Vault KV store
    project_id_path = os.getenv("project_id_path")  # Path for project_id
    processor_id_path = os.getenv("processor_id_path")  # Path for processor_id

    try:
        # Read the project_id
        project_id_response = client.secrets.kv.v2.read_secret_version(
            path=project_id_path,
            mount_point='kv',
            raise_on_deleted_version=True
        )
        project_id = project_id_response['data']['data']['id']  # Retrieve project_id

        # Read the processor_id
        processor_id_response = client.secrets.kv.v2.read_secret_version(
            path=processor_id_path,
            mount_point='kv',
            raise_on_deleted_version=True
        )
        processor_id = processor_id_response['data']['data']['id']  # Retrieve processor_id

        # Return the retrieved values
        return project_id, processor_id

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None, None
