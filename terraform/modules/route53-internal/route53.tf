resource "aws_route53_zone" "internal" {
  name = "internal"

  vpc {
    vpc_id = var.vpc_id
  }

  tags = merge(
    var.tags,
    {
      Name = "internal"
    }
  )
}
