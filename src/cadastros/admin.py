from django.contrib import admin

from .models.aviso import Aviso
from .models.condominio import Condominio
from .models.encomenda import Encomenda
from .models.unidade import Unidade
from .models.visitante import Visitante


@admin.register(Condominio)
class CondominioAdmin(admin.ModelAdmin):
    list_display = ("nome", "cnpj", "telefone", "created_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("nome", "cnpj", "telefone")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Encomenda)
class EncomendaAdmin(admin.ModelAdmin):
    list_display = (
        "unidade",
        "destinatario_nome",
        "descricao",
        "codigo_rastreio",
        "created_by",
        "created_on",
    )
    list_filter = ("created_on", "updated_on", "retirado_em")
    search_fields = (
        "unidade__numero",
        "unidade__bloco",
        "destinatario_nome",
        "descricao",
        "codigo_rastreio",
        "retirado_por",
    )
    readonly_fields = ("created_on", "updated_on")


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "bloco",
        "morador",
        "is_active",
        "created_on",
    )
    list_filter = ("is_active", "created_on", "updated_on")
    search_fields = ("numero", "bloco", "morador__full_name")
    readonly_fields = ("created_on", "updated_on")


@admin.register(Visitante)
class VisitanteAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "morador",
        "documento",
        "data_entrada",
        "data_saida",
        "is_permanente",
    )
    list_filter = ("is_permanente", "data_entrada", "data_saida", "created_on")
    search_fields = ("nome", "documento", "morador__full_name")
    readonly_fields = ("created_on", "updated_on")


@admin.register(Aviso)
class AvisoAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "grupo",
        "prioridade",
        "status",
        "data_inicio",
        "data_fim",
        "created_at",
    )
    list_filter = ("grupo", "prioridade", "status")
    search_fields = ("titulo", "descricao", "grupo__name")
