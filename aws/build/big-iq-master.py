#! /usr/bin/env python3
import argparse
from os import listdir
from os.path import isfile, join
from pathlib import Path

import troposphere
from troposphere import (Base64, FindInMap, GetAtt, Join,
                         Output, Parameter, Ref, cloudformation)
from troposphere.cloudformation import *
from troposphere.ec2 import *
from troposphere.elasticloadbalancing import (HealthCheck, Listener,
                                              LoadBalancer)

def parse_args ():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--branch",
        required=True,
        help="Please provide output of `git rev-parse --abbrev-ref HEAD`"
    )

    return parser.parse_args()

SCRIPT_PATH = "../scripts/"
# Files which configure the BIG-IQ instances

def generate_pwd_prompt (prompt_text, var_name):
    return (
        'read -s -p "' + prompt_text + '" v1 \n'
        'echo \n'
        'read -s -p "Re-enter ' + prompt_text + '" ' + var_name + ' \n'
        'while [ "$v1" != "$' + var_name + '" ]; do \n'
        '    echo \n'
        '    echo "Entries did not match, try again" \n'
        '    echo \n'
        '    read -s -p "' + prompt_text + '" v1 \n'
        '    echo \n'
        '    read -s -p "Re-enter ' + prompt_text + '" ' + var_name + ' \n'
        'done \n'
        'echo'
    )

def define_instance_init_files (t, args):
    init_files_map = {}

    # Download scripts archive from raw.gh and extract
    download_and_extract_scripts = (
        "mkdir -p /config/cloud \n"
        "cd /config/cloud \n"
        "curl https://s3.amazonaws.com/big-ip-ce-quickstart-cf-templates-aws/" + args.branch + "/scripts.tar.gz > scripts.tar.gz \n"
        "tar --strip-components=1 -xvzf scripts.tar.gz \n"
    )

    return {
        "cm": InitFiles({
            "/config/cloud/setup-cm.sh": InitFile(
                mode = "000755",
                owner = "root",
                group = "root",
                content = Join("\n", [
                    # This script is run in root context
                    "#!/usr/bin/env bash",
                    generate_pwd_prompt('AWS Access Key ID: ', 'AWS_ACCESS_KEY'),
                    generate_pwd_prompt('AWS Secret Access Key: ', 'AWS_SECRET_KEY'),
                    generate_pwd_prompt('BIG-IQ Password [Alphanumerics only]: ', 'BIG_IQ_PWD'),
                    generate_pwd_prompt('BIG-IP Password [Alphanumerics only]: ', 'BIG_IP_PWD'),
                    'nohup /config/cloud/setup-cm-background.sh "$AWS_ACCESS_KEY" "$AWS_SECRET_KEY" "$BIG_IQ_PWD" "$BIG_IP_PWD" &> /var/log/setup.log < /dev/null &',
                    "echo 'tail -f /var/log/setup.log in order to monitor setup progress'",
                    "echo;"
                    "echo 'Make sure you follow Teardown instructions from the GitHub repository once you are done with your testing.'"
                ])
            ),
            "/config/cloud/setup-cm-background.sh": InitFile(
                mode = "000755",
                owner = "root",
                group = "root",
                content = Join("\n", [
                    # This script is run in root context
                    "#!/usr/bin/env bash",
                    'AWS_ACCESS_KEY="$1"',
                    'AWS_SECRET_KEY="$2"',
                    'BIG_IQ_PWD="$3"',
                    'BIG_IP_PWD="$4"',
                    "mount -o remount,rw /usr",
                    download_and_extract_scripts,
                    "/usr/local/bin/pip install awscli",
                    # Delete default listener on ELB
                    Join("", [
                        " AWS_DEFAULT_REGION=", Ref("AWS::Region"),
                        ' AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY"',
                        ' AWS_SECRET_ACCESS_KEY="$AWS_SECRET_KEY"',
                        # Root doesn't have /u/l/bin in path
                        " /usr/local/bin/aws elb delete-load-balancer-listeners --load-balancer-name",
                        " ELB-", Ref("AWS::StackName"),
                        " --load-balancer-ports 80 80"
                    ]),
                    # Run configuration
                    Join(" ", [
                        "/config/cloud/configure-bigiq.py --LICENSE_KEY",
                        Ref(t.parameters["licenseKey1"]),
                        "--MASTER_PASSPHRASE ValidPassphrase1234567812345678!",
                        "--TIMEOUT_SEC 1200"
                    ]),
                    # Wait for restart to take effect, should be unnecessary since the setup wizard has resequenced to
                    # only set startup true after the restart has taken place
                    "sleep 10",
                    Join(" ", [
                        "/config/cloud/add-dcd.py --DCD_IP_ADDRESS",
                        GetAtt("BigIqDcdEth0", "PrimaryPrivateIpAddress"),
                        Join(" ", [
                            '--DCD_PWD "$BIG_IQ_PWD"',
                            "--DCD_USERNAME admin"
                        ])
                    ]),
                    Join("", [
                        "tmsh modify auth user admin",
                        ' password "$BIG_IQ_PWD"',
                        " && tmsh save sys config"
                    ]),
                    Join(" ", [
                        "/config/cloud/activate-dcd-services.py --SERVICES asm",
                        "--DCD_IP_ADDRESS",
                        GetAtt("BigIqDcdEth0", "PrimaryPrivateIpAddress")
                    ]),
                    "set-basic-auth on", # The calls within require identity gleaned from a login
                    Join(" ", ['/config/cloud/create-license-pool.py --REG_KEY', Ref(t.parameters["licensePoolKey"]), '--BIG_IQ_PWD "$BIG_IQ_PWD"']),
                    "set-basic-auth off",
                    Join("", [
                        "/config/cloud/create-auto-scaling.py ",
                        "--AWS_SUBNET_1A ", Ref(t.resources["Subnet1"]), " ",
                        "--AWS_SUBNET_1B ", Ref(t.resources["Subnet2"]), " ",
                        "--AWS_US_EAST_1A ", Ref(t.parameters["subnet1Az"]), " ",
                        "--AWS_US_EAST_1B ", Ref(t.parameters["subnet2Az"]), " ",
                        "--AWS_SSH_KEY ", Ref(t.parameters["sshKey"]), " ",
                        "--AWS_VPC ", Ref(t.resources["VPC"]), " ",
                        "--AWS_ACCESS_KEY_ID $AWS_ACCESS_KEY ",
                        "--AWS_SECRET_ACCESS_KEY $AWS_SECRET_KEY ",
                        "--BIGIP_AMI ", FindInMap("AmiRegionMap", Ref("AWS::Region"), "bigip"),
                        " --BIGIQ_URI http://localhost:8100 ",
                        "--BIGIP_USER admin",
                        ' --BIGIP_PWD "$BIG_IP_PWD"',
                        " --CLOUD_PROVIDER_NAME aws ",
                        "--CLOUD_ENVIRONMENT_NAME aws-env ",
                        "--DEFAULT_REGION ", Ref("AWS::Region"), " ",
                        "--DEVICE_TEMPLATE_NAME default-ssg-template ",
                        "--LOOKUP_SERVER_LIST 8.8.8.8 ",  # not used in 6.0.1
                        "--NTP_SERVER time.nist.gov ",
                        "--CM_IP ", Ref(t.resources["CmElasticIp"]),
                        ' --BIG_IQ_PWD "$BIG_IQ_PWD"',
                        # Though I would like to, I cannot substring the stackname and concat something here,
                        # there are no aws intrinsic functions which can do this
                        " --SSG_NAME ", Ref(t.parameters["ssgName"])
                    ]),
                    Join(" ", [
                        "/config/cloud/deploy-application.py --NODE_IP", GetAtt("UbuntuExampleApplicationStack", "Outputs.HTTPServerIP"),
                        "--ELB_NAME", Join("", [ "ELB-", Ref("AWS::StackName") ] ),
                        "--ELB_DNS_NAME", GetAtt("ClassicELB", "DNSName")
                    ])
                ])
            )
        }),
        "dcd": InitFiles({
            "/config/cloud/setup-dcd.sh": InitFile(
                mode = "000755",
                owner = "root",
                group = "root",
                content = Join("\n", [
                    "#!/usr/bin/env bash",
                    generate_pwd_prompt('BIG-IQ Password [Alphanumerics only]: ', 'BIG_IQ_PWD'),
                    'nohup /config/cloud/setup-dcd-background.sh "$BIG_IQ_PWD" &> /var/log/setup.log < /dev/null &',
                    "echo 'tail -f /var/log/setup.log in order to monitor setup progress'"
                ])
            ),
            "/config/cloud/setup-dcd-background.sh": InitFile(
                mode = "000755",
                owner = "root",
                group = "root",
                content = Join("\n", [
                    "#!/usr/bin/env bash",
                    download_and_extract_scripts,
                    "/config/cloud/wait-for-rjd.py",
                    'BIG_IQ_PWD="$1"',
                    Join("", [
                        "tmsh modify auth user admin",
                        ' password "$BIG_IQ_PWD"',
                        " && tmsh save sys config && set-basic-auth on"
                    ]),
                    Join(" ", [
                        "/config/cloud/configure-bigiq.py --LICENSE_KEY",
                        Ref(t.parameters["licenseKey2"]),
                        "--MASTER_PASSPHRASE ValidPassphrase1234567812345678!", # TODO HC hardcoded pf is okay maybe?
                        "--TIMEOUT_SEC 1200",
                        "--NODE_TYPE DCD"
                    ])
                ])
            )
        })
    }

def define_instance_metadata (t, args, is_cm_instance=True):
    init_files_map = define_instance_init_files(t, args)
    return Metadata(
        Init({
            "config": InitConfig(
                files = init_files_map["cm"] if is_cm_instance else init_files_map["dcd"]
            )
        })
    )

def define_metadata (t):
    t.add_metadata({
        "Version": "1.0.0",
        "AWS::CloudFormation::Interface": define_interface()
    })

# Define the AWS::CloudFormation::Interface for the template
def define_interface ():
    return {
            "ParameterGroups": [
                {
                    "Label": {
                        "default": "NETWORKING CONFIGURATION"
                    },
                    "Parameters": [
                        "vpcCidrBlock",
                        "subnet1CidrBlock",
                        "subnet2CidrBlock",
                        "subnet1Az",
                        "subnet2Az"
                    ]
                }, {
                    "Label": {
                        "default": "Accept BIG-IQ Terms and Conditions: https://aws.amazon.com/marketplace/pp/B00KIZG6KA"
                    },
                    "Parameters": [ ]
                }, {
                    "Label": {
                        "default": "Accept BIG-IP Terms and Conditions: https://aws.amazon.com/marketplace/pp/B07G5MT2KT"
                    },
                    "Parameters": [ ]
                }, {
                    "Label": {
                        "default": "BIG-IQ/IP CONFIGURATION"
                    },
                    "Parameters": [
                        "bigIqPassword",
                        "bigIpPassword",
                        "bigIqAmi",
                        "bigIpAmi",
                        "licenseKey1",
                        "licenseKey2",
                        "licensePoolKey",
                        "instanceType",
                        "restrictedSrcAddress",
                        "sshKey",
                        "iamAccessKey",
                        "iamSecretKey",
                        "ssgName"
                    ]
                }
            ],
            "ParameterLabels": define_param_labels()
        }

# Define the AMI mappings per region for BIG-IQ
def define_mappings (t):
    t.add_mapping("AmiRegionMap", {
        "ap-northeast-1": {
            "bigip": "ami-00320423988425f3d",
            "bigiq": "ami-03796972da9048ab2"
        },
        "ap-northeast-2": {
            "bigip": "ami-09954bada9cf468cb",
            "bigiq": "ami-00007ebd9e15cb581"
        },
        "ap-south-1": {
            "bigip": "ami-045104677062aef7d",
            "bigiq": "ami-07f35c4b4760fb76f"
        },
        "ap-southeast-1": {
            "bigip": "ami-095976ed364e0db59",
            "bigiq": "ami-0374f84dc0cc86cee"
        },
        "ap-southeast-2": {
            "bigip": "ami-098d744be7a18d539",
            "bigiq": "ami-02126de94a8e4a605"
        },
        "ca-central-1": {
            "bigip": "ami-0b6671ac004f408e8",
            "bigiq": "ami-0dd51fe2c81d4e7b0"
        },
        "eu-north-1": {
            "bigip": "ami-4145cb3f", 
            "bigiq": "ami-48b13f36"
        },
        "eu-central-1": {
            "bigip": "ami-08224fc41cc989329",
            "bigiq": "ami-0653f874e93ba6682"
        },
        "eu-west-1": {
            "bigip": "ami-06ccb3fa7c3c99e58",
            "bigiq": "ami-0c95964ce0f5d45ac"
        },
        "eu-west-2": {
            "bigip": "ami-05e10a3fc2419c8b6",
            "bigiq": "ami-0602be07b34c80953"
        },
        "sa-east-1": {
            "bigip": "ami-0a5d31ab37d68f28c",
            "bigiq": "ami-00c1b0342af6d712b"
        },
        "us-east-1": {
            "bigip": "ami-04e893bab1e8b9b10",
            "bigiq": "ami-031d2878cb4d3fb48"
        },
        "us-east-2": {
            "bigip": "ami-0d5e9d0e47f3d7c44",
            "bigiq": "ami-063ddf2d42d75365f"
        },
        "us-west-1": {
            "bigip": "ami-09ed2e81904ef5d57",
            "bigiq": "ami-0049e8ea793a198d9"
        },
        "us-west-2": {
            "bigip": "ami-0f8580cb1944b10ff",
            "bigiq": "ami-056accdfaf0533c43"
        }
    })

# Define the parameter labels for the AWS::CloudFormation::Interface
def define_param_labels ():
    return {
        "bigIqPassword": {
            "default": "BIG-IQ Admin Password"
        },
        "bigIpPassword": {
            "default": "BIG-IP Admin Password"
        },
        "bigIqAmi": {
            "default": "BIG-IQ AMI"
        },
        "bigIpAmi": {
            "default": "BIG-IP AMI"
        },
        "iamAccessKey": {
            "default": "IAM Access Key"
        },
        "iamSecretKey": {
            "default": "IAM Secret Key"
        },
        "imageName": {
            "default": "Image Name"
        },
        "instanceType": {
            "default": "AWS Instance Size"
        },
        "licenseKey1": {
            "default": "BIG-IQ CM License Key"
        },
        "licenseKey2": {
            "default": "BIG-IQ DCD License Key"
        },
        "licensePoolKey": {
            "default": "BIG-IP License Pool Key"
        },
        "vpcCidrBlock": {
            "default": "VPC CIDR Block"
        },
        "restrictedSrcAddress": {
            "default": "Source Address(es) for SSH Access"
        },
        "sshKey": {
            "default": "SSH Key"
        },
        "subnet1Az": {
            "default": "Subnet AZ1"
        },
        "subnet2Az": {
            "default": "Subnet AZ2"
        },
        "subnet1CidrBlock": {
            "default": "Subnet 1 CIDR Block"
        },
        "subnet2CidrBlock": {
            "default": "Subnet 2 CIDR Block"
        },
        "ssgName": {
            "default": "SSG CloudFormation Stack Name"
        }
    }

# Define the template parameters and constraints
def define_parameters (t):
    t.add_parameter(Parameter("instanceType",
        AllowedValues = [
            "m4.2xlarge", "m4.4xlarge"
        ],
        ConstraintDescription = "Must be a valid EC2 instance type for BIG-IQ",
        Default = "m4.2xlarge",
        Description = "Size of the F5 BIG-IQ Virtual Instance",
        Type = "String"
    ))
    t.add_parameter(Parameter("licenseKey1",
        ConstraintDescription = "Verify your F5 BYOL regkey.",
        Description = "F5 BIG-IQ CM license key",
        MaxLength = 255,
        MinLength = 1,
        Type = "String"
    ))
    t.add_parameter(Parameter("licenseKey2",
        ConstraintDescription = "Verify your F5 BYOL regkey.",
        Description = "F5 BIG-IQ DCD license key",
        MaxLength = 255,
        MinLength = 1,
        Type = "String"
    ))
    t.add_parameter(Parameter("licensePoolKey",
        ConstraintDescription = "Verify your F5 BIG-IP Pool regkey.",
        Description = "F5 BIG-IP license pool key",
        MaxLength = 255,
        MinLength = 1,
        Type = "String"
    ))
    t.add_parameter(Parameter("vpcCidrBlock",
        AllowedPattern = "(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})/(\\d{1,2})",
        ConstraintDescription = "Must be a valid IP CIDR range of the form x.x.x.x/x.",
        Default = "10.1.0.0/16",
        Description = " The CIDR block for the VPC",
        MaxLength = 18,
        MinLength = 9,
        Type = "String"
    ))
    t.add_parameter(Parameter("restrictedSrcAddress",
        AllowedPattern = "(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})/(\\d{1,2})",
        ConstraintDescription = "Must be a valid IP CIDR range of the form x.x.x.x/x.",
        Description = " The IP address range used to SSH and access managment GUI on the EC2 instances",
        Default = "0.0.0.0/0",
        MaxLength = 18,
        MinLength = 9,
        Type = "String"
    ))
    t.add_parameter(Parameter("sshKey",
        Description = "Key pair for accessing the instance",
        Type = "AWS::EC2::KeyPair::KeyName"
    ))
    t.add_parameter(Parameter("subnet1Az",
        Description = "Name of an Availability Zone in this Region",
        Type = "AWS::EC2::AvailabilityZone::Name"
    ))
    t.add_parameter(Parameter("subnet2Az",
        Description = "Name of an Availability Zone in this Region which is different than Subnet AZ1",
        Type = "AWS::EC2::AvailabilityZone::Name"
    ))
    t.add_parameter(Parameter("subnet1CidrBlock",
        AllowedPattern = "(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})/(\\d{1,2})",
        ConstraintDescription = "Must be a valid IP CIDR range of the form x.x.x.x/x.",
        Default = "10.1.1.0/24",
        Description = " The CIDR block for the second subnet which is compatible with the VPC CIDR block",
        MaxLength = 18,
        MinLength = 9,
        Type = "String"
    ))
    t.add_parameter(Parameter("subnet2CidrBlock",
        AllowedPattern = "(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})/(\\d{1,2})",
        ConstraintDescription = "Must be a valid IP CIDR range of the form x.x.x.x/x.",
        Default = "10.1.2.0/24",
        Description = " The CIDR block for the second subnet which is compatible with the VPC CIDR block",
        MaxLength = 18,
        MinLength = 9,
        Type = "String"
    ))
    t.add_parameter(Parameter("ssgName",
        AllowedPattern = "[\\da-zA-Z\\-]{1,25}",
        Description = "A unique CloudFormation StackName within your AWS account",
        ConstraintDescription = "SSG Name must contain only alphanumerics and hyphens and be less than 25 characters long",
        Default = "demo-ssg-trial",
        MaxLength = 25,
        MinLength = 1,
        Type = "String"
    ))

# Define the networking components for the stack
# VPC, two subnets, security group, classic ELB, IGW etc
def define_networking (t):
    t.add_resource(
        VPC(
            "VPC",
            CidrBlock = Ref(t.parameters["vpcCidrBlock"]),
            InstanceTenancy = "default",
            EnableDnsSupport = True,
            EnableDnsHostnames = False,
            Tags = troposphere.cloudformation.Tags(
                Name = Join(" ", ["BIG-IQ VPC:", Ref("AWS::StackName")])
            )
        )
    )

    t.add_resource(
        Subnet(
            "Subnet1",
            CidrBlock = Ref(t.parameters["subnet1CidrBlock"]),
            VpcId = Ref(t.resources["VPC"]),
            AvailabilityZone = Ref(t.parameters["subnet1Az"]),
            Tags = Tags(
                Name = Join(" ", ["BIG-IQ Subnet 1:", Ref("AWS::StackName")])
            )
        )
    )

    t.add_resource(
        Subnet(
            "Subnet2",
            CidrBlock = Ref(t.parameters["subnet2CidrBlock"]),
            VpcId = Ref(t.resources["VPC"]),
            AvailabilityZone = Ref(t.parameters["subnet2Az"]),
            Tags = Tags(
                Name = Join(" ", [ "Big-IQ Subnet 2:", Ref("AWS::StackName") ])
            )
        )
    )

    t.add_resource(RouteTable(
        "RouteTable1",
        VpcId = Ref(t.resources["VPC"]),
        Tags = Tags(
            Name = Join(" ", ["BIG-IQ Route Table 1:", Ref("AWS::StackName")])
        )
    ))

    t.add_resource(RouteTable(
        "RouteTable2",
        VpcId = Ref(t.resources["VPC"]),
        Tags = Tags(
            Name = Join(" ", ["BIG-IQ Route Table 2:", Ref("AWS::StackName")])
        )
    ))

    t.add_resource(SubnetRouteTableAssociation(
        "Subnet1RouteTableAssociation",
        SubnetId = Ref(t.resources["Subnet1"]),
        RouteTableId = Ref(t.resources["RouteTable1"])
    ))

    t.add_resource(SubnetRouteTableAssociation(
        "Subnet2RouteTableAssociation",
        SubnetId = Ref(t.resources["Subnet2"]),
        RouteTableId = Ref(t.resources["RouteTable2"])
    ))

    t.add_resource(InternetGateway(
        "IGW",
        Tags = Tags(
            Name = Join(" ", ["BIG-IQ Internet Gateway:", Ref("AWS::StackName")])
        )
    ))

    t.add_resource(VPCGatewayAttachment(
        "IGWAttachment",
        VpcId = Ref(t.resources["VPC"]),
        InternetGatewayId = Ref(t.resources["IGW"])
    ))

    t.add_resource(Route(
        "Route1Default",
        DestinationCidrBlock = "0.0.0.0/0",
        RouteTableId = Ref(t.resources["RouteTable1"]),
        GatewayId = Ref(t.resources["IGW"])
    ))

    t.add_resource(Route(
        "Route2Default",
        DestinationCidrBlock = "0.0.0.0/0",
        RouteTableId = Ref(t.resources["RouteTable2"]),
        GatewayId = Ref(t.resources["IGW"])
    ))

    t.add_resource(NetworkAcl(
        "VPCAcl",
        VpcId = Ref(t.resources["VPC"])
    ))

    t.add_resource(SecurityGroup(
        "SecurityGroup",
        GroupName = Join(" ",["BIG-IQ SG:", Ref("AWS::StackName")]),
        GroupDescription = "vpc-sg",
        VpcId = Ref(t.resources["VPC"]),
        SecurityGroupIngress = [
            SecurityGroupRule(
                IpProtocol = "tcp",
                FromPort = "443",
                ToPort = "443",
                CidrIp = "0.0.0.0/0"
            ),
            SecurityGroupRule(
                IpProtocol = "tcp",
                FromPort = "80",
                ToPort = "80",
                CidrIp = "0.0.0.0/0"
            ),
            SecurityGroupRule(
                IpProtocol = "tcp",
                FromPort = "22",
                ToPort = "22",
                CidrIp = "0.0.0.0/0"
            ),
            SecurityGroupRule(
                IpProtocol = "tcp", # TODO Determine actual ports which should be open
                FromPort = "1",
                ToPort = "65356",
                CidrIp = Ref(t.parameters["vpcCidrBlock"])
            )
        ]
    ))

    t.add_resource(SecurityGroup(
        "ElbSecurityGroup",
        GroupName = Join(" ",["ELB-SG-", Ref("AWS::StackName")]),
        GroupDescription = "vpc-sg",
        VpcId = Ref(t.resources["VPC"]),
        SecurityGroupIngress = [ ]
    ))

    t.add_resource(LoadBalancer(
        "ClassicELB",
        SecurityGroups = [ Ref(t.resources["ElbSecurityGroup"]) ],
        HealthCheck = HealthCheck(
            HealthyThreshold = "10",
            Interval = "30",
            Target = "TCP:22",
            Timeout = "5",
            UnhealthyThreshold = "2"
        ),
        Listeners = [
            Listener(
                LoadBalancerPort = "80",
                InstancePort = "80",
                Protocol = "TCP",
                InstanceProtocol = "TCP"
            )
        ],
        LoadBalancerName = Join("", [ "ELB-", Ref("AWS::StackName") ] ),
        Scheme = "internet-facing",
        Subnets = [ Ref(t.resources["Subnet1"]), Ref(t.resources["Subnet2"]) ]
    ))

# Define the BIQ ec2 instances, there is a centralized management and data collection device
def define_ec2_instances (t, args):
    t.add_resource(EIP(
        "CmElasticIp",
        Domain = "vpc"
    ))

    t.add_resource(EIP(
        "DcdElasticIp",
        Domain = "vpc"
    ))

    t.add_resource(NetworkInterface(
        "BigIqCmEth0",
        Description = "BIG-IQ CM Instance Management IP",
        GroupSet = [ Ref(t.resources["SecurityGroup"]) ],
        SubnetId = Ref("Subnet1")
    ))

    t.add_resource(NetworkInterface(
        "BigIqDcdEth0",
        Description = "BIG-IQ DCD Instance Management IP",
        GroupSet = [ Ref(t.resources["SecurityGroup"]) ],
        SubnetId = Ref("Subnet1")
    ))

    bd_mappings = [
            BlockDeviceMapping(
                DeviceName = "/dev/xvda",
                Ebs = EBSBlockDevice(
                    DeleteOnTermination = True,
                    VolumeType = "gp2"
                )
            )
        ]

    t.add_resource(Instance(
        "BigIqCm",
        # Kick off cfn-init b/c BIG-IP doesn't run this automatically
        UserData=Base64(Join("", [
                "#!/bin/bash\n",
                "/opt/aws/apitools/cfn-init-1.4-0.amzn1/bin/cfn-init -v -s ",
                Ref("AWS::StackId"), " -r ",
                "BigIqCm",
                " --region ", Ref("AWS::Region"),
                "\n"
            ]
        )),
        Metadata = define_instance_metadata(t, args),
        ImageId = FindInMap("AmiRegionMap", Ref("AWS::Region"), "bigiq"),
        InstanceType =  Ref(t.parameters["instanceType"]),
        KeyName = Ref(t.parameters["sshKey"]),
        NetworkInterfaces =  [
            NetworkInterfaceProperty(
                DeviceIndex =  "0",
                NetworkInterfaceId =  Ref(t.resources["BigIqCmEth0"])
            ),
            NetworkInterfaceProperty(
                DeleteOnTermination =  True,
                Description =  "BIG-IQ CM Instance Management IP",
                DeviceIndex =  "1",
                GroupSet =  [ Ref(t.resources["SecurityGroup"]) ],
                SubnetId = Ref(t.resources["Subnet1"])
            )
        ],
        Tags = Tags(
            Name = Join(" ", [
                        "Big-IQ CM:",
                        Ref("AWS::StackName")
                    ])
        ),
        BlockDeviceMappings = bd_mappings
    ))

    t.add_resource(Instance(
        "BigIqDcd",
        # Kick off cfn-init b/c BIG-IP doesn't run this automatically
        UserData=Base64(Join("", [
                "#!/bin/bash\n",
                "/opt/aws/apitools/cfn-init-1.4-0.amzn1/bin/cfn-init -v -s ",
                Ref("AWS::StackId"), " -r ",
                "BigIqDcd",
                " --region ", Ref("AWS::Region"),
                "\n"
            ]
        )),
        Metadata = define_instance_metadata(t, args, is_cm_instance=False),
        ImageId = FindInMap("AmiRegionMap", Ref("AWS::Region"), "bigiq"),
        InstanceType =  Ref(t.parameters["instanceType"]),
        KeyName = Ref(t.parameters["sshKey"]),
        NetworkInterfaces =  [
            NetworkInterfaceProperty(
                DeviceIndex =  "0",
                NetworkInterfaceId =  Ref(t.resources["BigIqDcdEth0"])
            ),
            NetworkInterfaceProperty(
                DeleteOnTermination =  True,
                Description =  "BIG-IQ DCD Instance Management IP",
                DeviceIndex =  "1",
                GroupSet =  [ Ref(t.resources["SecurityGroup"]) ],
                SubnetId = Ref(t.resources["Subnet1"])
            )
        ],
        Tags = Tags(
            Name = Join(" ", [
                        "Big-IQ DCD:",
                        Ref("AWS::StackName")
                    ])
        ),
        BlockDeviceMappings = bd_mappings
    ))

    t.add_resource(EIPAssociation(
        "CmEipAssociation",
        AllocationId = GetAtt("CmElasticIp", "AllocationId"),
        NetworkInterfaceId = Ref("BigIqCmEth0")
    ))

    t.add_resource(EIPAssociation(
        "DcdEipAssociation",
        AllocationId = GetAtt("DcdElasticIp", "AllocationId"),
        NetworkInterfaceId = Ref("BigIqDcdEth0")
    ))

    t.add_resource(
        Stack(
            "UbuntuExampleApplicationStack",
            Parameters = {
                "region": Ref("AWS::Region"),
                "vpcId": Ref(t.resources["VPC"]),
                "ec2Name": "apache-demo-server",
                "sshKey": Ref(t.parameters["sshKey"]),
                "subnet": Ref(t.resources["Subnet1"]),
                "instanceType": "t2.small",
                "ebsVolumeSize": "40",
                "loadBalancerDnsName": GetAtt("ClassicELB", "DNSName")
            },
            # TODO use a different S3 account to host this template
            TemplateURL = "https://s3.amazonaws.com/big-ip-ce-quickstart-cf-templates-aws/" + args.branch + "/Setup-Ubuntu-Trial.template"
        )
    )


# Define all the resources for this stack
def define_resources (t, args):
    define_networking(t)
    define_ec2_instances(t, args)

# Define the stack outputs
def define_outputs (t):
    t.add_output(Output("BigIqCmExternalInterfacePrivateIp",
        Description = "Internally routable IP of the public interface on BIG-IQ",
        Value = GetAtt(
                    "BigIqCmEth0",
                    "PrimaryPrivateIpAddress"
                )
    ))
    t.add_output(Output("BigIqCmInstanceId",
        Description = "Instance Id of BIG-IQ in Amazon",
        Value = Ref(t.resources["BigIqCm"])
    ))
    t.add_output(Output("BigIqCmEipAddress",
        Description = "IP address of the management port on BIG-IQ",
        Value = Ref(t.resources["CmElasticIp"])
    ))
    t.add_output(Output("BigIqCmManagementInterface",
        Description = "Management interface ID on BIG-IQ",
        Value = Ref(t.resources["BigIqCmEth0"])
    ))
    t.add_output(Output("BigIqCmUrl",
        Description = "BIG-IQ CM Management GUI",
        Value = Join("", ["https://", GetAtt("BigIqCm", "PublicIp")])
    ))
    t.add_output(Output("availabilityZone1",
        Description = "Availability Zone",
        Value = GetAtt("BigIqCm", "AvailabilityZone")
    ))


# Build the template in logical order (hopefully) by just the top level tags
def main ():
    args = parse_args()
    t = troposphere.Template()
    define_mappings(t)
    define_metadata(t)
    define_parameters(t)
    define_resources(t, args)
    define_outputs(t)

    print(t.to_json())

if __name__ == '__main__':
    main()
