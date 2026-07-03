provider "aws" {
  region = "us-west-2"
}

module "vpc" {
  source = "./modules/vpc"
  vpc_name = "observability-vpc"
  igw_name = "observability-igw"
  nat_name = "observability-nat-gateway"
  nat-eip = "observability-nat-eip"
}

module "eks" {
  source             = "./modules/eks"
  cluster_name       = "observability-eks-cluster"
  public_subnet_ids  = module.vpc.public_subnet_ids
  private_subnet_ids = module.vpc.private_subnet_ids
}
