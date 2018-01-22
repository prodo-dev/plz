provider "aws" {
  region = "eu-west-1"
}

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true

  tags {
    Name = "Batman"
  }
}

resource "aws_internet_gateway" "gateway" {
  vpc_id = "${aws_vpc.main.id}"

  tags {
    Name = "Batman"
  }
}

resource "aws_route" "gateway-route" {
  route_table_id         = "${aws_vpc.main.default_route_table_id}"
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = "${aws_internet_gateway.gateway.id}"
}

resource "aws_subnet" "main" {
  vpc_id     = "${aws_vpc.main.id}"
  cidr_block = "10.0.1.0/24"

  tags {
    Name = "Batman"
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
}

resource "aws_security_group" "ssh" {
  vpc_id      = "${aws_vpc.main.id}"
  name        = "ssh"
  description = "Allow SSH access"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags {
    Name = "Batman SSH"
  }
}

resource "aws_key_pair" "batman" {
  key_name   = "batman-key"
  public_key = "${file("../keys/batman.pubkey")}"
}

resource "aws_spot_instance_request" "experiments" {
  subnet_id                   = "${aws_subnet.main.id}"
  instance_type               = "g2.2xlarge"
  ami                         = "ami-4d46d534"
  vpc_security_group_ids      = ["${aws_default_security_group.default.id}", "${aws_security_group.ssh.id}"]
  key_name                    = "batman-key"
  associate_public_ip_address = true

  spot_price           = "1"
  wait_for_fulfillment = true

  tags {
    Name = "Batman Experiments Request"
  }
}
