#!/bin/bash

# exit as soon as an error occurs
set -e

# name of the component (eg: "extraction", "transform"...)
component_name=$1

# full path to lambda directory (eg: "/<root-dir>/shape_dvaults_etl/extraction/firehose_kinesis")
lambda_absolute_path=$2

# relative path to lambda package (eg: "extraction/firehose_kinesis")
lambda_relative_path=$3

echo "Working dir is: '$lambda_absolute_path'"
cd "$lambda_absolute_path"

# clean up any previously generated output
rm -rf .build
rm -rf .cache

# prepare the build dir
mkdir .build

echo "Creating virtual environment '.venv'..."
python -m venv .venv
source .venv/bin/activate
echo "Virtual environment activated!"

printf "\n\nPoetry info: --------------------------------------------------------------------------------------------\n"

poetry debug info
poetry config --list

printf "\n\nInstalling poetry packages... ---------------------------------------------------------------------------\n"

poetry install -n --no-dev -v

printf "\n\nGenerating zip package... -------------------------------------------------------------------------------\n"

# copy installed packages into zip
cd .venv/lib/python3.8/site-packages
zip -r -9 "$lambda_absolute_path/.build/lambda.zip" . \
    -x "**__pycache__/*" \
    -x "**.build/*" \
    -x "**.cache/*" \
    -x "**.venv/*" \
    -x "*.DS_Store*" \
    -x "**pip/*" \
    -x "**setuptools/*" \
    -x "**wheel/*" \
    -x "*docutils*" \
    -x "**mysql*"

echo ".venv/lib/python3.8/site-packages added to zip"

# copy main shape package structure including "common"
cd "$lambda_absolute_path/../../../"
zip -g -9 -r "$lambda_absolute_path/.build/lambda.zip" shape_dvaults_etl \
          -x "**extraction/*" \
          -x "**__pycache__/*" \
          -x "**.build/*" \
          -x "**.cache/*" \
          -x "**.venv/*" \
          -x "*.DS_Store*" \
          -x "**pip/*" \
echo "$(pwd) content added to zip"

zip -g -9 "$lambda_absolute_path/.build/lambda.zip" "shape_dvaults_etl/$component_name/__init__.py"

# copy lambda code into zip
zip -g -9 -r "$lambda_absolute_path/.build/lambda.zip" "shape_dvaults_etl/$lambda_relative_path" \
          -x "**__pycache__/*" \
          -x "**.build/*" \
          -x "**.cache/*" \
          -x "**.venv/*" \
          -x "*.DS_Store*" \
          -x "**pip/*" \
echo "$lambda_absolute_path content added to zip"

echo "zip file has been generated"

printf "\n\nRemoving virtual environment... -------------------------------------------------------------------------\n"

# delete virtual env
rm -rf "$lambda_absolute_path/.venv"

echo "Done!"