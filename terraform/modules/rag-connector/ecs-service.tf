resource "aws_ecs_service" "rag_connector" {
  name            = "rag-connector"
  cluster         = var.ecs_cluster_id
  task_definition = aws_ecs_task_definition.rag_connector.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.rag_connector.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.nlb.arn
    container_name   = "rag-connector"
    container_port   = 8000
  }

  dynamic "load_balancer" {
    for_each = var.enable_nipio_routing ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.alb[0].arn
      container_name   = "rag-connector"
      container_port   = 8000
    }
  }

  tags = merge(
    var.tags,
    {
      Name = "rag-connector-service"
    }
  )
}
