#! /usr/local/bin/python2.7

import argparse
import logging
import requests
import sys
import urllib3
import util
import time
from pprint import pprint

util.kill_ssl_warnings(logging, urllib3)

def parse_args ():
    parser = argparse.ArgumentParser()
    parser.add_argument("--REG_KEY", type=str, required=True)
    parser.add_argument("--BIG_IQ_PWD", type=str, required=True)
    return parser.parse_args()

def add_license_pool (reg_key, auth):
    util.req(
        "https://localhost/mgmt/cm/device/licensing/pool/initial-activation",
        auth,
        method="POST",
        json={
            "regKey": reg_key,
            "status": "ACTIVATING_AUTOMATIC",
            "name": "license-pool"
        }
    )

def poll_pipeline (expected_status, key, auth):
    print("Waiting for " + expected_status)
    count = 0
    while True:
        count += 1
        res = util.req(
            "https://localhost/mgmt/shared/pipeline/manager/cm-device-licensing-pool-purchased-pool-licenses",
            auth,
            method="POST",
            json={
                "multiStageQueryRequest": {
                    "repeatLastStageUntilTerminated": False,
                    "queryParamsList": [
                        {
                            "description": "aggregation",
                            "managedPipelineWorkerName": "aggregator-pipe",
                            "jsonContext": {
                                "resourceUriPathTail": ""
                            },
                            "pipelineAction": "DATA_RETRIEVAL",
                            "runStageInternally": False,
                            "jsonOutput": {
                                "items": [
                                    "https://localhost/mgmt/cm/device/licensing/pool/purchased-pool/licenses",
                                    "https://localhost/mgmt/cm/device/licensing/pool/utility/licenses",
                                    "https://localhost/mgmt/cm/device/licensing/pool/volume/licenses",
                                    "https://localhost/mgmt/cm/device/licensing/pool/websafe/licenses",
                                    "https://localhost/mgmt/cm/device/licensing/pool/initial-activation?%24filter=((kind%20eq%20'cm%3Adevice%3Alicensing%3Apool%3Ainitial-activation%3Ainitialactivationworkeritemstate')%20and%20(status%20ne%20'READY'))",
                                    "https://localhost/mgmt/cm/device/licensing/pool/regkey/licenses"
                                ]
                            }
                        },
                        {
                            "description": "sort",
                            "managedPipelineWorkerName": "sort-pipe",
                            "jsonContext": {
                                "sortParamsList": [
                                    {
                                        "sortField": "name",
                                        "sortOrder": "ASCENDING"
                                    }
                                ]
                            }
                        },
                        {
                            "description": "pagination",
                            "managedPipelineWorkerName": "page-pipe",
                            "jsonContext": {
                                "skip": 0,
                                "top": 150
                            },
                            "pipelineAction": "DATA_PROCESSING",
                            "runStageInternally": False
                        }
                    ]
                },
                "getOnPostAndTerminate": True
            }
        )
        res = res.json()

        try:
            status = res["items"][0][key]
        except KeyError:
            status = None

        if count >= 120:
            print("Timed out waiting or status " + expected_status)
            sys.exit(1)

        if not res or not res["items"]:
            time.sleep(1)
        elif status == expected_status:
            return res
        elif status == "ACTIVATION_FAILED":
            print("Activation failed")
            sys.exit(1)
        else:
            time.sleep(1)

def poll_for_accept_eula (auth):
    return poll_pipeline("ACTIVATING_AUTOMATIC_NEED_EULA_ACCEPT", "status", auth)

def accept_eula (reg_key, eula_text, auth):
    util.req(
        "https://localhost/mgmt/cm/device/licensing/pool/initial-activation/" + reg_key,
        auth,
        method="PATCH",
        json={
            "status": "ACTIVATING_AUTOMATIC_EULA_ACCEPTED",
            "eulaText": eula_text
        }
    )

def poll_for_complete (auth):
    poll_pipeline("LICENSED", "state", auth)

def main():
    args = parse_args()
    auth = requests.auth.HTTPBasicAuth("admin", args.BIG_IQ_PWD)
    print("Adding license")
    add_license_pool(args.REG_KEY, auth)
    time.sleep(2)
    eula_accept_res = poll_for_accept_eula(auth)
    print("Accepting EULA")
    eula_text = eula_accept_res["items"][0]["eulaText"]
    accept_eula(args.REG_KEY, eula_text, auth)

    poll_for_complete(auth)

if __name__ == '__main__':
    main()