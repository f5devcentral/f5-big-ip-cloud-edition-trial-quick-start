#! /usr/bin/env bash

dos2unix ../scripts/*
# Pack up scripts into an archive
tar cvz ../scripts/* > ../built/scripts.tar.gz
