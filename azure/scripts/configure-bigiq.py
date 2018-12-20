#! /usr/local/bin/python2.7
# Run a BIG IQ through the licensing and configuration wizard without any user interaction
# Return control when the BIG IQ is fully configured
import sys
import argparse
import requests
from requests.auth import HTTPBasicAuth
import time
import logging
import urllib3
import util
from util import print_partial, complete

util.kill_ssl_warnings(logging, urllib3)

DEFAULT_HOSTNAME = 'bigiq1'

# Enter the license key into the BIQ
def enter_license_info (license_key):
    req(
        BIGIQ_REST_URL + "tm/shared/licensing/activation",
        method="POST",
        json={"baseRegKey":LICENSE_KEY,"addOnKeys":[],"activationMethod":"AUTOMATIC"},
        auth=AUTH
    )
    # assume that a dossier is enclosed in the response which should be
    # submitted with the next request


# The dossier is retrievable from this endpoint always
# Register the return dossier
def poll_for_licensing_complete ():
    sys.stdout.write("Waiting for license activation...")
    sys.stdout.flush()
    i = 0
    while True:
        i += 1
        activation_res = req(BIGIQ_REST_URL + "tm/shared/licensing/activation")
        res_json = activation_res.json()
        if res_json['status'] == "LICENSING_COMPLETE" or i > TIMEOUT_SEC:
            # Break when licensing is complete or the operation has timed out
            break
        elif activation_res.json()['status'] == "LICENSING_FAILED":
            print("")
            print("Licensing failure, reason given: ")
            print(activation_res.json()['errorText'])
            sys.exit(1)
            break
        elif res_json['status'] == "NEED_EULA_ACCEPT":
            req(
                BIGIQ_REST_URL + "tm/shared/licensing/activation",
                method="POST",
                json={
                    "baseRegKey": LICENSE_KEY,
                    "addOnKeys": [],
                    "activationMethod": "AUTOMATIC",
                    "eulaText": res_json['eulaText']
                }

            )
            # Reset timeout
            i = 0
        else:
            time.sleep(1)
        sys.stdout.write(".")
        sys.stdout.flush()

    licenseText = ""
    try:
        licenseText = activation_res.json()['licenseText']
    except KeyError:
        pass

    # License text could be set but be empty
    if not licenseText:
        print(" Licensing failed")
        sys.exit(1)

    req(
        BIGIQ_REST_URL + "tm/shared/licensing/registration",
        json={ 'licenseText': licenseText },
        method="PUT"
    )

    return activation_res.json()

# Configure as CM or DCD node
def configure_big_iq_type (dcd=False):
    if dcd:
        req(
            BIGIQ_REST_URL + "cm/system/provisioning",
            json={"systemPersonality":"logging_node"},
            method="POST"
        )

# Step 3 configure managment address
def set_management_address (host_name = DEFAULT_HOSTNAME):
    default_config_res = req(BIGIQ_REST_URL + "shared/system/easy-setup")
    cfg = default_config_res.json()
    # I guess just post back what is set, TODO is this required then?
    management_addr = cfg["managementIpAddress"]
    # Turn it from cidr to ip
    management_addr = management_addr[:-3]
    req(
        BIGIQ_REST_URL + "shared/system/easy-setup",
        json={
                "hostname": host_name,
                "managementIpAddress": cfg["managementIpAddress"],
                "managementRouteAddress": cfg["managementRouteAddress"]
            },
        method="PATCH"
    )


    time.sleep(2)
    print("Setting discovery address to " + management_addr)
    req(
        BIGIQ_REST_URL + "shared/identified-devices/config/discovery",
        json={"discoveryAddress":management_addr},
        method="PUT"
    )

    # Suspicious of BIQ/TMOS interaction being fully atomic when this previous request returns
    time.sleep(2)
    disco_addr_res = req(
        BIGIQ_REST_URL + "shared/identified-devices/config/discovery"
    )

    try:
        if not disco_addr_res.json()['discoveryAddress'] == management_addr:
            print("Discovery address could not be set")
            sys.exit(1)
    except KeyError:
        print("Discovery address could not be set")
        sys.exit(1)



# Step 4 set the ntp and dns servers
def configure_services ():
    req(
        BIGIQ_REST_URL + "tm/sys/dns",
        json={"nameServers":["8.8.8.8"],"search":["localhost"]},
        method="PATCH"
    )

    req(
        BIGIQ_REST_URL + "tm/sys/ntp",
        json={"servers":["time.nist.gov"],"timezone":"America/Los_Angeles"},
        method="PATCH"
    )


# Step 5 set the master key. This can only be done once. This function is aware of that
def set_master_key ():
    mk_res = req(
        BIGIQ_REST_URL + "cm/shared/secure-storage/masterkey",
        json={"passphrase": MASTER_PASSPHRASE},
        method="POST",
        verify=False
    )

    if (not mk_res.ok and
            mk_res.json()['message'] == 'The Master Key has already been set on this system and cannot be reset'):
        return

    util.verify_success(mk_res)

# Step 6 Passwords are set using tmsh, this function marks the admin and root password as having been changed
def set_passwords ():
    req(
        BIGIQ_REST_URL + "shared/system/setup"
    ).json()

    # This doesn't work, suspect there is some weird encoding issue between client and server
    # Suffice to change the pwd using tmsh
    # Saving this code because it's correct, and if I can ever figure out why the service is sending me a 400
    # Then it would be better to have this working

    # print("Changing root password")
    # time.sleep(5)
    # root_res = req(
    #     BIGIQ_REST_URL + "shared/authn/root",
    #     json={
    #         "oldPassword":"default",
    #         "newPassword":ROOT_PWD
    #     },
    #     method="POST",
    #     verify=False
    # )
    # # Something isn't working right with the password setting
    # # Pausing might make it happier
    # time.sleep(5)
    # # verify_success(root_res)
    # # TODO verify that root pwd changed special case here
    # print("Changing pwd from" + AUTH.password + " to " + NEW_AUTH.password)
    # res = req(
    #     BIGIQ_REST_URL + "shared/authz/users",
    #     json={
    #             "name":"admin",
    #             "displayName":"Admin User",
    #             "kind":"shared:authz:users:usersworkerstate",
    #             "selfLink":"https://localhost/mgmt/shared/authz/users/admin",
    #             "oldPassword": unicode(AUTH.password, "utf-8"),
    #             "password":  unicode(NEW_AUTH.password, "utf-8"),
    #             "password2": unicode(NEW_AUTH.password, "utf-8")
    #         },
    #     method="PUT",
    #     verify=False
    # )
    # print(str(res.json()))



    # # Poll for authentication change persisting properly
    # i = 0
    # while i < TIMEOUT_SEC:
    #     time.sleep(10)
    #     res = req(BIGIQ_REST_URL + "shared/echo", verify=False, auth=NEW_AUTH)
    #     if res.status_code == 200:
    #         break
    #     # Wait 10 in order to not freak out the password limit
    #     i += 9

    # if not res.ok:
    #     print("")
    #     print("Setting password failed")

    req(
        BIGIQ_REST_URL + "shared/system/setup",
        json={"isRootPasswordChanged":True},
        method="PATCH",
        auth=AUTH
    )

    req(
        BIGIQ_REST_URL + "shared/system/setup",
        json={"isAdminPasswordChanged":True},
        method="PATCH",
        auth=AUTH
    )



# Step 7 Set a flag to true indicating that the setup wizard is complete
def set_system_setup ():
    req(
        BIGIQ_REST_URL + "shared/system/setup",
        json={"isSystemSetup":True},
        method="PATCH",
        auth=AUTH
    )

# Step 8 Restart the system
def do_restart ():
    req(
        BIGIQ_REST_URL + "shared/failover-state",
        json={"restart":True},
        method="PATCH",
        auth=AUTH
    )

# True response indicates a succesful service bring up
# Wrap the util function which was extracted from this file originally
def poll_for_services_available ():
    return util.poll_for_services_available(BIGIQ_ADDR, AUTH, timeout=TIMEOUT_SEC)

# Okay wrapper for requests which encapsulates with defaults some of the repetitive stuff that makes my eyes bleed
def req (url, json=None, method="GET", auth=None, verify=True):
    return util.req(url, auth or AUTH, json=json, method=method, verify=verify)

# Test that the authentication is working correctly. In a remote context, this will verify that basic auth is correct and the username
# password combination is correct. When run local to the BIQ, this proves nothing, because it doesn't need to.
def test_auth ():
    global AUTH
    res = req(BIGIQ_REST_URL + "shared/echo", verify=False)

    if res.ok:
        return
    else:
        print("Authentication failed, ensure that basic auth is enabled and your username password combinations are correct")
        sys.exit(1)

# Run through the steps of the setup wizard in order
def main():
    if not poll_for_services_available():
        print(" Timed out")
        sys.exit(1)
    else:
        complete()

    print_partial("Verifying authentication information...")
    test_auth()
    complete()

    if not SKIP_LICENSING:
        print_partial("Adding license key...")
        enter_license_info(LICENSE_KEY)
        complete()
        poll_for_licensing_complete()
        complete()


    print_partial("Configuring role...")
    configure_big_iq_type(dcd=(NODE_TYPE=="DCD"))
    complete()

    print_partial("Setting management address...")
    set_management_address(HOST_NAME)
    complete()

    poll_for_services_available()
    complete()

    print_partial("Configuring NTP/DNS services...")
    configure_services()
    complete()

    print_partial("Setting masterkey...")
    set_master_key()
    complete()

    if not poll_for_services_available():
        print(" Timed out")
        sys.exit(1)
    else:
        complete()

    print_partial("Setting password status to updated...")
    set_passwords()
    complete()

    print_partial("Configuration complete, restarting services")
    # Wait for toku to flush everything to disk? Maybe?
    time.sleep(10)
    do_restart()
    complete()
    util.poll_for_system_down(BIGIQ_ADDR, timeout=TIMEOUT_SEC)
    complete()
    poll_for_services_available()
    set_system_setup()
    complete()


# Generate the CLI argument parser
def generate_parser ():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--BIGIQ_ADDR",
        type=str,
        help="The IPv4 address of the BIG-IQ on which the setup will be run. If not specified, the script runs against localhost."
    )
    parser.add_argument(
        "--BIGIQ_REST_URL",
        type=str,
        help="This should probably always be omitted. Read the source to figure out if you want to set this."
    )
    parser.add_argument(
        "--LICENSE_KEY",
        type=str,
        help="The license key to use for this setup. Can be omitted if you want to manually license your BIG-IQ"
    )
    parser.add_argument(
        "--MASTER_PASSPHRASE",
        type=str,
        default="ValidPasswordValidPassword12341234!",
        help="The passphrase to use for the BIG-IQ"
    )
    parser.add_argument(
        "--SKIP_LICENSING",
        type=bool,
        default=False,
        help="Set this if your wish to skip the licensing process when your BIG-IQ has already been licensed manually for instance."
    )
    parser.add_argument(
        "--ADMIN_USERNAME",
        type=str,
        default="admin",
        help="Username for the administrative account"
    )
    parser.add_argument(
        "--ADMIN_PWD",
        type=str,
        default="f5site02",
        help="The admin password for the BIG-IQ"
    )
    parser.add_argument(
        "--TIMEOUT_SEC",
        type=int,
        default=120, help="The time in seconds to wait for the asynchronous polling operations in the setup process"
    )
    parser.add_argument(
        "--NODE_TYPE",
        type=str,
        default="CM", help="Either 'CM' for central management or 'DCD' for data collection device"
    )
    parser.add_argument(
        "--HOST_NAME",
        type=str,
        help="The fqdn of the hostname to be configured on bigiq cm / dcd instances"
    )

    args = parser.parse_args()

    global BIGIQ_ADDR
    global BIGIQ_REST_URL
    global LICENSE_KEY
    global MASTER_PASSPHRASE
    global SKIP_LICENSING
    global ADMIN_PWD
    global NODE_TYPE
    global TIMEOUT_SEC
    global HOST_NAME

    BIGIQ_ADDR = args.BIGIQ_ADDR
    # Remember DeMorgan...
    if not BIGIQ_ADDR and not BIGIQ_REST_URL:
        BIGIQ_REST_URL = "http://localhost:8100/"
        BIGIQ_ADDR = "localhost:8100"
    else:
        BIGIQ_REST_URL = args.BIGIQ_REST_URL or "https://" + BIGIQ_ADDR + "/mgmt/"

    LICENSE_KEY = args.LICENSE_KEY
    MASTER_PASSPHRASE = args.MASTER_PASSPHRASE
    SKIP_LICENSING = args.SKIP_LICENSING
    ADMIN_PWD = args.ADMIN_PWD
    NODE_TYPE = args.NODE_TYPE
    TIMEOUT_SEC = args.TIMEOUT_SEC
    HOST_NAME = args.HOST_NAME

    return args

# Configured global
BIGIQ_ADDR = None
BIGIQ_REST_URL = None
LICENSE_KEY = None
MASTER_PASSPHRASE = None
SKIP_LICENSING = None
ADMIN_PWD = None
NODE_TYPE = None

TIMEOUT_SEC = 120
# Declare these globals in a global scope, ie, not main

if __name__ == "__main__":
    args = generate_parser()
    AUTH = HTTPBasicAuth(args.ADMIN_USERNAME, ADMIN_PWD)
    main()