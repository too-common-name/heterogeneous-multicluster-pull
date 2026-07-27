# Bootstrap Scaling Assessment

This document identifies bootstrap resources that don't scale to a 200–300
cluster fleet and proposes solutions.

## Current bootstrap inventory

| File | What it creates | Scales with |
|------|----------------|-------------|
| `01-oauth-htpasswd.yaml` | OAuth identity provider | fixed (1) |
| `02-groups.yaml` | Groups (foundation-admins, mortgage-team, insurance-team) | teams (O(T)) |
| `03-foundation-cluster-admin.yaml` | ClusterRoleBinding for foundation-admins | fixed (1) |
| `04-team-namespaces.yaml` | Team gitops namespaces | teams (O(T)) |
| `05-managedclustersetbindings.yaml` | MCSBindings per team namespace | teams (O(T)) |
| `06-team-rolebindings.yaml` | RoleBindings for team namespaces + MCS view ClusterRoleBindings | teams (O(T)) |
| **`07-cluster-ns-secret-reader.yaml`** | **Role + RoleBinding per cluster namespace** | **clusters (O(C))** |
| `import/*/managedcluster.yaml` | ManagedCluster + KlusterletAddonConfig per cluster | **clusters (O(C))** |
| `managedclustersets/*.yaml` | ManagedClusterSet per team | teams (O(T)) |
| `argocd-agent/01–08` | ArgoCD CR, AppProjects, Placements, Policies | fixed / teams |

With ~10 teams, O(T) is fine. With 200+ clusters, O(C) is the problem.

---

## Issue 1: `07-cluster-ns-secret-reader.yaml` — O(C) identical Roles

### Problem

Every cluster gets an identical `secret-reader` Role (same rules) plus a
RoleBinding (same structure, only `namespace` and `subjects[0].name` differ).
At 200 clusters this means **200 Role + 200 RoleBinding** manifests, all
copy-pasted with namespace substitution.

### Root cause

We use namespace-scoped `Role` because the permission (read secrets) must be
limited to the cluster's own namespace on the hub. The team that owns the
cluster must be the only one bound to it. Currently both the Role definition
and the team binding are repeated per-cluster.

### Fix: ClusterRole + ConfigurationPolicy

Split the problem into two:

**Step A — one ClusterRole, hub-wide** (replaces 200 identical Roles):

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: cluster-ns-secret-reader
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get", "list"]
```

This is a single resource applied once. It doesn't grant anything until a
RoleBinding references it in a specific namespace.

**Step B — ConfigurationPolicy per team** (replaces 200 RoleBindings):

Use an ACM ConfigurationPolicy that targets `local-cluster` and deploys a
RoleBinding into every cluster namespace matching the team's MCS. This requires
the cluster namespace to carry a label indicating team ownership.

Problem: ACM-created cluster namespaces (e.g. `insolvency-check-sno`) don't
automatically carry `team=mortgage` labels. Two options:

1. **Policy-driven labeling**: a ConfigurationPolicy on the hub that reads
   `ManagedCluster` labels and mirrors `team=<value>` onto the corresponding
   namespace. Then a second ConfigurationPolicy uses `namespaceSelector` with
   `matchLabels: { team: mortgage }` to deploy the RoleBinding.

2. **Direct namespaceSelector by MCS**: the ConfigurationPolicy uses a
   template that iterates over `ManagedCluster` resources in a given MCS
   and emits RoleBindings for each. This uses the `hub-templates` feature
   of ConfigurationPolicy.

Either way, adding a new cluster to a MCS automatically creates the
RoleBinding — no manifest editing needed.

### Alternative: Helm chart for bootstrap RBAC

Template the per-cluster YAML with `range` over a values list. Less elegant
(still requires adding cluster names to a values file) but simpler than
ConfigurationPolicy hub-templates.

### Effort

Medium. Requires understanding ACM hub-templates or namespace labeling
policies. The ClusterRole part is trivial.

---

## Issue 2: `import/*/managedcluster.yaml` — O(C) import manifests

### Problem

Each cluster has its own directory (`import/<cluster-name>/`) with a
`managedcluster.yaml` containing:

- `ManagedCluster` resource (labels: name, cloud, vendor, clusterset, platform, team)
- `KlusterletAddonConfig` (enables policy, app, search, cert addons)

At 200 clusters: 200 directories, 200 nearly-identical files.

### Root cause

Manual import requires explicit `ManagedCluster` + `KlusterletAddonConfig`
resources per cluster. The only differences are:

- `metadata.name` / `metadata.namespace`
- Labels: `cloud`, `vendor`, `clusterset`, `platform`, `team`
- Addon config is identical across all clusters

### Fix options

| Option | How | Pros | Cons |
|--------|-----|------|------|
| **A. Helm chart** | Single `templates/managedcluster.yaml` with `range` over `.Values.clusters` list | Simple, portable, works with ArgoCD | Still need to list cluster names in values |
| **B. ApplicationSet + Git generator** | `import/*/config.json` files, AppSet templates the ManagedCluster | Auto-discovers new clusters from Git | Cluster must be in Git before it can be imported (chicken-egg for auto-import) |
| **C. ACM auto-import** | Use `ManagedClusterAutoImport` or cloud provider discovery | Zero-manifest for new clusters | Requires cloud credentials on hub, doesn't apply to bare-metal/Kind |
| **D. Cluster claims / Hive** | Hub provisions clusters via `ClusterDeployment` | Full lifecycle management | Only for hub-provisioned clusters, doesn't apply to pre-existing spokes |

For a heterogeneous fleet (some cloud, some bare-metal, some Kind), **Option A
(Helm chart)** is the pragmatic choice:

```yaml
# values.yaml
clusters:
  - name: insolvency-check-sno
    clusterset: mortgage
    platform: ocp
    team: mortgage
    cloud: auto-detect
    vendor: auto-detect
  - name: kind-local
    clusterset: mortgage
    platform: generic
    team: mortgage
    cloud: Other
    vendor: Other
  # ... 200 more entries
```

The `KlusterletAddonConfig` template is identical for all clusters (all
addons enabled), so it doesn't need per-cluster values.

### Effort

Low–Medium. Straightforward Helm templating.

---

## Issue 3: `06-team-rolebindings.yaml` — scaling OK but tightly coupled

### Not a scaling issue

This file has O(T) resources — one RoleBinding + one ClusterRoleBinding per
team. With ~10 teams this is fine. However, adding a new team requires editing
this file, `02-groups.yaml`, `04-team-namespaces.yaml`, and
`05-managedclustersetbindings.yaml`. A Helm chart for team onboarding would
bundle these.

---

## Summary of proposed issues

| # | Title | Priority | Scope |
|---|-------|----------|-------|
| 1 | Replace per-cluster Role/RoleBinding with ClusterRole + ConfigurationPolicy | High | `07-cluster-ns-secret-reader.yaml` |
| 2 | Templatize cluster import with Helm chart | Medium | `import/*/managedcluster.yaml` |
| 3 | Bundle team onboarding into a Helm chart | Low | `02`, `04`, `05`, `06` |

Issues 1 and 2 are blockers for scaling beyond ~20 clusters. Issue 3 is a
quality-of-life improvement for the foundation team.
