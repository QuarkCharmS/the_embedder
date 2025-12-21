resource "aws_lb_target_group" "alb" {
  count = var.enable_nipio_routing ? 1 : 0

  name        = "rag-connector-alb-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    protocol            = "HTTP"
    path                = "/health"
    port                = "8000"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
    matcher             = "200"
  }

  tags = merge(
    var.tags,
    {
      Name = "rag-connector-alb-tg"
    }
  )
}

resource "aws_lb_listener_rule" "alb" {
  count = var.enable_nipio_routing ? 1 : 0

  listener_arn = var.alb_listener_arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.alb[0].arn
  }

  condition {
    host_header {
      values = ["rag-connector.*.nip.io"]
    }
  }
}
