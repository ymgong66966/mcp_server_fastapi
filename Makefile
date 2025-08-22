# MCP Server FastAPI Makefile
# Based on successful patterns from langgraph-kafka-k8s

# Configuration
REGISTRY ?= 245230032478.dkr.ecr.us-east-2.amazonaws.com
REPOSITORY ?= mcp-server-fastapi
TAG ?= latest
AWS_REGION ?= us-east-2
CLUSTER_NAME ?= my-small-cluster
NAMESPACE ?= mcp-server

# Build targets
.PHONY: build push build-and-push

build:
	@echo "Building Docker image for MCP Server FastAPI..."
	docker buildx build --platform linux/amd64 \
		-f app/Dockerfile \
		-t $(REGISTRY)/$(REPOSITORY):$(TAG) \
		./app

push:
	@echo "Pushing Docker image to ECR..."
	aws ecr get-login-password --region $(AWS_REGION) | \
		docker login --username AWS --password-stdin $(REGISTRY)
	docker push $(REGISTRY)/$(REPOSITORY):$(TAG)

build-and-push: build push

# Development targets
.PHONY: deploy-dev deploy-prod status logs

deploy-dev:
	@echo "Deploying to development environment..."
	@if [ -z "$(TAG)" ] || [ "$(TAG)" = "latest" ]; then \
		echo "Warning: Using 'latest' tag for development. Consider using a specific tag."; \
	fi
	helm upgrade --install mcp-server-dev ./chart \
		--namespace $(NAMESPACE)-dev \
		--create-namespace \
		--values ./chart/values-dev.yaml \
		--set image.repository=$(REGISTRY)/$(REPOSITORY) \
		--set image.tag=$(TAG) \
		--wait \
		--timeout 10m

deploy-prod:
	@echo "Deploying to production environment..."
	@if [ "$(TAG)" = "latest" ]; then \
		echo "Error: Cannot deploy 'latest' tag to production. Use a specific tag."; \
		exit 1; \
	fi
	helm upgrade --install mcp-server-prod ./chart \
		--namespace $(NAMESPACE) \
		--create-namespace \
		--values ./chart/values.yaml \
		--set image.repository=$(REGISTRY)/$(REPOSITORY) \
		--set image.tag=$(TAG) \
		--wait \
		--timeout 10m

status:
	@echo "=== Development Status ==="
	@kubectl get pods -n $(NAMESPACE)-dev -l app.kubernetes.io/name=mcp-server || echo "No development deployment found"
	@echo ""
	@echo "=== Production Status ==="
	@kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/name=mcp-server || echo "No production deployment found"

logs:
	@echo "Fetching logs from development environment..."
	@kubectl logs -f deployment/mcp-server-dev -n $(NAMESPACE)-dev --tail=50 || \
		echo "No development deployment found, trying production..."
	@kubectl logs -f deployment/mcp-server-prod -n $(NAMESPACE) --tail=50 || \
		echo "No deployments found"

# Cleanup targets
.PHONY: clean-dev clean-prod clean

clean-dev:
	@echo "Cleaning up development environment..."
	helm uninstall mcp-server-dev -n $(NAMESPACE)-dev || echo "No development deployment to clean"
	kubectl delete namespace $(NAMESPACE)-dev || echo "No development namespace to delete"

clean-prod:
	@echo "Cleaning up production environment..."
	@read -p "Are you sure you want to delete the production deployment? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		helm uninstall mcp-server-prod -n $(NAMESPACE) || echo "No production deployment to clean"; \
		kubectl delete namespace $(NAMESPACE) || echo "No production namespace to delete"; \
	else \
		echo "Production cleanup cancelled."; \
	fi

clean: clean-dev clean-prod

# Testing targets
.PHONY: test-build test-health port-forward

test-build:
	@echo "Testing Docker build locally..."
	docker build -f app/Dockerfile -t mcp-server-test ./app
	@echo "Build successful. Testing container..."
	docker run --rm -d --name mcp-server-test-container -p 8080:8080 mcp-server-test
	@sleep 5
	@echo "Testing health endpoint..."
	curl -f http://localhost:8080/health || (docker stop mcp-server-test-container && exit 1)
	@echo "Testing readiness endpoint..."
	curl -f http://localhost:8080/ready || (docker stop mcp-server-test-container && exit 1)
	docker stop mcp-server-test-container
	docker rmi mcp-server-test
	@echo "Local testing completed successfully!"

test-health:
	@echo "Testing deployed service health..."
	@kubectl port-forward -n $(NAMESPACE)-dev service/mcp-server-dev 8080:80 &
	@PID=$$!; \
	sleep 5; \
	curl -f http://localhost:8080/health && curl -f http://localhost:8080/ready; \
	kill $$PID

port-forward:
	@echo "Port forwarding development service to localhost:8080..."
	kubectl port-forward -n $(NAMESPACE)-dev service/mcp-server-dev 8080:80

# Setup targets
.PHONY: aws-login cluster-access helm-setup

aws-login:
	@echo "Logging into AWS ECR..."
	aws ecr get-login-password --region $(AWS_REGION) | \
		docker login --username AWS --password-stdin $(REGISTRY)

cluster-access:
	@echo "Configuring kubectl for EKS cluster..."
	aws eks update-kubeconfig --region $(AWS_REGION) --name $(CLUSTER_NAME)

helm-setup:
	@echo "Setting up Helm..."
	@if ! command -v helm &> /dev/null; then \
		echo "Helm not found. Please install Helm first."; \
		exit 1; \
	fi
	@echo "Helm is ready."

# Help target
.PHONY: help

help:
	@echo "MCP Server FastAPI Deployment Commands"
	@echo "======================================"
	@echo ""
	@echo "Build Commands:"
	@echo "  build              Build Docker image"
	@echo "  push               Push image to ECR"
	@echo "  build-and-push     Build and push image"
	@echo ""
	@echo "Deployment Commands:"
	@echo "  deploy-dev         Deploy to development environment"
	@echo "  deploy-prod        Deploy to production environment"
	@echo ""
	@echo "Management Commands:"
	@echo "  status             Check deployment status"
	@echo "  logs               View application logs"
	@echo "  port-forward       Forward service to localhost:8080"
	@echo ""
	@echo "Testing Commands:"
	@echo "  test-build         Test Docker build locally"
	@echo "  test-health        Test deployed service health"
	@echo ""
	@echo "Cleanup Commands:"
	@echo "  clean-dev          Remove development deployment"
	@echo "  clean-prod         Remove production deployment"
	@echo "  clean              Remove all deployments"
	@echo ""
	@echo "Setup Commands:"
	@echo "  aws-login          Login to AWS ECR"
	@echo "  cluster-access     Configure kubectl for EKS"
	@echo "  helm-setup         Verify Helm installation"
	@echo ""
	@echo "Examples:"
	@echo "  make build TAG=v1.2.3"
	@echo "  make deploy-dev TAG=v1.2.3"
	@echo "  make deploy-prod TAG=v1.2.3"
	@echo ""
	@echo "Environment Variables:"
	@echo "  REGISTRY           ECR registry URL (default: $(REGISTRY))"
	@echo "  REPOSITORY         ECR repository name (default: $(REPOSITORY))"
	@echo "  TAG                Image tag (default: $(TAG))"
	@echo "  AWS_REGION         AWS region (default: $(AWS_REGION))"
	@echo "  CLUSTER_NAME       EKS cluster name (default: $(CLUSTER_NAME))"
	@echo "  NAMESPACE          Kubernetes namespace (default: $(NAMESPACE))"