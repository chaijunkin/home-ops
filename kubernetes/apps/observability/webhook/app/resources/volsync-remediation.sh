#!/bin/sh
# This script is triggered by the webhook when an alert is received
# It creates a Job from the existing CronJob in the jobs namespace

# Generate a unique job name with timestamp
TIMESTAMP=$(date +%s)
JOB_NAME="remediation-${TIMESTAMP}"

echo "Alert received, triggering remediation job: ${JOB_NAME}"

# Create a Job from the CronJob using full path to kubectl
/kubectl/kubectl create job "${JOB_NAME}" --from=cronjob/remediation -n jobs

echo "Job ${JOB_NAME} created successfully in jobs namespace"
