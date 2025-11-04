# Kubernetes mTLS Proxy & API Aggregation Extension

## Table of contents

* [Overview](#overview)
* [Architecture & dataflow](#architecture--dataflow)
* [Component: custom-api Flask server (aggregation extension)](#component-custom-api-flask-server-aggregation-extension)
* [Component: kubectl → proxy (mTLS + impersonation)](#component-kubectl-→-proxy-mtls--impersonation)
* [Kubernetes resources explained](#kubernetes-resources-explained)
* [TLS / certificate generation & cluster CA](#tls--certificate-generation--cluster-ca)
* [Security considerations & recommendations](#security-considerations--recommendations)
* [Troubleshooting & diagnostics](#troubleshooting--diagnostics)
* [Quick reference commands](#quick-reference-commands)
* [Links & references](#links--references)

---

## Overview

You built a Kubernetes API aggregation extension (a small HTTPS service that implements `custom.api.local/v1`) and registered it via an APIService. You also created an mTLS proxy used from a machine running `kubectl`. The proxy authenticates the human operator using client TLS, extracts CN/O from the client certificate, and impersonates that user to the kube-apiserver using `Impersonate-User` and `Impersonate-Group` headers. The aggregation service uses the Python client to create SubjectAccessReview (SAR) objects to decide whether the requester can list namespaces, optionally filtering by team label.

**Design enables:**

* Centralized, custom namespace-listing logic.
* Request-level auditability via impersonation.
* Extension relies on kube-apiserver for authorization via SAR.

---

## Architecture & dataflow

**High-level flow:**

1. `kubectl → proxy → kube-apiserver → APIService → custom-api (Flask app)`
2. Example: GET `/api/v1/namespaces?limit=500` is rewritten to `/apis/custom.api.local/v1/mynamespace` by the proxy.
3. kube-apiserver forwards the request to the extension.
4. Extension calls in-cluster Python client to create a SAR for the original user.

**Security points:**

* Proxy → kube-apiserver uses mTLS with a service account token.
* Proxy authenticates humans using client certs (CN/O).
* Proxy requires RBAC impersonation permissions.
* Extension has service account with `create` on SAR and `list` on namespaces.

---

## Component: custom-api Flask server (aggregation extension)

### Purpose

Expose `apis/custom.api.local/v1` resources:

* `GET /apis/custom.api.local/v1` — discovery (returns APIResourceList with `whoami` and `mynamespace`).
* `GET /apis/custom.api.local/v1/whoami` — returns `X-Remote-User` and `X-Remote-Group` headers as a fake NamespaceList.
* `GET /apis/custom.api.local/v1/mynamespace` — main endpoint enforcing SAR and optional team label filtering.

### Init & Kubernetes client

`init_k8s_client()`:

* Tries `config.load_incluster_config()` first.
* Falls back to `KUBECONFIG` env var or `~/.kube/config`.
* Returns `(v1, auth_v1)`: `v1=CoreV1Api()`, `auth_v1=AuthorizationV1Api()`.

### Request logging

* `@app.before_request` logs requests but suppresses `/apis` and `/openapi` paths.

### Whoami endpoint

* Reads `X-Remote-User` and `X-Remote-Group` headers.
* Returns Kubernetes-like NamespaceList JSON for debugging.

### Mynamespace endpoint — step-by-step

1. **Read headers:**

   * `X-Remote-User` → CN from proxy.

2. **SAR:**

   * Constructs `V1SubjectAccessReview` with user, groups, resource_attributes (verb=`list`, resource=`namespaces`).
   * Calls `auth_v1.create_subject_access_review(body=sar)`.
   * Checks `sar_resp.status.allowed`.
3. **Namespace listing:**

   * `v1.list_namespace()`.
   * If `user_can_list=False`, filters items with `NAMESPACE_TEAM_LABEL` in user's groups.
4. **Error handling:**

   * Returns Kubernetes-style Status object with `Failure` if SAR or list fails.

**Design rationale:** avoids reimplementing RBAC, delegates authority to kube-apiserver.

---

## Component: kubectl → proxy (mTLS + impersonation)

### Purpose

* Runs on operator machine.
* Accepts mTLS client certs, extracts CN/O, and sets impersonation headers.
* Rewrites GET `/api/v1/namespaces?limit=500` → `/apis/custom.api.local/v1/mynamespace`.
* Forwards other requests with proxy service account token.

### Important code behaviours

* **mTLS:** SSL context with `CERT_REQUIRED`, loads CA (`context.load_verify_locations(CA_CERT)`).
* **Client cert extraction:** `peer_cert = request.environ['SSL_CLIENT_CERT']` → parse CN/O.
* **Path rewrite:** only namespace listing goes through aggregation.
* **Forwarding:** includes `Impersonate-User`, optional `Impersonate-Group`, `Authorization: Bearer <TOKEN>`, `verify=CA_CERT`.
* **Interactive paths:** `exec`, `attach`, `portforward` redirected directly (307).

---

## Kubernetes resources explained

* **ServiceAccount + Deployment:** `custom-api-local-sa` mounted by `custom-api-local-dep`, TLS secret mounted at `/tls`.
* **Secret:** `custom-api-tls` from server cert/key signed by cluster CA.
* **Service:** `custom-api-local-svc` exposes Deployment port 8443.
* **APIService:**

  * `metadata.name=v1.custom.api.local`
  * `spec.service` points to `custom-api-local-svc`
  * `spec.group=custom.api.local`, `version=v1`
  * `insecureSkipTLSVerify=true` (testing, safer: use `caBundle`).
* **RBAC:**

  * `custom-api-local-namespace-reader` (list namespaces)
  * `subjectaccessreview-runner` (create SAR)
  * Human users: `custom-api-local-reader`
  * Proxy must have impersonation verbs for users/groups.

---

## TLS / certificate generation & cluster CA

```bash
openssl genrsa -out tls.key 2048
openssl req -new -key tls.key -out tls.csr -config tls.cnf
openssl x509 -req -in tls.csr   -CA /etc/kubernetes/pki/front-proxy-ca.crt   -CAkey /etc/kubernetes/pki/front-proxy-ca.key   -CAcreateserial   -out tls.crt -days 365   -extensions req_ext -extfile tls.conf
kubectl create secret tls custom-api-tls --cert=tls.crt --key=tls.key -n custom-api-local-ns
kubectl create secret generic proxy-ca-secret --from-file=ca.crt=/etc/kubernetes/pki/front-proxy-ca.crt -n custom-api-local-ns
```
## Example tls.conf
```bash
[ req ]
default_bits       = 2048
prompt             = no
default_md         = sha256
req_extensions     = req_ext
distinguished_name = dn

[ dn ]
C  = FR
ST = Paris
L  = Paris
O  = CustomAPI
CN = custom-api-local-svc.custom-api-local-ns.svc

[ req_ext ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = custom-api-local-svc
DNS.2 = custom-api-local-svc.custom-api-local-ns
DNS.3 = custom-api-local-svc.custom-api-local-ns.svc
DNS.4 = custom-api-local-svc.custom-api-local-ns.svc.cluster.local
DNS.5 = localhost
IP.1  = 10.107.68.159
```

* Recommended: use `caBundle` in APIService for secure TLS verification.

---

## Security considerations & recommendations

* Avoid `insecureSkipTLSVerify=true` in production and use Base64 of /etc/kubernetes/pki/front-proxy-ca.crt in caBundle
* Ensure proxy service account has impersonation RBAC.
* Support multiple `Impersonate-Group` headers if cert has multiple groups.
* Enable apiserver audit logs.
* Define certificate issuance/revocation for proxy.
* Redirect interactive paths directly to apiserver.

---

## Troubleshooting & diagnostics

* **APIService not Available:**

```bash
kubectl get apiservices v1.custom.api.local -o yaml
kubectl describe apiservice v1.custom.api.local
```

* **Proxy missing client cert:** ensure TLS fronting passes `SSL_CLIENT_CERT`.
* **Impersonation errors:** check proxy service account RBAC.
* **SAR false negatives:** verify RBAC roles for user.
* **TLS DNS mismatch:** CN/SANs must include service FQDN.

---

## Quick reference commands

* **View SANs in cert:**

```bash
openssl x509 -in tls.crt -noout -text | grep -A2 "Subject Alternative Name"
```

* **Check APIService status:**

```bash
kubectl get apiservices
kubectl describe apiservice v1.custom.api.local
```

* **Debug proxy:**

```bash
openssl s_client -connect proxy-host:8443 -cert client.crt -key client.key -CAfile ca.crt
```

* **Example secure APIService:**

```yaml
apiVersion: apiregistration.k8s.io/v1
kind: APIService
metadata:
  name: v1.custom.api.local
spec:
  service:
    name: custom-api-local-svc
    namespace: custom-api-local-ns
  group: custom.api.local
  version: v1
  insecureSkipTLSVerify: false
  caBundle: |-
    -----BEGIN CERTIFICATE-----
    ...
    -----END CERTIFICATE-----
  groupPriorityMinimum: 2000
  versionPriority: 10
```

---

## Links & references

* [Kubernetes API aggregation layer](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/apiserver-aggregation/)
* [Configure aggregation layer](https://kubernetes.io/docs/tasks/extend-kubernetes/configure-aggregation-layer/)
* [SubjectAccessReview API](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.27/#subjectaccessreview-v1-authorization-k8s-io)
* [Authentication / impersonation guidance](https://kubernetes.io/docs/reference/access-authn-authz/authentication/)

