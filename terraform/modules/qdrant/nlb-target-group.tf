resource "aws_lb_target_group" "qdrant_nlb" {
  name                 = "${var.environment}-qdrant-nlb-tg"
  port                 = 6333
  protocol             = "TCP"
  vpc_id               = var.vpc_id
  target_type          = "ip"
  preserve_client_ip   = false

  health_check {
    enabled  = true
    protocol = "TCP"
    port     = 6333
    interval = 30
  }

  deregistration_delay = 30

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-qdrant-nlb-tg"
    }
  )
}

resource "aws_lb_listener" "qdrant_nlb" {
  load_balancer_arn = var.nlb_arn
  port              = 6333
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.qdrant_nlb.arn
  }
}
