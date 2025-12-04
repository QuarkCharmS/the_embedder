# RAG System Helm Chart

Production-ready Helm chart for deploying a complete RAG (Retrieval Augmented Generation) system on Kubernetes.

## Architecture

This chart deploys a complete RAG system consisting of:

- **OpenWebUI**: Web interface for user interaction
- **Pipelines**: Backend processing service (automatically configured)
- **RAG Connector**: Custom service connecting to vector database
- **Qdrant**: Vector database with StatefulSet for high availability

## Prerequisites

- Kubernetes 1.19+
- Helm 3.8+
- PV provisioner support in the underlying infrastructure (for persistence)
- Storage class that supports ReadWriteOnce volumes

## Chart Dependencies

This chart uses official Helm charts as dependencies:

- [Qdrant](https://qdrant.github.io/qdrant-helm) v0.8.15
- [OpenWebUI](https://helm.openwebui.com) v3.1.6

## Installation

### 1. Update Dependencies

First, download the dependency charts:

```bash
cd helm-chart
helm dependency update
```

This will create a `charts/` directory with the official Qdrant and OpenWebUI charts.

### 2. Review Configuration

Edit `values.yaml` to customize your deployment:

```yaml
# Example: Enable ingress for external access
open-webui:
  ingress:
    enabled: true
    host: rag.yourcompany.com

# Example: Scale Qdrant for HA
qdrant:
  replicaCount: 3
  config:
    cluster:
      enabled: true
```

### 3. Install the Chart

```bash
# Install with default values
helm install my-rag-system ./helm-chart

# Install with custom values
helm install my-rag-system ./helm-chart -f custom-values.yaml

# Install in a specific namespace
helm install my-rag-system ./helm-chart -n rag-system --create-namespace
```

### 4. Verify Installation

```bash
# Check all pods are running
kubectl get pods -l app.kubernetes.io/instance=my-rag-system

# View services
kubectl get svc -l app.kubernetes.io/instance=my-rag-system

# Check persistent volumes
kubectl get pvc
```

## Accessing the Application

### OpenWebUI (Web Interface)

**Option 1: Port-forward (Development)**
```bash
kubectl port-forward svc/my-rag-system-open-webui 3000:80
# Access at: http://localhost:3000
```

**Option 2: Ingress (Production)**
```yaml
open-webui:
  ingress:
    enabled: true
    host: rag.yourcompany.com
    tls: true
```

### Qdrant Dashboard

```bash
kubectl port-forward svc/my-rag-system-qdrant 6333:6333
# Access at: http://localhost:6333/dashboard
```

## Configuration

### RAG Connector (Custom Service)

The RAG Connector is the only service managed directly by this chart:

```yaml
ragConnector:
  enabled: true
  replicaCount: 3  # Scale horizontally (stateless)

  image:
    repository: letpoquark/rag-connector
    tag: v1.0

  env:
    qdrantUrl: ""  # Auto-configured
    logLevel: "INFO"

  resources:
    limits:
      cpu: 1000m
      memory: 2Gi
```

### Qdrant Configuration

```yaml
qdrant:
  # Single instance (development)
  replicaCount: 1
  config:
    cluster:
      enabled: false

  # HA Cluster (production)
  replicaCount: 3
  config:
    cluster:
      enabled: true

  persistence:
    size: 50Gi
    storageClass: "fast-ssd"
```

### OpenWebUI & Pipelines

```yaml
open-webui:
  pipelines:
    enabled: true  # Automatically installs Pipelines
    extraEnvVars:
      - name: PIPELINES_API_KEY
        value: "your-secure-key"

  ollama:
    enabled: false  # Disable if using external LLM

  persistence:
    size: 10Gi
```

## Production Recommendations

### High Availability Setup

```yaml
# values-production.yaml
qdrant:
  replicaCount: 3
  config:
    cluster:
      enabled: true
  persistence:
    size: 100Gi
    storageClass: "premium-ssd"
  resources:
    limits:
      cpu: 4000m
      memory: 8Gi

ragConnector:
  replicaCount: 5
  resources:
    limits:
      cpu: 2000m
      memory: 4Gi

open-webui:
  replicaCount: 3  # Requires ReadWriteMany storage
  persistence:
    accessMode: ReadWriteMany
    storageClass: "nfs-storage"
  ingress:
    enabled: true
    className: "nginx"
    host: "rag.company.com"
    tls: true
```

### Resource-Constrained Environment

```yaml
# values-minimal.yaml
qdrant:
  replicaCount: 1
  persistence:
    size: 5Gi
  resources:
    limits:
      cpu: 1000m
      memory: 2Gi

ragConnector:
  replicaCount: 1
  resources:
    limits:
      cpu: 500m
      memory: 1Gi

open-webui:
  replicaCount: 1
  persistence:
    size: 2Gi
  resources:
    limits:
      cpu: 500m
      memory: 1Gi
```

## Upgrading

```bash
# Update dependencies
helm dependency update

# Upgrade the release
helm upgrade my-rag-system ./helm-chart

# Upgrade with new values
helm upgrade my-rag-system ./helm-chart -f new-values.yaml

# Rollback if needed
helm rollback my-rag-system
```

## Uninstalling

```bash
# Uninstall the release
helm uninstall my-rag-system

# Delete PVCs (they persist after uninstall)
kubectl delete pvc -l app.kubernetes.io/instance=my-rag-system
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name>

# View logs
kubectl logs <pod-name>

# Check events
kubectl get events --sort-by=.metadata.creationTimestamp
```

### Storage Issues

```bash
# Check PVC status
kubectl get pvc

# Describe PVC for details
kubectl describe pvc <pvc-name>

# Check available storage classes
kubectl get storageclass
```

### Qdrant Clustering Issues

```bash
# Check Qdrant cluster status
kubectl exec -it my-rag-system-qdrant-0 -- curl localhost:6333/cluster

# View Qdrant logs
kubectl logs -l app.kubernetes.io/name=qdrant --tail=100
```

### RAG Connector Connection Issues

```bash
# Check RAG Connector logs
kubectl logs -l app.kubernetes.io/component=rag-connector --tail=100

# Verify Qdrant service is accessible
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl http://my-rag-system-qdrant:6333/collections
```

## Chart Structure

```
helm-chart/
├── Chart.yaml                              # Chart metadata & dependencies
├── values.yaml                             # Default configuration
├── charts/                                 # Downloaded dependencies
│   ├── qdrant-0.8.15.tgz
│   └── open-webui-3.1.6.tgz
└── templates/
    ├── _helpers.tpl                       # Template helpers
    ├── NOTES.txt                          # Post-install notes
    ├── rag-connector-deployment.yaml      # RAG Connector deployment
    ├── rag-connector-service.yaml         # RAG Connector service
    ├── rag-connector-configmap.yaml       # RAG Connector config
    └── rag-connector-ingress.yaml         # RAG Connector ingress (optional)
```

## Values Reference

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ragConnector.enabled` | Enable RAG Connector | `true` |
| `ragConnector.replicaCount` | Number of replicas | `1` |
| `ragConnector.image.repository` | Image repository | `letpoquark/rag-connector` |
| `ragConnector.image.tag` | Image tag | `v1.0` |
| `ragConnector.env.logLevel` | Log level | `INFO` |
| `qdrant.enabled` | Enable Qdrant | `true` |
| `qdrant.replicaCount` | Number of Qdrant replicas | `1` |
| `qdrant.config.cluster.enabled` | Enable Qdrant clustering | `false` |
| `qdrant.persistence.size` | Qdrant storage size | `10Gi` |
| `open-webui.enabled` | Enable OpenWebUI | `true` |
| `open-webui.pipelines.enabled` | Enable Pipelines | `true` |
| `open-webui.ingress.enabled` | Enable ingress | `false` |

See `values.yaml` for complete configuration options.

## Contributing

For issues or contributions, please refer to the main project repository.

## License

See the main project LICENSE file.
