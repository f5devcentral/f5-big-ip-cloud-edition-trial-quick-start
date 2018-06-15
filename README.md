BIG-IP Cloud Edition Trial
==========================

Instructions for AWS
--------------------

1. Subscribe and Accept the Term for below F5 Products:

 * `F5 BIG-IQ 6.0 for AWS (BYOL)`_
 * `F5 BIG-IP Virtual Edition - BEST - (PAYG, 25Mbps)`_

2. Connect to your AWS console and open `Cloud Formation`_

3. Create stack, Select Upload template to Amazon S3 and load the latest  ``bigiq-cm-dcd-pair-with-ssg-genv0.x.template``.

  * Stack name (e.g. demo-bigiq6-trial)
  * Subnets AZ1 and AZ2 (make sure both are different)
  * BIG-IQ AMI and BIG-IP AMI (default: Virginia us-east-1, update if different region used)
  * License Key 1 and 2 (used for BIG-IQ CM and DCD, given by F5 Networks)
  * SSH Key (you AWS Key Pair Name)
  * SSG CloudFormation Stack Name (e.g. demo-ssg-trial)

4. Open the EC2 console and wait until the BIG_IQ CM and DCD fully up

  * Instance State: running
  * Status Checks: 2/2 checks passed

5. SSH into BIG-IQ DCD instance and run the following script::

    # bash
    # /config/cloud/setup-dcd.sh

Enter BIG-IQ password as prompted. This must match the password used on the BIG-IQ CM instance (next step).

6.	SSH into BIG-IQ CM instance::

    # bash
    # /config/cloud/setup-cm.sh

Enter access key id/secret key (used for the Service Scaling Group object creation) and BIG-IQ password as prompted. This must match the password used on the BIG-IQ DCD instance (previous step).

7. Open BIG-IQ CM using the Public IP: ``https://<public_ip>``, click on the Applications tab, then APPLICATIONS. You should see a demo application protected with a Web Application Firewall.

The Service Scaling Group is managed under the Application tab > ENVIRONEMENTS > Service Scaling Groups.

For more information, go to `the BIG-IP Cloud Edition Knowledge Center`_.


.. _F5 BIG-IQ 6.0 for AWS (BYOL): https://aws.amazon.com/marketplace/pp/B00KIZG6KA
.. _F5 BIG-IP Virtual Edition - BEST - (PAYG, 25Mbps): https://aws.amazon.com/marketplace/pp/B079C4WR32
.. _Cloud Formation: https://console.aws.amazon.com/cloudformation
.. _BIG-IP Cloud Edition Knowledge Center: https://support.f5.com/csp/knowledge-center/software/BIG-IP?module=BIG-IP%20Cloud%20Edition
