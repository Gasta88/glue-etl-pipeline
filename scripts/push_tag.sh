#!/usr/bin/env bash

echo "Starting push tag script"

CURRENT_BRANCH=$(git branch --show-current)

if [[ -z $1 ]]; then
    TAG="auto-merge"
    echo "No input provided, take the default tag ${TAG}"
else
    TAG=$1
    echo "Input provided, take the tag ${TAG}"
fi

echo "Pushing latest commit ..."
git push origin "${CURRENT_BRANCH}"

echo "Removing the tag $TAG on the local branch ..."
git tag -d "${TAG}"

echo "Removing the tag ${TAG} on the remote branch ..."
git push --delete origin "${TAG}"

echo "Adding the tag ${TAG} on the local branch ..."
git tag "${TAG}"

echo "Adding the tag ${TAG} on the remote branch ..."
git push origin "${TAG}"

echo "Push tag done. Please check the pipeline."