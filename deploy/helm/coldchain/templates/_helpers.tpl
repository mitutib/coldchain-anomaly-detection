{{- define "coldchain.labels" -}}
app.kubernetes.io/name: coldchain
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "coldchain.redisUrl" -}}
{{- if .Values.redis.enabled -}}
redis://{{ .Release.Name }}-redis:6379/0
{{- else -}}
{{ required "redis.externalUrl is required when redis.enabled is false" .Values.redis.externalUrl }}
{{- end -}}
{{- end }}
