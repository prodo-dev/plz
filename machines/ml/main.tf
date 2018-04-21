variable "environment_name" {}

variable "aws_region" {}

variable "aws_availability_zone" {}

variable "aws_dns_zone" {}

variable "subdomain" {}

variable "ami_tag" {}

variable "key_name" {}
variable "ssh_public_key_file" {}

variable "ec2_role" {
  default = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      }
    }
  ]
}
EOF
}

provider "aws" {
  version = "~> 1.11"
  region  = "${var.aws_region}"
}

///

data "aws_vpc" "main" {
  default = true
}

data "aws_subnet" "main" {
  availability_zone = "${var.aws_availability_zone}"
  default_for_az    = true
}

data "aws_security_group" "default" {
  vpc_id = "${data.aws_vpc.main.id}"

  filter = [
    {
      name   = "group-name"
      values = ["default"]
    },
  ]
}

data "aws_route53_zone" "internal" {
  name   = "${var.aws_dns_zone}"
  vpc_id = "${data.aws_vpc.main.id}"
}

resource "aws_key_pair" "plz" {
  key_name   = "${var.key_name}"
  public_key = "${file("${var.ssh_public_key_file}")}"
}

///

data "aws_ami" "controller-ami" {
  filter {
    name   = "name"
    values = ["plz-controller-${var.ami_tag}"]
  }
}

resource "aws_instance" "controller" {
  subnet_id                   = "${data.aws_subnet.main.id}"
  instance_type               = "m5.2xlarge"
  ami                         = "${data.aws_ami.controller-ami.id}"
  key_name                    = "${aws_key_pair.plz.key_name}"
  associate_public_ip_address = true
  iam_instance_profile        = "${aws_iam_instance_profile.controller.name}"

  tags {
    Name        = "Plz ${var.environment_name} Controller"
    Environment = "${var.environment_name}"
    Owner       = "Infrastructure"
  }
}

resource "aws_iam_instance_profile" "controller" {
  name = "plz-${lower(var.environment_name)}-controller"
  role = "${aws_iam_role.controller.name}"
}

resource "aws_iam_role" "controller" {
  name = "plz-${lower(var.environment_name)}-controller"

  assume_role_policy = "${var.ec2_role}"
}

resource "aws_iam_role_policy_attachment" "controller-policy-ec2" {
  role       = "${aws_iam_role.controller.name}"
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2FullAccess"
}

resource "aws_iam_role_policy_attachment" "controller-policy-ecr" {
  role       = "${aws_iam_role.controller.name}"
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryFullAccess"
}

resource "aws_ebs_volume" "controller-cache" {
  availability_zone = "${data.aws_subnet.main.availability_zone}"
  size              = 500

  tags {
    Name        = "Plz ${var.environment_name} Controller Cache"
    Environment = "${var.environment_name}"
    Owner       = "Infrastructure"
  }
}

resource "aws_volume_attachment" "controller-cache-attachment" {
  instance_id = "${aws_instance.controller.id}"
  volume_id   = "${aws_ebs_volume.controller-cache.id}"
  device_name = "/dev/sdx"

  skip_destroy = true

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command = "../../scripts/run-ansible-playbook-on-host ../../services/controller/src/plz/controller/startup/startup.yml ${aws_instance.controller.private_ip} /dev/stdin <<< 'device: /dev/xvdx'"
  }
}

resource "aws_route53_record" "controller" {
  zone_id = "${data.aws_route53_zone.internal.zone_id}"
  name    = "${var.subdomain}"
  type    = "A"
  ttl     = "300"
  records = ["${aws_instance.controller.private_ip}"]
}

output "controller-host" {
  value = "${aws_instance.controller.private_dns}"
}

///

data "aws_ami" "worker-ami" {
  filter {
    name   = "name"
    values = ["plz-worker-${var.ami_tag}"]
  }
}
