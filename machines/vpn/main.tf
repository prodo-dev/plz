variable "region" {}

variable "availability_zone" {}

provider "aws" {
  version                 = "~> 1.11"
  shared_credentials_file = "../credentials/root.awscreds"
  profile                 = "default"
  region                  = "${var.region}"
}

data "aws_vpc" "main" {
  default = true
}

data "aws_subnet" "main" {
  availability_zone = "${var.availability_zone}"
  default_for_az    = true
}

data "aws_route_table" "main" {
  vpc_id = "${data.aws_vpc.main.id}"
}

data "aws_security_group" "default" {
  vpc_id = "${data.aws_vpc.main.id}"

  filter = [
    {
      name = "group-name"

      values = [
        "default",
      ]
    },
  ]
}

resource "aws_security_group" "openvpn" {
  vpc_id      = "${data.aws_vpc.main.id}"
  name        = "Plz OpenVPN"
  description = "OpenVPN Access Server"

  ingress {
    from_port = 22
    to_port   = 22
    protocol  = "tcp"

    cidr_blocks = [
      "0.0.0.0/0",
    ]
  }

  ingress {
    from_port = 443
    to_port   = 443
    protocol  = "tcp"

    cidr_blocks = [
      "0.0.0.0/0",
    ]
  }

  ingress {
    from_port = 943
    to_port   = 943
    protocol  = "tcp"

    cidr_blocks = [
      "0.0.0.0/0",
    ]
  }

  ingress {
    from_port = 1194
    to_port   = 1194
    protocol  = "udp"

    cidr_blocks = [
      "0.0.0.0/0",
    ]
  }

  ingress {
    from_port = 60000
    to_port   = 61000
    protocol  = "udp"

    cidr_blocks = [
      "0.0.0.0/0",
    ]
  }

  tags {
    Name  = "Plz OpenVPN"
    Owner = "Infrastructure"
  }
}

resource "aws_key_pair" "plz" {
  key_name   = "plz-openvpn-key"
  public_key = "${file("../keys/plz.pubkey")}"
}

data "aws_ami" "ubuntu" {
  most_recent = true

  owners = [
    "099720109477",
  ]

  # Canonical

  filter {
    name = "name"

    values = [
      "ubuntu/images/hvm-ssd/ubuntu-xenial-16.04-amd64-server-*",
    ]
  }
  filter {
    name = "virtualization-type"

    values = [
      "hvm",
    ]
  }
}

resource "aws_instance" "server" {
  subnet_id         = "${data.aws_subnet.main.id}"
  instance_type     = "t2.small"
  ami               = "${data.aws_ami.ubuntu.id}"
  source_dest_check = false

  vpc_security_group_ids = [
    "${data.aws_security_group.default.id}",
    "${aws_security_group.openvpn.id}",
  ]

  key_name                    = "plz-openvpn-key"
  associate_public_ip_address = true

  tags {
    Name  = "Plz OpenVPN"
    Owner = "Infrastructure"
  }
}

resource "aws_ebs_volume" "keys" {
  availability_zone = "${data.aws_subnet.main.availability_zone}"
  size              = 8

  tags {
    Name  = "Plz OpenVPN Keys"
    Owner = "Infrastructure"
  }
}

resource "aws_volume_attachment" "keys" {
  instance_id = "${aws_instance.server.id}"
  volume_id   = "${aws_ebs_volume.keys.id}"
  device_name = "/dev/sdk"

  skip_destroy = true
}

resource "aws_route" "openvpn" {
  route_table_id         = "${data.aws_route_table.main.id}"
  destination_cidr_block = "10.8.0.0/16"
  instance_id            = "${aws_instance.server.id}"
}

resource "aws_eip" "server" {
  instance = "${aws_instance.server.id}"
  vpc      = true

  tags {
    Name  = "Plz OpenVPN"
    Owner = "Infrastructure"
  }
}

output "host" {
  value = "${aws_instance.server.public_dns}"
}
