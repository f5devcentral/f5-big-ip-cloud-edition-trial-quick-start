#!/usr/bin/env bash
echo "Searching for image where name begins with $1"
regions=$(aws ec2 describe-regions --output text --query 'Regions[*].RegionName')
for region in $regions; do
    (
     echo "$region $( aws ec2 describe-images --region $region --filters Name=is-public,Values=true Name=name,Values="$1*" | grep ImageId )"
    )
done