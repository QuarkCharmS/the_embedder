{{/*
Expand the name of the chart.
*/}}
{{- define "rag-system.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "rag-system.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "rag-system.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels for RAG Connector
*/}}
{{- define "rag-system.ragConnector.labels" -}}
helm.sh/chart: {{ include "rag-system.chart" . }}
{{ include "rag-system.ragConnector.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels for RAG Connector
*/}}
{{- define "rag-system.ragConnector.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rag-system.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: rag-connector
{{- end }}

{{/*
Create the name of the RAG Connector service account to use
*/}}
{{- define "rag-system.ragConnector.serviceAccountName" -}}
{{- if .Values.ragConnector.serviceAccount.create }}
{{- default (printf "%s-rag-connector" (include "rag-system.fullname" .)) .Values.ragConnector.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.ragConnector.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
RAG Connector full name
*/}}
{{- define "rag-system.ragConnector.fullname" -}}
{{- printf "%s-rag-connector" (include "rag-system.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Qdrant service name (from dependency chart)
*/}}
{{- define "rag-system.qdrant.serviceName" -}}
{{- printf "%s-qdrant" .Release.Name }}
{{- end }}

{{/*
Qdrant URL for RAG Connector
*/}}
{{- define "rag-system.qdrantUrl" -}}
{{- if .Values.ragConnector.env.qdrantUrl }}
{{- .Values.ragConnector.env.qdrantUrl }}
{{- else }}
{{- printf "http://%s:6333" (include "rag-system.qdrant.serviceName" .) }}
{{- end }}
{{- end }}
