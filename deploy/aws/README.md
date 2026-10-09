# AEGIS on AWS EC2

This is the first AWS deployment path for AEGIS. It keeps the existing Docker
Compose topology and private Tailscale ingress, while placing the always-on
control plane on an AWS EC2 host.

## What the stack creates

- One Amazon Linux 2023 x86_64 EC2 instance.
- An encrypted gp3 root EBS volume for the existing Docker volumes.
- An instance profile with `AmazonSSMManagedInstanceCore`.
- A security group with no inbound rules and unrestricted egress.
- IMDSv2 required on the instance.

Normal administration is through Systems Manager Session Manager. The app is
not exposed through an AWS load balancer or public port; `deploy/tailscale-up.sh`
continues to be the private ingress path.

## Prerequisites

1. An AWS CLI profile with permission to create the stack and its IAM role.
2. An existing VPC and subnet with outbound internet access. A public subnet
   needs a route to an internet gateway; a private subnet needs NAT or another
   egress path for Docker and Tailscale setup.
3. A Tailscale tailnet and an authorized way to install/configure Tailscale.
4. The repository available to the EC2 host. For a private repository, use a
   controlled Git credential or copy the checkout through an approved channel;
   do not put a GitHub token in user data or a clone URL.

The template defaults to `m7i-flex.large` (x86_64, 8 GiB) because the target
account rejects `t3.large` as not Free Tier eligible and the Compose stack has
several concurrent services. Confirm current account eligibility before
choosing a different size.

## Provision the host

Find a VPC and subnet in the target region, then deploy the stack:

```bash
aws cloudformation deploy \
  --region us-east-1 \
  --stack-name aegis-control-plane \
  --template-file deploy/aws/aegis-ec2.yaml \
  --parameter-overrides \
    VpcId=vpc-xxxxxxxx \
    SubnetId=subnet-xxxxxxxx \
  --capabilities CAPABILITY_NAMED_IAM
```

If the subnet already has NAT, set `AssociatePublicIpAddress=false`.

Get the instance ID and connect without SSH:

```bash
INSTANCE_ID="$(aws cloudformation describe-stacks \
  --region us-east-1 \
  --stack-name aegis-control-plane \
  --query 'Stacks[0].Outputs[?OutputKey==`InstanceId`].OutputValue' \
  --output text)"

aws ssm start-session --region us-east-1 --target "$INSTANCE_ID"
```

## Configure the host

Inside the SSM session:

```bash
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user

COMPOSE_VERSION=v5.6.0
sudo install -d -m 0755 /usr/local/lib/docker/cli-plugins
sudo curl -fsSL \
  "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
docker compose version
```

Install Tailscale using the official method for Amazon Linux, authenticate the
host to the intended tailnet, and verify `tailscale status`. Then place the
repository at `/opt/aegis/jarvis-fleet` and run:

```bash
cd /opt/aegis/jarvis-fleet
bash deploy/tailscale-up.sh
```

The launcher generates the local deployment secrets in the untracked
`deploy/.env`, starts Compose, and configures Tailscale Serve. Do not commit or
copy that file into logs, user data, or tickets.

## Persistence and model placement

The initial deployment keeps AEGIS's named Docker volumes on the encrypted EBS
root volume. Backups should be added before production use. For a later
scale-out, move evidence and source archives to S3 and the prospect database to
a managed database, then run stateless services on ECS/Fargate.

The default local model container is CPU-oriented. For GPU inference, use a
separate GPU-capable worker or route the model fabric to a managed/external
provider; do not make the control-plane instance responsible for large model
weights by default.

## Teardown

The CloudFormation stack owns the instance, security group, and instance role:

```bash
aws cloudformation delete-stack --region us-east-1 --stack-name aegis-control-plane
```

The stack's root volume is configured to delete with the instance. Export or
back up AEGIS data before teardown if it must be retained.
