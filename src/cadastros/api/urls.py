from django.urls import path

from . import views

app_name = "cadastros"

urlpatterns = [
    # URLs para Condomínios
    path("condominios/", views.condominio_list_view, name="condominio-list"),
    path(
        "condominios/options/",
        views.condominio_options_view,
        name="condominio-options",
    ),
    path(
        "condominios/create/",
        views.condominio_create_view,
        name="condominio-create",
    ),
    path(
        "condominios/<int:pk>/",
        views.condominio_detail_view,
        name="condominio-detail",
    ),
    path(
        "condominios/<int:pk>/update/",
        views.condominio_update_view,
        name="condominio-update",
    ),
    # Logo armazenada no DB (BLOB)
    path(
        "condominios/<int:pk>/logo-db/",
        views.condominio_logo_db_view,
        name="condominio-logo-db",
    ),
    path(
        "condominios/<int:pk>/logo-db/upload/",
        views.condominio_upload_logo_db_view,
        name="condominio-logo-db-upload",
    ),
    path(
        "condominios/<int:pk>/delete/",
        views.condominio_delete_view,
        name="condominio-delete",
    ),
    # URLs para Encomendas
    path("encomendas/", views.encomenda_list_view, name="encomenda-list"),
    path(
        "encomendas/badge/",
        views.encomenda_badge_view,
        name="encomenda-badge",
    ),
    path(
        "encomendas/create/",
        views.encomenda_create_view,
        name="encomenda-create",
    ),
    path(
        "encomendas/<int:pk>/",
        views.encomenda_detail_view,
        name="encomenda-detail",
    ),
    path(
        "encomendas/<int:pk>/update/",
        views.encomenda_update_view,
        name="encomenda-update",
    ),
    path(
        "encomendas/<int:pk>/delete/",
        views.encomenda_delete_view,
        name="encomenda-delete",
    ),
    # URLs para Unidades
    path("unidades/", views.unidade_list_view, name="unidade-list"),
    path("unidades/create/", views.unidade_create_view, name="unidade-create"),
    path(
        "unidades/create-bulk/",
        views.unidade_create_bulk_view,
        name="unidade-create-bulk",
    ),
    path(
        "unidades/<int:pk>/", views.unidade_detail_view, name="unidade-detail"
    ),
    path(
        "unidades/<int:pk>/update/",
        views.unidade_update_view,
        name="unidade-update",
    ),
    path(
        "unidades/<int:pk>/inactivate/",
        views.unidade_inactivate_view,
        name="unidade-inactivate",
    ),
    path(
        "unidades/<int:pk>/delete/",
        views.unidade_delete_view,
        name="unidade-delete",
    ),
    # URLs para Veículos
    path("veiculos/", views.veiculo_list_view, name="veiculo-list"),
    path("veiculos/create/", views.veiculo_create_view, name="veiculo-create"),
    path(
        "veiculos/<int:pk>/", views.veiculo_detail_view, name="veiculo-detail"
    ),
    path(
        "veiculos/<int:pk>/update/",
        views.veiculo_update_view,
        name="veiculo-update",
    ),
    path(
        "veiculos/<int:pk>/delete/",
        views.veiculo_delete_view,
        name="veiculo-delete",
    ),
    # URLs para Visitantes
    path("visitantes/", views.visitante_list_view, name="visitante-list"),
    path(
        "visitantes/create/",
        views.visitante_create_view,
        name="visitante-create",
    ),
    path(
        "visitantes/<int:pk>/",
        views.visitante_detail_view,
        name="visitante-detail",
    ),
    path(
        "visitantes/<int:pk>/update/",
        views.visitante_update_view,
        name="visitante-update",
    ),
    path(
        "visitantes/<int:pk>/delete/",
        views.visitante_delete_view,
        name="visitante-delete",
    ),
    # URLs para Avisos
    path("avisos/", views.aviso_list_view, name="aviso-list"),
    path("avisos/home/", views.aviso_home_view, name="aviso-home"),
    path("avisos/create/", views.aviso_create_view, name="aviso-create"),
    path("avisos/<int:pk>/", views.aviso_detail_view, name="aviso-detail"),
    path(
        "avisos/<int:pk>/update/",
        views.aviso_update_view,
        name="aviso-update",
    ),
    path(
        "avisos/<int:pk>/delete/",
        views.aviso_delete_view,
        name="aviso-delete",
    ),
    path(
        "avisos/grupos/options/",
        views.aviso_grupos_options_view,
        name="aviso-grupos-options",
    ),
    # URLs para Dashboard
    path(
        "dashboard/morador-stats/",
        views.morador_stats_view,
        name="morador-stats",
    ),
    path(
        "dashboard/sindico-stats/",
        views.sindico_stats_view,
        name="sindico-stats",
    ),
    # URLs para Espaços
    path("espacos/", views.espaco_list_view, name="espaco-list"),
    path("espacos/create/", views.espaco_create_view, name="espaco-create"),
    path("espacos/<int:pk>/", views.espaco_detail_view, name="espaco-detail"),
    path(
        "espacos/<int:pk>/update/",
        views.espaco_update_view,
        name="espaco-update",
    ),
    path(
        "espacos/<int:pk>/delete/",
        views.espaco_delete_view,
        name="espaco-delete",
    ),
    # URLs para Inventário de Espaços
    path(
        "espacos/inventario/",
        views.espaco_inventario_list_view,
        name="espaco-inventario-list",
    ),
    path(
        "espacos/inventario/create/",
        views.espaco_inventario_create_view,
        name="espaco-inventario-create",
    ),
    path(
        "espacos/inventario/<int:pk>/",
        views.espaco_inventario_detail_view,
        name="espaco-inventario-detail",
    ),
    path(
        "espacos/inventario/<int:pk>/update/",
        views.espaco_inventario_update_view,
        name="espaco-inventario-update",
    ),
    path(
        "espacos/inventario/<int:pk>/delete/",
        views.espaco_inventario_delete_view,
        name="espaco-inventario-delete",
    ),
    # URLs para Reservas de Espaços
    path(
        "espacos/reservas/",
        views.espaco_reserva_list_view,
        name="espaco-reserva-list",
    ),
    path(
        "espacos/reservas/hoje/",
        views.espaco_reserva_hoje_view,
        name="espaco-reserva-hoje",
    ),
    path(
        "espacos/reservas/disponibilidade/",
        views.espaco_disponibilidade_view,
        name="espaco-disponibilidade",
    ),
    path(
        "espacos/reservas/create/",
        views.espaco_reserva_create_view,
        name="espaco-reserva-create",
    ),
    path(
        "espacos/reservas/<int:pk>/",
        views.espaco_reserva_detail_view,
        name="espaco-reserva-detail",
    ),
    path(
        "espacos/reservas/<int:pk>/update/",
        views.espaco_reserva_update_view,
        name="espaco-reserva-update",
    ),
    path(
        "espacos/reservas/<int:pk>/delete/",
        views.espaco_reserva_delete_view,
        name="espaco-reserva-delete",
    ),
    # URLs para Eventos
    path("eventos/", views.evento_list_view, name="evento-list"),
    path("eventos/create/", views.evento_create_view, name="evento-create"),
    path("eventos/<int:pk>/", views.evento_detail_view, name="evento-detail"),
    path(
        "eventos/<int:pk>/update/",
        views.evento_update_view,
        name="evento-update",
    ),
    path(
        "eventos/<int:pk>/delete/",
        views.evento_delete_view,
        name="evento-delete",
    ),
]
