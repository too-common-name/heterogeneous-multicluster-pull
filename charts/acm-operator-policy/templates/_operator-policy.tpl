{{- define "acm-operator-policy.operatorPolicy" -}}
apiVersion: policy.open-cluster-management.io/v1
kind: Policy
metadata:
  name: {{ .Values.installPolicyName }}
  namespace: {{ .Values.policyNamespace }}
spec:
  remediationAction: {{ .Values.remediationAction }}
  disabled: false
  policy-templates:
    - objectDefinition:
        apiVersion: policy.open-cluster-management.io/v1beta1
        kind: OperatorPolicy
        metadata:
          name: {{ .Values.installPolicyName }}
        spec:
          remediationAction: {{ .Values.remediationAction }}
          complianceType: musthave
          upgradeApproval: {{ .Values.installPlanApproval }}
          severity: {{ .Values.severity }}
          subscription:
            name: {{ .Values.operatorName }}
            namespace: {{ .Values.operatorNamespace }}
            source: {{ .Values.source }}
            sourceNamespace: {{ .Values.sourceNamespace }}
            {{- if .Values.channel }}
            channel: {{ .Values.channel }}
            {{- end }}
{{- end }}

{{- define "acm-operator-policy.placementBinding" -}}
apiVersion: policy.open-cluster-management.io/v1
kind: PlacementBinding
metadata:
  name: {{ .Values.operatorName }}-binding
  namespace: {{ .Values.policyNamespace }}
placementRef:
  apiGroup: cluster.open-cluster-management.io
  kind: Placement
  {{- if .Values.placementRef }}
  name: {{ .Values.placementRef }}
  {{- else }}
  name: {{ .Values.operatorName }}-placement
  {{- end }}
subjects:
  - apiGroup: policy.open-cluster-management.io
    kind: Policy
    name: {{ .Values.installPolicyName }}
{{- range .Values.configPolicyNames }}
  - apiGroup: policy.open-cluster-management.io
    kind: Policy
    name: {{ . }}
{{- end }}
{{- end }}

{{- define "acm-operator-policy.placement" -}}
{{- if not .Values.placementRef }}
apiVersion: cluster.open-cluster-management.io/v1beta1
kind: Placement
metadata:
  name: {{ .Values.operatorName }}-placement
  namespace: {{ .Values.policyNamespace }}
spec:
  predicates:
    - requiredClusterSelector:
        labelSelector:
          matchExpressions:
            {{- toYaml .Values.placementMatchExpressions | nindent 12 }}
{{- end }}
{{- end }}

{{- define "acm-operator-policy.all" -}}
{{ include "acm-operator-policy.operatorPolicy" . }}
---
{{ include "acm-operator-policy.placementBinding" . }}
{{- if not .Values.placementRef }}
---
{{ include "acm-operator-policy.placement" . }}
{{- end }}
{{- end }}
