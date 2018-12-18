#! /usr/local/bin/python2.7
import time
import argparse
import util
import azureutils

SEPARATOR = '-'

config_set_name = "apache-test-application"
UNHEALTHY_THRESHOLD = 180

def parse_args ():
    # Ugly but expedient conversion of ansible-playbook to a parameterized python script
    parser = argparse.ArgumentParser()
    parser.add_argument("--SUBSCRIPTION_ID", type=str, required=True)
    parser.add_argument("--SERVICE_PRINCIPAL_SECRET", type=str, required=True)
    parser.add_argument("--TENANT_ID", type=str, required=True)
    parser.add_argument("--CLIENT_ID", type=str, required=True)
    parser.add_argument("--SSG_NAME", type=str, required=True)
    return parser.parse_args()

def getAzureCredentials(args):
    return azureutils.getCredentials(args.TENANT_ID, args.CLIENT_ID, args.SERVICE_PRINCIPAL_SECRET)

def getResourceClient(args):
    return azureutils.getResourceClient(getAzureCredentials(args) , args.SUBSCRIPTION_ID)

def getDnsName(args , resource_name):
    resource_group_name = ""
    alb_dns_name = ""
    try:
        resource_group_name = args.SSG_NAME
        client = getResourceClient(args)
        alb_dns_name = azureutils.getDnsName(client, resource_group_name, args.SUBSCRIPTION_ID , resource_name)
    except Exception as e:
        util.print_partial("Exception occurred while fetching azure dns name associated with ssg's resource group "+resource_group_name+" ,failed with error:"+str(e))
    return alb_dns_name

def getPublicIpResourceName(ssg_name=""):
    return ssg_name + SEPARATOR + config_set_name + SEPARATOR + 'pip'

def doesPublicIpExists(args,resource_name=""):
    public_ip_exists = False
    try:
        public_ip_exists = azureutils.doesPublicIpExists(getResourceClient(args) ,args.SUBSCRIPTION_ID, args.SSG_NAME , resource_name )
    except Exception as e:
        public_ip_exists = False
    return public_ip_exists

def main():
    alb_dns_name = ""
    try:
        args = parse_args()
        time.sleep(480)  # Eight minute wait for SSG to settle down

        client = getResourceClient(args)
        #util.print_partial("Validating ssg resource group creation...")
        # Sleep till the time ssg resource group gets created
        retry_count = 1
        while retry_count < UNHEALTHY_THRESHOLD:
            if azureutils.doesResourceGroupExists(client,args.SSG_NAME) == True:
                break
            else:
                retry_count += 1
                time.sleep(30)

        #util.complete()
        retry_count = 1
        resource_name = getPublicIpResourceName(args.SSG_NAME)
        #util.print_partial("Validating public ip "+resource_name+" ,resource creation...")
        while retry_count < UNHEALTHY_THRESHOLD:
            if doesPublicIpExists(args , resource_name ) == True:
                alb_dns_name = getDnsName(args , resource_name)
                #util.complete()
                break
            else:
                retry_count += 1
                time.sleep(30)

    except Exception as e:
        util.print_partial("Exception occurred while configuring the traffic generator ,failed with error:"+str(e))
    print(alb_dns_name)
    return alb_dns_name

if __name__ == '__main__':
    main()