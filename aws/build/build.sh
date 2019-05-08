#! /usr/bin/env bash
#rm -f ../built/scripts.tar.gz
dos2unix ../scripts/*
# Pack up scripts into an archive
tar cvz ../scripts/* > ../built/scripts.tar.gz
fname="bigiq-cm-dcd-pair-with-ssg.template"
output_dir="../experimental/"
template_output="$output_dir$fname"
# Get name of current branch, ideally it includes the BIQ version number
branch_name=$(git rev-parse --abbrev-ref HEAD)
# Upload scripts archive
aws s3 cp --acl public-read ../built/scripts.tar.gz "s3://big-ip-ce-quickstart-cf-templates-aws/$branch_name/"

# Compile template file
#./big-iq-master.py --branch $branch_name > $template_output

# Copy templates
for f in ../experimental/*.template; do
    aws s3 cp --acl public-read "$f" "s3://big-ip-ce-quickstart-cf-templates-aws/$branch_name/"
done

#aws s3 cp --acl public-read aws/experimental/Setup-Ubuntu-Trial.template "s3://big-ip-ce-quickstart-cf-templates-aws/6.1.0/"
#aws s3 cp --acl public-read aws/experimental/bigiq-cm-dcd-pair-with-ssg.template "s3://big-ip-ce-quickstart-cf-templates-aws/6.1.0/"
#aws s3 cp --acl public-read aws/experimental/bigiq-cm-dcd-pair-with-ssg-existing-vpc.template "s3://big-ip-ce-quickstart-cf-templates-aws/6.1.0/"