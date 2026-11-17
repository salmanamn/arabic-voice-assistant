{{/* Labels on everything the chart makes. */}}
{{- define "voice.labels" -}}
app.kubernetes.io/name: voice
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end }}

{{/* Selector of one component: (dict "root" $ "component" "stt"). NetworkPolicies select on the same labels. */}}
{{- define "voice.selector" -}}
app.kubernetes.io/name: voice
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/* One of our images: (dict "root" $ "name" "stt"). */}}
{{- define "voice.image" -}}
{{- $i := .root.Values.images -}}
{{- if $i.registry }}{{ $i.registry }}/{{ end }}voice-{{ .name }}:{{ $i.tag }}
{{- end }}

{{/* Restricted Pod Security Standard (D30): pod level. Every pod of the chart uses it. */}}
{{- define "voice.podSecurity" -}}
automountServiceAccountToken: false
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  runAsGroup: 10001
  fsGroup: 10001
  fsGroupChangePolicy: OnRootMismatch
  seccompProfile:
    type: RuntimeDefault
{{- end }}

{{/* Restricted Pod Security Standard: container level. */}}
{{- define "voice.containerSecurity" -}}
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: [ALL]
{{- end }}

{{/* The 16 MiB in-memory /tmp every container gets (as in compose, D19); it counts towards the memory limit. */}}
{{- define "voice.tmpVolume" -}}
- name: tmp
  emptyDir:
    medium: Memory
    sizeLimit: 16Mi
{{- end }}

{{/* The init container that checks the speech models on the read-only volume (D24): (dict "root" $ "model" "stt-small"). */}}
{{- define "voice.checkModels" -}}
- name: check-model
  image: {{ include "voice.image" (dict "root" .root "name" "models") }}
  imagePullPolicy: {{ .root.Values.images.pullPolicy }}
  # Waits for the fetch job on a new volume; checks every file's SHA-256 against the lock on every start.
  command: ["sh", "-c", "until python -m voice.fetch_job --check \"$0\"; do sleep 5; done", {{ .model | quote }}]
  env:
    - name: MODELS_DIR
      value: /models
  resources:
    requests: { cpu: 100m, memory: 128Mi }
    limits: { memory: 256Mi }
  {{- include "voice.containerSecurity" . | nindent 2 }}
  volumeMounts:
    - { name: models, mountPath: /models, readOnly: true }
    - { name: tmp, mountPath: /tmp }
{{- end }}

{{/* Probes for our services (D12): startup = model loaded, readiness = /readyz, liveness = /healthz. */}}
{{- define "voice.probes" -}}
startupProbe:
  httpGet: { path: /readyz, port: http }
  periodSeconds: 2
  timeoutSeconds: 3
  failureThreshold: {{ div (.startupSeconds | default 120) 2 }}
readinessProbe:
  httpGet: { path: /readyz, port: http }
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
livenessProbe:
  httpGet: { path: /healthz, port: http }
  periodSeconds: 20
  timeoutSeconds: 5
  failureThreshold: 3
{{- end }}

{{/* NetworkPolicy pieces (D29). */}}
{{- define "voice.peer" -}}
podSelector:
  matchLabels: {{- include "voice.selector" . | nindent 4 }}
{{- end }}
{{- define "voice.dnsEgress" -}}
- to:
    - namespaceSelector:
        matchLabels: { kubernetes.io/metadata.name: {{ .Values.network.dns.namespace }} }
      podSelector:
        matchLabels: {{- toYaml .Values.network.dns.podLabels | nindent 10 }}
  ports:
    - { protocol: UDP, port: 53 }
    - { protocol: TCP, port: 53 }
{{- end }}
{{- define "voice.modelHostEgress" -}}
- to:
    {{- range .Values.network.modelHosts.cidrs }}
    - ipBlock: {{- toYaml . | nindent 8 }}
    {{- end }}
  ports:
    {{- range .Values.network.modelHosts.ports }}
    - { protocol: TCP, port: {{ . }} }
    {{- end }}
{{- end }}