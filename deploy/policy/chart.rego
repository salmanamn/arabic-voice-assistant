# Rules for what `helm template` renders from deploy/charts/voice (D35). Run with --combine: `input` is the list of
# rendered documents, each as {"path": ..., "contents": <object>}.
#   helm template voice deploy/charts/voice -n voice | conftest test --combine -p deploy/policy -
package main

import rego.v1

docs := [d.contents | some d in input; d.contents.kind]

workloads := [w | some w in docs; w.kind in {"Deployment", "Job"}]

pod_specs contains {"name": sprintf("%s/%s", [w.kind, w.metadata.name]), "spec": w.spec.template.spec} if some w in workloads

pod_specs contains {"name": sprintf("Pod/%s", [p.metadata.name]), "spec": p.spec} if {
	some p in docs
	p.kind == "Pod"
}

containers contains {"owner": s.name, "c": c} if {
	some s in pod_specs
	some c in array.concat(object.get(s.spec, "containers", []), object.get(s.spec, "initContainers", []))
}

# --- restricted Pod Security Standard, and a bit more (D30) ---

deny contains sprintf("%s: automountServiceAccountToken must be false", [s.name]) if {
	some s in pod_specs
	s.spec.automountServiceAccountToken != false
}

deny contains sprintf("%s: runAsNonRoot must be true", [s.name]) if {
	some s in pod_specs
	not s.spec.securityContext.runAsNonRoot
}

deny contains sprintf("%s: seccompProfile must be RuntimeDefault", [s.name]) if {
	some s in pod_specs
	s.spec.securityContext.seccompProfile.type != "RuntimeDefault"
}

deny contains sprintf("%s: no seccompProfile", [s.name]) if {
	some s in pod_specs
	not s.spec.securityContext.seccompProfile
}

deny contains sprintf("%s/%s: allowPrivilegeEscalation must be false", [x.owner, x.c.name]) if {
	some x in containers
	object.get(x.c, ["securityContext", "allowPrivilegeEscalation"], true) != false
}

deny contains sprintf("%s/%s: readOnlyRootFilesystem must be true", [x.owner, x.c.name]) if {
	some x in containers
	not x.c.securityContext.readOnlyRootFilesystem
}

deny contains sprintf("%s/%s: capabilities must drop ALL", [x.owner, x.c.name]) if {
	some x in containers
	not "ALL" in object.get(x.c, ["securityContext", "capabilities", "drop"], [])
}

deny contains sprintf("%s/%s: must not add capabilities", [x.owner, x.c.name]) if {
	some x in containers
	count(object.get(x.c, ["securityContext", "capabilities", "add"], [])) > 0
}

# --- resources (D26) ---

deny contains sprintf("%s/%s: needs requests.%s", [x.owner, x.c.name, r]) if {
	some x in containers
	some r in ["cpu", "memory"]
	not x.c.resources.requests[r]
}

deny contains sprintf("%s/%s: needs limits.memory", [x.owner, x.c.name]) if {
	some x in containers
	not x.c.resources.limits.memory
}

deny contains sprintf("%s/%s: no CPU limits (D26)", [x.owner, x.c.name]) if {
	some x in containers
	x.c.resources.limits.cpu
}

deny contains "stt: STT_THREADS must come from the container's requests.cpu (D7, D26)" if {
	some w in workloads
	w.metadata.name == "stt"
	some c in w.spec.template.spec.containers
	c.name == "stt"
	not stt_threads_from_request(c)
}

stt_threads_from_request(c) if {
	some e in c.env
	e.name == "STT_THREADS"
	e.valueFrom.resourceFieldRef.resource == "requests.cpu"
	e.valueFrom.resourceFieldRef.containerName == "stt"
}

# --- probes and stopping (D12, D31) ---

services := {"stt", "tts", "gateway"}

deny contains sprintf("Deployment/%s: needs a %s", [w.metadata.name, p]) if {
	some w in workloads
	w.kind == "Deployment"
	w.metadata.name in services
	some c in w.spec.template.spec.containers
	c.name == w.metadata.name
	some p in ["startupProbe", "readinessProbe", "livenessProbe"]
	not c[p]
}

deny contains sprintf("Deployment/%s: needs a preStop hook and terminationGracePeriodSeconds >= 35 (D31)", [w.metadata.name]) if {
	some w in workloads
	w.kind == "Deployment"
	w.metadata.name in services
	not stops_gracefully(w)
}

stops_gracefully(w) if {
	w.spec.template.spec.terminationGracePeriodSeconds >= 35
	some c in w.spec.template.spec.containers
	c.name == w.metadata.name
	c.lifecycle.preStop
}

# --- model volumes: only Jobs write them (D24, D25) ---

model_claims := {"models", "ollama-models"}

deny contains sprintf("Deployment/%s: volume %s must be mounted read-only", [w.metadata.name, m.name]) if {
	some w in workloads
	w.kind == "Deployment"
	some v in object.get(w.spec.template.spec, "volumes", [])
	v.persistentVolumeClaim.claimName in model_claims
	some c in array.concat(w.spec.template.spec.containers, object.get(w.spec.template.spec, "initContainers", []))
	some m in object.get(c, "volumeMounts", [])
	m.name == v.name
	not m.readOnly
}

deny contains sprintf("Deployment/%s: claim %s must be read-only", [w.metadata.name, v.persistentVolumeClaim.claimName]) if {
	some w in workloads
	w.kind == "Deployment"
	some v in object.get(w.spec.template.spec, "volumes", [])
	v.persistentVolumeClaim.claimName in model_claims
	not v.persistentVolumeClaim.readOnly
}

# --- network (D29) ---

policies := [p | some p in docs; p.kind == "NetworkPolicy"]

deny contains "no default-deny NetworkPolicy (podSelector {}, Ingress and Egress, no rules)" if {
	not default_deny
}

default_deny if {
	some p in policies
	p.spec.podSelector == {}
	{"Ingress", "Egress"} == {t | some t in p.spec.policyTypes}
	not p.spec.ingress
	not p.spec.egress
}

deny contains sprintf("NetworkPolicy/%s: must cover both Ingress and Egress", [p.metadata.name]) if {
	some p in policies
	{"Ingress", "Egress"} != {t | some t in p.spec.policyTypes}
}

download_components := {"models", "ollama-pull"}

# components a policy selects, by matchLabels or by an `In` expression
selected(p) := {p.spec.podSelector.matchLabels["app.kubernetes.io/component"]} if p.spec.podSelector.matchLabels["app.kubernetes.io/component"]

selected(p) := {v | some e in p.spec.podSelector.matchExpressions; e.key == "app.kubernetes.io/component"; e.operator == "In"; some v in e.values} if {
	not p.spec.podSelector.matchLabels["app.kubernetes.io/component"]
}

deny contains sprintf("NetworkPolicy/%s: ipBlock egress only for the download Jobs, not %v", [p.metadata.name, extra]) if {
	some p in policies
	some rule in object.get(p.spec, "egress", [])
	some to in object.get(rule, "to", [])
	to.ipBlock
	extra := selected(p) - download_components
	count(extra) > 0
}

deny contains sprintf("NetworkPolicy/%s: egress rule without a destination (allows everything)", [p.metadata.name]) if {
	some p in policies
	some rule in object.get(p.spec, "egress", [])
	count(object.get(rule, "to", [])) == 0
}

private_ranges := {"10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16"}

deny contains sprintf("NetworkPolicy/%s: %s must except the private and link-local ranges", [p.metadata.name, to.ipBlock.cidr]) if {
	some p in policies
	some rule in object.get(p.spec, "egress", [])
	some to in object.get(rule, "to", [])
	to.ipBlock.cidr == "0.0.0.0/0"
	missing := private_ranges - {r | some r in object.get(to.ipBlock, "except", [])}
	count(missing) > 0
}

deny contains sprintf("NetworkPolicy/%s: %s must have no egress at all", [p.metadata.name, c]) if {
	some p in policies
	some c in selected(p)
	c in {"stt", "tts", "ollama"}
	count(object.get(p.spec, "egress", [])) > 0
}

# --- Jobs ---

deny contains sprintf("Job/%s: needs restartPolicy Never and a backoffLimit", [w.metadata.name]) if {
	some w in workloads
	w.kind == "Job"
	not job_bounded(w)
}

job_bounded(w) if {
	w.spec.template.spec.restartPolicy == "Never"
	w.spec.backoffLimit <= 6
}