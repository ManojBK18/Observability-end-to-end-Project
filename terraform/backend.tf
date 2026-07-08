terraform {
  backend "s3" {
    bucket       = "observability-tf-state-1"
    key          = "terraform.tfstate"
    region       = "ap-south-1"
    encrypt      = true
    use_lockfile = true # Native S3 locking pattern
  }
}
