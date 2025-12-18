resource "aws_ecs_service" "node1" {
  name            = "qdrant-node1"
  cluster         = var.ecs_cluster_id
  task_definition = aws_ecs_task_definition.node1.arn
  desired_count   = 1
  launch_type     = "EC2"

  placement_constraints {
    type       = "memberOf"
    expression = "ec2InstanceId == '${aws_instance.ecs_node1.id}'"
  }

  depends_on = [
    aws_volume_attachment.node1,
    aws_lb_target_group_attachment.node1
  ]
}

resource "aws_ecs_service" "node2" {
  name            = "qdrant-node2"
  cluster         = var.ecs_cluster_id
  task_definition = aws_ecs_task_definition.node2.arn
  desired_count   = 1
  launch_type     = "EC2"

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
    aws_volume_attachment.node2,
    aws_lb_target_group_attachment.node2
  ]
}
