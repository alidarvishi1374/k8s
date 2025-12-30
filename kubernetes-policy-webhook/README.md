# Kubernetes CEL Admission Webhook

This project implements a **minimal custom Kubernetes Admission Webhook** that supports both **mutation** and **validation** of Kubernetes resources using **CEL (Common Expression Language)**.

The webhook is designed to be lightweight, flexible, and namespace-aware, allowing platform teams to define policy behavior through Kubernetes Custom Resources rather than hard-coding logic.

---

## Overview

Kubernetes Admission Webhooks are HTTP callbacks that intercept requests to the Kubernetes API server **before objects are persisted**. They are commonly used to enforce policies, apply defaults, or block invalid resources.

This project provides:

* **Mutating Admission Webhook**

  * Automatically modifies incoming resources (e.g. adds labels).
* **Validating Admission Webhook**

  * Evaluates CEL expressions to allow, warn, or deny requests.

Policies can be scoped at:

* **Cluster level**
* **Namespace level**

---

## High-Level Architecture

```text
Kubernetes API Server
        |
        v
Admission Webhook (Flask)
        |
        v
CEL Policy Evaluation
        |
        +--> Mutate resources
        +--> Validate requests
```

---

## TLS & Webhook Bootstrap

A Helm **subchart** is responsible for:

* Generating a CA and TLS certificates
* Creating a Kubernetes TLS Secret
* Registering:

  * `MutatingWebhookConfiguration`
  * `ValidatingWebhookConfiguration`

This bootstrap process runs **inside the cluster** and automatically configures the webhook to securely communicate with the API server.

---

## Installation

Install the webhook using Helm:

```bash
helm install policy-webhook -n policy-engine --create-namespace .
```

After installation, the Admission Webhook will start intercepting Kubernetes API requests according to the defined policies.

---

## Notes

* Requires Kubernetes `admission.k8s.io/v1`
* Designed for extensibility and platform-level policy enforcement
* Suitable as a foundation for custom policy engines
