# 🚀 Calico → Cilium CNI Migration (Zero‑Downtime Rolling)

This document describes a **production‑style migration** of a live Kubernetes cluster  
from **Calico CNI** to **Cilium CNI** using a rolling, node‑by‑node approach with no cluster downtime.

The migration was performed by installing Cilium in *secondary mode*, gradually moving nodes,  
then promoting Cilium to primary and removing Calico.

---

# 📦 Cluster Baseline

| Component | Value |
|-----------|------|
Existing CNI | Calico (VXLAN) |
New CNI | Cilium (VXLAN) |
Old Pod CIDR | 10.244.0.0/16 |
New Pod CIDR | 10.245.0.0/16 |
Policy Mode During Migration | Disabled |
Routing Mode | Tunnel |
Encapsulation Port | 8473 |
Migration Strategy | Rolling per‑node |

---

# 🧭 Migration Strategy

The migration followed these phases:

```
Calico primary
     ↓
Cilium installed (secondary)
     ↓
Node‑by‑node takeover
     ↓
All nodes on Cilium
     ↓
Cilium primary
     ↓
Calico removed + cleanup
```

Key design goals:

- No cluster downtime
- No workload restarts cluster‑wide
- Mixed CNI nodes temporarily allowed
- Deterministic cutover per node

---

# ⚙️ Install Cilium (Secondary Mode)

Add Helm repo:

```bash
helm repo add cilium https://helm.cilium.io/
```

Install using migration values:

```bash
cilium install --chart-directory ./install/kubernetes/cilium --values values-migration.yaml --dry-run-helm-values > values-initial.yaml

helm repo add cilium https://helm.cilium.io/

helm install cilium cilium/cilium --namespace kube-system --values values-initial.yaml
```

### Migration‑specific settings

- Custom CNI config disabled
- Policy enforcement disabled
- Legacy host routing enabled
- Separate PodCIDR pool
- Different VXLAN port from Calico

---

# 🧩 Per‑Node Migration Procedure

Select a worker node first (not control‑plane).

```bash
NODE=<node-name>

kubectl cordon $NODE
kubectl drain $NODE --ignore-daemonsets
```

Apply migration label:

```bash
kubectl label node $NODE   io.cilium.migration/cilium-default=true   --overwrite
```

Restart Cilium on the node:

```bash
kubectl -n kube-system delete pod   -l k8s-app=cilium   --field-selector spec.nodeName=$NODE
```

Reboot node:

```bash
reboot
```

Re‑enable scheduling:

```bash
kubectl uncordon $NODE
```

Repeat for each node.

---

# ✅ Validation Checklist

Verify node networking:

```bash
cilium status --wait
kubectl get nodes -o wide
```

Run test pod on migrated node:

```bash
kubectl run netshoot   --rm -it   --image=ghcr.io/nicolaka/netshoot   --overrides='{"spec":{"nodeName":"'$NODE'"}}'   -- bash
```

Checks:

- Pod IP from new CIDR (10.245.x.x)
- Kubernetes API reachable
- Cross‑node pod ping works
- DNS resolution works

---

# 🔄 Promote Cilium to Primary

After all nodes migrated:

```bash
cilium install --chart-directory ./install/kubernetes/cilium --values values-initial.yaml --dry-run-helm-values \
  --set operator.unmanagedPodWatcher.restart=true --set cni.customConf=false \
  --set policyEnforcementMode=default \
  --set bpf.hostLegacyRouting=false > values-final.yaml

helm upgrade cilium cilium/cilium   -n kube-system   -f values-final.yaml

```

Restart daemonset:

```bash
kubectl -n kube-system rollout restart ds/cilium
cilium status --wait
```

Remove migration config:

```bash
kubectl delete ciliumnodeconfig -n kube-system cilium-default
```

---

# 🧹 Calico Cleanup

After Calico removal, residual iptables chains remained.

Cleanup per node:

```bash
export NODE=<node>
./calico-cleanup.sh pod
```

This flushes:

- cali-* chains
- nat/raw/mangle/filter rules
- bird routes

---

# 🗑 Remove Calico CRDs

```bash
kubectl get crd |grep calico|cut -d' ' -f1 | xargs -I{} -t kubectl delete crd {}
```

---


# 📁 Related Files

```
values-migration.yaml
values-final.yaml
ciliumnodeconfig.yaml
calico-cleanup.sh
calico-cleanup-pod.yaml
``‍‍`