#! /usr/local/bin/python2.7
import argparse
import subprocess
import os
from azure.mgmt.resource import ResourceManagementClient
from azure.common.credentials import ServicePrincipalCredentials

api_version = "2018-10-01"
subscription_holder = "{subscription}"
resource_group_holder = "{resourceGroupName}"
public_ip_holder = "/subscriptions/"+subscription_holder+"/resourceGroups/"+resource_group_holder+"/providers/Microsoft.Network/publicIPAddresses/"
resource_file = "resource_group_file"

# Vars which must exist in the env variable
# RESOURCE ~ resource group
def parse_args ():
    parser = argparse.ArgumentParser()
    parser.add_argument("--RESOURCE", type=str, required=True)
    parser.add_argument("--SUBSCRIPTION_ID", type=str, required=True)
    parser.add_argument("--SERVICE_PRINCIPAL_SECRET", type=str, required=True)
    parser.add_argument("--TENANT_ID", type=str, required=True)
    parser.add_argument("--CLIENT_ID", type=str, required=True)
    return parser.parse_args()

# Method to create a file with content
def createLockfile(lockFileName = resource_file , writestring=None):
    with open(lockFileName,"w") as lock_file:
        lock_file.write(str(writestring))
        lock_file.close()

# Method to delete the file
def deleteLockFile(lockFileName = resource_file):
    os.remove(lockFileName)

def writeAzureResourceGroupToFile(resource_group_name):
    try:
        print("Writing content to file "+resource_group_name)
        createLockfile(resource_file,resource_group_name)
    except Exception as e:
        print("writing "+resource_group_name+", to file failed.. "+e)

def getContentsOfResourceGroupLockFile(lockFileName = resource_file):
    command = 'cat ' + lockFileName + ";exit 0"
    contents = subprocess.check_output(command, shell=True).rstrip()
    print("contents present in lock file are " + str(contents))
    return str(contents)

# Get Azure credentials given tenant id , client id and service principal secret
def getCredentials(TENANT_ID=None ,CLIENT=None , KEY=None ):
    credentials = ServicePrincipalCredentials(
        client_id = CLIENT,
        secret = KEY,
        tenant = TENANT_ID
    )
    return credentials

# Get Azure resource client for given subscription_id and azure credentials
def getResourceClient(credentials=None , subscription_id=None):
    resource_client = ResourceManagementClient(credentials,subscription_id)
    return resource_client

# Get Azure resource group for given resource group name and azure resource client
def getResourceGroup(resource_group=None,client = None):
    return client.resource_groups.get(resource_group)

# Get DnsName/FQDN for given resource group and public ip resource name
def getDnsName(client = None, resource_group = None, subscription_id = None , public_ip_resource_name = ''):
    dns_name = ""
    try:
        resource_ip_id = getPublicIpResourceName(resource_group, subscription_id , public_ip_resource_name)
        for item in client.resources.list_by_resource_group(resource_group):
            resource_id = "{}".format(item.id)
            is_public_ip_resource = resource_id.startswith(resource_ip_id)
            if is_public_ip_resource and doesResourceExists(client, resource_id):
                dns_name = getFqdn(client, resource_id)
    except Exception as e:
        print(e)
    return dns_name

# Get FQDN for given resource id
# resource id should be properly formatted
# eg:/subscriptions/{subsctiption_id}/resourceGroups/{resource_group_name}/providers/Microsoft.Network/publicIPAddresses/{public_ip_name}
def getFqdn(client, resource_id):
    resource = getResourceById(client, resource_id)
    resource_resp = resource.properties
    resource_properties = resource_resp["dnsSettings"]
    dns_name = resource_properties["fqdn"]
    return dns_name

# Supplement method to construct formatted public ip resource id
def getPublicIpResourceName(resource_group, subscription_id , public_ip_resource=""):
    resource_ip_id = public_ip_holder.replace(subscription_holder, subscription_id)
    resource_ip_id = resource_ip_id.replace(resource_group_holder, resource_group)
    return resource_ip_id + public_ip_resource

# Checks whether a public ip resource with given resource_name exists or not
def doesPublicIpExists(client=None , subscription_id="", resource_group="" , resource_name="" ):
    resource_id = getPublicIpResourceName(resource_group , subscription_id ,resource_name)
    return getResourceById(client, resource_id) is not None

def doesResourceExists(client = None , resource_id = None):
    return getResourceById(client,resource_id) is not None

def getResourceById(client = None , resource_id = None):
    return client.resources.get_by_id(resource_id,api_version)

def doesResourceGroupExists(client = None , name = ""):
    return client.resources.list_by_resource_group(name) is not None

# Method to print detailed information about given resource group object
def print_item(group):
    """Print a ResourceGroup instance."""
    print("\tName: {}".format(group.name))
    print("\tId: {}".format(group.id))
    print("\tLocation: {}".format(group.location))
    print("\tTags: {}".format(group.tags))
    print_properties(group.properties)

# Method to print detailed information about given resource group object properties
def print_properties(props):
    """Print a ResourceGroup properties instance."""
    if props and props.provisioning_state:
        print("\tProperties:")
        print("\t\tProvisioning State: {}".format(props.provisioning_state))
    print("\n\n")

def main():
    try:
        print("Parsing arguments...")
        env = parse_args()
        subscription_id = env.SUBSCRIPTION_ID
        # Tenant ID for your Azure Subscription
        TENANT_ID = env.TENANT_ID
        # Your Service Principal App ID
        CLIENT = env.CLIENT_ID
        # Your Service Principal Password
        KEY = env.SERVICE_PRINCIPAL_SECRET
        creds = getCredentials(TENANT_ID,CLIENT,KEY)
        client = getResourceClient(creds)
        GROUP_NAME = env.RESOURCE
        resource_group = getResourceGroup(GROUP_NAME,client)
        print("resource group name:" + str(resource_group))
        #print("resource group" + resource_group.id)
        id = getDnsName(client, GROUP_NAME, subscription_id)
        print('dns Name'+id)
    except Exception as e:
        print("Exception occured while execution of azure dns name related functions:"+str(e))
#    for item in client.resources.list_by_resource_group(GROUP_NAME):
#        print_item(item)

if __name__ == '__main__':
    main()
