BIG-IP® Cloud Edition Trial
===========================

F5® [BIG-IP® Cloud Edition](https://www.f5.com/pdf/products/f5_bigip_cloud_edition_solution_overview.pdf): Automatically deploy pre-built app services dedicated to each application.

F5® BIG-IQ® Centralized Management makes it straightforward for you to securely manage traffic to your applications in an AWS cloud using a service scaling group (SSG).

From a centralized, single-pane of glass view, you can monitor the health and statistics of your applications as well as devices that are load balancing traffic and hosting applications. You can also set up alert thresholds to immediately notify you of certain events.

![Deployment Diagram](images/aws-ssg-example-in-cloud.png)

Instructions for AWS
--------------------

1. Go on the [F5® Cloud Edition Trial](https://f5.com/products/trials/product-trials) in order to get your BIG-IQ® trial Licenses.

2. Subscribe and Accept the Term for below F5 Products:

 * [F5 BIG-IQ 6.0 for AWS (BYOL)](https://aws.amazon.com/marketplace/pp/B00KIZG6KA)
 * [F5 BIG-IP Virtual Edition - BEST - (PAYG, 25Mbps)](https://aws.amazon.com/marketplace/pp/B079C4WR32)

3. Launch the *trial stack* template (click right, open new tab/window):  <a href="https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/new?stackName=BIG-IP-Cloud-Edition-Demo&templateURL=https:%2F%2Fs3.amazonaws.com%2Fbig-iq-quickstart-cf-templates%2F6.0.0%2Frefit-for-public-urls%2Fbigiq-cm-dcd-pair-with-ssg.template" target="_blank">  
   <img src="https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png"/></a>

  * Stack name
  * Subnets AZ1 and AZ2 (make sure both are different)
  * BIG-IQ® AMI and BIG-IP® AMI (default: Virginia us-east-1, update if different region used)
  * License Key 1 and 2 (used for BIG-IQ® CM and DCD, given by F5 Networks)
  * SSH Key (you AWS Key Pair Name)
  * SSG CloudFormation Stack Name (e.g. demo-ssg-trial)
  
  *Expected time: ~5 min*

4. Open the [EC2 console](https://console.aws.amazon.com/ec2/v2/home) and wait until the BIG_IQ® CM and DCD fully up

  * Instance State: running
  * Status Checks: 2/2 checks passed
  
  *Expected time: ~5 min*

5. SSH into BIG-IQ® DCD instance and execute the following:
```
# bash
# /config/cloud/setup-dcd.sh
```
  * Enter BIG-IQ® password as prompted. This must match the password used on the BIG-IQ® CM instance (next step).
  * Let the script scripts run to completion before moving to the next step.
  
  *Expected time: ~2 min*

6.	SSH into BIG-IQ® CM instance and execute the following:
```
# bash
# /config/cloud/setup-cm.sh
```
  * Enter access key id/secret key (used for the Service Scaling Group object creation) and BIG-IQ® password as prompted.
  * This must match the password used on the BIG-IQ® DCD instance (previous step).
  * Let the script scripts run to completion before moving to the next step.
  
  *Expected time: ~25 min*

7. Open BIG-IQ® CM using the Public IP: ``https://<public_ip>``

  * Click on the Applications tab > APPLICATIONS, you should see an application demo protected with an F5 Web Application Firewall.
  * The Service Scaling Group is managed under the Application tab > ENVIRONMENTS > Service Scaling Groups.

For more information, go to [the BIG-IP® Cloud Edition Knowledge Center](https://support.f5.com/csp/knowledge-center/software/BIG-IP?module=BIG-IP%20Cloud%20Edition)

Note: in case the application deployment fails, click on Retry.

Teardown instructions
---------------------
1. Open BIG-IQ® CM using the Public IP: ``https://<public_ip>``

  * Delete the application, under Applications tab > APPLICATIONS, select the application(s), then Delete.
  
  *Expected time: ~5 min*
    
  * Delete the Service Scaling Group, under Application tab > ENVIRONMENTS > Service Scaling Groups, select the AWS SSG, then Delete.
  
  *Expected time: ~10 min*
  
2. Open the (Cloud Formation Console](https://console.aws.amazon.com/cloudformation/) and delete the stack BIG-IP-Cloud-Edition-Demo.

  *Expected time: ~5 min*
  

Abbreviations:
- BIG-IQ® CM: Centralized Management (configure and orchestrate BIG-IP)
- BIG-IQ® DCD: Data Collection Device (storing the Analytics data)
