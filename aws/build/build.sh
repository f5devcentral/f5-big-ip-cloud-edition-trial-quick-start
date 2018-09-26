#! /usr/bin/env bash
rm -rf ../built
mkdir ../built
# Pack up scripts into an archive
tar cvz ../scripts/* > ../built/scripts.tar.gz
fname="bigiq-cm-dcd-pair-with-ssg.template"
output_dir="../experimental/"
template_output="$output_dir$fname"
# Get name of current branch, ideally it includes the BIQ version number
branch_name=$(git rev-parse --abbrev-ref HEAD)
# Upload scripts archive
aws s3 cp --acl public-read ../built/scripts.tar.gz "s3://big-iq-quickstart-cf-templates-aws/$branch_name/"

# Compile template file
./big-iq-master.py --branch $branch_name > $template_output

# Copy templates
for f in ../experimental/*.template; do
    aws s3 cp --acl public-read "$f" "s3://big-iq-quickstart-cf-templates-aws/$branch_name/"
done
