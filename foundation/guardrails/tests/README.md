# Guardrail Tests

Negative and positive tests for the Gatekeeper constraints. Run these as a
**team user** (not foundation-admin) to verify the guardrails work.

## Prerequisites

- Gatekeeper installed on the hub (see main README step 4)
- ConstraintTemplates and Constraints applied
- Logged in as a team user (e.g., `mortgage-user`)

## Run

```bash
# Login as a team user
oc login $HUB_API -u mortgage-user -p 'mortgage123' --insecure-skip-tls-verify

# Test 1: Policy targeting a protected namespace → should be REJECTED
oc apply -f foundation/guardrails/tests/test-policy-protected-ns.yaml

# Test 2: OperatorPolicy targeting a foundation operator → should be REJECTED
oc apply -f foundation/guardrails/tests/test-policy-protected-operator.yaml

# Test 3: Application targeting a protected namespace → should be REJECTED
oc apply -f foundation/guardrails/tests/test-app-protected-ns.yaml

# Test 4: Legitimate application → should be ALLOWED
oc apply -f foundation/guardrails/tests/test-app-legitimate.yaml
```

## Expected results

| Test | File | Expected |
|------|------|----------|
| Policy → protected namespace | `test-policy-protected-ns.yaml` | `denied: ConfigurationPolicy targets protected namespace 'openshift-logging'` |
| Policy → foundation operator | `test-policy-protected-operator.yaml` | `denied: OperatorPolicy targets foundation operator 'loki-operator'` |
| App → protected namespace | `test-app-protected-ns.yaml` | `denied: Application targets protected namespace 'openshift-logging'` |
| App → team namespace | `test-app-legitimate.yaml` | `application.argoproj.io/test-legitimate-app created` |

## Cleanup

```bash
# Only the legitimate app gets created — delete it after testing
oc delete application.argoproj.io test-legitimate-app -n mortgage-gitops
```
