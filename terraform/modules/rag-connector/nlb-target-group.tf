resource "aws_lb_target_group" "nlb" {
  name        = "rag-connector-nlb-tg"
  port        = 8000
  protocol    = "TCP"
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
  }

  tags = merge(
    var.tags,
    {
      Name = "rag-connector-nlb-tg"
    }
  )
}

resource "aws_lb_listener" "nlb" {
  load_balancer_arn = var.nlb_arn
  port              = "8000"
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.nlb.arn
  }
}
