#! /usr/local/bin/python2.7
import argparse
import logging
import requests
import string
import sys
import urllib3
import util

SERVICES = [ "access", "dos", "websafe", "ipsec", "afm", "asm" ]

# Key is front end representation
# Value is backend representation
# This will be used to print a message helpful in navigating our confused domain
SERVICE_TRANSLATION = {
    "Access":                   "access",
    "DoS Protection":           "dos",
    "Fraud Protection Service": "websafe",
    "IPsec":                    "ipsec",
    "Network Security":         "afm",
    "Web Application Security": "asm",
}

SERVICE_NAME_TO_URL = {
    "access":  "cm/access/event-logs/listener/add-listener-task/",
    "dos":     "cm/security-shared/tasks/add-dos-listener",
    "websafe": "cm/websafe/tasks/add-listener/",
    "ipsec":   "cm/adc-core/tasks/add-listener/",
    "afm":     "cm/firewall/tasks/add-afm-listener",
    "asm":     "cm/asm/tasks/add-syslog-listener"
}

def parse_args ():
    parser = argparse.ArgumentParser()
    services_help = ("Specify the list of services you wish to be activated on the DCD.\n"
                     "Available options are: "
                    )

    services_help += string.join(SERVICES, ", ")

    parser.add_argument(
        "--SERVICES",
        nargs="+",
        type=str,
        default=[],
        help=services_help

    )
    parser.add_argument("--LIST_SERVICES", type=bool, default=False)
    parser.add_argument("--DCD_IP_ADDRESS", type=str, required=True)
    parser.add_argument("--BIGIQ_ADDR", type=str, default="localhost")
    parser.add_argument("--BIGIQ_USERNAME", type=str, default=None)
    parser.add_argument("--BIGIQ_PWD", type=str, default=None)

    return parser.parse_args()

# Transform the service name from the the front end representation to the
# backend representation.
def print_service_name_translation ():
    print("Translation of service names to keys: ")
    for ui_name, backend_name in SERVICE_TRANSLATION.iteritems():
        print(ui_name + " = " + backend_name)


def activate_service (env, service, dcd_self_link, listener_interface_address):
    json_body = {
                "module": service,
                "listenerInterfaceAddress": listener_interface_address,
                "deviceReference": {
                    "link": dcd_self_link
                }
            }
    # ASM has a special property
    if service == "asm":
        json_body["indexName"] = "asmindex"

    util.req(
        env["base_url"] + SERVICE_NAME_TO_URL[service],
        env["auth"],
        method="POST",
        json=json_body
    )

def activate_services (env, dcd_ip, dcd_self_link, services):
    for service in services:
        activate_service(env, service, dcd_self_link, dcd_ip)
        util.print_partial(".")
        # ASM has a different JSON body

# Get the self link for the data collection device. This is necessary for any
# service activation request
def get_dcd_device_reference (env, dcd_ip):
    devices_res = util.req(
        env["base_url"] + "shared/resolver/device-groups/cm-esmgmt-logging-group/devices/",
        env["auth"]
    )

    # Suppose just let this fail if any of these steps puke
    # Distill the response down into just the data collection device on which
    # we are activating services
    devices = devices_res.json()
    devices = devices["items"]
    devices = [device for device in devices if device["address"] == dcd_ip]
    device = devices[0]

    return device["selfLink"]

# Check that every service the user specified exists in the services list
def verify_services_are_valid (user_specified_services):
    for service in user_specified_services:
        if not service in SERVICES:
            print("Invalid service specified: " + service)
            print("Refer to the following list for valid service names:")
            print_service_name_translation()
            sys.exit(1)


def main ():
    util.kill_ssl_warnings(logging, urllib3)
    args = parse_args()
    verify_services_are_valid(args.SERVICES)
    if args.LIST_SERVICES:
        print_service_name_translation()
        sys.exit(0)
        return

    if not args.SERVICES:
        print("No services specified")
        sys.exit(0)
        return

    env = util.get_environment(args.BIGIQ_ADDR, username=args.BIGIQ_USERNAME, pwd=args.BIGIQ_PWD)

    util.poll_for_services_available(env["address"], auth=env["auth"],  timeout=360)
    util.complete()

    util.print_partial("Retrieving DCD identifier...")
    dcd_self_link = get_dcd_device_reference(env, args.DCD_IP_ADDRESS)
    util.complete()

    util.print_partial("Activating services: " + string.join(args.SERVICES, ", ") + "...")
    activate_services(env, args.DCD_IP_ADDRESS, dcd_self_link, args.SERVICES)
    util.complete()


if __name__ == '__main__':
    main()