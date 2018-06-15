BIG-IP Cloud Edition Trial
==========================

Instructions for AWS
--------------------

1. Subscribe and Accept the Term for below F5 Products:

 * [F5 BIG-IQ 6.0 for AWS (BYOL)](https://aws.amazon.com/marketplace/pp/B00KIZG6KA)
 * [F5 BIG-IP Virtual Edition - BEST - (PAYG, 25Mbps)](https://aws.amazon.com/marketplace/pp/B079C4WR32)

2. Connect to your AWS console and open [Cloud Formation](https://console.aws.amazon.com/cloudformation)

3. Create Stack, Select Upload template to Amazon S3 and load the latest  ``bigiq-cm-dcd-pair-with-ssg-genv0.x.template`` (under aws/experimental). Fill all requested information:

  * Stack name (e.g. demo-bigiq6-trial)
  * Subnets AZ1 and AZ2 (make sure both are different)
  * BIG-IQ AMI and BIG-IP AMI (default: Virginia us-east-1, update if different region used)
  * License Key 1 and 2 (used for BIG-IQ CM and DCD, given by F5 Networks)
  * SSH Key (you AWS Key Pair Name)
  * SSG CloudFormation Stack Name (e.g. demo-ssg-trial)

4. Open the [EC2 console](https://console.aws.amazon.com/ec2/v2/home) and wait until the BIG_IQ CM and DCD fully up

  * Instance State: running
  * Status Checks: 2/2 checks passed

5. SSH into BIG-IQ DCD instance and execute the following:
```
    # bash
    # /config/cloud/setup-dcd.sh
```
Enter BIG-IQ password as prompted. This must match the password used on the BIG-IQ CM instance (next step).

6.	SSH into BIG-IQ CM instance and execute the following:
```
    # bash
    # /config/cloud/setup-cm.sh
```
Enter access key id/secret key (used for the Service Scaling Group object creation) and BIG-IQ password as prompted.

This must match the password used on the BIG-IQ DCD instance (previous step).

7. Open BIG-IQ CM using the Public IP: ``https://<public_ip>``, click on the Applications tab, then APPLICATIONS.

You should see a demo application protected with a Web Application Firewall.

The Service Scaling Group is managed under the Application tab > ENVIRONEMENTS > Service Scaling Groups.

For more information, go to [the BIG-IP Cloud Edition Knowledge Center](https://support.f5.com/csp/knowledge-center/software/BIG-IP?module=BIG-IP%20Cloud%20Edition)

Note: in case the application deployment fails, click on Retry.

Abbreviations:
- BIG-IQ CM: Configuration Management (configure and orchestrate BIG-IP)
- BIG-IQ DCD: Data Collection Device (storing the Analytics data)
