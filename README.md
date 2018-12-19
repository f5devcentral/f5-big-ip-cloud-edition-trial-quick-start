BIG-IP Cloud Edition Trial Quick Start
======================================

F5 [BIG-IP Cloud Edition](https://www.f5.com/pdf/products/f5_bigip_cloud_edition_solution_overview.pdf): Automatically deploy pre-built app services dedicated to each application.

With F5 BIG-IQ Centralized Management (CM), you can securely manage traffic to your applications in AWS and Azure by using what F5 calls a Service Scaling Group (SSG).

From a centralized view, you can monitor the health and statistics of your applications as well as devices that are load balancing traffic and hosting applications. You can also set up alert thresholds to immediately notify you of certain events.

This **CloudFormation Template (CFT)** or **Azure Resource Manager (ARM)** creates two BIG-IQ VE instances: 

- a BIG-IQ Centralized Management (CM) instance to configure and orchestrate instances of BIG-IP VE
- a BIG-IQ Data Collection Device (DCD) to store analytics data. 

The templates also create an Apache demo web server. 

After you configure the BIG-IQ instances, BIG-IQ automatically launches a BIG-IP VE instance in AWS or Azure.

- [AWS Quick Start](/aws)
- [Azure Quick Start](/azure)

### Copyright

Copyright 2014-2019 F5 Networks Inc.

### License

#### Apache V2.0

Licensed under the Apache License, Version 2.0 (the "License"); you may not use
this file except in compliance with the License. You may obtain a copy of the
License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations
under the License.

#### Contributor License Agreement

Individuals or business entities who contribute to this project must have
completed and submitted the [F5 Contributor License Agreement](http://f5-openstack-docs.readthedocs.io/en/latest/cla_landing.html).
