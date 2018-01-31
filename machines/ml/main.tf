variable "availability-zone" {
  default = "eu-west-1a"
}

provider "aws" {
  region = "eu-west-1"
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

resource "aws_subnet" "main" {
  vpc_id            = "${aws_vpc.main.id}"
  availability_zone = "${var.availability-zone}"
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

data "aws_ami" "build-ami" {
  filter {
    name   = "name"
    values = ["prodo-ml-build-test"]
  }
}

resource "aws_instance" "build" {
  subnet_id                   = "${aws_subnet.main.id}"
  instance_type               = "t2.medium"
  ami                         = "${data.aws_ami.build-ami.id}"
  vpc_security_group_ids      = ["${aws_default_security_group.default.id}", "${aws_security_group.ssh.id}"]
  key_name                    = "batman-key"
  associate_public_ip_address = true
  iam_instance_profile        = "docker-build-machines"

  tags {
    Name  = "Batman Build"
    Owner = "Infrastructure"
  }
}

output "build-host" {
  value = "${aws_instance.build.public_dns}"
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
}

data "aws_ami" "experiments-ami" {
  filter {
    name   = "name"
    values = ["prodo-ml-experiments-test"]
  }
}

resource "aws_spot_instance_request" "experiments" {
  subnet_id                   = "${aws_subnet.main.id}"
  instance_type               = "g2.2xlarge"
  ami                         = "${data.aws_ami.experiments-ami.id}"
  vpc_security_group_ids      = ["${aws_default_security_group.default.id}", "${aws_security_group.ssh.id}"]
  key_name                    = "batman-key"
  associate_public_ip_address = true
  iam_instance_profile        = "docker-build-machines"

  spot_price           = "1"
  wait_for_fulfillment = true

  ebs_block_device {
    volume_size = 100
    device_name = "/dev/sdx"
  }

  provisioner "remote-exec" {
    connection {
      type        = "ssh"
      user        = "ubuntu"
      private_key = "${file("../keys/batman.privkey")}"
    }

    inline = "${replace(file("initialize-cache"), "$1", "/dev/xvdx")}"
  }

  tags {
    Name  = "Batman Experiments Request"
    Owner = "Infrastructure"
  }
}

output "experiments-host" {
  value = "${aws_spot_instance_request.experiments.public_dns}"
}
