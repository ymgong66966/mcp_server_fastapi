# MCP Server FastAPI - Robust Deployment Guide

A comprehensive deployment guide for MCP (Model Context Protocol) Server FastAPI to AWS EKS, following proven patterns from the langgraph-kafka-k8s project.

## 🏗️ Architecture Overview

**MCP Server FastAPI** is a FastMCP-based server that provides:
- **MCP Tools**: `add`, `find_products`, `online_search` for LLM integration
- **Health Endpoints**: `/health` and `/ready` for Kubernetes probes
- **Modular Design**: Main server with mountable sub-servers (`online_mcp`)
- **Cloud-Native**: Kubernetes-ready with proper security and observability

## 🔧 Components

### Core Application (`app/`)
- **main.py**: FastMCP server with HTTP transport on port 8080
- **online_search_mcp.py**: Modular MCP sub-server for online search functionality
- **Dockerfile**: Multi-stage, security-hardened container build
- **requirements.txt**: Python dependencies (fastmcp, starlette, uvicorn)

### Kubernetes Deployment (`chart/`)
- **Helm Chart**: Production-ready with security, health checks, and scalability
- **Multi-Environment**: Separate configurations for dev/prod
- **AWS EKS Optimized**: LoadBalancer service, proper resource limits, security context

### CI/CD (`.github/workflows/`)
- **GitHub Actions**: Multi-stage pipeline with security scanning
- **Multi-Environment**: Automatic dev/prod deployment based on branch
- **Security**: Trivy vulnerability scanning, ECR integration

## ⚠️ CRITICAL DEPLOYMENT WARNINGS

### Docker Build Requirements
1. **Architecture Compatibility**: Build for `linux/amd64` for AWS EKS
   ```bash
   docker buildx build --platform linux/amd64 -f app/Dockerfile -t $REGISTRY/mcp-server-fastapi:$TAG ./app
   ```

2. **Security**: Uses non-root user and minimal base image
3. **Port Configuration**: Exposes port 8080 (not 8000)

### FastMCP Configuration
1. **Transport**: Uses HTTP transport (not stdio) for containerized deployment
2. **Health Endpoints**: Implements `/health` and `/ready` for Kubernetes probes
3. **Environment**: Configurable HOST and PORT via environment variables

### AWS EKS Integration
1. **ECR Repository**: Uses us-east-1 region (matching langgraph cluster)
2. **Service Type**: LoadBalancer for external access (configurable to ClusterIP for internal)
3. **Security Context**: Enabled by default with non-root user

## 📋 Prerequisites

- **AWS EKS Cluster**: Running cluster (same as langgraph-kafka deployment)
- **kubectl**: Configured for your EKS cluster
- **Helm 3.x**: For Kubernetes deployments
- **Docker with Buildx**: For multi-platform builds
- **AWS CLI**: Configured with appropriate permissions

### Required AWS Permissions
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
                "ecr:PutImage",
                "ecr:InitiateLayerUpload",
                "ecr:UploadLayerPart",
                "ecr:CompleteLayerUpload"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "eks:DescribeCluster",
                "eks:ListClusters"
            ],
            "Resource": "*"
        }
    ]
}
```

## 🚀 Step-by-Step Deployment

### 1. Environment Setup

```bash
# Set environment variables (replace with your values)
export REGISTRY="245230032478.dkr.ecr.us-east-2.amazonaws.com"
export REPOSITORY="mcp-server-fastapi"
export TAG="v1.0.0"
export CLUSTER_NAME="my-small-cluster"

# Configure AWS and kubectl
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin $REGISTRY
aws eks update-kubeconfig --region us-east-2 --name $CLUSTER_NAME
```

### 2. Build and Push Docker Image

```bash
# Build for the correct architecture (AWS EKS uses x86_64)
make build TAG=$TAG

# Push to ECR
make push TAG=$TAG

# Or combine both steps
make build-and-push TAG=$TAG
```

### 3. Deploy to Development Environment

```bash
# Deploy to development namespace
make deploy-dev TAG=$TAG

# Verify deployment
make status

# View logs
make logs

# Test the service
make port-forward
# In another terminal:
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

### 4. Deploy to Production Environment

```bash
# Deploy to production (requires specific tag, not 'latest')
make deploy-prod TAG=$TAG

# Verify production deployment
kubectl get pods -n mcp-server
kubectl get svc -n mcp-server
```

## 🔧 Configuration Options

### Environment Variables
- `HOST`: Server host (default: "0.0.0.0")
- `PORT`: Server port (default: 8080)
- `LOG_LEVEL`: Logging level (INFO for prod, DEBUG for dev)

### Helm Values Configuration

#### Development (`chart/values-dev.yaml`)
```yaml
service:
  type: ClusterIP  # Internal access only
resources:
  limits:
    memory: "256Mi"
    cpu: "200m"
app:
  logLevel: "DEBUG"
```

#### Production (`chart/values.yaml`)
```yaml
service:
  type: LoadBalancer  # External access via ELB
resources:
  limits:
    memory: "512Mi"
    cpu: "500m"
securityContext:
  enabled: true
```

## 🧪 Testing and Verification

### Local Testing
```bash
# Test Docker build locally
make test-build

# Test deployed service
make test-health
```

### Health Check Endpoints
```bash
# Health check (liveness probe)
curl http://your-service/health
# Response: "OK"

# Readiness check (readiness probe)  
curl http://your-service/ready
# Response: "READY"
```

### MCP Tools Testing
```bash
# Example MCP tool calls (requires MCP client)
curl -X POST http://your-service/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/call", "params": {"name": "add", "arguments": {"a": 5, "b": 3}}}'
```

## 🛠️ Troubleshooting Common Issues

### 1. Image Pull Errors
```bash
# Verify ECR authentication
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin $REGISTRY

# Check image exists
aws ecr describe-images --repository-name mcp-server-fastapi --region us-east-2
```

### 2. Pod Startup Failures
```bash
# Check pod logs
kubectl logs -f deployment/mcp-server-dev -n mcp-server-dev

# Check pod events
kubectl describe pod -l app.kubernetes.io/name=mcp-server -n mcp-server-dev
```

### 3. Health Check Failures
- Verify port 8080 is exposed and the application is listening
- Check if health endpoints `/health` and `/ready` return 200 status
- Verify security context isn't blocking access

### 4. Service Access Issues
```bash
# For LoadBalancer service, get external IP
kubectl get svc -n mcp-server

# For ClusterIP, use port-forwarding
kubectl port-forward -n mcp-server-dev svc/mcp-server-dev 8080:80
```

## 🔒 Security Considerations

### Container Security
- **Non-root user**: Runs as user ID 1000
- **Read-only filesystem**: Where possible (app requires write access)
- **Minimal base image**: python:3.11-slim
- **No privileged escalation**: Security context prevents privilege escalation

### Kubernetes Security
- **Security context**: Enabled by default in production
- **Resource limits**: Prevents resource exhaustion
- **Network policies**: Consider implementing for production
- **Secrets management**: Use Kubernetes secrets for sensitive data

### Monitoring and Observability
- **Health checks**: Comprehensive liveness, readiness, and startup probes
- **Logging**: Structured logging with configurable levels
- **Metrics**: Ready for Prometheus integration (add metrics endpoint if needed)

## 📊 Production Recommendations

### Scaling
```yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
```

### High Availability
```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchExpressions:
          - key: app.kubernetes.io/name
            operator: In
            values:
            - mcp-server
        topologyKey: kubernetes.io/hostname
```

### Resource Management
```yaml
resources:
  limits:
    memory: "1Gi"
    cpu: "1"
  requests:
    memory: "512Mi"
    cpu: "500m"
```

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow
- **Build**: Multi-platform Docker build with caching
- **Security**: Trivy vulnerability scanning
- **Deploy**: Environment-specific deployment (dev/prod)
- **Verification**: Post-deployment health checks

### Branch Strategy
- `develop` → Automatic deployment to development environment
- `main` → Automatic deployment to production environment
- Pull requests → Build and security scan only

## 📚 Quick Commands Reference

```bash
# Development workflow
make build TAG=dev
make deploy-dev TAG=dev
make port-forward

# Production workflow  
make build TAG=v1.0.0
make push TAG=v1.0.0
make deploy-prod TAG=v1.0.0

# Monitoring
make status
make logs

# Cleanup
make clean-dev
make clean-prod

# Testing
make test-build
make test-health

# Help
make help
```

## 🆘 Support and Maintenance

### Regular Maintenance Tasks
1. **Update dependencies**: Regularly update Python packages and base images
2. **Security patches**: Monitor and apply security updates
3. **Resource monitoring**: Monitor CPU/memory usage and adjust limits
4. **Log monitoring**: Set up log aggregation and alerting

### Disaster Recovery
1. **Backup**: Helm chart configurations and secrets
2. **Recovery**: Use `helm rollback` for quick rollbacks
3. **Monitoring**: Set up alerts for service availability

### Contact Information
- **Repository**: `mcp_server_fastapi`
- **Namespace**: `mcp-server` (prod), `mcp-server-dev` (dev)
- **Monitoring**: Check AWS CloudWatch for EKS cluster metrics

---

This deployment guide provides a robust, production-ready deployment strategy based on proven patterns from the langgraph-kafka-k8s project, ensuring reliable operation in your AWS EKS environment.