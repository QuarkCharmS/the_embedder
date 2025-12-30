# Manual Destroy Guide

If the automated scripts continue to fail, here's how to manually destroy the infrastructure.

## Option 1: Use AWS Console

1. Go to AWS Console (us-east-1 region)
2. Delete resources in this order:

### Step 1: Delete Lambda Functions
- Navigate to Lambda
- Delete: `dev-rag-embedder-trigger` or similar

### Step 2: Delete VPC Endpoints
- Navigate to VPC → Endpoints
- Delete endpoints with "dev" or matching your environment

### Step 3: Delete Route53 Records
- Navigate to Route53
- Delete internal hosted zone records

### Step 4: Delete ECS Services & Tasks
- Navigate to ECS
- Stop all tasks in rag-embedder, rag-connector, and qdrant services
- Delete the services
- Delete task definitions

### Step 5: Delete Load Balancers
- Navigate to EC2 → Load Balancers
- Delete ALB and NLB
- Navigate to EC2 → Target Groups
- Delete all target groups

### Step 6: Delete ECS Cluster
- Navigate to ECS → Clusters
- Delete the dev cluster

### Step 7: Delete EC2 Instances (if any)
- Navigate to EC2 → Instances
- Terminate Qdrant EC2 instances

### Step 8: Delete Security Groups
- Navigate to VPC → Security Groups
- Delete security groups (may need to retry if dependencies exist):
  - rag-embedder-task
  - rag-connector-sg
  - qdrant-ecs-sg
  - ecr-vpc-endpoints-sg
  - ALB/NLB security groups

### Step 9: Delete VPC
- Navigate to VPC
- Delete NAT Gateways (wait for deletion)
- Release Elastic IPs
- Delete Subnets
- Delete Route Tables
- Delete Internet Gateway
- Delete VPC

## Option 2: Use AWS CLI

```bash
# Set your region
export AWS_REGION=us-east-1
export ENV=dev

# 1. Delete Lambda functions
aws lambda list-functions --query 'Functions[?contains(FunctionName, `rag-embedder`)].FunctionName' --output text | \
  xargs -I {} aws lambda delete-function --function-name {}

# 2. Delete VPC Endpoints
aws ec2 describe-vpc-endpoints --filters "Name=tag:Environment,Values=$ENV" --query 'VpcEndpoints[].VpcEndpointId' --output text | \
  xargs -I {} aws ec2 delete-vpc-endpoints --vpc-endpoint-ids {}

# 3. Stop and delete ECS services
CLUSTER_NAME=$(aws ecs list-clusters --query 'clusterArns[?contains(@, `dev`)]' --output text | awk -F'/' '{print $2}')

if [ -n "$CLUSTER_NAME" ]; then
  # List and delete services
  aws ecs list-services --cluster $CLUSTER_NAME --query 'serviceArns[]' --output text | \
    xargs -I {} bash -c 'aws ecs update-service --cluster '"$CLUSTER_NAME"' --service {} --desired-count 0 && aws ecs delete-service --cluster '"$CLUSTER_NAME"' --service {} --force'

  # Wait for services to be deleted
  sleep 30

  # Delete cluster
  aws ecs delete-cluster --cluster $CLUSTER_NAME
fi

# 4. Delete Load Balancers
aws elbv2 describe-load-balancers --query 'LoadBalancers[?contains(LoadBalancerName, `dev`)].LoadBalancerArn' --output text | \
  xargs -I {} aws elbv2 delete-load-balancer --load-balancer-arn {}

# Wait for ALBs to delete
sleep 60

# Delete Target Groups
aws elbv2 describe-target-groups --query 'TargetGroups[?contains(TargetGroupName, `dev`)].TargetGroupArn' --output text | \
  xargs -I {} aws elbv2 delete-target-group --target-group-arn {}

# 5. Terminate EC2 instances
aws ec2 describe-instances --filters "Name=tag:Environment,Values=$ENV" "Name=instance-state-name,Values=running" \
  --query 'Reservations[].Instances[].InstanceId' --output text | \
  xargs -I {} aws ec2 terminate-instances --instance-ids {}

# Wait for instances to terminate
sleep 120

# 6. Delete Security Groups (may need multiple passes)
for i in {1..3}; do
  echo "Pass $i: Deleting security groups..."
  aws ec2 describe-security-groups --filters "Name=tag:Environment,Values=$ENV" \
    --query 'SecurityGroups[?GroupName!=`default`].GroupId' --output text | \
    xargs -I {} aws ec2 delete-security-group --group-id {} 2>/dev/null || true
  sleep 10
done

# 7. Get VPC ID
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=tag:Environment,Values=$ENV" --query 'Vpcs[0].VpcId' --output text)

if [ "$VPC_ID" != "None" ] && [ -n "$VPC_ID" ]; then
  echo "Deleting VPC: $VPC_ID"

  # Delete NAT Gateways
  aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$VPC_ID" --query 'NatGateways[].NatGatewayId' --output text | \
    xargs -I {} aws ec2 delete-nat-gateway --nat-gateway-id {}

  # Wait for NAT Gateways to delete
  echo "Waiting for NAT Gateways to delete..."
  sleep 120

  # Release Elastic IPs
  aws ec2 describe-addresses --filters "Name=domain,Values=vpc" --query 'Addresses[].AllocationId' --output text | \
    xargs -I {} aws ec2 release-address --allocation-id {}

  # Delete Subnets
  aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query 'Subnets[].SubnetId' --output text | \
    xargs -I {} aws ec2 delete-subnet --subnet-id {}

  # Delete Route Tables (except main)
  aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC_ID" --query 'RouteTables[?Associations[0].Main==`false`].RouteTableId' --output text | \
    xargs -I {} aws ec2 delete-route-table --route-table-id {}

  # Detach and delete Internet Gateway
  aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$VPC_ID" --query 'InternetGateways[].InternetGatewayId' --output text | \
    xargs -I {} bash -c 'aws ec2 detach-internet-gateway --internet-gateway-id {} --vpc-id '"$VPC_ID"' && aws ec2 delete-internet-gateway --internet-gateway-id {}'

  # Delete VPC
  aws ec2 delete-vpc --vpc-id $VPC_ID

  echo "VPC $VPC_ID deleted"
fi

echo "Manual cleanup complete!"
```

## Option 3: Clean up Terragrunt state and start fresh

If you just want to remove the Terragrunt tracking without destroying AWS resources:

```bash
cd /home/santiago/rag_in_aws_the_big_project/terragrunt/dev

# Remove all Terragrunt cache
find . -type d -name ".terragrunt-cache" -exec rm -rf {} + 2>/dev/null || true

# Remove any local state files
find . -name "terraform.tfstate*" -type f -delete
find . -name ".terraform" -type d -exec rm -rf {} + 2>/dev/null || true
```

Then manually delete resources via AWS Console or CLI as shown above.
