#!/usr/bin/env bash
echo "Searching for image where name begins with $1"
# e.g. F5 Networks BYOL BIG-IQ-6.0.1.1.0.0.9
regions=$(aws ec2 describe-regions --output text --query 'Regions[*].RegionName')
for region in $regions; do
    (
     echo "$region $( aws ec2 describe-images --region $region --filters Name=is-public,Values=true Name=name,Values="$1*" | grep ImageId )"
    )
done