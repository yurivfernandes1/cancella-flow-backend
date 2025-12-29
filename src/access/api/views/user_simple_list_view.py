from access.models import User
from django.db.models import Q
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from ..serializers.user_minimal_serializer import UserMinimalSerializer


class UserSimpleListView(generics.ListAPIView):
    """
    Lista simples de usuários (id e full_name). Acessível por qualquer usuário autenticado.

    Parâmetros suportados:
    - type=moradores: retorna apenas usuários do grupo "Moradores" (padrão)
      - include_sindico=1: quando presente, inclui também usuários do grupo "Síndicos"
    Para usuários não-staff, o resultado é filtrado pelo condomínio do usuário logado.
    """

    serializer_class = UserMinimalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = User.objects.all()

        # Filtrar por tipo de usuário
        user_type = self.request.query_params.get("type", "")
        include_sindico_param = self.request.query_params.get(
            "include_sindico", "0"
        )
        include_sindico = str(include_sindico_param).lower() in {
            "1",
            "true",
            "yes",
        }

        if user_type == "moradores":
            group_filters = [Q(groups__name__iexact="Moradores")]
            if include_sindico:
                group_filters.append(
                    Q(groups__name__iexact="Síndicos")
                    | Q(groups__name__iexact="Sindicos")
                )
            query_q = Q()
            for gf in group_filters:
                query_q |= gf
            queryset = queryset.filter(query_q)

        # Filtrar por condomínio (para não-staff)
        if not self.request.user.is_staff:
            # Usuário comum (ex.: síndico) só vê usuários do mesmo condomínio
            if (
                hasattr(self.request.user, "condominio")
                and self.request.user.condominio
            ):
                queryset = queryset.filter(
                    condominio=self.request.user.condominio
                )

        # Evitar duplicados caso o usuário esteja em mais de um grupo
        return queryset.distinct().order_by("full_name")
