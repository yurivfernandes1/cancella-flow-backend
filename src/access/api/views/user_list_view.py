from access.models import User
from django.db.models import Q
from rest_framework import filters, generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..permissions import IsStaffOrSindico
from ..serializers import UserListSerializer


class UserListView(generics.ListAPIView):
    serializer_class = UserListSerializer
    permission_classes = [IsAuthenticated, IsStaffOrSindico]
    pagination_class = PageNumberPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ["username", "full_name"]

    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.exclude(id=user.id)

        # Filtrar por tipo de usuário
        user_type = self.request.query_params.get("type", "")
        if user_type:
            if user_type == "sindicos":
                queryset = queryset.filter(groups__name="Síndicos")
            elif user_type == "portaria":
                queryset = queryset.filter(groups__name="Portaria")
            elif user_type == "moradores":
                queryset = queryset.filter(groups__name="Moradores")

        # Restringir por condomínio para Síndico (e não staff)
        if not user.is_staff and getattr(user, "condominio_id", None):
            queryset = queryset.filter(condominio_id=user.condominio_id)

        # Aplicar busca se houver termo de pesquisa
        search = self.request.query_params.get("search", "")
        if search:
            if user.is_staff:
                # Staff pode buscar em todos os campos
                queryset = queryset.filter(
                    Q(username__icontains=search)
                    | Q(full_name__icontains=search)
                ).distinct()
            else:
                # Gestor só busca nos campos básicos
                queryset = queryset.filter(
                    Q(username__icontains=search)
                    | Q(full_name__icontains=search)
                ).distinct()

        return queryset.order_by("username")

    def get_paginated_response(self, data):
        assert self.paginator is not None
        return Response(
            {
                "count": self.paginator.page.paginator.count,
                "num_pages": self.paginator.page.paginator.num_pages,
                "next": self.paginator.get_next_link(),
                "previous": self.paginator.get_previous_link(),
                "results": data,
            }
        )
