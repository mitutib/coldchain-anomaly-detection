variable "image" {
  description = "Service image, already built locally"
  type        = string
  default     = "coldchain:0.4.0"
}

variable "port" {
  description = "Host port the service listens on"
  type        = number
  default     = 18088
}

variable "offset" {
  description = "Degrees above the setpoint that count as too warm"
  type        = number
  default     = 1.0
}

variable "consecutive_readings" {
  description = "Readings in a row above the threshold before an alarm"
  type        = number
  default     = 2
}
