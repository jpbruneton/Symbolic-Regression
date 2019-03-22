#!/bin/sh

imageName=${1:-badoit:latest}

inDockerGroup=`id -Gn | grep docker`
if [ -z "$inDockerGroup" ]; then
	sudoCMD="sudo"
else
	sudoCMD=""
fi
dockerCMD="$sudoCMD docker"
dockerParams="" # "--nocache"

$dockerCMD build $dockerParams -t $imageName .

