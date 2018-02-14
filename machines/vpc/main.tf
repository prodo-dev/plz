variable "region" {}

provider "aws" {
  version                 = "~> 1.8"
  shared_credentials_file = "../credentials/root.awscreds"
  profile                 = "default"
  region                  = "${var.region}"
}

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

resource "aws_default_security_group" "default" {
  vpc_id = "${aws_vpc.main.id}"

  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["${aws_vpc.main.cidr_block}"]
  }

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
