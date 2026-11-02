from django.urls import path

from . import views

app_name = "voos"

urlpatterns = [
    path("", views.MonitoramentoLista.as_view(), name="lista"),
    path("horarios/", views.AgendaEditar.as_view(), name="agenda"),
    path("rotas/nova/", views.MonitoramentoCriar.as_view(), name="criar"),
    path("rotas/<int:pk>/", views.MonitoramentoDetalhe.as_view(), name="detalhe"),
    path("rotas/<int:pk>/editar/", views.MonitoramentoEditar.as_view(), name="editar"),
    path("rotas/<int:pk>/excluir/", views.MonitoramentoExcluir.as_view(), name="excluir"),
    path("rotas/<int:pk>/checar/", views.MonitoramentoChecar.as_view(), name="checar"),
    path("rotas/<int:pk>/alternar/", views.MonitoramentoAlternar.as_view(), name="alternar"),
]
