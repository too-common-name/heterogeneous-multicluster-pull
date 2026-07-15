# ACM Pull Model with ArgoCD Agent — Heterogeneous Multi-Tenant Validation

## Use Case

Validate the **ACM advanced pull model (ArgoCD Agent)** in a scenario where:

- The **hub cluster** cannot reach the spoke clusters (hub → spoke is **blocked**)
- The **spoke clusters** can reach the hub (spoke → hub is **allowed**)
- The organization must support a **heterogeneous fleet** (OCP and non-OCP clusters).
  The heterogeneous requirement makes the **advanced pull model** mandatory — the
  base pull model only supports OCP clusters. Push model is not an option either,
  since the hub cannot reach the spokes.
- The organization follows a **layered structure**: a **foundation team** manages
  cross-cutting concerns (operators, security policies, baselines) on all clusters,
  while **business unit teams** (mortgage, insurance) independently manage their own
  applications and operators on a scoped subset of clusters.

This forces a **pure pull-based** architecture where all synchronization is initiated from the spoke side.

## Architecture

![Architecture Diagram](diagrams/out/architecture.png)

> Regenerate with: `source .venv/bin/activate && python diagrams/architecture.py`

## Network Constraint

| Source | Destination | Allowed |
|--------|-------------|---------|
| insolvency-check-sno → Hub | API, ArgoCD Agent channel | Yes |
| parasol-sno → Hub | API, ArgoCD Agent channel | Yes |
| kind-local → Hub | API, ArgoCD Agent channel | Yes |
| Hub → insolvency-check-sno | Any | **No** |
| Hub → parasol-sno | Any | **No** |
| Hub → kind-local | Any | **No** (no route from cloud to local PC) |

This constraint makes the **push model impossible** and mandates:
- ArgoCD Agent on each spoke pulling application definitions from the hub
- ACM registration agent (klusterlet) initiating connections outbound from the spoke

## Heterogeneous Environment Emulation

The fleet includes both OCP and non-OCP clusters, distinguished by **labels**:

| Cluster | Platform | Label | Type |
|---------|----------|-------|------|
| insolvency-check-sno | OCP (SNO on AWS) | `platform=ocp` | Real OCP cluster |
| parasol-sno | OCP (SNO on AWS) | `platform=ocp` | Real OCP cluster |
| kind-local | Kind (local PC) | `platform=generic` | **Genuinely non-OCP** — proves Helm portability |

### Operator Delivery: Helm Everywhere

All operators are deployed via **Helm charts** on every cluster, regardless of platform label. This provides:

- **Portability** — the same delivery method works on OCP and non-OCP clusters
- **No OLM dependency** — Helm charts deploy operators directly (Deployment, RBAC, CRDs)
- **Simplicity** — one pipeline, one packaging format, one set of ApplicationSets
- **No OperatorPolicy** — ACM OperatorPolicy is not used; governance policies handle compliance only

The `platform` label remains useful for conditional configuration (e.g., Route vs Ingress, SecurityContextConstraints vs PodSecurityStandards) but does **not** affect the operator delivery mechanism.

## Organizational Model

### Foundation Team

- **Scope**: all clusters in the fleet
- **ManagedClusterSet**: `global` (built-in — automatically contains every ManagedCluster)
- **Responsibilities**:
  - Foundation operators (logging, monitoring, cert-manager, service mesh, etc.)
  - Cluster-wide policies (security baselines, network policies, image policies)
  - Foundation namespaces are **protected** — teams cannot override them

### Business Unit Teams (Mortgage, Insurance)

- **Scope**: only their assigned clusters
- **ManagedClusterSet**: `mortgage` (insolvency-check-sno, kind-local), `insurance` (parasol-sno)
- **Responsibilities**:
  - Application-specific operators and workloads
  - Team-scoped policies within their namespaces
- **Constraints**:
  - Cannot create policies that target foundation-managed namespaces
  - Cannot modify or disable foundation operators
  - Cannot create policies with higher priority than foundation policies

## Technology Stack

| Component | Role |
|-----------|------|
| Red Hat ACM 2.17 | Hub multi-cluster management |
| ArgoCD Agent | Pull-based GitOps on spokes |
| ACM Governance (Policies) | Compliance & remediation (no OperatorPolicy) |
| Helm 3 | **Universal** operator & workload delivery on all clusters |
| Gatekeeper / OPA | Guardrails on team policy creation |
| Placement API | Cluster selection with label-based routing |
| ManagedClusterSets | Team isolation & RBAC boundaries |

