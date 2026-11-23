resource "docker_network" "coldchain" {
  name = "coldchain"
}

resource "docker_image" "redis" {
  name = "redis:7-alpine"
  # other containers on this machine may use the same image, so destroy must not remove it
  keep_locally = true
}

resource "docker_container" "redis" {
  name    = "coldchain-redis"
  image   = docker_image.redis.image_id
  command = ["redis-server", "--appendonly", "no"]

  networks_advanced {
    name = docker_network.coldchain.name
  }
}

resource "docker_container" "service" {
  name  = "coldchain-service"
  image = var.image

  env = [
    "COLDCHAIN_OFFSET=${var.offset}",
    "COLDCHAIN_N=${var.consecutive_readings}",
    "COLDCHAIN_REDIS_URL=redis://${docker_container.redis.name}:6379/0",
  ]

  ports {
    internal = 8000
    external = var.port
    ip       = "127.0.0.1"
  }

  networks_advanced {
    name = docker_network.coldchain.name
  }
}
