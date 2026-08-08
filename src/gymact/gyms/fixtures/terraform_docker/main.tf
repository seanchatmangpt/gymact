/*
 * Hand-authored, checked-in Terraform configuration for
 * TerraformDockerApplyProvider (see ../../terraform_docker_apply.py).
 *
 * Fixed, small, auditable blast radius:
 *   - exactly one docker_image resource (pinned nginx:alpine)
 *   - exactly one docker_container resource built from that image
 *   - the docker provider host is colima's real LOCAL Docker socket, never
 *     a cloud endpoint or cloud credentials
 *
 * The provider host is parameterized via `var.docker_host` (default: the
 * standard colima socket path) so it can be overridden per-machine with
 * `-var docker_host=...` or `TF_VAR_docker_host=...` without editing this
 * checked-in file.
 */

terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

variable "docker_host" {
  description = "Real local Docker daemon socket URI (colima by default). Never a cloud endpoint."
  type        = string
  default     = "unix:///Users/sac/.colima/default/docker.sock"
}

variable "container_name" {
  description = "Name of the single docker_container this config creates."
  type        = string
  default     = "gymact-terraform-docker-apply-test"
}

provider "docker" {
  host = var.docker_host
}

resource "docker_image" "app" {
  name = "nginx:alpine"
}

resource "docker_container" "app" {
  name  = var.container_name
  image = docker_image.app.image_id
}
