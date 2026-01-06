resource "aws_lb_target_group" "qdrant" {
  name        = "qdrant-api"
  port        = 6333
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    path                = "/"
    matcher             = "200"
  }

  deregistration_delay = 30

  tags = merge(
    var.tags,
    {
      Name = "qdrant-api-tg"
    }
  )
}

resource "aws_lb_listener_rule" "nip_io" {
  count = var.enable_nipio_routing ? 1 : 0

  listener_arn = var.alb_listener_arn
  priority     = 200

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.qdrant.arn
  }

  condition {
    host_header {
      values = ["qdrant.*.nip.io"]
    }
  }
}
