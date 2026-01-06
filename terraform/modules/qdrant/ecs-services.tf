resource "aws_ecs_service" "node1" {
  name            = "qdrant-node1"
  cluster         = var.ecs_cluster_id
  task_definition = aws_ecs_task_definition.node1.arn
  desired_count   = 1
  launch_type     = "EC2"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_instances.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.qdrant.arn
    container_name   = "qdrant-node1"
    container_port   = 6333
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.qdrant_nlb.arn
    container_name   = "qdrant-node1"
    container_port   = 6333
  }

  placement_constraints {
    type       = "memberOf"
    expression = "ec2InstanceId == '${aws_instance.ecs_node1.id}'"
  }

  depends_on = [
    aws_volume_attachment.node1
  ]
}

resource "aws_ecs_service" "node2" {
  name            = "qdrant-node2"
  cluster         = var.ecs_cluster_id
  task_definition = aws_ecs_task_definition.node2.arn
  desired_count   = 1
  launch_type     = "EC2"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_instances.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.qdrant.arn
    container_name   = "qdrant-node2"
    container_port   = 6333
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.qdrant_nlb.arn
    container_name   = "qdrant-node2"
    container_port   = 6333
  }

  placement_constraints {
    type       = "memberOf"
    expression = "ec2InstanceId == '${aws_instance.ecs_node2.id}'"
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [
    aws_ecs_service.node1,
    aws_volume_attachment.node2
  ]
}
