data "aws_ami" "ecs_optimized" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-ecs-hvm-*-x86_64-ebs"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Get subnet details to extract availability zones
data "aws_subnet" "private" {
  count = 2
  id    = var.private_subnet_ids[count.index]
}

resource "aws_instance" "ecs_node1" {
  ami                    = data.aws_ami.ecs_optimized.id
  instance_type          = var.instance_type
  subnet_id              = var.private_subnet_ids[0]
  vpc_security_group_ids = [aws_security_group.ecs_instances.id]
  iam_instance_profile   = var.ecs_instance_profile_name

  user_data = base64encode(templatefile("${path.module}/user-data.sh", {
    cluster_name = var.ecs_cluster_name
    device_name  = "/dev/xvdf"
  }))

  tags = {
    Name = "qdrant-node1"
  }
}

resource "aws_instance" "ecs_node2" {
  ami                    = data.aws_ami.ecs_optimized.id
  instance_type          = var.instance_type
  subnet_id              = var.private_subnet_ids[1]
  vpc_security_group_ids = [aws_security_group.ecs_instances.id]
  iam_instance_profile   = var.ecs_instance_profile_name

  user_data = base64encode(templatefile("${path.module}/user-data.sh", {
    cluster_name = var.ecs_cluster_name
    device_name  = "/dev/xvdf"
  }))

  tags = {
    Name = "qdrant-node2"
  }
}

resource "aws_ebs_volume" "node1" {
  availability_zone = data.aws_subnet.private[0].availability_zone
  size              = var.ebs_volume_size
  type              = "gp3"
  iops              = 3000
  throughput        = 125
  encrypted         = true

  tags = {
    Name = "qdrant-node1-data"
  }
}

resource "aws_ebs_volume" "node2" {
  availability_zone = data.aws_subnet.private[1].availability_zone
  size              = var.ebs_volume_size
  type              = "gp3"
  iops              = 3000
  throughput        = 125
  encrypted         = true

  tags = {
    Name = "qdrant-node2-data"
  }
}

resource "aws_volume_attachment" "node1" {
  device_name = "/dev/xvdf"
  volume_id   = aws_ebs_volume.node1.id
  instance_id = aws_instance.ecs_node1.id
}

resource "aws_volume_attachment" "node2" {
  device_name = "/dev/xvdf"
  volume_id   = aws_ebs_volume.node2.id
  instance_id = aws_instance.ecs_node2.id
}
