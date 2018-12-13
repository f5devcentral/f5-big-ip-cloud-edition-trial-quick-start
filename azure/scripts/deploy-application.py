#! /usr/local/bin/python2.7
import argparse
import time
import util
import azureutils
import sys

def parse_args ():
    # Ugly but expedient conversion of ansible-playbook to a parameterized python script
    parser = argparse.ArgumentParser()
    parser.add_argument("--NODE_IP", type=str, required=True)
    parser.add_argument("--SUBSCRIPTION_ID", type=str, required=True)
    parser.add_argument("--SERVICE_PRINCIPAL_SECRET", type=str, required=True)
    parser.add_argument("--TENANT_ID", type=str, required=True)
    parser.add_argument("--CLIENT_ID", type=str, required=True)
    return parser.parse_args()


def get_ssg_reference ():
    return util.req(
        "http://localhost:8100/cm/cloud/service-scaling-groups/",
        None
    ).json()

def poll_for_ssg_present (timeout=1200):
    count = 0
    while True:
        result = get_ssg_reference()

        if count >= timeout:
            sys.exit(-1)
            break

        if not result["items"]:
            time.sleep(1)
        else:
            break
        util.print_partial(".")
        count += 1

def poll_for_ssg_ready (ssg_id, timeout=1200):
    url = "http://localhost:8100/cm/cloud/service-scaling-groups/" + ssg_id
    count = 0
    while True:
        if count >= timeout:
            sys.exit(-1)
            break

        result = util.req(url, None)
        status = result.json()["status"]

        if status == "READY":
            break
        else:
            time.sleep(1)
        util.print_partial(".")
        count += 1

def deploy_application (ssg_id, node_ip, alb_dns_name):
    util.req(
        "http://localhost:8100/cm/global/tasks/apply-template",
        None,
        method="POST",
        json={
            "resources": {
                "ltm:virtual:90735960bf4b": [
                    {
                        "parameters": {
                            "name": "default_vs"
                        },
                        "parametersToRemove": [],
                        "subcollectionResources": {
                            "profiles:78b1bcfdafad": [
                                {
                                    "parameters": {},
                                    "parametersToRemove": []
                                }
                            ],
                            "profiles:2f52acac9fde": [
                                {
                                    "parameters": {},
                                    "parametersToRemove": []
                                }
                            ],
                            "profiles:9448fe71611e": [
                                {
                                    "parameters": {},
                                    "parametersToRemove": []
                                }
                            ]
                        }
                    }
                ],
                "ltm:pool:8bc5b256f9d1": [
                    {
                        "parameters": {
                            "name": "pool_0"
                        },
                        "parametersToRemove": [],
                        "subcollectionResources": {
                            "members:dec6d24dc625": [
                                {
                                    "parameters": {
                                        "port": "80",
                                        "nodeReference": {
                                            "link": "#/resources/ltm:node:c072248f8e6a/" + node_ip,
                                            "fullPath": "# " + node_ip
                                        }
                                    },
                                    "parametersToRemove": []
                                }
                            ]
                        }
                    }
                ],
                "ltm:node:c072248f8e6a": [
                    {
                        "parameters": {
                            "name": node_ip,
                            "address": node_ip
                        },
                        "parametersToRemove": []
                    }
                ],
                "ltm:monitor:http:18765a198150": [
                    {
                        "parameters": {
                            "name": "monitor-http"
                        },
                        "parametersToRemove": []
                    }
                ],
                "ltm:profile:client-ssl:78b1bcfdafad": [
                    {
                        "parameters": {
                            "name": "clientssl"
                        },
                        "parametersToRemove": []
                    }
                ],
                "ltm:profile:http:2f52acac9fde": [
                    {
                        "parameters": {
                            "name": "profile_http"
                        },
                        "parametersToRemove": []
                    }
                ]
            },
            "addAnalytics": True,
            "domains": [
                {
                    "domainName": alb_dns_name
                }
            ],
            "configSetName": "apache-test-application",
            "ssgReference": {
                "link": "https://localhost/mgmt/cm/cloud/service-scaling-groups/" + ssg_id
            },
            "azureLoadBalancer": {
                "listeners": [
                    {
                        "loadBalancerPort": 443,
                        "instancePort": 443
                    },
                    {
                        "loadBalancerPort": 80,
                        "instancePort": 80
                    }
                ]
            },
            "subPath": "apache-test-application",
            "templateReference": {
                "link": "https://localhost/mgmt/cm/global/templates/10e8d657-ed1c-3cc9-962d-f291ef02512e"
            },
            "mode": "CREATE"
        }
    )

def getDnsName(args):
    resource_group_name = ""
    alb_dns_name = ""
    try:
        resource_group_name = azureutils.getContentsOfResourceGroupLockFile()
        credentials = azureutils.getCredentials(args.TENANT_ID, args.CLIENT_ID, args.SERVICE_PRINCIPAL_SECRET)
        client = azureutils.getResourceClient(credentials , args.SUBSCRIPTION_ID)
        alb_dns_name = azureutils.getDnsName(client, resource_group_name, args.SUBSCRIPTION_ID)
        util.print_partial('Application can be accessible through https on dns Name:' + alb_dns_name)
    except Exception as e:
        util.print_partial("Exception occurred while fetching azure dns name associated with ssg's resource group "+resource_group_name+" ,failed with error:"+str(e))
    return alb_dns_name

def main():
    args = parse_args()
    util.print_partial("Waiting for SSG to be present...")
    poll_for_ssg_present()
    util.complete()

    util.print_partial("Getting SSG reference...")
    ssgs = get_ssg_reference()
    util.complete()

    # Let this reference be unsafe and tacky so that this fails loudly if the SSG is not present
    ssg_id = ssgs["items"][0]["id"]
    util.print_partial("Waiting for SSG to be ready...")
    poll_for_ssg_ready(ssg_id)
    util.complete()

    time.sleep(180) # Three minute wait for SSG to settle down

    util.print_partial("Getting ALB DNS Name reference...")
    alb_dns_name = getDnsName(args)
    util.complete()
    #TODO: can delete file here azureutils.deleteLockFile()

    util.print_partial("Deploying application...")
    deploy_application(ssg_id, args.NODE_IP, alb_dns_name)
    util.complete()

if __name__ == '__main__':
    main()