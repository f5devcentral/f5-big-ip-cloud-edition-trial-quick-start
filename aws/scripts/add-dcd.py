#! /usr/local/bin/python2.7

import argparse
import requests
import sys
import time
import util
import logging
import urllib3
# Add a data collection device to a BIG IQ CM device
util.kill_ssl_warnings(logging, urllib3)

# Return an object representing the arguments passed in to this program
def parse_args ():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--BIGIQ_ADDR",
        type=str,
        default="localhost",
        help="Address of BIG-IQ CM instance to which a data collection device will be added. Optional: defaults to localhost"
    )
    parser.add_argument(
        "--DCD_IP_ADDRESS",
        type=str,
        required=True,
        help="IP of the BIG-IQ DCD instance. This must already be configured with the logging_node personality"
    )
    parser.add_argument(
        "--DCD_USERNAME",
        type=str,
        required=True,
        help="Username to use for the DCD"
    )
    parser.add_argument(
        "--DCD_PWD",
        type=str,
        required=True,
        help="Password to use for the DCD"
    )
    parser.add_argument(
        "--BIGIQ_USERNAME",
        type=str,
        help="Username to use for the BIG-IQ CM instance. This is not necessary when running against localhost"
    )
    parser.add_argument(
        "--BIGIQ_PWD",
        type=str,
        help="Password to use for the BIG-IQ CM instance. This is not necessary when running against localhost"
    )
    parser.add_argument(
        "--TIMEOUT_SEC",
        type=str,
        help="Time to wait in seconds for the services to come available. This is approximate. Total wait time will be strictly greater than or equal to the time specified.",
        default=60
    )
    args = parser.parse_args()
    return args

# Determine the environment from url, either localhost or remote
def get_environment (address, username=None, pwd=None):
    return util.get_environment(address, username, pwd)

# Returns UUID of new node
def add_node (env, ip_address, username, password):
    # POST
    # https://18.232.246.131/mgmt/cm/shared/esmgmt/add-node
    # {"address":"35.173.117.194","bigIqUsername":"admin","bigIqPassword":"P@$$Word!","httpPort":9200,"transportAddress":"10.1.1.230","transportPort":9300,"zone":"default"}
    # Returns something like
    # {"address":"35.173.117.194","transportAddress":"10.1.1.230","httpPort":"9200","transportPort":"9300","zone":"default","bigIqUsername":"admin","bigIqPassword":"P@$$Word!","id":"0d043d33-7619-404b-b184-58aa5c8ef0cf","status":"STARTED","userReference":{"link":"https://localhost/mgmt/shared/authz/users/admin"},"identityReferences":[{"link":"https://localhost/mgmt/shared/authz/users/admin"}],"ownerMachineId":"1f7b1aa0-8fa6-498a-bae6-9c7bb9318435","taskWorkerGeneration":1,"generation":1,"lastUpdateMicros":1525977026342300,"kind":"cm:shared:esmgmt:add-node:esaddnodetaskstate","selfLink":"https://localhost/mgmt/cm/shared/esmgmt/add-node/0d043d33-7619-404b-b184-58aa5c8ef0cf"}
    node_res = util.req(
        env['base_url'] + "cm/shared/esmgmt/add-node",
        env['auth'],
        method="POST",
        json={
            "address": ip_address,
            "bigIqUsername": username,
            "bigIqPassword": password,
            "httpPort": 9200,
            "transportAddress": ip_address,
            "transportPort":9300,
            "zone":"default"
        }
    )
    # Won't reach this point w/o 200 OK
    return node_res.json()['id']


def poll_for_result (env, uuid):
    # Based on a the UUID returned from add_node poll this endpoint until something happens
    # GET
    # https://18.232.246.131/mgmt/cm/shared/esmgmt/add-node/0d043d33-7619-404b-b184-58aa5c8ef0cf
    # Returns something like this in progress
    # {"address":"35.173.117.194","bigIqPassword":"","bigIqUsername":"admin","cluster":{"clusterName":"39d30597-4d09-419b-ad64-450e5ba01edf","primaryMachineId":"1f7b1aa0-8fa6-498a-bae6-9c7bb9318435","clusterIndexCollectionReference":{"link":"https://localhost/mgmt/cm/shared/esmgmt/cluster/3fa8567f-b10d-49d1-8e50-09d8741ada4e/indices","isSubcollection":true},"nodes":[{"machineId":"1f7b1aa0-8fa6-498a-bae6-9c7bb9318435","allowData":false,"allowMaster":true,"httpAddress":"127.0.0.1","httpPort":"9200","transportAddress":"10.1.1.169/24","transportPort":"9300","zone":"default","mlockall":false,"repo":"/var/config/rest/elasticsearch/data","generation":0,"lastUpdateMicros":0}],"numberOfDataNodes":0,"id":"3fa8567f-b10d-49d1-8e50-09d8741ada4e","generation":1,"lastUpdateMicros":1525976702076194,"kind":"cm:shared:esmgmt:cluster:esclusterinstancestate","selfLink":"https://localhost/mgmt/cm/shared/esmgmt/cluster/3fa8567f-b10d-49d1-8e50-09d8741ada4e"},"currentStep":"CHECK_DEVICE_STATUS_ADD","deviceReference":{"link":"https://localhost/mgmt/shared/resolver/device-groups/cm-esmgmt-logging-group/devices/f5258bfe-b583-439e-ab92-1d063e3366d1"},"deviceState":{"uuid":"f5258bfe-b583-439e-ab92-1d063e3366d1","deviceUri":"https://35.173.117.194:443","machineId":"f5258bfe-b583-439e-ab92-1d063e3366d1","state":"PENDING","address":"35.173.117.194","httpsPort":443,"properties":{"isLoggingNode":true},"groupName":"cm-esmgmt-logging-group","generation":1,"lastUpdateMicros":1525977026535394,"kind":"shared:resolver:device-groups:restdeviceresolverdevicestate","selfLink":"https://localhost/mgmt/shared/resolver/device-groups/cm-esmgmt-logging-group/devices/f5258bfe-b583-439e-ab92-1d063e3366d1"},"generation":5,"httpPort":"9200","id":"0d043d33-7619-404b-b184-58aa5c8ef0cf","identityReferences":[{"link":"https://localhost/mgmt/shared/authz/users/admin"}],"kind":"cm:shared:esmgmt:add-node:esaddnodetaskstate","lastUpdateMicros":1525977028708833,"ownerMachineId":"1f7b1aa0-8fa6-498a-bae6-9c7bb9318435","selfLink":"https://localhost/mgmt/cm/shared/esmgmt/add-node/0d043d33-7619-404b-b184-58aa5c8ef0cf","startDateTime":"2018-05-10T11:30:26.360-0700","status":"STARTED","transportAddress":"10.1.1.230","transportPort":"9300","userReference":{"link":"https://localhost/mgmt/shared/authz/users/admin"},"username":"admin","zone":"default"}
    i = 0
    while i < 120:
        add_node_res = util.req(env['base_url'] + "cm/shared/esmgmt/add-node/" + uuid, env['auth'])
        status = add_node_res.json()['status']
        if status == "FINISHED":
            break
        elif status == "FAILED":
            print("")
            print("Node addition failed with:")
            print(add_node_res.json()['errorMessage'])
            sys.exit(1)

        util.print_partial(".")
        time.sleep(2)
        i += 2

    # Returns something like this on failure
    # {"address":"35.173.117.194","bigIqPassword":"","bigIqUsername":"admin","cluster":{"clusterName":"39d30597-4d09-419b-ad64-450e5ba01edf","primaryMachineId":"1f7b1aa0-8fa6-498a-bae6-9c7bb9318435","clusterIndexCollectionReference":{"link":"https://localhost/mgmt/cm/shared/esmgmt/cluster/3fa8567f-b10d-49d1-8e50-09d8741ada4e/indices","isSubcollection":true},"nodes":[{"machineId":"1f7b1aa0-8fa6-498a-bae6-9c7bb9318435","allowData":false,"allowMaster":true,"httpAddress":"127.0.0.1","httpPort":"9200","transportAddress":"10.1.1.169/24","transportPort":"9300","zone":"default","mlockall":false,"repo":"/var/config/rest/elasticsearch/data","generation":0,"lastUpdateMicros":0}],"numberOfDataNodes":0,"id":"3fa8567f-b10d-49d1-8e50-09d8741ada4e","generation":1,"lastUpdateMicros":1525976702076194,"kind":"cm:shared:esmgmt:cluster:esclusterinstancestate","selfLink":"https://localhost/mgmt/cm/shared/esmgmt/cluster/3fa8567f-b10d-49d1-8e50-09d8741ada4e"},"currentStep":"POST_DEVICE_ES","deviceReference":{"link":"https://localhost/mgmt/shared/resolver/device-groups/cm-esmgmt-logging-group/devices/f5258bfe-b583-439e-ab92-1d063e3366d1"},"deviceState":{"uuid":"f5258bfe-b583-439e-ab92-1d063e3366d1","deviceUri":"https://35.173.117.194:443","machineId":"f5258bfe-b583-439e-ab92-1d063e3366d1","state":"ACTIVE","address":"35.173.117.194","httpsPort":443,"hostname":"bigiq1","version":"6.0.0","product":"BIG-IQ","edition":"Final","build":"0.0.1490","restFrameworkVersion":"6.0.0-0.0.1490","managementAddress":"10.1.1.230","mcpDeviceName":"/Common/localhost","properties":{"shared:resolver:device-groups:discoverer":"1f7b1aa0-8fa6-498a-bae6-9c7bb9318435","isLoggingNode":true},"isClustered":false,"isVirtual":true,"groupName":"cm-esmgmt-logging-group","slots":[{"volume":"HD1.1","product":"BIG-IQ","version":"6.0.0","build":"0.0.1490","isActive":true}],"generation":3,"lastUpdateMicros":1525977031900228,"kind":"shared:resolver:device-groups:restdeviceresolverdevicestate","selfLink":"https://localhost/mgmt/shared/resolver/device-groups/cm-esmgmt-logging-group/devices/f5258bfe-b583-439e-ab92-1d063e3366d1"},"endDateTime":"2018-05-10T11:30:33.773-0700","errorMessage":"Unable to add Data Collection Device 35.173.117.194 to logging cluster with error 'invalid\r\ntransportAddress: 10.1.1.169/24'","generation":7,"httpPort":"9200","id":"0d043d33-7619-404b-b184-58aa5c8ef0cf","identityReferences":[{"link":"https://localhost/mgmt/shared/authz/users/admin"}],"kind":"cm:shared:esmgmt:add-node:esaddnodetaskstate","lastUpdateMicros":1525977033823047,"ownerMachineId":"1f7b1aa0-8fa6-498a-bae6-9c7bb9318435","selfLink":"https://localhost/mgmt/cm/shared/esmgmt/add-node/0d043d33-7619-404b-b184-58aa5c8ef0cf","startDateTime":"2018-05-10T11:30:26.360-0700","status":"FAILED","transportAddress":"10.1.1.230","transportPort":"9300","userReference":{"link":"https://localhost/mgmt/shared/authz/users/admin"},"username":"admin","zone":"default"}

    # Success response includes "FINISHED" in the "status" property

def check_that_device_not_already_registered (env, dcd_ip):
    res = util.req(
        env["base_url"] + "shared/resolver/device-groups/cm-esmgmt-logging-group/devices",
        env["auth"]
    )
    devices = res.json()["items"]

    if any(device["address"] == dcd_ip for device in devices):
        print("")
        print("Device is already registered.")
        sys.exit(0)


def main ():
    # load vars from parser
    args = parse_args()
    # Determine local or remote
    environment = get_environment(args.BIGIQ_ADDR, username=args.DCD_USERNAME, pwd=args.DCD_PWD)
    # Test authentication?
    util.poll_for_services_available(environment['address'], auth=environment['auth'])
    util.complete()

    # Wait for DCD available and assume basic auth is enabled
    util.poll_for_system_setup(
        args.DCD_IP_ADDRESS,
        auth=requests.auth.HTTPBasicAuth(args.DCD_USERNAME,
        args.DCD_PWD),
        timeout=args.TIMEOUT_SEC
    )
    util.complete()

    # Verify that device is not added already
    util.print_partial("Checking that device is not already registered...")
    check_that_device_not_already_registered(environment, args.DCD_IP_ADDRESS)
    util.complete()

    # post to add node
    util.print_partial("Adding node...")
    node_uuid = add_node(environment, args.DCD_IP_ADDRESS, args.DCD_USERNAME, args.DCD_PWD)
    util.complete()

    # poll add until success or failure
    util.print_partial("Waiting for result...")
    poll_for_result(environment, node_uuid)
    util.complete()


if __name__ == "__main__":
    main()