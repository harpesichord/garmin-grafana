# Kubernetes Deployment
Helm chart for deploying garmin-grafana.

## Prerequisites
Use `./templates/example-secret.yaml` to provide secrets (apply your credentials directly or use any secret operator separately).
Default setup uses emptyDir volumes for easy testing. Enable persistence for production use.

## Quick Start

### Local Testing (minikube)

# If missing tools, install them:
# - minikube: https://minikube.sigs.k8s.io/docs/start/
# - helm: https://helm.sh/docs/intro/install/

```bash
# One command setup - will open Grafana in browser in ~2 minutes and show password in terminal
make test-minikube
# Cleanup when done  
make clean-minikube
# Get Grafana password
make get-grafana-password
```

### Install to any K8s cluster
```bash
helm dependency build
helm install garmin-grafana . -n garmin-grafana --create-namespace
# With custom values
helm install garmin-grafana . -f your-values.yaml
```

### Fetcher-only deployment (no dashboard)
```bash
# Deploy data fetcher + influx without Grafana dashboard
helm install garmin-grafana . --set grafana.enabled=false -n garmin-grafana --create-namespace
```

### Get raw manifests
```bash
helm template garmin-grafana . -n garmin-grafana  > garmin-grafana.yaml
```
