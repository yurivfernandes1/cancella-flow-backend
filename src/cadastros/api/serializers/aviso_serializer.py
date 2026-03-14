from django.contrib.auth.models import Group
from rest_framework import serializers

from ...models import Aviso


class AvisoSerializer(serializers.ModelSerializer):
    grupo_nome = serializers.SerializerMethodField()
    grupos_nomes = serializers.SerializerMethodField()
    grupos = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Group.objects.exclude(name__iexact="admin"),
        required=False,
    )
    enviar_para_todos = serializers.BooleanField(
        write_only=True, required=False
    )
    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True
    )

    class Meta:
        model = Aviso
        fields = [
            "id",
            "titulo",
            "descricao",
            "grupo",
            "grupo_nome",
            "grupos",
            "grupos_nomes",
            "enviar_para_todos",
            "prioridade",
            "status",
            "data_inicio",
            "data_fim",
            "created_at",
            "updated_at",
            "created_by",
            "created_by_name",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]

    def validate_grupo(self, value):
        if value and value.name.lower() == "admin":
            raise serializers.ValidationError(
                "O grupo 'admin' não pode ser selecionado."
            )
        return value

    def get_grupo_nome(self, obj):
        nomes = self.get_grupos_nomes(obj)
        return nomes[0] if nomes else None

    def get_grupos_nomes(self, obj):
        grupos = list(obj.grupos.all())
        if grupos:
            return [g.name for g in grupos]
        if obj.grupo:
            return [obj.grupo.name]
        return []

    def _get_target_groups(self, validated_data, instance=None):
        enviar_para_todos = bool(
            validated_data.pop("enviar_para_todos", False)
        )
        provided_grupos = validated_data.pop("grupos", None)
        grupo_legacy = validated_data.get("grupo")

        if enviar_para_todos:
            groups_qs = Group.objects.filter(
                name__in=["Moradores", "Portaria", "Síndicos", "Sindicos"]
            ).exclude(name__iexact="admin")
            return list(groups_qs), True

        if provided_grupos is not None:
            selected = list(provided_grupos)
            if not selected:
                raise serializers.ValidationError(
                    {"grupos": "Selecione pelo menos um grupo destinatário."}
                )
            return selected, True

        if grupo_legacy:
            return [grupo_legacy], True

        if instance is None:
            raise serializers.ValidationError(
                {
                    "grupos": "Selecione ao menos um grupo ou use 'enviar_para_todos'."
                }
            )

        return None, False

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
            validated_data["updated_by"] = request.user
        selected_groups, has_group_update = self._get_target_groups(
            validated_data
        )
        if has_group_update and selected_groups:
            validated_data["grupo"] = selected_groups[0]

        instance = super().create(validated_data)
        if has_group_update:
            instance.grupos.set(selected_groups)
        return instance

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["updated_by"] = request.user
        selected_groups, has_group_update = self._get_target_groups(
            validated_data, instance=instance
        )
        if has_group_update and selected_groups:
            validated_data["grupo"] = selected_groups[0]

        instance = super().update(instance, validated_data)
        if has_group_update:
            instance.grupos.set(selected_groups)
        return instance


class AvisoListSerializer(serializers.ModelSerializer):
    grupo_nome = serializers.SerializerMethodField()
    grupos_nomes = serializers.SerializerMethodField()
    grupos = serializers.SerializerMethodField()

    class Meta:
        model = Aviso
        fields = [
            "id",
            "titulo",
            "descricao",
            "grupo",
            "grupo_nome",
            "grupos",
            "grupos_nomes",
            "prioridade",
            "status",
            "data_inicio",
            "data_fim",
            "created_at",
            "updated_at",
        ]

    def get_grupos(self, obj):
        grupos = list(obj.grupos.values_list("id", flat=True))
        if grupos:
            return grupos
        if obj.grupo_id:
            return [obj.grupo_id]
        return []

    def get_grupos_nomes(self, obj):
        grupos = list(obj.grupos.values_list("name", flat=True))
        if grupos:
            return grupos
        if obj.grupo:
            return [obj.grupo.name]
        return []

    def get_grupo_nome(self, obj):
        nomes = self.get_grupos_nomes(obj)
        return nomes[0] if nomes else None


class AvisoOptionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name"]
