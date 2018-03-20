variable "region" {}

variable "availability_zone" {}

variable "environment" {
  default = "Production"
}

variable "ami_tag" {
  default = "2018-03-01"
}

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
  version                 = "~> 1.11"
  shared_credentials_file = "../credentials/root.awscreds"
  profile                 = "default"
  region                  = "${var.region}"
}

///

data "aws_vpc" "main" {
  default = true
}

data "aws_subnet" "main" {
  availability_zone = "${var.availability_zone}"
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

resource "aws_key_pair" "plz" {
  key_name   = "plz-${lower(var.environment)}-key"
  public_key = "${file("../keys/plz.pubkey")}"
}

///

data "aws_ami" "controller-ami" {
  filter {
    name   = "name"
    values = ["plz-build-${var.ami_tag}"]
  }
}

resource "aws_instance" "controller" {
  subnet_id                   = "${data.aws_subnet.main.id}"
  instance_type               = "t2.small"
  ami                         = "${data.aws_ami.controller-ami.id}"
  key_name                    = "plz-${lower(var.environment)}-key"
  associate_public_ip_address = true
  iam_instance_profile        = "${aws_iam_instance_profile.controller.name}"
  security_groups             = ["${data.aws_security_group.default.id}"]

  tags {
    Name        = "Plz ${var.environment} Controller"
    Environment = "${var.environment}"
    Owner       = "Infrastructure"
  }
}

resource "aws_iam_instance_profile" "controller" {
  name = "plz-${lower(var.environment)}-controller"
  role = "${aws_iam_role.controller.name}"
}

resource "aws_iam_role" "controller" {
  name = "plz-${lower(var.environment)}-controller"

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

resource "aws_ebs_volume" "build-cache" {
  availability_zone = "${data.aws_subnet.main.availability_zone}"
  size              = 500

  tags {
    Name        = "Plz ${var.environment} Build Cache"
    Environment = "${var.environment}"
    Owner       = "Infrastructure"
  }
}

resource "aws_volume_attachment" "build-cache-attachment" {
  instance_id = "${aws_instance.controller.id}"
  volume_id   = "${aws_ebs_volume.build-cache.id}"
  device_name = "/dev/sdx"

  skip_destroy = true

  provisioner "local-exec" {
    command = "../scripts/on-host ubuntu@${aws_instance.controller.private_dns} ../../services/controller/src/scripts/initialize-cache /dev/xvdx"
  }
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
