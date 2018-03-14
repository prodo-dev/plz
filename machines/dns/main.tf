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

data "aws_route53_zone" "external" {
  name = "${var.domain}"
}

resource "aws_route53_zone" "internal" {
  name    = "${var.subdomain}"
  vpc_id  = "${data.aws_vpc.main.id}"
  comment = "Internal"
}

data "aws_instance" "vpn" {
  filter = {
    name   = "tag:Name"
    values = ["Batman OpenVPN"]
  }
}

resource "aws_route53_record" "vpn_external" {
  zone_id = "${data.aws_route53_zone.external.zone_id}"
  name    = "${var.subdomain}"
  type    = "A"
  ttl     = "300"

  records = [
    "${data.aws_instance.vpn.public_ip}",
  ]
}

resource "aws_route53_record" "vpn_internal" {
  zone_id = "${aws_route53_zone.internal.zone_id}"
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
  zone_id = "${aws_route53_zone.internal.zone_id}"
  name    = "batman.${var.subdomain}"
  type    = "A"
  ttl     = "300"

  records = [
    "${data.aws_instance.controller.private_ip}",
  ]
}
