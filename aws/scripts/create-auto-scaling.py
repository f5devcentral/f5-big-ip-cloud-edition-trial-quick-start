#! /usr/local/bin/python2.7
import sys
import argparse
import requests
from requests.auth import HTTPBasicAuth
import time
import logging
import urllib3

from util import print_partial, complete, req

# Creates auto scaling resources on BIG-IQ

# Vars which must exist in the env variable
def parse_args ():
    # Ugly but expedient conversion of ansible-playbook to a parameterized python script
    parser = argparse.ArgumentParser()
    parser.add_argument("--AWS_SUBNET_1A", type=str, required=True)
    parser.add_argument("--AWS_SUBNET_1B", type=str, required=True)
    parser.add_argument("--AWS_US_EAST_1A", type=str, required=True)
    parser.add_argument("--AWS_US_EAST_1B", type=str, required=True)
    parser.add_argument("--AWS_SSH_KEY", type=str, required=True)
    parser.add_argument("--AWS_VPC", type=str, required=True)
    parser.add_argument("--AWS_ACCESS_KEY_ID", type=str, required=True)
    parser.add_argument("--AWS_SECRET_ACCESS_KEY", type=str, required=True)
    parser.add_argument("--BIGIP_AMI", type=str, required=True)
    parser.add_argument("--BIGIQ_URI", type=str, required=True)
    parser.add_argument("--BIGIP_PWD", type=str, required=True)
    parser.add_argument("--BIGIP_USER", type=str, required=True)
    parser.add_argument("--CLOUD_PROVIDER_NAME", type=str, required=True)
    parser.add_argument("--CLOUD_ENVIRONMENT_NAME", type=str, required=True)
    parser.add_argument("--DEFAULT_REGION", type=str, required=True)
    parser.add_argument("--DEVICE_TEMPLATE_NAME", type=str, required=True)
    parser.add_argument("--LOOKUP_SERVER_LIST", type=str, required=True)
    parser.add_argument("--NTP_SERVER", type=str, required=True)
    parser.add_argument("--SSG_NAME", type=str, required=True)
    parser.add_argument("--CM_IP", type=str, required=True)
    parser.add_argument("--BIG_IQ_PWD", type=str, required=True)
    return parser.parse_args()


def post(url, json, identifier_name=None):
    # Set the id name by which duplicates will be detected
    identifier_name = "name" if not identifier_name else identifier_name

    # Check for duplicate by 'identifier_name'
    response = req(url, None)
    duplicates = [ item for item in response.json()["items"] if item[identifier_name] == json[identifier_name] ]
    # if duplicates return that duplicate entry
    if duplicates:
        return duplicates[0]

    # else post and return the response body
    response = req(url, None, json=json, method="POST")

    return response.json()


def create_device_template(env):
    return post(
        env.BIGIQ_URI + "/cm/device/templates",
        {
            "name": env.DEVICE_TEMPLATE_NAME,
            "timeZone": "UTC",
            "ntpServerList": [env.NTP_SERVER],
            "lookupServerList": [env.LOOKUP_SERVER_LIST],
            # "provisionedModuleList": [{
            #     "module": "LTM",
            #     "level": "NOMINAL"
            # }],
            "userAccountList": [{
                "username": env.BIGIP_USER,
                "password": env.BIGIP_PWD,
                "role": "admin"
            }]
        }
    )
    # var_name: device_template_result


def create_cloud_resources(env, device_template_result):
    cloud_provider_result = post(
        env.BIGIQ_URI + "/cm/cloud/providers",
        {
            "providerType": "AWS",
            "name": env.CLOUD_PROVIDER_NAME,
            "description": "AWS cloud provider",
            "awsProperties": {
                "accessKeyId": env.AWS_ACCESS_KEY_ID,
                "secretAccessKey": env.AWS_SECRET_ACCESS_KEY
            }
        }
    )

    # Creating cloud environment
    return post(
        env.BIGIQ_URI + "/cm/cloud/environments",
        {
            "name": env.CLOUD_ENVIRONMENT_NAME,
            "description": "AWS cloud environment",
            "providerReference": {
                "link": "https://localhost/mgmt/cm/cloud/providers/" + cloud_provider_result["id"]
            },
            "deviceTemplateReference": {
                "link": "https://localhost/mgmt/cm/device/templates/" + device_template_result["id"]
            },
            "awsProperties": {
                "region": env.DEFAULT_REGION,
                "vpc": env.AWS_VPC,
                "availabilityZones": [env.AWS_US_EAST_1A, env.AWS_US_EAST_1B],
                "subnets": [env.AWS_SUBNET_1A, env.AWS_SUBNET_1B],
                "restrictedSourceAddress": "0.0.0.0/0",
                "sshKeyName": env.AWS_SSH_KEY,
                "moduleSelection": "WAF",
                "licenseType": "BYOL",
                "imageId": env.BIGIP_AMI,
                "instanceType": "m3.2xlarge",
                "byolLicenseInformation": {
                    "bigiqAddress": env.CM_IP,
                    "bigiqUser": "admin",
                    "bigiqPassword": env.BIG_IQ_PWD,
                    "licensePoolName": "license-pool",
                    "unitOfMeasure": "hourly"
                }
            },
            "isVmwCluster": True
        }
    )


def create_ssg(env, cloud_environment_result):
    # Create service scaling group
    return post(
        env.BIGIQ_URI + "/cm/cloud/service-scaling-groups",
        {
            "name": env.SSG_NAME,
            "description": "AWS scaling group",
            "environmentReference": {
                "link": "https://localhost/mgmt/cm/cloud/environments/" + cloud_environment_result["id"]
            },
            "minSize": 1,
            "maxSize": 3,
            "maxSupportedApplications": 3,
            "desiredSize": 1,
            "postDeviceCreationUserScriptReference": None,
            "preDeviceDeletionUserScriptReference": None,
            "scalingPolicies": [{
                "name": "scale-out",
                "cooldown": 15,
                "direction": "ADD",
                "type": "ChangeCount",
                "value": 1
            },
            {
                "name": "scale-in",
                "cooldown": 15,
                "direction": "REMOVE",
                "type": "ChangeCount",
                "value": 1
            }]
        }
    )
# TODO Verify=False ???


def create_scale_rules_and_alerts(env, ssg_result):
    # Creating scale in alert
    post(
        env.BIGIQ_URI + "/cm/shared/policymgmt/alert-rules",
        {
            "name": env.SSG_NAME + "-device-scale-in",
            "alertTypeId": "device-scale-in-recommendation",
            "isDefault": False,
            "producerType": "device",
            "alertType": "active",
            "alertContext": "scale-in-recommendation",
            "includeInternalAlerts": False,
            "aggregationMethod": "and",
            "external": "true",
            "nestedRules": [{
                "alertTypeId": "device-cpu",
                "alertRuleType": "nested-metric",
                "warningThreshold": 5,
                "errorThreshold": 5,
                "unit": "percent",
                "operator": "less-than",
                "enabled": True
            },
            {
                "alertTypeId": "device-throughput-in",
                "alertRuleType": "nested-metric",
                "warningThreshold": 5,
                "errorThreshold": 5,
                "unit": "K",
                "operator": "greater-than",
                "enabled": True
            }],
            "ssgReferences": [{
                "name": env.SSG_NAME,
                "link": "https://localhost/mgmt/cm/cloud/service-scaling-groups/" + ssg_result["id"]
            }],
            "alertRuleType": "aggregated",
            "isPublic": False
        }
    )

    # Creating scale in alert OR
    post(
        env.BIGIQ_URI + "/cm/shared/policymgmt/alert-rules",
        {
            "aggregationMethod": "or",
            "producerType": "ssg",
            "name": env.SSG_NAME + "-device-scale-in",
            "alertTypeId": "ssg-scale-in-recommendation",
            "includeInternalAlerts": True,
            "alertRuleReferences": [{
                "name": env.SSG_NAME + "-device-scale-in",
                "link": "https://localhost/mgmt/cm/shared/policymgmt/alert-rules/" + env.SSG_NAME + "-device-scale-in"
            }],
            "external": True,
            "ssgReferences": [{
                "name": env.SSG_NAME,
                "link": "https://localhost/mgmt/cm/cloud/service-scaling-groups/" + ssg_result["id"]
            }],
            "alertContext": "scale-in-recommendation",
            "alertRuleType": "aggregated",
            "alertType": "active",
            "isDefault": False,
            "isPublic": False
        }
    )

    # Create scale in workflow rule
    post(
        env.BIGIQ_URI + "/cm/shared/policymgmt/workflow-rules",
        {
            "workflowRuleName": env.SSG_NAME + "-scale-in",
            "workflowParameters": {
                "parameters": {
                    "ssgName": env.SSG_NAME,
                    "scalingPolicyName": "scale-in"
                }
            },
            "targetWorkflowUri": "https://localhost/mgmt/cm/cloud/tasks/handle-scaling-alert",
            "alertRuleReference": {
                "link": "https://localhost/mgmt/cm/shared/policymgmt/alert-rules/" + env.SSG_NAME + "-ssg-scale-in"
            },
            "sendEmail": False,
            "sendEmailContacts": None,
            "sendSNMP": False
        },
        identifier_name="workflowRuleName"
    )

    # Creating scale out alert
    post(
        env.BIGIQ_URI + "/cm/shared/policymgmt/alert-rules",
        {
            "aggregationMethod": "or",
            "producerType": "device",
            "name": env.SSG_NAME + "-device-scale-out",
            "alertTypeId": "device-scale-out-recommendation",
            "includeInternalAlerts": False,
            "nestedRules": [{
                "alertRuleType": "nested-metric",
                "alertTypeId": "device-cpu",
                "warningThreshold": 75,
                "errorThreshold": 75,
                "unit": "percent",
                "operator": "greater-than",
                "enabled": True
            },
            {
                "alertRuleType": "nested-metric",
                "alertTypeId": "device-throughput-in",
                "warningThreshold": 20,
                "errorThreshold": 20,
                "unit": "K",
                "operator": "greater-than",
                "enabled": True
            }],
            "external": True,
            "ssgReferences": [{
                "name": env.SSG_NAME,
                "link": "https://localhost/mgmt/cm/cloud/service-scaling-groups/" + ssg_result["id"]
            }],
            "alertContext": "scale-out-recommendation",
            "alertRuleType": "aggregated",
            "alertType": "active",
            "isDefault": False,
            "isPublic": False
        }
    )

    # Create scale in alert
    post(
        env.BIGIQ_URI + "/cm/shared/policymgmt/alert-rules",
        {
            "aggregationMethod": "or",
            "producerType": "ssg",
            "name": env.SSG_NAME + "-ssg-scale-out",
            "alertTypeId": "ssg-scale-out-recommendation",
            "includeInternalAlerts": True,
            "alertRuleReferences": [{
                "name": env.SSG_NAME + "-device-scale-out",
                "link": "https://localhost/mgmt/cm/shared/policymgmt/alert-rules/" + env.SSG_NAME + "-device-scale-out"
            }],
            "external": True,
            "ssgReferences": [{
                "name": env.SSG_NAME,
                "link": "https://localhost/mgmt/cm/cloud/service-scaling-groups/" + ssg_result["id"]
            }],
            "alertContext": "scale-out-recommendation",
            "alertRuleType": "aggregated",
            "alertType": "active",
            "isDefault": False,
            "isPublic": False
        }
    )

    # Create scale in workflow rule
    post(
        env.BIGIQ_URI + "/cm/shared/policymgmt/workflow-rules",
        {
            "workflowRuleName": env.SSG_NAME + "-scale-out",
            "workflowParameters": {
                "parameters": {
                    "ssgName": env.SSG_NAME,
                    "scalingPolicyName": "scale-out"
                }
            },
            "targetWorkflowUri": "https://localhost/mgmt/cm/cloud/tasks/handle-scaling-alert",
            "alertRuleReference": {
                "link": "https://localhost/mgmt/cm/shared/policymgmt/alert-rules/" + env.SSG_NAME + "-ssg-scale-out"
            },
            "sendEmail": False,
            "sendEmailContacts": None,
            "sendSNMP": False
        },
        identifier_name="workflowRuleName"
    )

    # Create scale out alert
    post(
        env.BIGIQ_URI + "/cm/shared/policymgmt/alert-rules",
        {
            "name": env.SSG_NAME + "-active-device-health",
            "alertTypeId": "device-health",
            "isDefault": False,
            "isPublic": False,
            "producerType": "device",
            "alertType": "active",
            "alertContext": "health",
            "includeInternalAlerts": True,
            "aggregationMethod": "or",
            "alertRuleType": "aggregated",
            "ssgReferences": [{
                "name": env.SSG_NAME,
                "link": "https://localhost/mgmt/cm/cloud/service-scaling-groups/" + ssg_result["id"]
            }],
            "external": True,
            "nestedRules": [{
                "alertRuleType": "nested-metric",
                "alertTypeId": "device-cpu",
                "unit": "percent",
                "operator": "greater-than",
                "enabled": True,
                "warningThreshold": 75,
                "errorThreshold": 90
            }]
        }
    )

    # Create scale out workflow rule
    post(
        env.BIGIQ_URI + "/cm/shared/policymgmt/workflow-rules",
        {
            "workflowRuleName": env.SSG_NAME + "-health",
            "workflowParameters": {
                "parameters": {
                    "ssgName": env.SSG_NAME
                }
            },
            "alertRuleReference": {
                "link": "https://localhost/mgmt/cm/shared/policymgmt/alert-rules/" + env.SSG_NAME + "-active-device-health"
            },
            "sendEmail": False,
            "sendEmailContacts": None,
            "sendSNMP": False
        },
        identifier_name="workflowRuleName"
    )

    # Create scale out alert
    post(
        env.BIGIQ_URI + "/cm/shared/policymgmt/alert-rules",
        {
            "name": env.SSG_NAME + "-active-ssg-health",
            "alertTypeId": "ssg-health",
            "isDefault": False,
            "producerType": "ssg",
            "alertType": "active",
            "alertContext": "health",
            "includeInternalAlerts": True,
            "aggregationMethod": "or",
            "external": True,
            "alertRuleType": "aggregated",
            "ssgReferences": [{
                "name": env.SSG_NAME,
                "link": "https://localhost/mgmt/cm/cloud/service-scaling-groups/" + ssg_result["id"]
            }],
            "alertRuleReferences": [{
                "name": env.SSG_NAME + "-active-device-health",
                "link": "https://localhost/mgmt/cm/shared/policymgmt/alert-rules/" + env.SSG_NAME + "-active-device-health"
            }]
        }
    )

def randomize_ssg_name (ssg_name):
    ssg_name = ssg_name[0:10]
    random_part = str(int(round(time.time() * 1000)))
    return ssg_name + (random_part[-14:])


def main():
    print("Parsing arguments...")
    env = parse_args()
    env.SSG_NAME = randomize_ssg_name(env.SSG_NAME)
    print("Fetching device template...")
    device_template_result = create_device_template(env)
    print("Creating cloud resources...")
    cloud_environment_result = create_cloud_resources(env, device_template_result)
    print("Launching SSG...")
    ssg_result = create_ssg(env, cloud_environment_result)
    print("Creating scale workflows and rules...")
    create_scale_rules_and_alerts(env, ssg_result)

if __name__ == '__main__':
    main()
