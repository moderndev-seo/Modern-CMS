from django.urls import path

from integrations.views import MetadataView, ProbeView

urlpatterns = [
    path("namespaces/", MetadataView.as_view(kind="namespace")),
    path("namespaces/<uuid:object_id>/", MetadataView.as_view(kind="namespace")),
    path("connections/", MetadataView.as_view(kind="connection")),
    path("connections/<uuid:object_id>/", MetadataView.as_view(kind="connection")),
    path("connections/<uuid:connection_id>/state/", MetadataView.as_view(kind="state")),
    path(
        "connections/<uuid:connection_id>/credentials/",
        MetadataView.as_view(kind="issue"),
    ),
    path(
        "connections/<uuid:connection_id>/credentials/<uuid:credential_id>/revoke/",
        MetadataView.as_view(kind="revoke"),
    ),
    path("connections/<uuid:connection_id>/audit/", MetadataView.as_view(kind="audit")),
    path("service/probe/", ProbeView.as_view()),
]
