{{/*
Expand the name of the chart.
*/}}
{{- define "tasktracker.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "tasktracker.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "tasktracker.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "tasktracker.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{/*
Common labels
*/}}
{{- define "tasktracker.labels" -}}
helm.sh/chart: {{ include "tasktracker.chart" . }}
{{ include "tasktracker.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "tasktracker.selectorLabels" -}}
app.kubernetes.io/name: {{ include "tasktracker.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "tasktracker.serviceAccountName" -}}
{{- if .Values.openbao.serviceAccount -}}
{{- .Values.openbao.serviceAccount -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end }}

{{/*
Generate database URL
*/}}
{{- define "tasktracker.databaseUrl" -}}
{{- if .Values.openbao.enabled -}}
postgresql://{{ .Values.database.username }}:$(DATABASE_PASSWORD)@{{ .Values.database.host }}:{{ .Values.database.port }}/{{ .Values.database.name }}?sslmode={{ .Values.database.sslmode }}
{{- else -}}
postgresql://{{ .Values.database.username }}:{{ .Values.database.password | default "postgres" }}@{{ .Values.database.host }}:{{ .Values.database.port }}/{{ .Values.database.name }}?sslmode={{ .Values.database.sslmode }}
{{- end -}}
{{- end }}

{{/*
Create Kafka bootstrap servers list
*/}}
{{- define "tasktracker.kafkaBrokers" -}}
{{- .Values.kafka.brokers -}}
{{- end }}