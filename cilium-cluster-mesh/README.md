# Cilium ClusterMesh

This repository demonstrates connecting two Kubernetes clusters using **Cilium ClusterMesh** and applying cross-cluster network policies. It also includes sample Nginx deployments to test connectivity across clusters.

## Prerequisites

* Two Kubernetes clusters (e.g., `cluster01` and `cluster02`)
* **Cilium** installed in both clusters
* **ClusterMesh** enabled for cross-cluster connectivity
* Access to a Docker registry hosting `nginx:1.20` image 

---

## Cluster Setup

1. Install Cilium on both clusters:

```bash
# On cluster01
cilium install --set cluster.name=$CLUSTER1 --set cluster.id=1 --context $CLUSTER1

# On cluster02
cilium install --set cluster.name=$CLUSTER2 --set cluster.id=2 --context $CLUSTER2
```

2. Enable **ClusterMesh**:

```bash
# Join cluster01 and cluster02
cilium clustermesh enable --context $CLUSTER2 --service-type NodePort
cilium clustermesh enable --context $CLUSTER1 --service-type NodePort
cilium clustermesh connect --namespace cilium --context $CLUSTER1 --destination-context $CLUSTER2
```

> After this, services annotated with `service.cilium.io/global: "true"` will be reachable across clusters.

---

## Deploying Applications

### Cluster01 Deployment

File: `cluster01-dep.yaml`

* Deploys a single Nginx pod labeled `app: nginx-cluster01`
* Sets environment variables:

  * `CLUSTER_NAME=cluster01`
  * `POD_IP` of the pod
* Creates a Service annotated with `service.cilium.io/global: "true"` for cross-cluster access

```bash
kubectl apply -f cluster01-dep.yaml --context cluster01
```

### Cluster02 Deployment

File: `cluster02-dep.yaml`

* Similar to Cluster01, but pod labeled `app: nginx-cluster02`
* Environment variable `CLUSTER_NAME=cluster02`
* Global Service annotation enables ClusterMesh access

```bash
kubectl apply -f cluster02-dep.yaml --context cluster02
```

---

## Cilium Network Policies

These policies control which pods can communicate across clusters.

### `policy01-cluster01.yaml` and `policy01-cluster02.yaml`

* Allow Nginx pods in both clusters to communicate on TCP port 80
* `io.cilium.k8s.policy.cluster` label ensures traffic is allowed only from specific clusters

```text
nginx-cluster01 <---> nginx-cluster02
```

### `policy02-cluster01.yaml`

* More specific policy allowing:

  * Pods from `default` namespace in cluster01
  * Pods from `ali` namespace in cluster02
* Useful for limiting cross-namespace traffic

### `policy03-cluster01.yaml`

* Cluster-wide network policy (`CiliumClusterwideNetworkPolicy`)
* Allows frontend pods in cluster02 to communicate with backend pods in cluster01
* Controls both ingress and egress for backend pods

---

## Testing Connectivity

1. Check pods in both clusters:

```bash
kubectl get pods -A --context cluster01
kubectl get pods -A --context cluster02
```

2. Curl Nginx from cluster01 to cluster02:

```bash
# Exec into a pod in cluster01
kubectl exec -it <pod-name> --context cluster01 -- curl http://nginx.default.svc.cluster.local
```

* You should see the `Cluster` and `PodIP` values from cluster02 pod.

3. Verify Cilium policies:

```bash
cilium policy get --context cluster01
cilium clustermesh status
```

---