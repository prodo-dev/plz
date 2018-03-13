variable "region" {}

variable "domain" {}

variable "subdomain" {}

provider "aws" {
  version                 = "~> 1.11"
  shared_credentials_file = "../credentials/root.awscreds"
  profile                 = "default"
  region                  = "${var.region}"
}

data "aws_vpc" "main" {
  default = true
}

data "aws_route53_zone" "zone" {
  name = "${var.domain}"
}

data "aws_instance" "vpn" {
  filter = {
    name   = "tag:Name"
    values = ["Batman OpenVPN"]
  }
}

resource "aws_route53_record" "vpn" {
  zone_id = "${data.aws_route53_zone.zone.zone_id}"
  name    = "${var.subdomain}"
  type    = "A"
  ttl     = "300"

  records = [
    "${data.aws_instance.vpn.public_ip}",
  ]
}

data "aws_instance" "controller" {
  filter = {
    name   = "tag:Name"
    values = ["Batman Production Controller"]
  }
}

resource "aws_route53_record" "controller" {
  zone_id = "${data.aws_route53_zone.zone.zone_id}"
  name    = "batman.${var.subdomain}"
  type    = "A"
  ttl     = "300"

  records = [
    "${data.aws_instance.controller.private_ip}",
  ]
}
