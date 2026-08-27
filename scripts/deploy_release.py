"""Promote ECS task definitions after migrations, using CodeDeploy for the public BFF."""

from __future__ import annotations

import argparse
import json

import boto3


def latest_task_definition(ecs, family: str) -> str:
    definitions = ecs.list_task_definitions(
        familyPrefix=family,
        status="ACTIVE",
        sort="DESC",
        maxResults=1,
    )["taskDefinitionArns"]
    if not definitions:
        raise RuntimeError(f"No active task definition exists for {family}.")
    return definitions[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--environment", required=True, choices=["staging", "production"]
    )
    args = parser.parse_args()
    prefix = f"spi-{args.environment}"
    ecs = boto3.client("ecs", region_name="ap-south-1")

    for service_name in ("api", "agents"):
        description = ecs.describe_services(cluster=prefix, services=[service_name])[
            "services"
        ]
        if not description or description[0]["desiredCount"] == 0:
            continue
        ecs.update_service(
            cluster=prefix,
            service=service_name,
            taskDefinition=latest_task_definition(ecs, f"{prefix}-{service_name}"),
            forceNewDeployment=True,
        )
        ecs.get_waiter("services_stable").wait(cluster=prefix, services=[service_name])

    web_service = ecs.describe_services(cluster=prefix, services=["web"])["services"]
    if not web_service or web_service[0]["desiredCount"] == 0:
        return 0
    task_definition = latest_task_definition(ecs, f"{prefix}-web")
    app_spec = {
        "version": 1,
        "Resources": [
            {
                "TargetService": {
                    "Type": "AWS::ECS::Service",
                    "Properties": {
                        "TaskDefinition": task_definition,
                        "LoadBalancerInfo": {
                            "ContainerName": "web",
                            "ContainerPort": 3000,
                        },
                        "PlatformVersion": "LATEST",
                    },
                }
            }
        ],
    }
    codedeploy = boto3.client("codedeploy", region_name="ap-south-1")
    deployment_id = codedeploy.create_deployment(
        applicationName=f"{prefix}-web",
        deploymentGroupName=f"{prefix}-web",
        revision={
            "revisionType": "AppSpecContent",
            "appSpecContent": {"content": json.dumps(app_spec, separators=(",", ":"))},
        },
        description="Signed digest promotion after successful database migration",
    )["deploymentId"]
    codedeploy.get_waiter("deployment_successful").wait(deploymentId=deployment_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
