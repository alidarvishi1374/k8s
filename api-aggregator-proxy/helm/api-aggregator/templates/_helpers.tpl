{{- define "api-aggregator.name" -}}
{{ default .Chart.Name .Values.nameOverride }}
{{- end }}

{{- define "api-aggregator.fullname" -}}
{{- if .Values.fullnameOverride }}
{{ .Values.fullnameOverride }}
{{- else }}
{{ .Release.Name }}-{{ include "api-aggregator.name" . }}
{{- end }}
{{- end }}