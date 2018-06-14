import requests
from requests import ConnectionError
import sys
import time


def req (url, auth, json=None, method="GET", verify=True):
    response = requests.request(method, url, json=json, auth=auth, verify=False)
    if verify:
        verify_success(response)

    return response

def print_partial (msg):
    sys.stdout.write(msg)
    sys.stdout.flush()

def complete ():
    print(" done!\n")

def verify_success (response):
    try:
        if not response.ok:
            print(
                "Request to " + str(response.url) + " failed with " +
                str(response.status_code)
            )
            print(" and response body \n" + str(response.json()))
            sys.exit(1)
    except ValueError:
        sys.exit(1)

def _get_poll_addr (addr):
    return  "https://localhost/info/system" if "localhost" in addr else "https://" + addr + "/info/system"

def poll_for_system_down (address, auth=None,  timeout=60):
    print_partial("Waiting for system to go down...")
    i = 0
    url = _get_poll_addr(address)
    while True:
        print_partial(".")
        i += 1
        conn_failed = False
        try:
            status_res = req(url, auth, verify=False)
        except ConnectionError: # Errors when connection refused
            conn_failed = True
            print_partial("x")
            return True
        if i > timeout:
            return False # System failed to go down I guess
        if conn_failed or not status_res:
            return True
        elif status_res.ok and safe_access(status_res.json(), 'available'):
            time.sleep(1)
        else: # available was False
            return True

def safe_access (d, prop):
    value = None
    try:
        value = d[prop]
    except KeyError:
        pass
    return value



# True response indicates a succesful service bring up
def poll_for_services_available (address, auth=None,  timeout=60):
    print_partial("Waiting for service availablity...")
    i = 0
    url = _get_poll_addr(address)
    while True:
        print_partial(".")
        i += 1
        conn_failed = False
        try:
            status_res = req(url, auth, verify=False)
        except ConnectionError: # Errors when connection refused
            conn_failed = True
            print_partial("x")

        if i > timeout:
            return False
        if conn_failed or not status_res:
            time.sleep(1)
        elif status_res.ok and safe_access(status_res.json(), 'available'):
            time.sleep(1)
            return True
        else:
            time.sleep(1)

    verify_success(status_res)
    return status_res.json()['available']

def poll_for_system_setup (address, auth=None,  timeout=60):
    print_partial("Waiting for system setup to complete...")
    i = 0
    url = "http://localhost:8100/shared/system/setup" if "localhost" in address else "https://" + address + "/mgmt/shared/system/setup"
    while True:
        print_partial(".")
        i += 1
        conn_failed = False
        try:
            status_res = req(url, auth, verify=False)
        except ConnectionError: # Errors when connection refused
            conn_failed = True
            print_partial("x")

        if i > timeout:
            return False
        if conn_failed or not status_res:
            time.sleep(1)
        elif status_res.ok and safe_access(status_res.json(), 'isSystemSetup'):
            time.sleep(1)
            return True
        else:
            time.sleep(1)

    verify_success(status_res)
    return status_res.json()['available']

def kill_ssl_warnings (logging, urllib3):
    # Set log leve for requests module
    logging.getLogger("requests").setLevel(logging.CRITICAL)
    # Demo machines will not have valid signed certificate
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_environment (address, username=None, pwd=None):
    local = "localhost" in address

    return {
        "base_url": "http://localhost:8100/" if local else "https://" + address + "/mgmt/",
        "address": address,
        "auth": None if local else requests.auth.HTTPBasicAuth(username, pwd)
    }