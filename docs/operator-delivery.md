# Operator Delivery Strategy

This document explains how operators are installed across a heterogeneous fleet (OCP + non-OCP clusters) using ACM Policies and ArgoCD, and why the architecture is designed this way.

## 1. How OLM works on OpenShift

Operator Lifecycle Manager (OLM) is the OpenShift subsystem that manages operator installation, upgrades, and removal. It relies on five resources that form a pipeline:

```
CatalogSource → Subscription → InstallPlan → ClusterServiceVersion → Deployment
```

| Resource | Role |
|---|---|
| **CatalogSource** | A registry of available operators. Red Hat ships `redhat-operators`, `certified-operators`, and `community-operators` by default. Each catalog is a gRPC index of operator bundles. |
| **OperatorGroup** | Defines the target namespace scope for an operator. An operator can watch *all namespaces* (cluster-scoped), a *single namespace*, or a *set of namespaces*. Most Red Hat operators are cluster-scoped and require an OperatorGroup in their install namespace (e.g. `openshift-operators-redhat`). |
| **Subscription** | Declares intent: "I want operator X from catalog Y, tracking channel Z". OLM watches the Subscription and creates an InstallPlan whenever a new version appears on the channel. |
| **InstallPlan** | A concrete upgrade action: "install bundle version A.B.C". Can be `Automatic` (applied immediately) or `Manual` (requires admin approval). |
| **ClusterServiceVersion (CSV)** | The running operator descriptor. Created by the InstallPlan, it owns the operator Deployment, RBAC, CRDs, and API services. The CSV is the proof that the operator is installed and healthy. |

### OperatorGroup scoping

Most operators need exactly one OperatorGroup in their namespace. If no OperatorGroup exists, the Subscription stays pending. If multiple OperatorGroups exist, the operator errors out. Red Hat operators installed in `openshift-operators-redhat` (e.g. Loki, Tempo, Elasticsearch) share a single cluster-scoped OperatorGroup that OpenShift creates automatically.

### Channels and version pinning

Channels (`stable`, `stable-6.6`, `stable-5.9`, ...) group compatible versions. Each OCP cluster version has a `defaultChannel` that is compatible with its API level. Pinning a channel (`stable-6.6`) gives you tight control but risks failure on clusters where that channel doesn't exist. Omitting the channel lets OLM pick the `defaultChannel` per cluster — safer for heterogeneous fleets.

## 2. Why OperatorPolicy instead of raw YAML

On a single cluster you could `oc apply` a Subscription YAML and be done. At fleet scale, raw Subscription YAML creates several problems.

### The naive approach (raw Subscription YAML via ConfigurationPolicy)

```yaml
apiVersion: policy.open-cluster-management.io/v1
kind: ConfigurationPolicy
metadata:
  name: install-loki
spec:
  object-templates:
    - complianceType: musthave
      objectDefinition:
        apiVersion: operators.coreos.com/v1alpha1
        kind: Subscription
        metadata:
          name: loki-operator
          namespace: openshift-operators-redhat
        spec:
          channel: stable-6.6
          source: redhat-operators
          sourceNamespace: openshift-marketplace
          installPlanApproval: Automatic
```

This *works*, but:

| Problem | Impact |
|---|---|
| **No lifecycle awareness** | ConfigurationPolicy sees the Subscription as a generic object. If the operator fails to install (CatalogSource missing, InstallPlan rejected, CSV errored), the ConfigurationPolicy still reports `Compliant` because the Subscription object exists. |
| **Channel version mismatches** | If `stable-6.6` doesn't exist on an older OCP cluster, the Subscription stays pending. ConfigurationPolicy reports `Compliant` anyway — the YAML matches. |
| **No upgrade control** | You cannot inspect or approve InstallPlans. If `installPlanApproval: Manual`, no one approves the plan on the spoke. |
| **OperatorGroup management** | You must create a separate ConfigurationPolicy for the OperatorGroup and get the ordering right. |
| **No health signal** | There is no feedback on whether the CSV is actually running. |

### OperatorPolicy solves all of this

OperatorPolicy (`policy.open-cluster-management.io/v1beta1`) is an ACM-native resource designed specifically for operator lifecycle:

```yaml
apiVersion: policy.open-cluster-management.io/v1beta1
kind: OperatorPolicy
metadata:
  name: loki-operator-install
spec:
  remediationAction: enforce
  complianceType: musthave
  severity: medium
  subscription:
    name: loki-operator
    namespace: openshift-operators-redhat
    source: redhat-operators
    sourceNamespace: openshift-marketplace
    installPlanApproval: Automatic
```

What OperatorPolicy does that raw YAML cannot:

| Capability | How |
|---|---|
| **Auto-creates OperatorGroup** | If the target namespace has no OperatorGroup, OperatorPolicy creates one. No extra manifest needed. |
| **Tracks the full pipeline** | Reports compliance based on the *entire chain*: Subscription → InstallPlan → CSV → Deployment. A stuck InstallPlan = `NonCompliant`. |
| **Channel-safe** | Omit `channel` and OperatorPolicy uses the catalog's `defaultChannel` on each cluster. No version mismatch risk. |
| **Upgrade control** | With `installPlanApproval: Manual`, OperatorPolicy can auto-approve InstallPlans when it detects a new version (configurable). |
| **Health monitoring** | Reports the CSV phase. If the operator Deployment crashes or the CSV enters `Failed`, the policy goes `NonCompliant`. |
| **Idempotent removal** | Set `remediationAction: enforce` with `complianceType: mustnothave` and the operator is cleanly uninstalled (CSV, Subscription, InstallPlan, CRDs). |

**Bottom line**: OperatorPolicy replaces Subscription + OperatorGroup + monitoring logic with a single, audit-aware resource.

## 3. Operator installation is more than OperatorPolicy

Installing an operator is step one. Most operators require post-install configuration to be useful:

| Operator | Install (OperatorPolicy) | Configuration (ConfigurationPolicy) |
|---|---|---|
| **Loki** | `loki-operator` Subscription | `LokiStack` CR (storage backend, size, tenants) |
| **Tempo** | `tempo-operator` Subscription | `TempoStack` CR (storage backend, retention) |
| **Compliance Operator** | `compliance-operator` Subscription | `ScanSettingBinding`, `TailoredProfile` |
| **Gatekeeper** | `gatekeeper-operator` Subscription | `ConstraintTemplate`, `Constraint` objects |

The OperatorPolicy handles installation. Configuration is expressed as a separate Policy wrapping a ConfigurationPolicy:

```
Policy: loki-operator-install          ← contains OperatorPolicy
Policy: loki-operator-config           ← contains ConfigurationPolicy with LokiStack
```

Both policies are bound to the **same Placement** through a single PlacementBinding. This guarantees that the configuration targets exactly the same clusters where the operator is installed.

## 4. The library chart

### Problem: boilerplate explosion

Every OCP operator needs the same scaffolding:

1. A **Policy** wrapping an **OperatorPolicy** (install)
2. A **PlacementBinding** linking policies to a Placement
3. Optionally, a **Placement** (if not using a shared one)

Without abstraction, each operator duplicates ~70 lines of YAML. With 10+ operators, that's 700+ lines of nearly identical templates differing only in names and subscription fields.

### Solution: `acm-operator-policy` library chart

The library chart (`charts/acm-operator-policy/`) is a Helm `type: library` chart that provides named templates:

| Template | Renders |
|---|---|
| `acm-operator-policy.operatorPolicy` | Policy wrapping an OperatorPolicy |
| `acm-operator-policy.placementBinding` | PlacementBinding with all policies (install + config) as subjects |
| `acm-operator-policy.placement` | Placement (only if `placementRef` is not set) |
| `acm-operator-policy.all` | All of the above in one call |

### Why a library chart

A library chart (`type: library`) was chosen over a subchart (`type: application`) for these reasons:

| | Library chart | Subchart (application) |
|---|---|---|
| **Template rendering** | Explicit — you call `{{ include }}` | Automatic — all templates render |
| **Values merging** | None — parent must set everything | Only `global:` flows down from parent |
| **Onboarding clarity** | If you forget the `include`, you get no output but `helm template` shows it immediately | If you forget a `global:` value, the output renders with empty fields — hard to spot |
| **Flexibility** | Parent has full control over what renders and where | Less control; subchart always renders all its templates |

The library approach makes the contract explicit: each operator chart must include the templates and must provide all values. This is slightly more verbose (one `operator.yaml` per chart with a single `include` line) but fails loudly when something is wrong.

### Values contract

Each operator chart must set these values (the library has no defaults):

```yaml
# Required — operator identity
operatorName: loki-operator
operatorNamespace: openshift-operators-redhat
installPolicyName: loki-operator-install

# Required — policy framework
policyNamespace: openshift-gitops
remediationAction: enforce
severity: medium

# Required — OLM source
source: redhat-operators
sourceNamespace: openshift-marketplace
installPlanApproval: Automatic

# Placement: pick ONE of these two approaches
placementRef: platform-ocp           # use a shared Placement (no Placement rendered)
# OR
placementMatchExpressions:           # render an operator-specific Placement
  - key: platform
    operator: In
    values: ["ocp"]
  - key: region
    operator: In
    values: ["eu-west-1"]

# Optional — config policies bound alongside the install policy
configPolicyNames:
  - loki-operator-config
```

### How it works in an operator chart

An operator chart (e.g. `foundation/operators/loki/ocp/`) depends on the library:

```yaml
# Chart.yaml
dependencies:
  - name: acm-operator-policy
    version: 0.1.0
    repository: file://../../../../charts/acm-operator-policy
```

And includes the templates with a single line:

```yaml
# templates/operator.yaml
{{ include "acm-operator-policy.all" . }}
```

The operator chart then adds its own templates for configuration:

```yaml
# templates/lokistack.yaml
apiVersion: policy.open-cluster-management.io/v1
kind: Policy
metadata:
  name: {{ .Values.configPolicyNames | first }}
  namespace: {{ .Values.policyNamespace }}
spec:
  # ... ConfigurationPolicy wrapping a LokiStack CR
```

### What the library renders

For Loki with `placementRef: platform-ocp` and one config policy, `helm template` produces:

```
Policy:            loki-operator-install    (OperatorPolicy — installs the operator)
PlacementBinding:  loki-operator-binding    (binds both policies to Placement)
  → subjects:
    - loki-operator-install
    - loki-operator-config
  → placementRef: platform-ocp             (shared, not rendered by the chart)
```

The config policy (`loki-operator-config`) is rendered by the operator chart's own `lokistack.yaml` template. The PlacementBinding from the library binds *both* policies (install + config) to the same Placement.

## 5. Placement strategy

### Shared Placements

Two shared Placements cover the most common targeting needs:

| Placement | Selects | Used by |
|---|---|---|
| `platform-ocp` | All OCP spokes (excludes `local-cluster`) | Most OCP operator policies |
| `platform-generic` | All non-OCP clusters (Kind, etc.) | Generic ApplicationSets |

These are defined in `foundation/app-of-apps/` and synced by the bootstrap Application.

### Per-operator custom Placements

When an operator targets a subset of clusters, the chart renders its own Placement. Set `placementMatchExpressions` instead of `placementRef`:

```yaml
# values.yaml — operator targets only EU OCP clusters
placementMatchExpressions:
  - key: platform
    operator: In
    values: ["ocp"]
  - key: region
    operator: In
    values: ["eu-west-1"]
```

The library renders a Placement named `<operatorName>-placement` with the given expressions.

### Single PlacementBinding per operator

Each operator has exactly **one** PlacementBinding that references **one** Placement and binds **all** its policies (install + config) as subjects. This keeps the relationship clean:

```
Placement ←── PlacementBinding ──→ Policy (install)
                                 ──→ Policy (config-1)
                                 ──→ Policy (config-2)
```

No extra bindings needed when you add configuration policies — just add the name to `configPolicyNames` in `values.yaml`.

## 6. ApplicationSet auto-discovery

Operators are not registered manually. Two ApplicationSets auto-discover operators from the Git repo:

### OCP operators (`appset-ocp.yaml`)

Uses a **Git files generator** that scans `foundation/operators/*/ocp/appset-config.json`:

```json
{ "operator": "loki" }
```

For each config file found, ArgoCD creates an Application that renders the Helm chart on the hub. The rendered output (ACM Policies) is applied to the hub, and ACM distributes them to matching spokes.

```
Git repo                          Hub cluster
foundation/operators/loki/ocp/ → Application: loki-ocp → Policy + PlacementBinding
foundation/operators/tempo/ocp/ → Application: tempo-ocp → Policy + PlacementBinding
```

### Generic operators (`appset-generic.yaml`)

Uses a **matrix generator** combining:
- Git files generator (`foundation/operators/*/generic/appset-config.json`)
- clusterDecisionResource (clusters selected by `platform-generic` Placement)

```json
{
  "operator": "loki",
  "chartRepo": "https://grafana.github.io/helm-charts",
  "chartName": "loki",
  "chartVersion": "6.x",
  "namespace": "loki"
}
```

The matrix produces one Application per operator per cluster:

```
Git repo × Clusters           Spoke clusters
loki × kind-local          → Application: loki-kind-local    → deploys Loki via Helm
tempo × kind-local          → Application: tempo-kind-local   → deploys Tempo via Helm
```

### Onboarding a new operator

To add a new operator to the fleet:

1. **Create the OCP chart** at `foundation/operators/<name>/ocp/`:
   - `Chart.yaml` with `acm-operator-policy` dependency
   - `values.yaml` with operator-specific values
   - `templates/operator.yaml` with `{{ include "acm-operator-policy.all" . }}`
   - `templates/<config>.yaml` for any ConfigurationPolicy
   - `appset-config.json` with `{"operator": "<name>"}`
   - Run `helm dependency update .`

2. **Create the generic values** at `foundation/operators/<name>/generic/`:
   - `values.yaml` for the upstream Helm chart
   - `appset-config.json` with chart coordinates and namespace

3. **Push to Git** — the ApplicationSets pick up the new directories automatically. No YAML editing in `app-of-apps/` required.

## 7. Hybrid mode prerequisites

Running the hub App Controller alongside the Agent Principal requires three
policies applied **before** deploying operators (all in `bootstrap/argocd-agent/`):

### 7a. `skip-reconcile` annotation (`07-skip-reconcile-policy.yaml`)

The hub App Controller is enabled (`controller.enabled: true`) to reconcile
hub-targeted Applications (e.g. `foundation-bootstrap`, `loki-ocp`). Without
guardrails, it would also try to reconcile agent-targeted Applications (e.g.
`loki-kind-local`) by connecting through the resource proxy — which fails on
non-OCP clusters because the resource proxy doesn't support full OpenAPI
schema discovery ([argocd-agent#961](https://github.com/argoproj-labs/argocd-agent/issues/961)).

A ConfigurationPolicy annotates all agent-managed cluster secrets with
`argocd.argoproj.io/skip-reconcile: "true"`. This tells the hub controller
to ignore those clusters and all Applications targeting them. The spoke
agents handle reconciliation independently.

The policy targets `local-cluster` (the hub) because the cluster secrets
live on the hub.

### 7b. Spoke controller RBAC supplementation (`08-agent-controller-rbac-policy.yaml`)

ACM deploys the spoke ArgoCD App Controller with a read-only ClusterRole for
most resources (write access is limited to the `openshift-gitops` namespace).
This is by design — ACM assumes workloads on spokes are managed by
`config-policy-controller` (which has cluster-admin), not by ArgoCD directly.

When deploying workloads directly via ArgoCD Helm charts (the generic path),
the controller needs write access for standard workload resources (Deployments,
Services, StatefulSets, etc.) in arbitrary namespaces. A ConfigurationPolicy
creates a supplemental ClusterRole + ClusterRoleBinding on all spokes:

| apiGroups | Resources | Verbs |
|-----------|-----------|-------|
| `""` | pods, services, secrets, configmaps, serviceaccounts, ... | `*` |
| `apps` | deployments, statefulsets, daemonsets, replicasets | `*` |
| `batch` | jobs, cronjobs | `*` |
| `networking.k8s.io` | ingresses, networkpolicies | `*` |
| `policy` | poddisruptionbudgets | `*` |
| `autoscaling` | horizontalpodautoscalers | `*` |

The supplemental ClusterRole is a separate resource (`argocd-application-controller-workload`)
so the ACM addon manager doesn't revert it.

### 7c. `destination.name` for agent routing

The Agent Principal uses **destination-based mapping** to route Applications
to agents. Applications targeting spokes must use `destination.name` (e.g.
`kind-local`) instead of `destination.server` (the resource proxy URL).
The generic ApplicationSet template uses `destination.name: '{{name}}'`.

## 8. Bootstrap

Everything is driven by a single Application:

```bash
oc apply -f foundation/app-of-apps.yaml
```

This creates `foundation-bootstrap`, which syncs `foundation/app-of-apps/` and produces:

```
foundation-bootstrap (Application)
  ├── platform-ocp          (Placement)
  ├── platform-generic       (Placement)
  ├── foundation-ocp-operators   (ApplicationSet)
  │   ├── loki-ocp           (Application → Helm → ACM Policies)
  │   └── tempo-ocp          (Application → Helm → ACM Policies)
  └── foundation-generic-operators (ApplicationSet)
      ├── loki-kind-local    (Application → upstream Helm → spoke)
      └── tempo-kind-local   (Application → upstream Helm → spoke)
```
