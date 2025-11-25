# Terraform configuration block
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# AWS provider configuration - Frankfurt region
provider "aws" {
  region = "eu-central-1"
}

# Use your specific VPC
data "aws_vpc" "main" {
  id = "vpc-077187b22841dfd66"
}

# Find a public subnet in your VPC (one that has internet gateway route)
data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }
  
  # Look for subnets that have a route to an internet gateway
  filter {
    name   = "map-public-ip-on-launch"
    values = ["true"]
  }
}

# Get the first public subnet
data "aws_subnet" "public" {
  id = data.aws_subnets.public.ids[0]
}

# Get latest Ubuntu 22.04 LTS AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# Create SSH key
resource "tls_private_key" "key" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

# Upload SSH key to AWS
resource "aws_key_pair" "key" {
  key_name   = "chunker-key"
  public_key = tls_private_key.key.public_key_openssh
}

# Security group for SSH access
resource "aws_security_group" "ssh" {
  name   = "chunker-ssh"
  vpc_id = data.aws_vpc.main.id  # Make sure it's in your VPC
  
  # Allow SSH from anywhere
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
 
  ingress {
    from_port   = 6333
    to_port     = 6333
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  ingress {
    from_port   = -1
    to_port     = -1
    protocol    = "icmp"
    cidr_blocks = ["0.0.0.0/0"]
  }
   
  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "chunker-ssh-sg"
  }
}

# EC2 instance in your specific VPC and public subnet
resource "aws_instance" "main" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.medium"
  key_name              = aws_key_pair.key.key_name
  vpc_security_group_ids = [aws_security_group.ssh.id]
  subnet_id             = data.aws_subnet.public.id  # Deploy in public subnet
  
  # Ensure it gets a public IP
  associate_public_ip_address = true
  
  # Root volume configuration
  root_block_device {
    volume_size = 8
    volume_type = "gp3"
  }
  
  # User data script - runs on first boot
  user_data = base64encode(<<-EOF
    #!/bin/bash
    
    # Update system
    apt-get update
    apt-get upgrade -y
    
    # Install Docker
    apt-get install docker.io -y
    
    # Start Docker service
    systemctl start docker
    systemctl enable docker
    
    # Add ubuntu user to docker group
    usermod -aG docker ubuntu
    
    # Wait for EBS volume to be attached and format it
    sleep 30
    
    # Format the EBS volume (only if not already formatted)
    if ! blkid /dev/nvme1n1; then
        mkfs.ext4 /dev/nvme1n1
    fi
    
    # Create mount point and mount the EBS volume
    mkdir -p /dev/sdf
    mount /dev/nvme1n1 /dev/sdf
    
    # Make mount permanent
    echo '/dev/nvme1n1 /dev/sdf ext4 defaults 0 2' >> /etc/fstab
    
    # Set permissions
    chown ubuntu:ubuntu /dev/sdf
    
    # Create qdrant storage directory
    mkdir -p /dev/sdf/qdrant_storage
    chown ubuntu:ubuntu /dev/sdf/qdrant_storage
    
    # Run Qdrant container
    docker run -d \
      --name qdrant \
      --restart unless-stopped \
      -p 6333:6333 \
      -p 6334:6334 \
      -v "/dev/sdf/qdrant_storage:/qdrant/storage:z" \
      qdrant/qdrant:dev
    
    # Log completion
    echo "Setup completed at $(date)" >> /var/log/user-data.log
  EOF
  )
  
  tags = {
    Name = "chunker-instance"
  }
}

# EBS volume for database
resource "aws_ebs_volume" "database" {
  availability_zone = aws_instance.main.availability_zone
  size              = 20
  type              = "gp3"
  
  tags = {
    Name = "chunker-database-volume"
  }
}

# Attach EBS volume to EC2 instance
resource "aws_volume_attachment" "database" {
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.database.id
  instance_id = aws_instance.main.id
}

# Outputs
output "vpc_id" {
  description = "VPC ID being used"
  value       = data.aws_vpc.main.id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = data.aws_vpc.main.cidr_block
}

output "subnet_id" {
  description = "Public subnet ID used"
  value       = data.aws_subnet.public.id
}

output "subnet_cidr" {
  description = "Public subnet CIDR"
  value       = data.aws_subnet.public.cidr_block
}

output "availability_zone" {
  description = "AZ where instance is deployed"
  value       = aws_instance.main.availability_zone
}

output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.main.id
}

output "public_ip" {
  description = "Public IP address of the instance"
  value       = aws_instance.main.public_ip
}

output "ssh_key" {
  description = "Private SSH key to connect"
  value       = tls_private_key.key.private_key_pem
  sensitive   = true
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i chunker-key.pem ubuntu@${aws_instance.main.public_ip}"
}

output "qdrant_rest_api" {
  description = "Qdrant REST API URL"
  value       = "http://${aws_instance.main.public_ip}:6333"
}

output "qdrant_grpc_api" {
  description = "Qdrant gRPC API URL"
  value       = "http://${aws_instance.main.public_ip}:6334"
}

output "ping_test" {
  description = "Ping test command"
  value       = "ping ${aws_instance.main.public_ip}"
}
