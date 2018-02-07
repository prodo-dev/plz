variable "region" {}
variable "availability_zone" {}

variable "ami_tag" {
  default = "2018-02-07"
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
  shared_credentials_file = "../credentials/root.awscreds"
  region                  = "${var.region}"
}

///

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true

  tags {
    Name  = "Batman"
    Owner = "Infrastructure"
  }
}

resource "aws_internet_gateway" "gateway" {
  vpc_id = "${aws_vpc.main.id}"

  tags {
    Name  = "Batman"
    Owner = "Infrastructure"
  }
}

resource "aws_route" "gateway-route" {
  route_table_id         = "${aws_vpc.main.default_route_table_id}"
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = "${aws_internet_gateway.gateway.id}"
}

resource "aws_subnet" "main" {
  vpc_id            = "${aws_vpc.main.id}"
  availability_zone = "${var.availability_zone}"
  cidr_block        = "10.0.1.0/24"

  tags {
    Name  = "Batman"
    Owner = "Infrastructure"
  }
}

resource "aws_default_security_group" "default" {
  vpc_id = "${aws_vpc.main.id}"

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags {
    Owner = "Infrastructure"
  }
}

resource "aws_security_group" "ssh" {
  vpc_id      = "${aws_vpc.main.id}"
  name        = "ssh"
  description = "Allow SSH and Mosh access"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 60000
    to_port     = 61000
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags {
    Name  = "Batman SSH"
    Owner = "Infrastructure"
  }
}

resource "aws_key_pair" "batman" {
  key_name   = "batman-key"
  public_key = "${file("../keys/batman.pubkey")}"
}

///

data "aws_ami" "controller-ami" {
  filter {
    name   = "name"
    values = ["batman-controller-${var.ami_tag}"]
  }
}

resource "aws_instance" "controller" {
  subnet_id                   = "${aws_subnet.main.id}"
  instance_type               = "t2.small"
  ami                         = "${data.aws_ami.controller-ami.id}"
  vpc_security_group_ids      = ["${aws_default_security_group.default.id}", "${aws_security_group.ssh.id}"]
  key_name                    = "batman-key"
  associate_public_ip_address = true
  iam_instance_profile        = "${aws_iam_instance_profile.controller.name}"

  tags {
    Name  = "Batman Controller"
    Owner = "Infrastructure"
  }
}

resource "aws_iam_instance_profile" "controller" {
  name = "batman-controller"
  role = "${aws_iam_role.controller.name}"
}

resource "aws_iam_role" "controller" {
  name = "batman-controller"

  assume_role_policy = "${var.ec2_role}"
}

resource "aws_iam_role_policy_attachment" "controller-policy-autoscaling" {
  role       = "${aws_iam_role.controller.name}"
  policy_arn = "arn:aws:iam::aws:policy/AutoScalingFullAccess"
}

resource "aws_iam_role_policy_attachment" "controller-policy-ecr" {
  role       = "${aws_iam_role.controller.name}"
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

output "controller-host" {
  value = "${aws_instance.controller.public_dns}"
}

///

data "aws_ami" "build-ami" {
  filter {
    name   = "name"
    values = ["batman-build-${var.ami_tag}"]
  }
}

resource "aws_instance" "build" {
  subnet_id                   = "${aws_subnet.main.id}"
  instance_type               = "t2.medium"
  ami                         = "${data.aws_ami.build-ami.id}"
  vpc_security_group_ids      = ["${aws_default_security_group.default.id}", "${aws_security_group.ssh.id}"]
  key_name                    = "batman-key"
  associate_public_ip_address = true
  iam_instance_profile        = "${aws_iam_instance_profile.build.name}"

  tags {
    Name  = "Batman Build"
    Owner = "Infrastructure"
  }
}

resource "aws_iam_instance_profile" "build" {
  name = "batman-build"
  role = "${aws_iam_role.build.name}"
}

resource "aws_iam_role" "build" {
  name = "batman-build"

  assume_role_policy = "${var.ec2_role}"
}

resource "aws_iam_role_policy_attachment" "build-policy-ecr" {
  role       = "${aws_iam_role.build.name}"
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryFullAccess"
}

resource "aws_ebs_volume" "build-cache" {
  availability_zone = "${aws_subnet.main.availability_zone}"
  size              = 500

  tags {
    Name  = "Batman Build Cache"
    Owner = "Infrastructure"
  }
}

resource "aws_volume_attachment" "build-cache-attachment" {
  instance_id = "${aws_instance.build.id}"
  volume_id   = "${aws_ebs_volume.build-cache.id}"
  device_name = "/dev/sdx"

  provisioner "local-exec" {
    command = "./on-host ubuntu@${aws_instance.build.public_dns} ./initialize-cache /dev/xvdx"
  }
}

output "build-host" {
  value = "${aws_instance.build.public_dns}"
}

///

data "aws_ami" "worker-ami" {
  filter {
    name   = "name"
    values = ["batman-worker-${var.ami_tag}"]
  }
}

resource "aws_launch_configuration" "worker-configuration" {
  name                        = "batman-worker"
  instance_type               = "g2.2xlarge"
  image_id                    = "${data.aws_ami.worker-ami.id}"
  security_groups             = ["${aws_default_security_group.default.id}", "${aws_security_group.ssh.id}"]
  key_name                    = "batman-key"
  associate_public_ip_address = true
  iam_instance_profile        = "${aws_iam_instance_profile.worker.name}"

  spot_price = "1"

  ebs_block_device {
    volume_size = 100
    device_name = "/dev/sdx"
  }

  user_data = "${replace(file("initialize-cache"), "$1", "/dev/xvdx")}"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "worker" {
  name                 = "batman-worker"
  vpc_zone_identifier  = ["${aws_subnet.main.id}"]
  availability_zones   = ["${var.availability_zone}"]
  launch_configuration = "${aws_launch_configuration.worker-configuration.name}"

  min_size         = 0
  max_size         = 50
  desired_capacity = 0

  lifecycle {
    ignore_changes = ["min_size", "desired_capacity"]
  }

  tags = [
    {
      key                 = "Name"
      value               = "Batman Worker"
      propagate_at_launch = true
    },
    {
      key                 = "Owner"
      value               = "Infrastructure"
      propagate_at_launch = true
    },
    {
      key                 = "Execution-Id"
      value               = ""
      propagate_at_launch = true
    },
  ]
}

resource "aws_iam_instance_profile" "worker" {
  name = "batman-worker"
  role = "${aws_iam_role.worker.name}"
}

resource "aws_iam_role" "worker" {
  name = "batman-worker"

  assume_role_policy = "${var.ec2_role}"
}

resource "aws_iam_role_policy_attachment" "worker-policy-ecr" {
  role       = "${aws_iam_role.worker.name}"
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}
