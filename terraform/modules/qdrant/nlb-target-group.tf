resource "aws_lb_target_group" "qdrant_nlb" {
  name     = "${var.environment}-qdrant-nlb-tg"
  port     = 6333
  protocol = "TCP"
  vpc_id   = var.vpc_id

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

resource "aws_lb_target_group_attachment" "node1" {
  target_group_arn = aws_lb_target_group.qdrant_nlb.arn
  target_id        = aws_instance.ecs_node1.id
  port             = 6333
}

resource "aws_lb_target_group_attachment" "node2" {
  target_group_arn = aws_lb_target_group.qdrant_nlb.arn
  target_id        = aws_instance.ecs_node2.id
  port             = 6333
}
