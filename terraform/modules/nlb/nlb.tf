resource "aws_lb" "main" {
  name               = var.name
  internal           = true
  load_balancer_type = "network"
  subnets            = var.subnet_ids

  tags = merge(
    var.tags,
    {
      Name = var.name
    }
  )
}
