variable "region" {}

variable "vpn_cidr_block" {
  default = "10.8.0.0/16"
}

provider "aws" {
  version                 = "~> 1.11"
  shared_credentials_file = "../credentials/root.awscreds"
  profile                 = "default"
  region                  = "${var.region}"
}

data "aws_vpc" "main" {
  default = true
}

resource "aws_default_security_group" "default" {
  vpc_id = "${data.aws_vpc.main.id}"

  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["${data.aws_vpc.main.cidr_block}", "${var.vpn_cidr_block}"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ssh" {
  vpc_id      = "${data.aws_vpc.main.id}"
  name        = "Plz SSH"
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
    Name  = "Plz SSH"
    Owner = "Infrastructure"
  }
}
